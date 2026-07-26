"""Phase 2: Layered vs Flat agent architecture A/B on summary questions.

Runs both:
  - Layered: build_agent (search + lookup + summarize + propose_memory)
  - Flat:    build_flat_agent (search_knowledge only)

LLM-as-judge scores answers 1–5 blindly. Writes
benchmarks/results/02_architecture.{md,json}.

Across questions: bounded concurrency (asyncio.Semaphore, default 5).
Within a question: layered and flat agents run concurrently; judge is sequential.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "backend"))
import bench_env  # noqa: F401  # sets env BEFORE other memento imports

from pydantic_ai import Agent, RunContext  # noqa: E402

from config.settings import get_settings  # noqa: E402
from core.agent.chat_agent import (  # noqa: E402
    ChatDeps,
    EMBEDDING_UNAVAILABLE_TOOL_MESSAGE,
    build_agent,
    build_system_prompt,
)
from core.models.factory import (  # noqa: E402
    build_chat_completion_client,
    build_chat_model,
    build_embedding_client,
)
from core.rag.document_summary_store import DocumentSummaryStore  # noqa: E402
from core.rag.embedding import EmbeddingError  # noqa: E402
from core.rag.retrieval import HybridRetriever  # noqa: E402
from storage.qdrant_client import QdrantStore  # noqa: E402
from storage.sqlite_client import SQLiteClient  # noqa: E402

EVAL_SET = ROOT / "benchmarks" / "eval_set.jsonl"
OUT_MD = ROOT / "benchmarks" / "results" / "02_architecture.md"
OUT_JSON = ROOT / "benchmarks" / "results" / "02_architecture.json"

# Vestigial: tags from an earlier eval set. No current summary question maps
# to these video_ids. Kept for the lacks_l2_l3 column in the report; will tag
# 0 questions. Safe to delete in a later cleanup.
DOCS_LACKING_L2_L3 = frozenset({"BV1ev411w7bs", "P-NmMX9rlYQ", "oYxTTirKY8M"})

FLAT_SYSTEM_PROMPT = (
    "You are Memento, an assistant for a personal video knowledge base. "
    "Answer in the same language as the user. When a question concerns "
    "stored video content, call search_knowledge first and ground your "
    "answer in the returned excerpts. If nothing relevant is found, say so.\n\n"
    "## Tool Use\n"
    "You have only one tool: search_knowledge. Use it for detail questions "
    "and for summary/overview questions. For overview questions, issue one "
    "or more targeted search queries and synthesize a structured overview "
    "from the returned excerpts. You do not have document lookup or "
    "document-summary tools.\n\n"
    "## Citation Rules (MANDATORY)\n\n"
    "Every claim grounded in search results MUST include a clickable timestamp link. "
    "This is not optional.\n\n"
    "### Search Result Format\n"
    "Each result contains: [title] [platform: PLATFORM] [video_id: XXX] [MM:SS] text\n"
    "- platform: the exact source platform (bilibili, douyin, or youtube)\n"
    "- video_id: the source platform's video identifier\n"
    "- start_timestamp: the timestamp in MM:SS or H:MM:SS format — use this EXACTLY, "
    "do NOT invent or modify timestamps\n\n"
    "### Link Format (REQUIRED for every citation)\n"
    "- Bilibili: [MM:SS description](memento://play?platform=bilibili&video_id=VIDEO_ID&t=SECONDS)\n"
    "- Douyin: [description](memento://play?platform=douyin&video_id=VIDEO_ID)\n"
    "- YouTube: [MM:SS description](memento://play?platform=youtube&video_id=VIDEO_ID&t=SECONDS)\n\n"
    "### Rules\n"
    "1. ALWAYS use the exact start_timestamp from search results. NEVER invent, "
    "combine, or modify timestamps.\n"
    "2. Convert MM:SS to total seconds for the t= parameter "
    "(e.g., 5:30 → t=330, 1:23:45 → t=5025).\n"
    "3. Use the exact platform field from the search result. NEVER infer a "
    "platform from video_id.\n"
    "4. For Douyin: do NOT include t= parameter.\n"
    "5. If platform or video_id is null, cite in plain text instead of creating "
    "a memento link.\n\n"
    "### Example\n"
    "Search result: [React Hooks tutorial] [platform: bilibili] "
    "[video_id: BV1234567890] [05:30] \"useState allows...\"\n"
    "Your response: \"According to [05:30 useState introduction](memento://play?"
    "platform=bilibili&video_id=BV1234567890&t=330), useState allows...\"\n\n"
    "WRONG (do NOT do this): citing as [00:48-01:36], citing without a link, "
    "inventing timestamps."
    "\n\n### Tool Failure Rules\n"
    "If a tool says knowledge base retrieval is currently unavailable because "
    "the embedding model is unavailable, tell the user this plainly. Do not "
    "cite stored video content and do not fabricate timestamp links."
)

RUBRIC = """Score 1–5 for answer completeness on a summary/overview question:
5 = Covers nearly all key points from the source topic; accurate; well structured overview
4 = Covers most key points; minor gaps or slight inaccuracy
3 = Partial coverage; several important points missing or vague
2 = Thin or mostly off-topic; major gaps
1 = Empty, refusal, hallucination-heavy, or fails to answer
Also consider: factual accuracy relative to provided key points (notes); do not reward inventing content not grounded in the answer's claims about the video."""

