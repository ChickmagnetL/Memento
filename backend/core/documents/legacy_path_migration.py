"""One-off migration utility for the legacy knowledge file layout."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from core.documents.paths import normalize_clean_stem


@dataclass(frozen=True)
class PlannedFileMove:
    source: Path
    destination: Path


@dataclass(frozen=True)
class PlannedDocumentUpdate:
    document_id: str
    old_path: str
    new_path: str


@dataclass(frozen=True)
class PlannedConflict:
    reason: str
    destination: Path
    sources: tuple[Path, ...]


@dataclass(frozen=True)
class MigrationPlan:
    file_moves: list[PlannedFileMove]
    document_updates: list[PlannedDocumentUpdate]
    conflicts: list[PlannedConflict]


@dataclass(frozen=True)
class MigrationResult:
    plan: MigrationPlan
    applied: bool
    moved_file_count: int
    updated_row_count: int


def legacy_destination_path(path: str | Path) -> Path | None:
    """Return the canonical destination for a legacy knowledge markdown path."""
    candidate = Path(path)
    if candidate.suffix != ".md":
        return None
    if candidate.parent.name in {"raw", "cleaned"}:
        return None

    stem = candidate.stem
    if not stem:
        return None

    cleaned_stem = normalize_clean_stem(stem)
    if cleaned_stem != stem:
        return candidate.parent / "cleaned" / f"{cleaned_stem}.md"
    return candidate.parent / "raw" / candidate.name


def migrate_legacy_knowledge_layout(
    *, data_dir: str | Path, db_path: str | Path, apply: bool = False
) -> MigrationResult:
    """Plan or apply the legacy knowledge path migration."""
    data_dir = Path(data_dir).expanduser().resolve()
    db_path = Path(db_path).expanduser().resolve()
    plan = _build_plan(data_dir=data_dir, db_path=db_path)

    if not apply:
        return MigrationResult(
            plan=plan,
            applied=False,
            moved_file_count=0,
            updated_row_count=0,
        )

    _raise_for_conflicts(plan.conflicts)
    moved_file_count = _apply_file_moves(plan.file_moves)
    updated_row_count = _apply_document_updates(db_path, plan.document_updates)
    return MigrationResult(
        plan=plan,
        applied=True,
        moved_file_count=moved_file_count,
        updated_row_count=updated_row_count,
    )


def _build_plan(*, data_dir: Path, db_path: Path) -> MigrationPlan:
    knowledge_dir = data_dir / "knowledge"
    file_moves = _plan_file_moves(knowledge_dir)
    conflicts = _plan_conflicts(file_moves)
    document_updates = _plan_document_updates(db_path, file_moves)
    return MigrationPlan(
        file_moves=file_moves,
        document_updates=document_updates,
        conflicts=conflicts,
    )


def _plan_file_moves(knowledge_dir: Path) -> list[PlannedFileMove]:
    if not knowledge_dir.exists():
        return []

    moves: list[PlannedFileMove] = []
    for platform_dir in sorted(path for path in knowledge_dir.iterdir() if path.is_dir()):
        for path in sorted(platform_dir.glob("*.md")):
            destination = legacy_destination_path(path)
            if destination is None:
                continue
            moves.append(PlannedFileMove(source=path, destination=destination))
    return moves


def _plan_conflicts(file_moves: list[PlannedFileMove]) -> list[PlannedConflict]:
    conflicts: list[PlannedConflict] = []
    moves_by_destination: dict[Path, list[Path]] = {}
    for move in file_moves:
        moves_by_destination.setdefault(move.destination, []).append(move.source)

    for destination, sources in sorted(moves_by_destination.items()):
        if len(sources) > 1:
            conflicts.append(
                PlannedConflict(
                    reason="duplicate_destination",
                    destination=destination,
                    sources=tuple(sorted(sources)),
                )
            )
            continue
        if destination.exists():
            conflicts.append(
                PlannedConflict(
                    reason="destination_exists",
                    destination=destination,
                    sources=(sources[0],),
                )
            )

    return conflicts


def _plan_document_updates(
    db_path: Path, file_moves: list[PlannedFileMove]
) -> list[PlannedDocumentUpdate]:
    if not db_path.exists() or not file_moves:
        return []

    replacements = {str(move.source): str(move.destination) for move in file_moves}
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id, file_path FROM documents WHERE file_path IN ({})".format(
                ",".join("?" for _ in replacements)
            ),
            tuple(replacements),
        ).fetchall()
    finally:
        conn.close()

    return [
        PlannedDocumentUpdate(
            document_id=document_id,
            old_path=file_path,
            new_path=replacements[file_path],
        )
        for document_id, file_path in rows
    ]


def _apply_file_moves(file_moves: list[PlannedFileMove]) -> int:
    moved = 0
    for move in file_moves:
        move.destination.parent.mkdir(parents=True, exist_ok=True)
        move.source.rename(move.destination)
        moved += 1
    return moved


def _raise_for_conflicts(conflicts: list[PlannedConflict]) -> None:
    if not conflicts:
        return

    details = "; ".join(
        f"{conflict.reason}: {conflict.destination} <- "
        f"{', '.join(str(source) for source in conflict.sources)}"
        for conflict in conflicts
    )
    raise ValueError(f"Migration conflicts detected: {details}")


def _apply_document_updates(
    db_path: Path, document_updates: list[PlannedDocumentUpdate]
) -> int:
    if not document_updates:
        return 0

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.executemany(
            "UPDATE documents SET file_path = ? WHERE id = ? AND file_path = ?",
            [
                (update.new_path, update.document_id, update.old_path)
                for update in document_updates
            ],
        )
        conn.commit()
        return cursor.rowcount if cursor.rowcount != -1 else len(document_updates)
    finally:
        conn.close()
