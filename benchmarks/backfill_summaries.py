"""Backfill missing L2 summary + L3 brief for documents in bench_data.

Idempotent: skips docs that already have non-empty summary and brief.
Large docs use map-reduce summarization. Supports:
  python -m benchmarks.backfill_summaries
"""

from __future__ import annotations

import asyncio
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "backend"))
import bench_env  # noqa: F401

from config.settings import get_settings  # noqa: E402
from core.models.chat_completion import ChatCompletionError  # noqa: E402
from core.models.factory import (  # noqa: E402
    build_chat_completion_client,
    build_embedding_client,
)
from core.rag.document_summary_store import (  # noqa: E402
    DocumentSummaryStore,
    generate_summary,
    read_markdown,
)
from core.rag.embedding_supervisor import ensure_embedding_running  # noqa: E402
from storage.qdrant_client import QdrantStore  # noqa: E402
from storage.sqlite_client import SQLiteClient  # noqa: E402

# Map-reduce: prefer ~12k–20k char chunks at paragraph boundaries.
CHUNK_TARGET = 16_000
CHUNK_MAX = 20_000
LARGE_DIRECT_THRESHOLD = 50_000  # always map-reduce above this

_CHUNK_SUMMARY_PROMPT = (
    "Summarize the following document section in 3–6 sentences. "
    "Capture key topics, claims, and entities. Output plain text only."
)


def _has_both(summary: str | None, brief: str | None) -> bool:
    return bool((summary or "").strip()) and bool((brief or "").strip())


def _resolve_file_path(doc: dict, data_dir: Path) -> Path:
    raw = doc.get("file_path") or ""
    path = Path(raw) if raw else Path()
    if path.is_file():
        return path
    # Fallback: try under data_dir if stored path is stale/relative
    if raw:
        candidate = data_dir / raw
        if candidate.is_file():
            return candidate
        # basename search under knowledge/
        name = Path(raw).name
        for hit in (data_dir / "knowledge").rglob(name):
            if hit.is_file():
                return hit
    raise FileNotFoundError(f"markdown not found for doc {doc.get('id')}: {raw!r}")


def _split_paragraphs(text: str, target: int = CHUNK_TARGET, max_size: int = CHUNK_MAX) -> list[str]:
    """Split text into chunks near *target* chars, preferring paragraph breaks."""
    if len(text) <= max_size:
        return [text]

    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    buf: list[str] = []
    buf_len = 0

    def flush() -> None:
        nonlocal buf, buf_len
        if buf:
            chunks.append("\n\n".join(buf))
            buf = []
            buf_len = 0

    for para in paragraphs:
        para_len = len(para) + (2 if buf else 0)
        if buf and buf_len + para_len > target:
            flush()
            para_len = len(para)
        # Hard-split oversized single paragraphs
        if len(para) > max_size:
            flush()
            for start in range(0, len(para), target):
                chunks.append(para[start : start + target])
            continue
        buf.append(para)
        buf_len += para_len
        if buf_len >= target:
            flush()
    flush()
    return chunks or [text]


def _summarize_chunk(chat, text: str) -> str:
    return chat.complete(
        [
            {"role": "system", "content": _CHUNK_SUMMARY_PROMPT},
            {"role": "user", "content": text},
        ]
    ).strip()


def map_reduce_summary(markdown_text: str, chat) -> tuple[str, str]:
    """Map-reduce: chunk summaries → final L2/L3 via generate_summary."""
    chunks = _split_paragraphs(markdown_text)
    print(f"    map-reduce: {len(chunks)} chunk(s), sizes={[len(c) for c in chunks]}")
    intermediates: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        print(f"    summarizing chunk {i}/{len(chunks)} ({len(chunk)} chars)...")
        try:
            s = _summarize_chunk(chat, chunk)
        except Exception as exc:  # noqa: BLE001
            print(f"    chunk {i} failed: {exc}; using truncated raw excerpt")
            s = chunk[:2000]
        intermediates.append(f"[Part {i}/{len(chunks)}]\n{s}")
    combined = "\n\n".join(intermediates)
    print(f"    generating final L2/L3 from {len(combined)} chars of intermediates...")
    return generate_summary(combined, chat_client=chat)


