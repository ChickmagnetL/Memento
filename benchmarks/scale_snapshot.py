"""Snapshot KB scale stats into benchmarks/results/05_scale.md (+ .json).

Prefers local QdrantStore; falls back to HTTP API + metadata.db when locked.
"""

from __future__ import annotations

import json
import sqlite3
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "backend"))
import bench_env  # noqa: F401  # sets env before other memento imports

from config.settings import get_settings  # noqa: E402

BASE_URL = "http://127.0.0.1:8010"
OUT_MD = ROOT / "benchmarks" / "results" / "05_scale.md"
OUT_JSON = ROOT / "benchmarks" / "results" / "05_scale.json"


def _mean(xs: list[float | int]) -> float | None:
    if not xs:
        return None
    return float(statistics.mean(xs))


def _sqlite_stats(db_path: Path) -> dict:
    if not db_path.exists():
        return {"error": f"metadata.db missing: {db_path}"}
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        video_count = conn.execute("SELECT COUNT(*) AS c FROM videos").fetchone()["c"]
        document_count = conn.execute("SELECT COUNT(*) AS c FROM documents").fetchone()["c"]
        docs = conn.execute(
            "SELECT id, video_id, status, chunk_count, summary, brief, file_path FROM documents"
        ).fetchall()
        rows = [dict(r) for r in docs]
    finally:
        conn.close()

    chunk_counts = [int(d.get("chunk_count") or 0) for d in rows]
    l2 = sum(1 for d in rows if (d.get("summary") or "").strip())
    l3 = sum(1 for d in rows if (d.get("brief") or "").strip())
    return {
        "video_count": video_count,
        "document_count": document_count,
        "documents": rows,
        "chunk_count_min": min(chunk_counts) if chunk_counts else None,
        "chunk_count_mean": _mean(chunk_counts),
        "chunk_count_max": max(chunk_counts) if chunk_counts else None,
        "l2_coverage": l2,
        "l3_coverage": l3,
        "l2_coverage_pct": (100.0 * l2 / document_count) if document_count else 0.0,
        "l3_coverage_pct": (100.0 * l3 / document_count) if document_count else 0.0,
    }


def _try_qdrant(settings) -> dict | None:
    """Return qdrant stats or None if lock/open fails."""
    try:
        from storage.qdrant_client import QdrantStore

        data_dir = Path(settings.storage.data_dir).expanduser()
        qdrant = QdrantStore(data_dir / "qdrant")
        qdrant.connect(vector_size=settings.rag.vector_size)
        payloads = qdrant.scroll_all_points()
        texts = []
        for p in payloads:
            if isinstance(p, dict):
                t = p.get("text")
                if isinstance(t, str):
                    texts.append(t)
        lengths = [len(t) for t in texts]
        vec_size = qdrant.collection_vector_size()
        return {
            "source": "qdrant_local",
            "point_count": len(payloads),
            "vector_size": vec_size or settings.rag.vector_size,
            "distance": "COSINE",
            "avg_chunk_chars": _mean(lengths),
            "min_chunk_chars": min(lengths) if lengths else None,
            "max_chunk_chars": max(lengths) if lengths else None,
            "chunk_char_samples": len(lengths),
        }
    except Exception as exc:  # noqa: BLE001
        print(f"Qdrant local open failed (will fallback HTTP): {exc}")
        return None


def _http_chunk_stats(docs: list[dict]) -> dict:
    lengths: list[int] = []
    point_count = 0
    with httpx.Client(timeout=60.0) as client:
        for d in docs:
            did = d.get("id")
            if not did:
                continue
            try:
                r = client.get(f"{BASE_URL}/api/documents/{did}/chunks")
                if r.status_code >= 400:
                    continue
                chunks = r.json()
                if not isinstance(chunks, list):
                    continue
                point_count += len(chunks)
                for c in chunks:
                    t = c.get("text") if isinstance(c, dict) else None
                    if isinstance(t, str):
                        lengths.append(len(t))
            except Exception as exc:  # noqa: BLE001
                print(f"  chunks fetch failed for {did}: {exc}")
    settings = get_settings()
    return {
        "source": "http_chunks_api",
        "point_count": point_count,
        "vector_size": settings.rag.vector_size,
        "distance": "COSINE",
        "avg_chunk_chars": _mean(lengths),
        "min_chunk_chars": min(lengths) if lengths else None,
        "max_chunk_chars": max(lengths) if lengths else None,
        "chunk_char_samples": len(lengths),
    }


