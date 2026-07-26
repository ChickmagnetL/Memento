"""Phase 4: Agent routing accuracy.

Runs Layered Agent (build_agent) on eval_set questions (42 total:
detail 28, summary 10, self 4), maps tool calls to routes
(search / lookup+summarize / memory), computes overall accuracy,
3×3 confusion matrix, per-class P/R, and writes
benchmarks/results/04_routing.{md,json}.

Questions run with bounded concurrency (default 5) via asyncio.Semaphore.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
import traceback
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "backend"))
import bench_env  # noqa: F401  # sets env BEFORE other memento imports

from config.settings import get_settings  # noqa: E402
from core.agent.chat_agent import (  # noqa: E402
    ChatDeps,
    build_agent,
    build_system_prompt,
)
from core.models.factory import build_chat_model, build_embedding_client  # noqa: E402
from core.rag.document_summary_store import DocumentSummaryStore  # noqa: E402
from core.rag.retrieval import HybridRetriever  # noqa: E402
from storage.qdrant_client import QdrantStore  # noqa: E402
from storage.sqlite_client import SQLiteClient  # noqa: E402

EVAL_SET = ROOT / "benchmarks" / "eval_set.jsonl"
OUT_MD = ROOT / "benchmarks" / "results" / "04_routing.md"
OUT_JSON = ROOT / "benchmarks" / "results" / "04_routing.json"

ROUTE_LABELS = ("search", "lookup+summarize", "memory")
RETRIEVAL_TOOLS = frozenset(
    {"search_knowledge", "lookup_documents", "summarize_document"}
)
LOOKUP_SUMMARIZE_TOOLS = frozenset({"lookup_documents", "summarize_document"})

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504, 524})
MAX_RETRIES = 3
BACKOFF_S = (30, 60, 120)
INTER_QUESTION_SLEEP_S = 1.5

# Seed memories for self questions (q045–q048) when memories table is empty.
SEED_MEMORIES = [
    "我最近在学习 AI/大模型工程，关注 MCP 协议、Agent 与 Harness Engineering",
    "除了 AI 和软件开发，我也关注生活与经济话题（如 GDP 核算、瑞士经济）",
    "数据库方面我学过 PostgreSQL 高级特性（索引、查询优化等）",
    "我的主要学习兴趣：系统架构、数据库、AI 工程、健身训练理论",
]


def _status_code(exc: BaseException) -> int | None:
    code = getattr(exc, "status_code", None)
    if isinstance(code, int):
        return code
    cause = getattr(exc, "__cause__", None)
    if cause is not None and cause is not exc:
        nested = _status_code(cause)
        if nested is not None:
            return nested
    context = getattr(exc, "__context__", None)
    if context is not None and context is not exc:
        nested = _status_code(context)
        if nested is not None:
            return nested
    return None


def _exception_body(exc: BaseException) -> Any:
    for attr in ("body", "response", "content"):
        body = getattr(exc, attr, None)
        if body is not None:
            return body
    return None


def _retry_after_from_body(body: Any) -> float | None:
    if body is None:
        return None
    if isinstance(body, dict):
        for key in ("retry_after", "retry-after", "Retry-After"):
            if key in body:
                try:
                    return float(body[key])
                except (TypeError, ValueError):
                    pass
        # Nested error payloads, e.g. {"error": {"retry_after": 120}}
        for v in body.values():
            found = _retry_after_from_body(v)
            if found is not None:
                return found
        return None
    text = body if isinstance(body, str) else str(body)
    m = re.search(r"retry[_-]?after[\"']?\s*[:=]\s*(\d+(?:\.\d+)?)", text, re.I)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def is_retryable(exc: BaseException) -> bool:
    code = _status_code(exc)
    if code in RETRYABLE_STATUS:
        return True
    text = f"{type(exc).__name__}: {exc}".lower()
    keywords = (
        "timeout",
        "timed out",
        "connect",
        "connection",
        "temporarily",
        "unavailable",
        "524",
        "502",
        "503",
        "429",
    )
    return any(k in text for k in keywords)


def retry_after_seconds(exc: BaseException, attempt: int) -> float:
    body = _exception_body(exc)
    honor = _retry_after_from_body(body)
    if honor is not None and honor > 0:
        return honor
    # Also try parsing from the exception string (ModelHTTPError body may be in message)
    honor = _retry_after_from_body(str(exc))
    if honor is not None and honor > 0:
        return honor
    return float(BACKOFF_S[min(attempt, len(BACKOFF_S) - 1)])


async def agent_run_with_retry(agent, prompt: str, deps, qid: str):
    last_exc: BaseException | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return await agent.run(prompt, deps=deps)
        except Exception as exc:
            last_exc = exc
            if attempt >= MAX_RETRIES or not is_retryable(exc):
                raise
            sleep_s = retry_after_seconds(exc, attempt)
            print(f"retry {attempt + 1}/{MAX_RETRIES} after {sleep_s:.0f}s for {qid}: {exc}")
            await asyncio.sleep(sleep_s)
    assert last_exc is not None
    raise last_exc


def load_all_questions(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def extract_tool_names(result) -> list[str]:
    """Extract tool names from agent result (order-preserving, with duplicates)."""
    names: list[str] = []
    if result is None or not hasattr(result, "all_messages"):
        return names
    try:
        messages = result.new_messages()
    except Exception:
        try:
            messages = result.all_messages()
        except Exception:
            return names
    for msg in messages:
        if not hasattr(msg, "parts"):
            continue
        for part in msg.parts:
            tool_name = getattr(part, "tool_name", None)
            if tool_name:
                names.append(str(tool_name))
    return names


def tools_unique(tools: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for t in tools:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def predict_route(tools: list[str]) -> str:
    """Map tool calls → route with priority:
    1. any lookup_documents / summarize_document → lookup+summarize
    2. else only search_knowledge among retrieval tools → search
    3. else (no search/lookup/summarize) → memory
    propose_memory is ignored for classification.
    """
    retrieval = [t for t in tools if t in RETRIEVAL_TOOLS]
    if any(t in LOOKUP_SUMMARIZE_TOOLS for t in retrieval):
        return "lookup+summarize"
    if any(t == "search_knowledge" for t in retrieval):
        return "search"
    return "memory"


def empty_confusion() -> dict[str, dict[str, int]]:
    return {e: {p: 0 for p in ROUTE_LABELS} for e in ROUTE_LABELS}


def compute_per_class(
    confusion: dict[str, dict[str, int]],
) -> dict[str, dict[str, float | int]]:
    per: dict[str, dict[str, float | int]] = {}
    for label in ROUTE_LABELS:
        tp = confusion[label][label]
        support = sum(confusion[label][p] for p in ROUTE_LABELS)
        predicted = sum(confusion[e][label] for e in ROUTE_LABELS)
        precision = (tp / predicted) if predicted else 0.0
        recall = (tp / support) if support else 0.0
        per[label] = {
            "precision": precision,
            "recall": recall,
            "support": support,
            "tp": tp,
            "predicted": predicted,
        }
    return per


def fmt_pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def write_md(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# 04 Agent 路由准确率")
    lines.append("")
    lines.append(f"生成时间: {payload['timestamp']}")
    lines.append(f"Chat model: `{payload['chat_model']}` @ `{payload['chat_endpoint']}`")
    lines.append(
        f"Embedding: `{payload['embedding_model']}` @ `{payload['embedding_endpoint']}`"
    )
    lines.append(f"n = **{payload['n_total']}**（accuracy 分母含全部题；errors 计为 incorrect）")
    lines.append(
        f"overall accuracy = **{fmt_pct(payload['overall_accuracy'])}** "
        f"({payload['n_correct']}/{payload['n_total']})"
    )
    lines.append(f"n_errors = {payload['n_errors']}")
    lines.append("")
    lines.append("## expected_route 分布")
    lines.append("")
    dist = payload.get("expected_distribution") or {}
    lines.append("| route | n |")
    lines.append("|-------|---|")
    for label in ROUTE_LABELS:
        lines.append(f"| `{label}` | {dist.get(label, 0)} |")
    lines.append("")
    lines.append("## 混淆矩阵（expected × predicted）")
    lines.append("")
    header = "| expected \\ predicted | " + " | ".join(f"`{p}`" for p in ROUTE_LABELS) + " |"
    lines.append(header)
    lines.append("|" + "---|" * (len(ROUTE_LABELS) + 1))
    cm = payload["confusion_matrix"]
    for e in ROUTE_LABELS:
        row = [f"`{e}`"] + [str(cm[e].get(p, 0)) for p in ROUTE_LABELS]
        lines.append("| " + " | ".join(row) + " |")
    # errors column note
    n_err_pred = payload.get("n_error_predictions", 0)
    if n_err_pred:
        lines.append("")
        lines.append(
            f"另有 **{n_err_pred}** 题 predicted=`error`/`null`（未计入矩阵单元格，计为 incorrect）。"
        )
    lines.append("")
    lines.append("## 每类 Precision / Recall")
    lines.append("")
    lines.append("| route | precision | recall | support |")
    lines.append("|-------|-----------|--------|---------|")
    for label in ROUTE_LABELS:
        pc = payload["per_class"][label]
        lines.append(
            f"| `{label}` | {fmt_pct(pc['precision'])} | {fmt_pct(pc['recall'])} | "
            f"{pc['support']} |"
        )
    lines.append("")
    lines.append("## 失败用例")
    lines.append("")
    failures = payload.get("failures") or []
    if not failures:
        lines.append("（无）")
    else:
        lines.append("| id | question | expected | predicted | tools | error |")
        lines.append("|----|----------|----------|-----------|-------|-------|")
        for f in failures:
            q = (f.get("question") or "").replace("|", "\\|")
            if len(q) > 60:
                q = q[:57] + "..."
            tools = ", ".join(f.get("tools") or []) or "—"
            err = (f.get("error") or "—").replace("|", "\\|")
            if len(err) > 40:
                err = err[:37] + "..."
            lines.append(
                f"| {f.get('id')} | {q} | `{f.get('expected')}` | "
                f"`{f.get('predicted')}` | {tools} | {err} |"
            )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    for note in payload.get("notes") or []:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


async def seed_memories_if_empty(sqlite: SQLiteClient) -> list[str]:
    """If memories table empty, seed profile facts for self questions. Returns contents used."""
    existing = await sqlite.list_memories()
    if existing:
        print(f"memories already present: n={len(existing)} (skip seed)")
        return [m["content"] for m in existing]
    print("memories empty → seeding profile facts for self route")
    for content in SEED_MEMORIES:
        await sqlite.add_memory(content=content, category="profile")
        print(f"  seeded: {content[:40]}...")
    after = await sqlite.list_memories()
    return [m["content"] for m in after]


async def main_async(
    limit: int | None = None,
    smoke_only: bool = False,
    concurrency: int = 5,
) -> int:
    settings = get_settings()
    data_dir = Path(settings.storage.data_dir).expanduser()
    questions = load_all_questions(EVAL_SET)
    if not questions:
        print("ERROR: no questions in", EVAL_SET)
        return 1
    if limit is not None:
        questions = questions[:limit]
        print(f"limit={limit}, using first {len(questions)} questions")
    if concurrency < 1:
        concurrency = 1
    print(f"concurrency={concurrency}")

    chat_model_name = settings.models.chat.model
    chat_endpoint = settings.models.chat.endpoint
    emb_model = settings.models.embedding.model
    emb_endpoint = settings.models.embedding.endpoint
    print(f"chat={chat_model_name} @ {chat_endpoint}")
    print(f"embedding={emb_model} @ {emb_endpoint}")
    print(f"data_dir={data_dir}")

    sqlite = SQLiteClient(data_dir / "metadata.db")
    await sqlite.connect()
    qdrant = QdrantStore(data_dir / "qdrant")
    qdrant.connect(vector_size=settings.rag.vector_size)

    notes: list[str] = []
    try:
        point_count = len(qdrant.scroll_all_points())
        print(f"Qdrant open ok, points={point_count}")

        memory_contents = await seed_memories_if_empty(sqlite)
        if len(memory_contents) >= len(SEED_MEMORIES) and any(
            "MCP" in c or "PostgreSQL" in c for c in memory_contents
        ):
            notes.append(
                "Seeded or reused profile memories for self questions (q045–q048)."
            )
        else:
            notes.append(f"Memories in DB: n={len(memory_contents)}")

        embedding_client = build_embedding_client(settings)
        smoke_vec = embedding_client.embed(["routing_accuracy smoke"])
        smoke_dim = len(smoke_vec[0]) if smoke_vec and smoke_vec[0] else 0
        print(f"smoke embed ok, dim={smoke_dim}")
        if smoke_dim != settings.rag.vector_size:
            print(
                f"WARNING: smoke dim {smoke_dim} != settings.rag.vector_size "
                f"{settings.rag.vector_size}"
            )

        retriever = HybridRetriever(
            embedding_client=embedding_client,
            qdrant=qdrant,
            weights=settings.rag.hybrid_weights,
        )
        summary_store = DocumentSummaryStore(
            sqlite=sqlite, qdrant=qdrant, embedding=embedding_client
        )
        deps = ChatDeps(
            retriever=retriever,
            top_k=settings.rag.top_k,
            summary_store=summary_store,
            embedder=embedding_client,
        )
        memories = await sqlite.list_memories()
        system_prompt = build_system_prompt(memories=memories)
        agent = build_agent(build_chat_model(settings), system_prompt=system_prompt)

        # Smoke: one simple agent.run before full suite (with transient retry)
        print("smoke agent.run ...")
        t0 = time.perf_counter()
        smoke_result = await agent_run_with_retry(
            agent, "一句话介绍你自己", deps, qid="smoke"
        )
        smoke_ms = (time.perf_counter() - t0) * 1000.0
        smoke_tools = extract_tool_names(smoke_result)
        print(
            f"smoke ok latency={smoke_ms:.0f}ms tools={smoke_tools} "
            f"output_len={len(str(getattr(smoke_result, 'output', '') or ''))}"
        )
        if smoke_ms > 60000:
            notes.append(
                f"Smoke agent.run took {smoke_ms:.0f}ms (>60s); suite still proceeds."
            )
            print(f"WARNING: smoke latency {smoke_ms:.0f}ms > 60000ms, proceeding anyway")
        if smoke_only:
            print("smoke_only=True, exiting after smoke")
            return 0

        notes.append(
            "3 docs may lack L2/L3 (增肌饮食 BV1ev411w7bs, GDP P-NmMX9rlYQ, "
            "系统设计 oYxTTirKY8M); summary route still counts if lookup/summarize tools called."
        )
        notes.append(
            "Route mapping: lookup_documents|summarize_document → lookup+summarize; "
            "else search_knowledge → search; else → memory. propose_memory ignored."
        )
        notes.append(
            "Accuracy denominator = n_total (42: detail 28, summary 10, self 4); "
            "agent errors count as incorrect (predicted=error)."
        )
        notes.append(
            "Corpus is 50-video with noise docs; eval questions target first-10 videos only."
        )
        notes.append(
            f"Bounded concurrency={concurrency} via asyncio.Semaphore; "
            "no store lock — concurrent Qdrant/SQLite reads may race and reduce "
            "effective concurrency if the store is not concurrent-safe."
        )
        notes.append(
            f"Transient API retry: max_retries={MAX_RETRIES}, backoff_s={list(BACKOFF_S)}, "
            f"retryable_status={sorted(RETRYABLE_STATUS)}; inter-question sleep="
            f"{INTER_QUESTION_SLEEP_S}s."
        )

        expected_distribution: dict[str, int] = defaultdict(int)
        for q in questions:
            expected_distribution[q.get("expected_route") or ""] += 1

        n_total = len(questions)
        sem = asyncio.Semaphore(concurrency)
        progress_lock = asyncio.Lock()
        done_count = 0
        n_correct_running = 0
        n_errors_running = 0

        async def run_one(i: int, q: dict[str, Any]) -> dict[str, Any]:
            nonlocal done_count, n_correct_running, n_errors_running
            qid = q["id"]
            question = q["question"]
            expected = q.get("expected_route") or "search"
            tools: list[str] = []
            predicted: str | None = None
            err: str | None = None
            latency_ms: float | None = None

            async with sem:
                try:
                    t0 = time.perf_counter()
                    result = await agent_run_with_retry(agent, question, deps, qid=qid)
                    latency_ms = (time.perf_counter() - t0) * 1000.0
                    tools = extract_tool_names(result)
                    predicted = predict_route(tools)
                except Exception as exc:
                    err = f"{type(exc).__name__}: {exc}"
                    predicted = "error"
                    print(f"  TRACEBACK for {qid}:")
                    traceback.print_exc()
                if INTER_QUESTION_SLEEP_S > 0:
                    await asyncio.sleep(INTER_QUESTION_SLEEP_S)

            if predicted in ROUTE_LABELS and expected in ROUTE_LABELS:
                correct = predicted == expected
            else:
                correct = False

            row = {
                "index": i,
                "id": qid,
                "type": q.get("type"),
                "question": question,
                "expected_route": expected,
                "predicted_route": predicted,
                "tools": tools,
                "tools_unique": tools_unique(tools),
                "correct": correct,
                "error": err,
                "latency_ms": round(latency_ms, 1) if latency_ms is not None else None,
            }

            async with progress_lock:
                done_count += 1
                if correct:
                    n_correct_running += 1
                if err is not None or predicted == "error":
                    n_errors_running += 1
                status = "ok" if correct else "FAIL"
                print(
                    f"{qid} expected={expected} predicted={predicted} "
                    f"tools={tools_unique(tools)} {status}"
                    + (f" err={err[:80]}" if err else "")
                )
                print(
                    f"  progress {done_count}/{n_total} "
                    f"correct={n_correct_running} errors={n_errors_running}"
                )
            return row

        wall_t0 = time.perf_counter()
        raw_results = await asyncio.gather(
            *[run_one(i, q) for i, q in enumerate(questions)],
            return_exceptions=True,
        )
        wall_time_s = time.perf_counter() - wall_t0

        # Aggregate in original question order
        confusion = empty_confusion()
        per_question: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        n_correct = 0
        n_errors = 0
        n_error_predictions = 0

        ordered_rows: list[dict[str, Any]] = []
        for i, res in enumerate(raw_results):
            q = questions[i]
            if isinstance(res, BaseException):
                qid = q["id"]
                question = q["question"]
                expected = q.get("expected_route") or "search"
                err = f"{type(res).__name__}: {res}"
                print(f"  GATHER exception for {qid}: {err}")
                traceback.print_exception(type(res), res, res.__traceback__)
                ordered_rows.append(
                    {
                        "index": i,
                        "id": qid,
                        "type": q.get("type"),
                        "question": question,
                        "expected_route": expected,
                        "predicted_route": "error",
                        "tools": [],
                        "tools_unique": [],
                        "correct": False,
                        "error": err,
                        "latency_ms": None,
                    }
                )
            else:
                ordered_rows.append(res)

        ordered_rows.sort(key=lambda r: r.get("index", 0))

        for row in ordered_rows:
            expected = row["expected_route"]
            predicted = row["predicted_route"]
            tools = row["tools"]
            err = row["error"]
            correct = bool(row["correct"])
            qid = row["id"]
            question = row.get("question") or ""

            if err is not None or predicted == "error":
                n_errors += 1
                n_error_predictions += 1

            if predicted in ROUTE_LABELS and expected in ROUTE_LABELS:
                confusion[expected][predicted] += 1
                correct = predicted == expected
            else:
                correct = False
                if predicted not in ROUTE_LABELS and predicted != "error":
                    n_error_predictions += 1

            if correct:
                n_correct += 1
            else:
                failures.append(
                    {
                        "id": qid,
                        "question": question,
                        "expected": expected,
                        "predicted": predicted,
                        "tools": tools,
                        "error": err,
                    }
                )

            per_question.append(
                {
                    "id": qid,
                    "type": row.get("type"),
                    "expected_route": expected,
                    "predicted_route": predicted,
                    "tools": tools,
                    "tools_unique": row.get("tools_unique") or tools_unique(tools),
                    "correct": correct,
                    "error": err,
                    "latency_ms": row.get("latency_ms"),
                }
            )

        overall = (n_correct / n_total) if n_total else 0.0
        per_class = compute_per_class(confusion)
        notes.append(f"wall_time_s={wall_time_s:.2f}, concurrency={concurrency}")

        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "chat_model": chat_model_name,
            "chat_endpoint": chat_endpoint,
            "embedding_model": emb_model,
            "embedding_endpoint": emb_endpoint,
            "n_total": n_total,
            "n_correct": n_correct,
            "n_errors": n_errors,
            "n_error_predictions": n_error_predictions,
            "overall_accuracy": overall,
            "expected_distribution": dict(expected_distribution),
            "confusion_matrix": confusion,
            "per_class": per_class,
            "failures": failures,
            "per_question": per_question,
            "notes": notes,
            "qdrant_point_count": point_count,
            "smoke_embed_dim": smoke_dim,
            "route_labels": list(ROUTE_LABELS),
            "seeded_memories": memory_contents,
            "wall_time_s": round(wall_time_s, 3),
            "concurrency": concurrency,
        }

        OUT_MD.parent.mkdir(parents=True, exist_ok=True)
        OUT_MD.write_text(write_md(payload), encoding="utf-8")
        OUT_JSON.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {OUT_MD}")
        print(f"wrote {OUT_JSON}")
        print(
            f"OVERALL accuracy={fmt_pct(overall)} ({n_correct}/{n_total}) "
            f"wall_time_s={wall_time_s:.2f} concurrency={concurrency}"
        )
        for label in ROUTE_LABELS:
            pc = per_class[label]
            print(
                f"  {label}: P={fmt_pct(pc['precision'])} R={fmt_pct(pc['recall'])} "
                f"support={pc['support']}"
            )
        return 0
    finally:
        qdrant.close()
        await sqlite.close()
        print("Qdrant + SQLite closed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 4: Agent routing accuracy")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only run first N questions (debug)",
    )
    parser.add_argument(
        "--smoke-only",
        action="store_true",
        help="Only open deps and run one smoke agent call",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Max concurrent agent runs (default: 5)",
    )
    args = parser.parse_args()
    raise SystemExit(
        asyncio.run(
            main_async(
                limit=args.limit,
                smoke_only=args.smoke_only,
                concurrency=args.concurrency,
            )
        )
    )


if __name__ == "__main__":
    main()