JUDGE_SYSTEM = (
    "You are an independent evaluator. Score two answers to the same summary "
    "question. Be fair and consistent. Output ONLY a JSON object, no markdown fences."
)


def build_flat_agent(model, system_prompt: str | None = None) -> Agent:
    """Flat control agent: search_knowledge only (same body as layered)."""
    agent = Agent(
        model, deps_type=ChatDeps, system_prompt=system_prompt or FLAT_SYSTEM_PROMPT
    )

    @agent.tool
    async def search_knowledge(ctx: RunContext[ChatDeps], query: str) -> str:
        """Search the video knowledge base and return matching excerpts."""
        try:
            results = await ctx.deps.retriever.search(query, top_k=ctx.deps.top_k)
        except EmbeddingError:
            return EMBEDDING_UNAVAILABLE_TOOL_MESSAGE
        if not results:
            return "No matching knowledge found."
        return "\n\n".join(
            f"[{result.title_path}]"
            + (f" [platform: {result.platform}]" if result.platform else "")
            + (f" [video_id: {result.video_id}]" if result.video_id else "")
            + (f" [{result.start_timestamp}]" if result.start_timestamp else "")
            + f"\n{result.text}"
            for result in results
        )

    return agent


def load_summary_questions(path: Path) -> tuple[list[dict[str, Any]], int]:
    """Return (eligible_rows, n_skipped_ineligible).

    Per EVAL_SPEC §8: only summary rows with summary_eligible=True enter the
    layered-vs-flat scoring pool. Ineligible rows are counted but skipped.
    """
    rows: list[dict[str, Any]] = []
    n_skipped_ineligible = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row.get("type") != "summary":
            continue
        if not row.get("summary_eligible"):
            n_skipped_ineligible += 1
            continue
        rows.append(row)
    return rows, n_skipped_ineligible


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


def _clamp_score(v: Any) -> int | None:
    try:
        n = int(round(float(v)))
    except (TypeError, ValueError):
        return None
    if n < 1 or n > 5:
        return None
    return n


def parse_judge_response(text: str) -> dict[str, Any] | None:
    """Parse judge JSON; return {score_a, score_b, brief_reason} or None."""
    if not text or not text.strip():
        return None
    raw = text.strip()
    # strip markdown fences
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence:
        raw = fence.group(1).strip()
    # extract first JSON object
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    sa = _clamp_score(obj.get("score_a"))
    sb = _clamp_score(obj.get("score_b"))
    if sa is None or sb is None:
        return None
    reason = obj.get("brief_reason") or obj.get("reason") or ""
    return {
        "score_a": sa,
        "score_b": sb,
        "brief_reason": str(reason)[:500],
    }