def _http_counts_fallback() -> dict:
    """If sqlite missing, use HTTP list endpoints."""
    with httpx.Client(timeout=30.0) as client:
        videos = client.get(f"{BASE_URL}/api/videos").json()
        docs = client.get(f"{BASE_URL}/api/documents").json()
    if not isinstance(videos, list):
        videos = []
    if not isinstance(docs, list):
        docs = []
    chunk_counts = [int(d.get("chunk_count") or 0) for d in docs]
    l2 = sum(1 for d in docs if (d.get("summary") or "").strip())
    l3 = sum(1 for d in docs if (d.get("brief") or "").strip())
    n = len(docs)
    return {
        "video_count": len(videos),
        "document_count": n,
        "documents": docs,
        "chunk_count_min": min(chunk_counts) if chunk_counts else None,
        "chunk_count_mean": _mean(chunk_counts),
        "chunk_count_max": max(chunk_counts) if chunk_counts else None,
        "l2_coverage": l2,
        "l3_coverage": l3,
        "l2_coverage_pct": (100.0 * l2 / n) if n else 0.0,
        "l3_coverage_pct": (100.0 * l3 / n) if n else 0.0,
    }


def write_outputs(payload: dict) -> None:
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    s = payload
    q = s.get("qdrant") or {}
    lines = [
        "# 05 知识库规模快照",
        "",
        f"生成时间: {s.get('timestamp')}",
        f"data_dir: `{s.get('data_dir')}`",
        f"统计来源: sqlite={s.get('sqlite_source')}, chunks={q.get('source')}",
        "",
        "## 计数",
        "",
        f"- 视频数: **{s.get('video_count')}**",
        f"- 文档数: **{s.get('document_count')}**",
        f"- L2 summary 覆盖: **{s.get('l2_coverage')}** / {s.get('document_count')} "
        f"({s.get('l2_coverage_pct'):.1f}%)",
        f"- L3 brief 覆盖: **{s.get('l3_coverage')}** / {s.get('document_count')} "
        f"({s.get('l3_coverage_pct'):.1f}%)",
        "",
        "## 分块",
        "",
        f"- 每文档 chunk_count min/mean/max: "
        f"**{s.get('chunk_count_min')}** / **{s.get('chunk_count_mean')}** / **{s.get('chunk_count_max')}**",
        f"- 向量点数(估算): **{q.get('point_count')}**",
        f"- 向量维度: **{q.get('vector_size')}** (distance={q.get('distance')})",
        f"- 平均 chunk 字符数: **{q.get('avg_chunk_chars')}** "
        f"(min={q.get('min_chunk_chars')}, max={q.get('max_chunk_chars')}, "
        f"samples={q.get('chunk_char_samples')})",
        "",
        "## 文档明细",
        "",
        "| document_id | video_id | status | chunk_count | has_summary | has_brief |",
        "|-------------|----------|--------|-------------|-------------|-----------|",
    ]
    for d in s.get("documents") or []:
        lines.append(
            f"| `{d.get('id')}` | `{d.get('video_id')}` | {d.get('status')} | "
            f"{d.get('chunk_count')} | "
            f"{'Y' if (d.get('summary') or '').strip() else 'N'} | "
            f"{'Y' if (d.get('brief') or '').strip() else 'N'} |"
        )
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_MD}")
    print(f"Wrote {OUT_JSON}")


def main() -> int:
    settings = get_settings()
    data_dir = Path(settings.storage.data_dir).expanduser()
    db_path = data_dir / "metadata.db"
    print(f"scale_snapshot data_dir={data_dir}")

    if db_path.exists():
        sql = _sqlite_stats(db_path)
        sqlite_source = "metadata.db"
    else:
        print("metadata.db missing; using HTTP list endpoints")
        sql = _http_counts_fallback()
        sqlite_source = "http_api"

    if sql.get("error"):
        print(sql["error"])
        return 1

    qstats = _try_qdrant(settings)
    if qstats is None:
        qstats = _http_chunk_stats(sql.get("documents") or [])

    # Strip heavy fields for json documents list (keep summary/brief flags only)
    docs_out = []
    for d in sql.get("documents") or []:
        docs_out.append(
            {
                "id": d.get("id"),
                "video_id": d.get("video_id"),
                "status": d.get("status"),
                "chunk_count": d.get("chunk_count"),
                "summary": d.get("summary"),
                "brief": d.get("brief"),
                "file_path": d.get("file_path"),
            }
        )

    payload = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "data_dir": str(data_dir),
        "sqlite_source": sqlite_source,
        "video_count": sql.get("video_count"),
        "document_count": sql.get("document_count"),
        "l2_coverage": sql.get("l2_coverage"),
        "l3_coverage": sql.get("l3_coverage"),
        "l2_coverage_pct": sql.get("l2_coverage_pct"),
        "l3_coverage_pct": sql.get("l3_coverage_pct"),
        "chunk_count_min": sql.get("chunk_count_min"),
        "chunk_count_mean": sql.get("chunk_count_mean"),
        "chunk_count_max": sql.get("chunk_count_max"),
        "qdrant": qstats,
        "documents": docs_out,
    }
    write_outputs(payload)
    print(
        f"videos={payload['video_count']} docs={payload['document_count']} "
        f"points={qstats.get('point_count')} avg_chunk_chars={qstats.get('avg_chunk_chars')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
