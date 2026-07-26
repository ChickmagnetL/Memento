"""Phase 1: retrieval A/B — hybrid vs pure vector vs pure BM25.

Loads detail questions with non-empty relevant_chunks from eval_set.jsonl,
runs each retriever config (top_k=10), computes Recall/Precision@5/10 and MRR,
writes benchmarks/results/01_retrieval_ab.{md,json}.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "backend"))
import bench_env  # noqa: F401  # sets env before other memento imports

from config.settings import get_settings  # noqa: E402
from core.models.factory import build_embedding_client  # noqa: E402
from core.rag.retrieval import HybridRetriever, VectorRetriever  # noqa: E402
from storage.qdrant_client import QdrantStore  # noqa: E402

EVAL_SET = ROOT / "benchmarks" / "eval_set.jsonl"
OUT_MD = ROOT / "benchmarks" / "results" / "01_retrieval_ab.md"
OUT_JSON = ROOT / "benchmarks" / "results" / "01_retrieval_ab.json"

# Fallback scale if live counts unavailable (50-video corpus with noise).
SCALE = {
    "videos": 50,
    "chunks": 2040,
    "vector_dim": 1024,
}

EVAL_NOTE = (
    "评测说明: eval_set detail 题仅覆盖前 10 个视频；"
    "当前语料为 50 视频（额外 40 为干扰噪声）"
)

TOP_K = 10
K_VALUES = (5, 10)

# English tech/jargon tokens common in this eval set + general acronyms.
_EN_JARGON = re.compile(
    r"\b("
    r"PostgreSQL|Postgres|MySQL|MongoDB|Redis|Kafka|Docker|Kubernetes|K8s|"
    r"MCP|API|GDP|PPP|GNP|CPI|HTTP|HTTPS|JSON|SQL|NoSQL|REST|GraphQL|"
    r"LLM|GPT|ASR|RRF|BM25|RAG|SSE|CLI|SDK|GPU|CPU|OOM|TTL|"
    r"harness|embedding|chunk|vector|token|"
    r"Bilibili|Douyin|YouTube"
    r")\b",
    re.IGNORECASE,
)
# CJK product / named-entity-ish: Latin mixed product names, brand-like 2+ CJK + alnum.
_CJK_ENTITY = re.compile(
    r"(凯圣王|苏姿丰|青蒿素|[A-Za-z][A-Za-z0-9_+./-]{1,}|[一-龥]{2,}(?:[A-Za-z0-9]+|[一-龥]{0,4}(?:协议|框架|模型|引擎|数据库)))"
)


def load_detail_questions(path: Path) -> list[dict[str, Any]]:
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


def gt_keys(relevant_chunks: list[dict]) -> set[tuple[str, int]]:
    out: set[tuple[str, int]] = set()
    for c in relevant_chunks:
        out.add((str(c["document_id"]), int(c["chunk_index"])))
    return out


def result_keys(results: list) -> list[tuple[str, int]]:
    return [(r.document_id, int(r.chunk_index)) for r in results]


def metrics_for_ranking(
    ranking: list[tuple[str, int]], relevant: set[tuple[str, int]]
) -> dict[str, float]:
    """Compute Recall/Precision at 5 and 10, and MRR from top-10 ranking."""
    n_rel = len(relevant)
    out: dict[str, float] = {}
    for k in K_VALUES:
        top = ranking[:k]
        hits = sum(1 for key in top if key in relevant)
        out[f"recall@{k}"] = (hits / n_rel) if n_rel else 0.0
        out[f"precision@{k}"] = hits / k if k else 0.0

    mrr = 0.0
    for rank, key in enumerate(ranking[:TOP_K], start=1):
        if key in relevant:
            mrr = 1.0 / rank
            break
    out["mrr"] = mrr
    return out


def is_jargon_question(question: str) -> bool:
    if _EN_JARGON.search(question):
        return True
    # Proper-noun heavy: English acronyms already covered; also bare ALLCAPS 2+ letters.
    if re.search(r"\b[A-Z]{2,}\b", question):
        return True
    # Chinese product / tech named entities that appear as Latin in the Q.
    if re.search(r"[A-Za-z]{3,}", question) and re.search(r"[一-龥]", question):
        # Mixed CJK+Latin often jargon (e.g. "什么是 MCP", "PostgreSQL 索引")
        return True
    return False


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def aggregate(per_q: list[dict[str, float]]) -> dict[str, float]:
    keys = [f"recall@{k}" for k in K_VALUES] + [f"precision@{k}" for k in K_VALUES] + ["mrr"]
    return {k: mean([m[k] for m in per_q]) for k in keys}


async def run_config(
    name: str,
    retriever,
    questions: list[dict[str, Any]],
) -> dict[str, Any]:
    per_question: list[dict[str, Any]] = []
    metrics_list: list[dict[str, float]] = []
    jargon_metrics: list[dict[str, float]] = []
    general_metrics: list[dict[str, float]] = []

    for q in questions:
        results = await retriever.search(q["question"], top_k=TOP_K)
        ranking = result_keys(results)
        relevant = gt_keys(q["relevant_chunks"])
        m = metrics_for_ranking(ranking, relevant)
        metrics_list.append(m)
        jargon = is_jargon_question(q["question"])
        if jargon:
            jargon_metrics.append(m)
        else:
            general_metrics.append(m)

        first_hit_rank = None
        for rank, key in enumerate(ranking[:TOP_K], start=1):
            if key in relevant:
                first_hit_rank = rank
                break

        hit_keys_at_10 = [list(key) for key in ranking[:10] if key in relevant]
        per_question.append(
            {
                "id": q["id"],
                "jargon": jargon,
                "n_relevant": len(relevant),
                "first_hit_rank": first_hit_rank,
                "hits_at_10": hit_keys_at_10,
                **m,
            }
        )

    return {
        "name": name,
        "n_questions": len(questions),
        "macro": aggregate(metrics_list),
        "slice_jargon": {
            "n": len(jargon_metrics),
            "macro": aggregate(jargon_metrics) if jargon_metrics else None,
        },
        "slice_general": {
            "n": len(general_metrics),
            "macro": aggregate(general_metrics) if general_metrics else None,
        },
        "per_question": per_question,
    }


def fmt_pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def fmt_f(x: float) -> str:
    return f"{x:.4f}"


def write_md(payload: dict[str, Any]) -> str:
    configs = payload["configs"]
    by_name = {c["name"]: c for c in configs}
    hybrid = by_name["hybrid"]["macro"]
    pure_v = by_name["pure_vector"]["macro"]
    abs_lift = hybrid["recall@5"] - pure_v["recall@5"]
    rel_lift = (abs_lift / pure_v["recall@5"] * 100.0) if pure_v["recall@5"] > 0 else float("nan")

    lines: list[str] = []
    lines.append("# 01 检索 A/B：混合 vs 纯向量 vs 纯 BM25")
    lines.append("")
    lines.append(f"生成时间: {payload['timestamp']}")
    lines.append(f"Embedding: `{payload['embedding_model']}` @ `{payload['embedding_endpoint']}`")
    lines.append(
        f"数据规模: {payload['scale']['videos']} videos / "
        f"{payload['scale']['chunks']} chunks / dim {payload['scale']['vector_dim']}"
    )
    if payload.get("eval_note"):
        lines.append(payload["eval_note"])
    lines.append(
        f"评测题: detail + non-empty relevant_chunks = **{payload['n_questions']}** "
        f"（跳过 summary/self；chunk 级 Recall/Precision/MRR 仅对 detail）"
    )
    lines.append(f"top_k 检索: {payload['top_k']}；指标 k ∈ {list(payload['k_values'])}")
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
    lines.append("## Headline：hybrid vs pure_vector（Recall@5）")
    lines.append("")
    lines.append(
        f"- hybrid Recall@5 = **{fmt_f(hybrid['recall@5'])}** ({fmt_pct(hybrid['recall@5'])})"
    )
    lines.append(
        f"- pure_vector Recall@5 = **{fmt_f(pure_v['recall@5'])}** ({fmt_pct(pure_v['recall@5'])})"
    )
    if pure_v["recall@5"] > 0:
        lines.append(
            f"- **绝对提升** = {fmt_f(abs_lift)} ({fmt_pct(abs_lift)} points)  |  "
            f"**相对提升** = **{rel_lift:.2f}%**"
        )
    else:
        lines.append("- pure_vector Recall@5 为 0，相对提升未定义")
    lines.append("")
    lines.append("## 宏平均指标（macro over questions）")
    lines.append("")
    header = (
        "| config | Recall@5 | Recall@10 | Precision@5 | Precision@10 | MRR |"
    )
    lines.append(header)
    lines.append("|--------|----------|-----------|-------------|--------------|-----|")
    for c in configs:
        m = c["macro"]
        lines.append(
            f"| `{c['name']}` | {fmt_f(m['recall@5'])} | {fmt_f(m['recall@10'])} | "
            f"{fmt_f(m['precision@5'])} | {fmt_f(m['precision@10'])} | {fmt_f(m['mrr'])} |"
        )
    lines.append("")
    lines.append("## 切片：jargon / 专有名词倾向 vs general semantic")
    lines.append("")
    lines.append(
        "启发式：题干含英文技术缩写/产品名（PostgreSQL、MCP、GDP、API 等）或中英混排专有词 → jargon；否则 general。"
    )
    lines.append("")
    lines.append("| config | slice | n | Recall@5 | Recall@10 | Precision@5 | Precision@10 | MRR |")
    lines.append("|--------|-------|---|----------|-----------|-------------|--------------|-----|")
    for c in configs:
        for slice_name, key in (("jargon", "slice_jargon"), ("general", "slice_general")):
            sl = c[key]
            n = sl["n"]
            m = sl["macro"]
            if not m:
                lines.append(
                    f"| `{c['name']}` | {slice_name} | {n} | — | — | — | — | — |"
                )
                continue
            lines.append(
                f"| `{c['name']}` | {slice_name} | {n} | "
                f"{fmt_f(m['recall@5'])} | {fmt_f(m['recall@10'])} | "
                f"{fmt_f(m['precision@5'])} | {fmt_f(m['precision@10'])} | {fmt_f(m['mrr'])} |"
            )
    lines.append("")
    lines.append("## 说明")
    lines.append("")
    lines.append(
        "- 命中定义：结果 `(document_id, chunk_index)` 与 ground-truth relevant_chunks 集合求交。"
    )
    lines.append(
        "- 每次 search 使用 top_k=10；Recall/Precision@5 取排名前 5；MRR 基于 top-10 首个命中秩（无命中则 0）。"
    )
    lines.append(
        "- pure_bm25 仍走 HybridRetriever（vector weight=0），实现上仍会 embed 查询，属实现细节。"
    )
    lines.append(
        f"- smoke embed dim 抽样: {payload.get('smoke_embed_dim')}；Qdrant points: {payload.get('qdrant_point_count')}"
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
    smoke = embedding.embed(["retrieval_ab smoke"])
    smoke_dim = len(smoke[0]) if smoke and smoke[0] else 0
    print(f"smoke embed ok, dim={smoke_dim}")
    if smoke_dim != settings.rag.vector_size:
        print(
            f"WARNING: smoke dim {smoke_dim} != settings.rag.vector_size {settings.rag.vector_size}"
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
            print(f"running config={name} n={len(questions)} ...")
            cfg_result = await run_config(name, retrievers[name], questions)
            results_configs.append(cfg_result)
            m = cfg_result["macro"]
            print(
                f"  Recall@5={m['recall@5']:.4f} Recall@10={m['recall@10']:.4f} "
                f"P@5={m['precision@5']:.4f} P@10={m['precision@10']:.4f} MRR={m['mrr']:.4f}"
            )

        by_name = {c["name"]: c for c in results_configs}
        hybrid_r5 = by_name["hybrid"]["macro"]["recall@5"]
        vector_r5 = by_name["pure_vector"]["macro"]["recall@5"]
        abs_lift = hybrid_r5 - vector_r5
        rel_lift = (abs_lift / vector_r5) if vector_r5 > 0 else None

        emb_model = settings.models.embedding.model
        emb_endpoint = settings.models.embedding.endpoint

        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "embedding_model": emb_model,
            "embedding_endpoint": emb_endpoint,
            "smoke_embed_dim": smoke_dim,
            "qdrant_point_count": point_count,
            "scale": scale,
            "eval_note": EVAL_NOTE,
            "n_questions": len(questions),
            "n_eval_set_total": sum(
                1 for line in EVAL_SET.read_text(encoding="utf-8").splitlines() if line.strip()
            ),
            "question_filter": "type=detail AND non-empty relevant_chunks",
            "top_k": TOP_K,
            "k_values": list(K_VALUES),
            "config_defs": config_defs,
            "headline": {
                "metric": "recall@5",
                "hybrid": hybrid_r5,
                "pure_vector": vector_r5,
                "absolute_lift": abs_lift,
                "relative_lift": rel_lift,
            },
            "configs": [
                {
                    "name": c["name"],
                    "n_questions": c["n_questions"],
                    "macro": c["macro"],
                    "slice_jargon": c["slice_jargon"],
                    "slice_general": c["slice_general"],
                    "per_question": c["per_question"],
                }
                for c in results_configs
            ],
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
        if rel_lift is not None:
            print(
                f"HEADLINE hybrid vs pure_vector Recall@5: "
                f"abs={abs_lift:+.4f} rel={rel_lift * 100:+.2f}%"
            )
        return 0
    finally:
        qdrant.close()
        print("Qdrant closed")


def main() -> None:
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