def build_judge_user_prompt(
    question: str, notes: str, answer_a: str, answer_b: str
) -> str:
    return (
        f"## Question\n{question}\n\n"
        f"## Key points (reference notes from eval set)\n{notes or '(none)'}\n\n"
        f"## Rubric\n{RUBRIC}\n\n"
        f"## Answer A\n{answer_a or '(empty)'}\n\n"
        f"## Answer B\n{answer_b or '(empty)'}\n\n"
        "Respond with JSON only:\n"
        '{"score_a": <1-5>, "score_b": <1-5>, "brief_reason": "<one sentence>"}\n'
    )


async def judge_pair(
    judge,
    question: str,
    notes: str,
    layered_answer: str,
    flat_answer: str,
) -> dict[str, Any]:
    """Blind A/B scoring. Returns scores mapped back to layered/flat."""
    # Randomize assignment
    if random.random() < 0.5:
        assignment = {"A": "layered", "B": "flat"}
        answer_a, answer_b = layered_answer, flat_answer
    else:
        assignment = {"A": "flat", "B": "layered"}
        answer_a, answer_b = flat_answer, layered_answer

    messages = [
        {"role": "system", "content": JUDGE_SYSTEM},
        {
            "role": "user",
            "content": build_judge_user_prompt(question, notes, answer_a, answer_b),
        },
    ]

    parsed: dict[str, Any] | None = None
    raw_text = ""
    judge_error: str | None = None

    for attempt in range(2):
        try:
            raw_text = await asyncio.to_thread(judge.complete, messages)
            parsed = parse_judge_response(raw_text)
            if parsed is not None:
                break
            judge_error = "parse_fail"
        except Exception as exc:
            judge_error = f"{type(exc).__name__}: {exc}"
            if attempt == 0:
                continue
            break

    if parsed is None:
        return {
            "assignment": assignment,
            "layered_score": None,
            "flat_score": None,
            "winner": None,
            "brief_reason": None,
            "judge_error": judge_error or "parse_fail",
            "judge_raw": (raw_text or "")[:800],
        }

    score_by_slot = {"A": parsed["score_a"], "B": parsed["score_b"]}
    layered_score = score_by_slot[
        "A" if assignment["A"] == "layered" else "B"
    ]
    flat_score = score_by_slot["A" if assignment["A"] == "flat" else "B"]

    if layered_score > flat_score:
        winner = "layered"
    elif layered_score < flat_score:
        winner = "flat"
    else:
        winner = "tie"

    return {
        "assignment": assignment,
        "layered_score": layered_score,
        "flat_score": flat_score,
        "winner": winner,
        "brief_reason": parsed.get("brief_reason"),
        "judge_error": None,
        "judge_raw": None,
    }


