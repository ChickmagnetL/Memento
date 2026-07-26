"""Phase 3: retrieval latency — hybrid vs pure_vector vs pure_bm25.

Times await retriever.search(query, top_k=5) with N=5 runs per query,
reports mean/P50/P95 in ms. E2E chat latency is skipped (documented).
Writes benchmarks/results/03_latency.{md,json}.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "backend"))
import bench_env  # noqa: F401  # sets env BEFORE other memento imports

from config.settings import get_settings  # noqa: E402
from core.models.factory import build_embedding_client  # noqa: E402
from core.rag.retrieval import HybridRetriever, VectorRetriever  # noqa: E402
from storage.qdrant_client import QdrantStore  # noqa: E402

EVAL_SET = ROOT / "benchmarks" / "eval_set.jsonl"
OUT_MD = ROOT / "benchmarks" / "results" / "03_latency.md"
OUT_JSON = ROOT / "benchmarks" / "results" / "03_latency.json"

# Fallback scale if live counts unavailable (50-video corpus with noise).
SCALE = {"videos": 50, "chunks": 2040, "vector_dim": 1024}

EVAL_NOTE = (
    "评测说明: eval_set detail 题仅覆盖前 10 个视频；"
    "当前语料为 50 视频（额外 40 为干扰噪声）"
)

TOP_K = 5
N_RUNS = 5


def load_detail_questions(path: Path) -> list[dict[str, Any]]:
    """Same filter as retrieval_ab: type=detail AND non-empty relevant_chunks."""
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if obj.get("type") != "detail":
            continue
        chunks = obj.get("relevant_chunks") or []
        if not chunks:
            continue
        rows.append(obj)
    return rows


def percentile(xs: list[float], p: float) -> float:
    """Nearest-rank style via round((p/100)*(n-1)). Documented in report."""
    if not xs:
        return 0.0
    s = sorted(xs)
    idx = min(len(s) - 1, max(0, int(round((p / 100.0) * (len(s) - 1)))))
    return s[idx]


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def aggregate_latencies(xs: list[float]) -> dict[str, float | int]:
    return {
        "n_samples": len(xs),
        "mean_ms": mean(xs),
        "p50_ms": percentile(xs, 50),
        "p95_ms": percentile(xs, 95),
        "min_ms": min(xs) if xs else 0.0,
        "max_ms": max(xs) if xs else 0.0,
    }


async def time_search(retriever: Any, query: str, top_k: int) -> float:
    """Return search latency in milliseconds."""
    t0 = time.perf_counter()
    await retriever.search(query, top_k=top_k)
    return (time.perf_counter() - t0) * 1000.0


async def run_config(
    name: str,
    retriever: Any,
    questions: list[dict[str, Any]],
    n_runs: int,
    top_k: int,
) -> dict[str, Any]:
    # Warmup: 1 untimed search per config
    warmup_q = questions[0]["question"]
    await retriever.search(warmup_q, top_k=top_k)
    print(f"  warmup done for {name}")

    all_latencies: list[float] = []
    per_question: list[dict[str, Any]] = []

    for i, q in enumerate(questions):
        lats: list[float] = []
        for _ in range(n_runs):
            ms = await time_search(retriever, q["question"], top_k)
            lats.append(ms)
            all_latencies.append(ms)
        per_question.append(
            {
                "id": q["id"],
                "latencies_ms": [round(x, 3) for x in lats],
                "mean_ms": mean(lats),
                "p50_ms": percentile(lats, 50),
            }
        )
        if (i + 1) % 10 == 0 or (i + 1) == len(questions):
            print(
                f"  {name}: {i + 1}/{len(questions)} queries "
                f"(last mean={mean(lats):.1f} ms)"
            )

    agg = aggregate_latencies(all_latencies)
    # Round aggregate floats for JSON cleanliness
    agg_out = {
        "n_samples": agg["n_samples"],
        "mean_ms": round(float(agg["mean_ms"]), 3),
        "p50_ms": round(float(agg["p50_ms"]), 3),
        "p95_ms": round(float(agg["p95_ms"]), 3),
        "min_ms": round(float(agg["min_ms"]), 3),
        "max_ms": round(float(agg["max_ms"]), 3),
    }
    for pq in per_question:
        pq["mean_ms"] = round(float(pq["mean_ms"]), 3)
        pq["p50_ms"] = round(float(pq["p50_ms"]), 3)

    return {
        "name": name,
        "aggregate": agg_out,
        "per_question": per_question,
    }


def fmt_ms(x: float) -> str:
    return f"{x:.1f}"


def write_md(payload: dict[str, Any]) -> str:
    by_name = {c["name"]: c for c in payload["configs"]}
    hybrid = by_name["hybrid"]["aggregate"]
    pure_v = by_name["pure_vector"]["aggregate"]
    pure_b = by_name["pure_bm25"]["aggregate"]

    lines: list[str] = []
    lines.append("# 03 检索延迟：hybrid vs pure_vector vs pure_bm25")
    lines.append("")
    lines.append(f"生成时间: {payload['timestamp']}")
    lines.append(
        f"Embedding: `{payload['embedding_model']}` @ `{payload['embedding_endpoint']}`"
    )
    lines.append(
        f"数据规模: {payload['scale']['videos']} videos / "
        f"{payload['scale']['chunks']} chunks / dim {payload['scale']['vector_dim']}"
    )
    if payload.get("eval_note"):
        lines.append(payload["eval_note"])
    lines.append(
        f"评测题数: detail + non-empty relevant_chunks = **{payload['n_questions']}**"
    )
    lines.append(
        f"N runs / query: **{payload['n_runs']}**；top_k=**{payload['top_k']}**；"
        f"warmup: **{payload['warmup']}**（每个 config 正式计时前 1 次不计时 search）"
    )
    lines.append(
        f"分位数: nearest-rank，`idx = round((p/100)*(n-1))`；"
        f"聚合范围 = 全部 timed runs（queries × N）"
    )
    lines.append(f"Qdrant points: **{payload.get('qdrant_point_count')}**")
    lines.append("")
    lines.append("## 配置")
    lines.append("")
    lines.append("| name | impl | weights |")
    lines.append("|------|------|---------|")
    for c in payload["config_defs"]:
        w = c.get("weights")
        w_s = json.dumps(w, ensure_ascii=False) if w else "—"
        lines.append(f"| `{c['name']}` | {c['impl']} | `{w_s}` |")
    lines.append("")
    lines.append("## Headline：hybrid 延迟")
    lines.append("")
    lines.append(
        f"- hybrid mean / P50 / P95 = **{fmt_ms(hybrid['mean_ms'])}** / "
        f"**{fmt_ms(hybrid['p50_ms'])}** / **{fmt_ms(hybrid['p95_ms'])}** ms"
    )
    lines.append(
        f"- pure_vector mean / P50 / P95 = **{fmt_ms(pure_v['mean_ms'])}** / "
        f"**{fmt_ms(pure_v['p50_ms'])}** / **{fmt_ms(pure_v['p95_ms'])}** ms"
    )
    lines.append(
        f"- pure_bm25 mean / P50 / P95 = **{fmt_ms(pure_b['mean_ms'])}** / "
        f"**{fmt_ms(pure_b['p50_ms'])}** / **{fmt_ms(pure_b['p95_ms'])}** ms"
    )
    lines.append("")
    lines.append("## 汇总表")
    lines.append("")
    lines.append("| config | n_samples | mean_ms | p50_ms | p95_ms | min_ms | max_ms |")
    lines.append("|--------|-----------|---------|--------|--------|--------|--------|")
    for c in payload["configs"]:
        a = c["aggregate"]
        lines.append(
            f"| `{c['name']}` | {a['n_samples']} | {fmt_ms(a['mean_ms'])} | "
            f"{fmt_ms(a['p50_ms'])} | {fmt_ms(a['p95_ms'])} | "
            f"{fmt_ms(a['min_ms'])} | {fmt_ms(a['max_ms'])} |"
        )
    lines.append("")
    lines.append("## 说明")
    lines.append("")
    lines.append(
        "- **已知瓶颈**：HybridRetriever 每次 query 会经 `scroll_all_points()` 重建 BM25 语料，"
        "hybrid / pure_bm25 延迟显著高于 pure_vector 属预期。"
    )
    lines.append(
        "- **pure_bm25** 仍走 HybridRetriever（vector weight=0），实现上仍会 embed 查询。"
    )
    lines.append(
        f"- **E2E chat 延迟**：跳过。"
        f" 原因：{payload['e2e_chat'].get('reason', 'best-effort skip')}"
    )
    lines.append(
        f"- smoke embed dim: {payload.get('smoke_embed_dim')}；"
        f"Qdrant point count 校验: {payload.get('qdrant_point_count')}"
    )
    lines.append("")
    return "\n".join(lines)


def _sqlite_document_count(data_dir: Path) -> int | None:
    """Return documents count from metadata.db, or None if unavailable."""
    db_path = data_dir / "metadata.db"
    if not db_path.exists():
        return None
    try:
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute("SELECT COUNT(*) FROM documents").fetchone()
            return int(row[0]) if row else None
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: sqlite document count failed: {exc}")
        return None


async def main_async() -> int:
    settings = get_settings()
    data_dir = Path(settings.storage.data_dir).expanduser()
    questions = load_detail_questions(EVAL_SET)
    if not questions:
        print("ERROR: no detail questions with relevant_chunks in", EVAL_SET)
        return 1

    embedding = build_embedding_client(settings)
    smoke = embedding.embed(["latency smoke"])
    smoke_dim = len(smoke[0]) if smoke and smoke[0] else 0
    print(f"smoke embed ok, dim={smoke_dim}")
    if smoke_dim != settings.rag.vector_size:
        print(
            f"WARNING: smoke dim {smoke_dim} != settings.rag.vector_size "
            f"{settings.rag.vector_size}"
        )

    qdrant = QdrantStore(data_dir / "qdrant")
    try:
        qdrant.connect(vector_size=settings.rag.vector_size)
        point_count = len(qdrant.scroll_all_points())
        print(f"Qdrant open ok, points={point_count}")

        # Live scale from SQLite + Qdrant (fallback to SCALE defaults).
        doc_count = _sqlite_document_count(data_dir)
        scale = {
            "videos": doc_count if doc_count is not None else SCALE["videos"],
            "chunks": point_count if point_count else SCALE["chunks"],
            "vector_dim": smoke_dim or settings.rag.vector_size or SCALE["vector_dim"],
        }
        print(
            f"scale live: videos={scale['videos']} chunks={scale['chunks']} "
            f"dim={scale['vector_dim']}"
        )

        config_defs = [
            {
                "name": "hybrid",
                "impl": "HybridRetriever",
                "weights": {"bm25": 0.3, "vector": 0.7},
            },
            {
                "name": "pure_vector",
                "impl": "VectorRetriever",
                "weights": None,
            },
            {
                "name": "pure_bm25",
                "impl": "HybridRetriever",
                "weights": {"bm25": 1.0, "vector": 0.0},
            },
        ]

        retrievers: dict[str, Any] = {
            "hybrid": HybridRetriever(
                embedding_client=embedding,
                qdrant=qdrant,
                weights={"bm25": 0.3, "vector": 0.7},
            ),
            "pure_vector": VectorRetriever(
                embedding_client=embedding,
                qdrant=qdrant,
            ),
            "pure_bm25": HybridRetriever(
                embedding_client=embedding,
                qdrant=qdrant,
                weights={"bm25": 1.0, "vector": 0.0},
            ),
        }

        results_configs: list[dict[str, Any]] = []
        for name in ("hybrid", "pure_vector", "pure_bm25"):
            print(f"running config={name} n_q={len(questions)} n_runs={N_RUNS} ...")
            cfg_result = await run_config(
                name, retrievers[name], questions, N_RUNS, TOP_K
            )
            results_configs.append(cfg_result)
            a = cfg_result["aggregate"]
            print(
                f"  {name}: mean={a['mean_ms']:.1f} p50={a['p50_ms']:.1f} "
                f"p95={a['p95_ms']:.1f} ms (n={a['n_samples']})"
            )

        by_name = {c["name"]: c for c in results_configs}
        h = by_name["hybrid"]["aggregate"]

        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "embedding_model": settings.models.embedding.model,
            "embedding_endpoint": settings.models.embedding.endpoint,
            "smoke_embed_dim": smoke_dim,
            "qdrant_point_count": point_count,
            "scale": scale,
            "eval_note": EVAL_NOTE,
            "n_questions": len(questions),
            "n_runs": N_RUNS,
            "top_k": TOP_K,
            "warmup": True,
            "percentile_method": "nearest-rank: idx=round((p/100)*(n-1))",
            "e2e_chat": {
                "skipped": True,
                "reason": "best-effort skip; flaky chat SSE not required for Phase 3; retrieval latency only",
            },
            "config_defs": config_defs,
            "configs": results_configs,
        }

        OUT_MD.parent.mkdir(parents=True, exist_ok=True)
        md = write_md(payload)
        OUT_MD.write_text(md, encoding="utf-8")
        OUT_JSON.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {OUT_MD}")
        print(f"wrote {OUT_JSON}")
        print(
            f"HEADLINE hybrid mean/P50/P95: "
            f"{h['mean_ms']:.1f} / {h['p50_ms']:.1f} / {h['p95_ms']:.1f} ms"
        )
        return 0
    finally:
        qdrant.close()
        print("Qdrant closed")


def main() -> None:
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