def generate_l2_l3(markdown_text: str, chat) -> tuple[str, str]:
    """Direct generate_summary, with map-reduce for large docs or on failure."""
    n = len(markdown_text)
    if n >= LARGE_DIRECT_THRESHOLD:
        print(f"    large doc ({n} chars) → map-reduce")
        return map_reduce_summary(markdown_text, chat)

    try:
        print(f"    trying direct generate_summary ({n} chars)...")
        return generate_summary(markdown_text, chat_client=chat)
    except (ChatCompletionError, Exception) as exc:
        print(f"    direct failed ({type(exc).__name__}: {exc}); falling back to map-reduce")
        return map_reduce_summary(markdown_text, chat)


async def process_doc(
    *,
    store: DocumentSummaryStore,
    sqlite: SQLiteClient,
    doc: dict,
    data_dir: Path,
    chat,
    embedding,
) -> str:
    """Return status string: SKIPPED | OK | FAIL:..."""
    doc_id = doc["id"]
    summary = doc.get("summary")
    brief = doc.get("brief")
    if _has_both(summary, brief):
        return (
            f"SKIPPED (already has L2={len(summary or '')} L3={len(brief or '')})"
        )

    path = _resolve_file_path(doc, data_dir)
    markdown = await asyncio.to_thread(read_markdown, str(path))
    print(f"  file={path} chars={len(markdown)}")

    l2, l3 = await asyncio.to_thread(generate_l2_l3, markdown, chat)
    if not (l2 or "").strip() or not (l3 or "").strip():
        raise RuntimeError(f"empty L2/L3 produced: l2_len={len(l2 or '')} l3_len={len(l3 or '')}")

    title = await store._resolve_title(doc)
    l3_vector = (await asyncio.to_thread(embedding.embed, [l3]))[0]

    try:
        await store.save_summary(
            document_id=doc_id,
            title=title,
            l2=l2,
            l3=l3,
            l3_vector=l3_vector,
        )
        return f"OK full (L2={len(l2)} L3={len(l3)} title={title[:40]!r})"
    except Exception as qexc:  # noqa: BLE001
        # Prefer full save; if Qdrant locked, still persist SQLite L2/L3
        print(f"  full save failed ({qexc}); trying SQLite-only...")
        await sqlite.set_document_summary(doc_id, l2=l2, l3=l3)
        return f"OK sqlite-only (L2={len(l2)} L3={len(l3)}; qdrant_err={qexc})"


async def main() -> int:
    settings = get_settings()
    data_dir = Path(settings.storage.data_dir).expanduser()
    db_path = data_dir / "metadata.db"
    print(f"data_dir={data_dir}")
    print(f"metadata.db={db_path}")

    sqlite = SQLiteClient(db_path)
    await sqlite.connect()

    qdrant = QdrantStore(data_dir / "qdrant")
    qdrant.connect(vector_size=settings.rag.vector_size)
    qdrant.ensure_summary_collection(settings.rag.vector_size)

    embedding = build_embedding_client(settings)
    ensure_embedding_running(settings.models.embedding.endpoint)
    chat = build_chat_completion_client()
    store = DocumentSummaryStore(
        sqlite=sqlite,
        qdrant=qdrant,
        embedding=embedding,
        chat_client=chat,
    )

    results: list[tuple[str, str]] = []
    try:
        docs = await sqlite.list_documents()
        print(f"documents total={len(docs)}")
        for doc in docs:
            doc_id = doc["id"]
            print(f"\n== doc {doc_id} ==")
            try:
                status = await process_doc(
                    store=store,
                    sqlite=sqlite,
                    doc=doc,
                    data_dir=data_dir,
                    chat=chat,
                    embedding=embedding,
                )
            except Exception as exc:  # noqa: BLE001
                traceback.print_exc()
                status = f"FAIL: {exc}"
            print(f"  → {status}")
            results.append((doc_id, status))
    finally:
        await sqlite.close()
        qdrant.close()

    print("\n======== FINAL STATUS ========")
    ok = fail = skip = 0
    for doc_id, status in results:
        print(f"  {doc_id}: {status}")
        if status.startswith("OK"):
            ok += 1
        elif status.startswith("SKIP"):
            skip += 1
        else:
            fail += 1
    print(f"done: ok={ok} skipped={skip} failed={fail} total={len(results)}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