def write_md(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# 02 架构 A/B：分层 Agent vs 平铺 Agent（summary 完整度）")
    lines.append("")
    lines.append(f"生成时间: {payload['timestamp']}")
    lines.append(f"Chat agent model: `{payload['chat_model']}` @ `{payload['chat_endpoint']}`")
    lines.append(f"Judge model: `{payload['judge_model']}` @ `{payload['judge_endpoint']}`")
    lines.append(f"Embedding: `{payload['embedding_model']}` @ `{payload['embedding_endpoint']}`")
    lines.append(f"n summary questions = **{payload['n_total']}**")
    lines.append(
        f"scored = **{payload['n_scored']}** | agent_errors = {payload['n_agent_errors']} | "
        f"judge_errors = {payload['n_judge_errors']}"
    )
    lines.append("")
    lines.append("## Rubric")
    lines.append("")
    lines.append("```")
    lines.append(RUBRIC.strip())
    lines.append("```")
    lines.append("")
    lines.append("## Headline metrics")
    lines.append("")
    lines.append(f"- Layered mean score = **{payload['layered_mean']:.3f}**")
    lines.append(f"- Flat mean score = **{payload['flat_mean']:.3f}**")
    lines.append(
        f"- Delta (layered − flat) = **{payload['delta']:.3f}**"
    )
    lines.append(
        f"- Layered win / tie / loss = "
        f"**{payload['n_layered_win']}** / **{payload['n_tie']}** / "
        f"**{payload['n_flat_win']}** "
        f"(rates: {payload['layered_win_rate']:.1%} / "
        f"{payload['tie_rate']:.1%} / {payload['flat_win_rate']:.1%})"
    )
    lines.append("")
    lines.append("## Score distribution")
    lines.append("")
    lines.append("| score | layered n | flat n |")
    lines.append("|-------|-----------|--------|")
    dist_l = payload.get("layered_score_dist") or {}
    dist_f = payload.get("flat_score_dist") or {}
    for s in range(1, 6):
        lines.append(
            f"| {s} | {dist_l.get(str(s), 0)} | {dist_f.get(str(s), 0)} |"
        )
    lines.append("")
    lines.append("## Per-question results")
    lines.append("")
    lines.append(
        "| id | video_id | lacks_L2/L3 | L score | F score | winner | "
        "L tools | F tools | lookup | summarize |"
    )
    lines.append(
        "|----|----------|-------------|---------|---------|--------|"
        "---------|---------|--------|-----------|"
    )
    for row in payload.get("per_question") or []:
        ls = row.get("layered_score")
        fs = row.get("flat_score")
        ls_s = str(ls) if ls is not None else "—"
        fs_s = str(fs) if fs is not None else "—"
        win = row.get("winner") or ("judge_err" if row.get("judge_error") else "—")
        l_tools = ", ".join(row.get("layered_tools_unique") or []) or "—"
        f_tools = ", ".join(row.get("flat_tools_unique") or []) or "—"
        if len(l_tools) > 36:
            l_tools = l_tools[:33] + "..."
        if len(f_tools) > 36:
            f_tools = f_tools[:33] + "..."
        lines.append(
            f"| {row.get('id')} | {row.get('video_id')} | "
            f"{'Y' if row.get('lacks_l2_l3') else ''} | "
            f"{ls_s} | {fs_s} | `{win}` | {l_tools} | {f_tools} | "
            f"{'Y' if row.get('layered_called_lookup') else ''} | "
            f"{'Y' if row.get('layered_called_summarize') else ''} |"
        )
    lines.append("")
    lines.append("## Sample Q&A pairs")
    lines.append("")
    samples = payload.get("samples") or []
    if not samples:
        lines.append("（无）")
    else:
        for i, s in enumerate(samples, 1):
            lines.append(f"### Sample {i}: {s.get('id')}")
            lines.append("")
            lines.append(f"**Q:** {s.get('question')}")
            lines.append("")
            lines.append(f"**Notes:** {s.get('notes') or '—'}")
            lines.append("")
            lines.append(
                f"**Scores:** Layered={s.get('layered_score')} | "
                f"Flat={s.get('flat_score')} | winner=`{s.get('winner')}`"
            )
            if s.get("brief_reason"):
                lines.append(f"**Judge:** {s.get('brief_reason')}")
            lines.append("")
            lines.append("**Layered answer:**")
            lines.append("")
            lines.append(s.get("layered_answer") or "(empty)")
            lines.append("")
            lines.append("**Flat answer:**")
            lines.append("")
            lines.append(s.get("flat_answer") or "(empty)")
            lines.append("")
    lines.append("## Docs lacking L2/L3")
    lines.append("")
    lines.append(
        "Known video_ids without reliable L2/L3 in this corpus: "
        + ", ".join(f"`{v}`" for v in sorted(DOCS_LACKING_L2_L3))
    )
    n_lack = payload.get("n_lacking_l2_l3", 0)
    lines.append(f"- Questions tagged lacks_l2_l3: **{n_lack}**")
    lines.append(
        "- Layered may still call lookup/summarize; summarize may generate on the fly "
        "or return thin content. Flat must synthesize from search chunks only."
    )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    for note in payload.get("notes") or []:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


async def run_one_agent(agent, question: str, deps: ChatDeps) -> tuple[str, list[str], str | None]:
    """Run agent; return (answer_text, tools, error)."""
    try:
        result = await agent.run(question, deps=deps)
        answer = str(getattr(result, "output", "") or "")
        tools = extract_tool_names(result)
        return answer, tools, None
    except Exception as exc:
        traceback.print_exc()
        return "", [], f"{type(exc).__name__}: {exc}"


async def timed_run(
    agent, question: str, deps: ChatDeps
) -> tuple[str, list[str], str | None, float]:
    """Run agent with wall latency; return (answer, tools, error, latency_ms)."""
    t0 = time.perf_counter()
    answer, tools, err = await run_one_agent(agent, question, deps)
    ms = (time.perf_counter() - t0) * 1000.0
    return answer, tools, err, ms


async def main_async(
    limit: int | None = None,
    smoke_only: bool = False,
    concurrency: int = 5,
) -> int:
    settings = get_settings()
    data_dir = Path(settings.storage.data_dir).expanduser()
    questions, n_skipped_ineligible = load_summary_questions(EVAL_SET)
    if n_skipped_ineligible:
        print(
            f"NOTE: skipped {n_skipped_ineligible} summary question(s) with "
            f"summary_eligible=false (not entered into scoring pool per EVAL_SPEC §8)"
        )
    if not questions:
        print("ERROR: no eligible summary questions in", EVAL_SET)
        return 1
    if limit is not None:
        questions = questions[:limit]
        print(f"limit={limit}, using first {len(questions)} summary questions")
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
    print(f"summary questions n={len(questions)}")

    sqlite = SQLiteClient(data_dir / "metadata.db")
    await sqlite.connect()
    qdrant = QdrantStore(data_dir / "qdrant")
    qdrant.connect(vector_size=settings.rag.vector_size)

    notes: list[str] = []
    try:
        point_count = len(qdrant.scroll_all_points())
        print(f"Qdrant open ok, points={point_count}")

        embedding_client = build_embedding_client(settings)
        smoke_vec = embedding_client.embed(["architecture_ab smoke"])
        smoke_dim = len(smoke_vec[0]) if smoke_vec and smoke_vec[0] else 0
        print(f"smoke embed ok, dim={smoke_dim}")

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
        layered_prompt = build_system_prompt(memories=memories)
        chat_model = build_chat_model(settings)
        layered_agent = build_agent(chat_model, system_prompt=layered_prompt)
        # Separate model instance for flat to avoid shared tool registration issues
        flat_model = build_chat_model(settings)
        flat_agent = build_flat_agent(flat_model, system_prompt=FLAT_SYSTEM_PROMPT)

        judge = build_chat_completion_client(settings)
        print(f"judge={chat_model_name} @ {chat_endpoint}")

        # Smoke: one layered + one flat call
        print("smoke layered agent.run ...")
        t0 = time.perf_counter()
        smoke_l = await layered_agent.run("一句话介绍你自己", deps=deps)
        print(
            f"smoke layered ok latency={(time.perf_counter() - t0) * 1000:.0f}ms "
            f"tools={extract_tool_names(smoke_l)}"
        )
        print("smoke flat agent.run ...")
        t0 = time.perf_counter()
        smoke_f = await flat_agent.run("一句话介绍你自己", deps=deps)
        print(
            f"smoke flat ok latency={(time.perf_counter() - t0) * 1000:.0f}ms "
            f"tools={extract_tool_names(smoke_f)}"
        )
        if smoke_only:
            print("smoke_only=True, exiting after smoke")
            return 0

        notes.append(
            "Blind LLM-as-judge: answers randomized as A/B; scores mapped back to layered/flat."
        )
        notes.append(
            "Flat agent has only search_knowledge; Layered has search + lookup + summarize + propose_memory."
        )
        notes.append(
            f"Summary eligibility: scored {len(questions)} eligible, "
            f"skipped {n_skipped_ineligible} ineligible (summary_eligible=false)."
        )
        notes.append(
            f"Docs lacking L2/L3 tags: {sorted(DOCS_LACKING_L2_L3)}"
        )
        notes.append(
            "Judge.complete called via asyncio.to_thread to avoid nested event loop."
        )
        notes.append(
            f"Bounded concurrency={concurrency} across questions via asyncio.Semaphore; "
            "within each question layered+flat run concurrently then judge sequential. "
            "No store lock — concurrent Qdrant/SQLite reads may race and reduce "
            "effective concurrency if the store is not concurrent-safe."
        )

        n_total = len(questions)
        sem = asyncio.Semaphore(concurrency)
        progress_lock = asyncio.Lock()
        done_count = 0
        n_agent_errors_running = 0
        n_judge_errors_running = 0

        async def run_question(i: int, q: dict[str, Any]) -> dict[str, Any]:
            nonlocal done_count, n_agent_errors_running, n_judge_errors_running
            qid = q["id"]
            question = q["question"]
            video_id = q.get("video_id") or ""
            notes_field = q.get("notes") or ""
            lacks = video_id in DOCS_LACKING_L2_L3

            async with sem:
                print(f"\n=== {qid} video={video_id} lacks_l2_l3={lacks} ===")
                print(f"Q: {question[:80]}")

                (
                    (layered_answer, layered_tools, layered_err, layered_ms),
                    (flat_answer, flat_tools, flat_err, flat_ms),
                ) = await asyncio.gather(
                    timed_run(layered_agent, question, deps),
                    timed_run(flat_agent, question, deps),
                )

                print(
                    f"  layered tools={tools_unique(layered_tools)} "
                    f"ans_len={len(layered_answer)} ms={layered_ms:.0f}"
                    + (f" err={layered_err[:80]}" if layered_err else "")
                )
                print(
                    f"  flat    tools={tools_unique(flat_tools)} "
                    f"ans_len={len(flat_answer)} ms={flat_ms:.0f}"
                    + (f" err={flat_err[:80]}" if flat_err else "")
                )

                # Judge sequential after both agents finish
                judge_result = await judge_pair(
                    judge,
                    question=question,
                    notes=notes_field,
                    layered_answer=layered_answer,
                    flat_answer=flat_answer,
                )

            agent_err_count = (1 if layered_err else 0) + (1 if flat_err else 0)
            has_judge_err = bool(judge_result.get("judge_error"))
            if has_judge_err:
                print(f"  judge ERROR: {judge_result['judge_error']}")
            else:
                ls = judge_result["layered_score"]
                fs = judge_result["flat_score"]
                win = judge_result["winner"]
                print(
                    f"  judge L={ls} F={fs} winner={win} "
                    f"reason={judge_result.get('brief_reason') or ''}"
                )

            row = {
                "index": i,
                "id": qid,
                "video_id": video_id,
                "document_id": q.get("document_id"),
                "question": question,
                "notes": notes_field,
                "lacks_l2_l3": lacks,
                "layered_answer": layered_answer,
                "flat_answer": flat_answer,
                "layered_tools": layered_tools,
                "flat_tools": flat_tools,
                "layered_tools_unique": tools_unique(layered_tools),
                "flat_tools_unique": tools_unique(flat_tools),
                "layered_called_lookup": "lookup_documents" in layered_tools,
                "layered_called_summarize": "summarize_document" in layered_tools,
                "layered_latency_ms": round(layered_ms, 1),
                "flat_latency_ms": round(flat_ms, 1),
                "layered_error": layered_err,
                "flat_error": flat_err,
                "layered_score": judge_result.get("layered_score"),
                "flat_score": judge_result.get("flat_score"),
                "winner": judge_result.get("winner"),
                "brief_reason": judge_result.get("brief_reason"),
                "judge_error": judge_result.get("judge_error"),
                "assignment": judge_result.get("assignment"),
            }

            async with progress_lock:
                done_count += 1
                n_agent_errors_running += agent_err_count
                if has_judge_err:
                    n_judge_errors_running += 1
                print(
                    f"  progress {done_count}/{n_total} "
                    f"agent_errors={n_agent_errors_running} "
                    f"judge_errors={n_judge_errors_running}"
                )
            return row

        wall_t0 = time.perf_counter()
        raw_results = await asyncio.gather(
            *[run_question(i, q) for i, q in enumerate(questions)],
            return_exceptions=True,
        )
        wall_time_s = time.perf_counter() - wall_t0

        # Aggregate in original question order
        ordered_rows: list[dict[str, Any]] = []
        for i, res in enumerate(raw_results):
            q = questions[i]
            if isinstance(res, Exception):
                qid = q["id"]
                question = q["question"]
                video_id = q.get("video_id") or ""
                notes_field = q.get("notes") or ""
                lacks = video_id in DOCS_LACKING_L2_L3
                err = f"{type(res).__name__}: {res}"
                print(f"  GATHER exception for {qid}: {err}")
                traceback.print_exception(type(res), res, res.__traceback__)
                ordered_rows.append(
                    {
                        "index": i,
                        "id": qid,
                        "video_id": video_id,
                        "document_id": q.get("document_id"),
                        "question": question,
                        "notes": notes_field,
                        "lacks_l2_l3": lacks,
                        "layered_answer": "",
                        "flat_answer": "",
                        "layered_tools": [],
                        "flat_tools": [],
                        "layered_tools_unique": [],
                        "flat_tools_unique": [],
                        "layered_called_lookup": False,
                        "layered_called_summarize": False,
                        "layered_latency_ms": None,
                        "flat_latency_ms": None,
                        "layered_error": err,
                        "flat_error": err,
                        "layered_score": None,
                        "flat_score": None,
                        "winner": None,
                        "brief_reason": None,
                        "judge_error": err,
                        "assignment": None,
                    }
                )
            else:
                ordered_rows.append(res)

        ordered_rows.sort(key=lambda r: r.get("index", 0))

        per_question: list[dict[str, Any]] = []
        n_agent_errors = 0
        n_judge_errors = 0
        n_layered_win = 0
        n_flat_win = 0
        n_tie = 0
        layered_scores: list[int] = []
        flat_scores: list[int] = []
        layered_dist: dict[str, int] = {str(i): 0 for i in range(1, 6)}
        flat_dist: dict[str, int] = {str(i): 0 for i in range(1, 6)}
        n_lacking = 0

        for row in ordered_rows:
            if row.get("lacks_l2_l3"):
                n_lacking += 1
            if row.get("layered_error"):
                n_agent_errors += 1
            if row.get("flat_error"):
                n_agent_errors += 1
            if row.get("judge_error"):
                n_judge_errors += 1
            else:
                ls = row.get("layered_score")
                fs = row.get("flat_score")
                win = row.get("winner")
                if ls is not None:
                    layered_scores.append(ls)
                    layered_dist[str(ls)] = layered_dist.get(str(ls), 0) + 1
                if fs is not None:
                    flat_scores.append(fs)
                    flat_dist[str(fs)] = flat_dist.get(str(fs), 0) + 1
                if win == "layered":
                    n_layered_win += 1
                elif win == "flat":
                    n_flat_win += 1
                elif win == "tie":
                    n_tie += 1

            # Drop internal index from payload rows
            out_row = {k: v for k, v in row.items() if k != "index"}
            per_question.append(out_row)

        n_scored = len(layered_scores)
        layered_mean = (
            sum(layered_scores) / len(layered_scores) if layered_scores else 0.0
        )
        flat_mean = sum(flat_scores) / len(flat_scores) if flat_scores else 0.0
        delta = layered_mean - flat_mean
        denom = n_layered_win + n_flat_win + n_tie
        layered_win_rate = (n_layered_win / denom) if denom else 0.0
        flat_win_rate = (n_flat_win / denom) if denom else 0.0
        tie_rate = (n_tie / denom) if denom else 0.0

        # Pick 2–3 interesting samples for MD (prefer non-tie or lacking L2)
        candidates = [
            r
            for r in per_question
            if r.get("layered_score") is not None and r.get("flat_score") is not None
        ]
        samples: list[dict[str, Any]] = []
        # prefer wins for layered, then flat, then any with lacks_l2
        preferred = sorted(
            candidates,
            key=lambda r: (
                0 if r.get("winner") == "layered" else 1 if r.get("winner") == "flat" else 2,
                0 if r.get("lacks_l2_l3") else 1,
            ),
        )
        for r in preferred[:3]:
            samples.append(
                {
                    "id": r["id"],
                    "question": r["question"],
                    "notes": r.get("notes"),
                    "layered_score": r.get("layered_score"),
                    "flat_score": r.get("flat_score"),
                    "winner": r.get("winner"),
                    "brief_reason": r.get("brief_reason"),
                    "layered_answer": r.get("layered_answer"),
                    "flat_answer": r.get("flat_answer"),
                }
            )

        notes.append(f"wall_time_s={wall_time_s:.2f}, concurrency={concurrency}")

        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "chat_model": chat_model_name,
            "chat_endpoint": chat_endpoint,
            "judge_model": chat_model_name,
            "judge_endpoint": chat_endpoint,
            "embedding_model": emb_model,
            "embedding_endpoint": emb_endpoint,
            "n_total": n_total,
            "n_scored": n_scored,
            "n_agent_errors": n_agent_errors,
            "n_judge_errors": n_judge_errors,
            "n_lacking_l2_l3": n_lacking,
            "layered_mean": layered_mean,
            "flat_mean": flat_mean,
            "delta": delta,
            "n_layered_win": n_layered_win,
            "n_flat_win": n_flat_win,
            "n_tie": n_tie,
            "layered_win_rate": layered_win_rate,
            "flat_win_rate": flat_win_rate,
            "tie_rate": tie_rate,
            "layered_score_dist": layered_dist,
            "flat_score_dist": flat_dist,
            "docs_lacking_l2_l3": sorted(DOCS_LACKING_L2_L3),
            "rubric": RUBRIC,
            "per_question": per_question,
            "samples": samples,
            "notes": notes,
            "qdrant_point_count": point_count,
            "smoke_embed_dim": smoke_dim,
            "wall_time_s": round(wall_time_s, 3),
            "concurrency": concurrency,
        }

        OUT_MD.parent.mkdir(parents=True, exist_ok=True)
        OUT_MD.write_text(write_md(payload), encoding="utf-8")
        OUT_JSON.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\nwrote {OUT_MD}")
        print(f"wrote {OUT_JSON}")
        print(
            f"HEADLINE layered_mean={layered_mean:.3f} flat_mean={flat_mean:.3f} "
            f"delta={delta:+.3f} win/tie/loss={n_layered_win}/{n_tie}/{n_flat_win} "
            f"wall_time_s={wall_time_s:.2f} concurrency={concurrency}"
        )
        return 0
    finally:
        qdrant.close()
        await sqlite.close()
        print("Qdrant + SQLite closed")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 2: Layered vs Flat architecture A/B (summary completeness)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only run first N summary questions (debug)",
    )
    parser.add_argument(
        "--smoke-only",
        action="store_true",
        help="Only open deps and run smoke agent calls",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Max concurrent questions (default: 5); layered+flat still concurrent within each",
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
