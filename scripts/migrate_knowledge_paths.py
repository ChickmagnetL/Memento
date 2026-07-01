#!/usr/bin/env python3
"""Manual one-off migration for legacy knowledge document paths."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from core.documents.legacy_path_migration import migrate_legacy_knowledge_layout


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or apply the legacy knowledge layout migration. "
            "Dry-run is the default."
        )
    )
    parser.add_argument(
        "--data-dir",
        default=str(ROOT / "data"),
        help="Data directory that contains knowledge/ (default: %(default)s)",
    )
    parser.add_argument(
        "--db-path",
        default=str(ROOT / "data" / "metadata.db"),
        help="SQLite database path (default: %(default)s)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply file moves and SQLite updates. Omit for dry-run.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = migrate_legacy_knowledge_layout(
        data_dir=args.data_dir,
        db_path=args.db_path,
        apply=args.apply,
    )

    mode = "APPLY" if result.applied else "DRY RUN"
    print(f"[{mode}] planned file moves: {len(result.plan.file_moves)}")
    for move in result.plan.file_moves:
        print(f"FILE  {move.source} -> {move.destination}")

    print(f"[{mode}] planned document updates: {len(result.plan.document_updates)}")
    for update in result.plan.document_updates:
        print(f"DB    {update.document_id}: {update.old_path} -> {update.new_path}")

    if result.applied:
        print(
            f"Applied {result.moved_file_count} file moves and "
            f"{result.updated_row_count} document updates."
        )
    else:
        print("No changes applied. Re-run with --apply to execute the migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
