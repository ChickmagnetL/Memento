"""Build benchmarks/eval_set.jsonl from indexed documents via chat + embedding.

Per document: 3-5 Q&A (detail + summary). Across whole set: 3-5 self/memory.
Maps relevant_chunks via embedding cosine similarity (detail) or empty (summary/self).
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "backend"))
import bench_env  # noqa: F401

from config.settings import get_settings  # noqa: E402
from core.models.chat_completion import ChatCompletionError  # noqa: E402, F401
from core.models.factory import (  # noqa: E402
    build_chat_completion_client,
    build_embedding_client,
)


def chat_complete_retry(chat, messages, retries=3):
    last = None
    for i in range(retries):
        try:
            return chat.complete(messages)
        except Exception as e:
            last = e
            wait = [2, 5, 10][min(i, 2)]
            print(f"  chat error try {i+1}/{retries}: {type(e).__name__}: {e}; sleep {wait}s")
            time.sleep(wait)
    raise last

BASE_URL = "http://127.0.0.1:8010"
OUT_JSONL = ROOT / "benchmarks" / "eval_set.jsonl"
DATASET_MD = ROOT / "benchmarks" / "results" / "00_dataset.md"
SELF_TARGET = 4  # total self questions across whole set (3-5)
PER_DOC_MIN = 3
PER_DOC_MAX = 5
COSINE_TOP_K = 3
COSINE_MIN = 0.25


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def load_indexed_docs() -> list[dict]:
    settings = get_settings()
    db_path = Path(settings.storage.data_dir).expanduser() / "metadata.db"
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT id, video_id, file_path, chunk_count, status, summary, brief "
                "FROM documents WHERE status='indexed' AND chunk_count > 0"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    with httpx.Client(timeout=30.0) as client:
        docs = client.get(f"{BASE_URL}/api/documents").json()
    if not isinstance(docs, list):
        return []
    return [
        d
        for d in docs
        if (d.get("status") or "").lower() == "indexed"
        and int(d.get("chunk_count") or 0) > 0
    ]


def read_markdown(doc: dict) -> str:
    fp = doc.get("file_path") or ""
    if fp:
        p = Path(fp)
        if not p.is_absolute():
            settings = get_settings()
            data_dir = Path(settings.storage.data_dir).expanduser()
            p = data_dir / fp
        if p.exists():
            text = p.read_text(encoding="utf-8", errors="replace")
            # Cap context for chat prompt
            if len(text) > 24000:
                return text[:24000] + "\n\n...[truncated]..."
            return text
    # fallback: stitch chunks
    chunks = fetch_chunks(doc["id"])
    joined = "\n\n".join(c.get("text") or "" for c in chunks)
    if len(joined) > 24000:
        return joined[:24000] + "\n\n...[truncated]..."
    return joined


def fetch_chunks(document_id: str) -> list[dict]:
    with httpx.Client(timeout=60.0) as client:
        r = client.get(f"{BASE_URL}/api/documents/{document_id}/chunks")
        if r.status_code >= 400:
            print(f"  chunks HTTP {r.status_code} for {document_id}")
            return []
        data = r.json()
    return data if isinstance(data, list) else []


def extract_json_array(text: str) -> list | None:
    text = (text or "").strip()
    if not text:
        return None
    # strip markdown fences
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data["items"]
        if isinstance(data, dict) and isinstance(data.get("questions"), list):
            return data["questions"]
    except json.JSONDecodeError:
        pass
    # try first [...] slice
    start, end = text.find("["), text.rfind("]")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            return None
    return None


def generate_qa_for_doc(chat, doc: dict, md: str) -> list[dict]:
    """Ask chat model for 3-5 Q&A items (detail + summary)."""
    title = Path(doc.get("file_path") or "").stem or doc.get("id")
    system = (
        "You generate evaluation questions for a RAG benchmark. "
        "Return ONLY a JSON array. Each item: "
        '{"question":"...","type":"detail"|"summary","answer_hint":"short phrase from the text"}. '
        f"Produce {PER_DOC_MIN}-{PER_DOC_MAX} items: mostly detail (specific facts), "
        "1-2 summary (whole-video overview). Language: match the document (Chinese if Chinese). "
        "Detail questions must be answerable from a specific passage. No self/memory questions."
    )
    user = (
        f"Document id={doc.get('id')} video_id={doc.get('video_id')} title={title}\n\n"
        f"--- DOCUMENT START ---\n{md}\n--- DOCUMENT END ---\n\n"
        "Return JSON array only."
    )
    raw = chat_complete_retry(
        chat,
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    items = extract_json_array(raw)
    if items is None:
        print("  non-JSON response; retrying once")
        raw2 = chat_complete_retry(
            chat,
            [
                {
                    "role": "system",
                    "content": "Fix the previous output into a valid JSON array only. No prose.",
                },
                {
                    "role": "user",
                    "content": f"Previous output:\n{raw[:4000]}\n\nReturn JSON array only.",
                },
            ],
        )
        items = extract_json_array(raw2)
    if not items:
        return []

    cleaned = []
    for it in items:
        if not isinstance(it, dict):
            continue
        q = (it.get("question") or "").strip()
        t = (it.get("type") or "detail").strip().lower()
        if t not in ("detail", "summary"):
            t = "detail"
        if not q:
            continue
        cleaned.append(
            {
                "question": q,
                "type": t,
                "answer_hint": (it.get("answer_hint") or "").strip(),
            }
        )
    return cleaned[:PER_DOC_MAX]


def generate_self_questions(chat, docs: list[dict]) -> list[dict]:
    titles = []
    for d in docs[:12]:
        titles.append(
            f"- video_id={d.get('video_id')} path={d.get('file_path')} "
            f"brief={(d.get('brief') or '')[:80]}"
        )
    system = (
        "Generate self/memory style evaluation questions for a personal knowledge base. "
        f"Return ONLY a JSON array of {SELF_TARGET} objects: "
        '{"question":"...","type":"self"}. '
        "Questions should be about the user's learning interests based on watched videos "
        '(e.g. "我最近在学什么？", "根据我看过的视频，我的学习兴趣是什么？"). Chinese OK.'
    )
    user = "User has watched / indexed these videos:\n" + "\n".join(titles)
    raw = chat_complete_retry(
        chat,
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    items = extract_json_array(raw)
    if items is None:
        raw2 = chat_complete_retry(
            chat,
            [
                {
                    "role": "system",
                    "content": "Return a valid JSON array only with type=self questions.",
                },
                {"role": "user", "content": f"Previous:\n{raw[:3000]}"},
            ],
        )
        items = extract_json_array(raw2) or []
    out = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        q = (it.get("question") or "").strip()
        if q:
            out.append({"question": q, "type": "self"})
    if not out:
        # minimal fallback if model fails
        out = [
            {"question": "我最近在学什么？", "type": "self"},
            {"question": "根据我看过的视频，我的学习兴趣是什么？", "type": "self"},
            {"question": "我知识库里有哪些主题？", "type": "self"},
            {"question": "总结一下我最近观看的内容方向。", "type": "self"},
        ]
    return out[:SELF_TARGET]


def map_relevant_chunks(
    emb,
    question: str,
    answer_hint: str,
    document_id: str,
    chunks: list[dict],
    qtype: str,
) -> list[dict]:
    if qtype in ("summary", "self") or not chunks:
        return []

    texts = [(c.get("text") or "") for c in chunks]
    # substring boost: if answer_hint appears, prefer those chunks
    substring_hits = []
    hint = (answer_hint or "").strip()
    if hint and len(hint) >= 4:
        for c in chunks:
            t = c.get("text") or ""
            if hint in t:
                substring_hits.append(
                    {
                        "document_id": document_id,
                        "chunk_index": int(c.get("chunk_index") or 0),
                    }
                )
        if substring_hits:
            return substring_hits[:COSINE_TOP_K]

    try:
        # batch embed question + chunks; chunk if too many
        batch_size = 32
        q_vec = emb.embed([question])[0]
        scored: list[tuple[float, dict]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            vecs = emb.embed(batch)
            for j, v in enumerate(vecs):
                c = chunks[i + j]
                score = cosine(q_vec, v)
                scored.append(
                    (
                        score,
                        {
                            "document_id": document_id,
                            "chunk_index": int(c.get("chunk_index") or 0),
                        },
                    )
                )
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = [item for s, item in scored if s >= COSINE_MIN][:COSINE_TOP_K]
        if not selected and scored:
            selected = [scored[0][1]]
        return selected
    except Exception as exc:  # noqa: BLE001
        print(f"  embed mapping failed: {exc}")
        return []


def expected_route(qtype: str) -> str:
    if qtype == "detail":
        return "search"
    if qtype == "summary":
        return "lookup+summarize"
    return "memory"


def append_dataset_summary(items: list[dict], docs: list[dict]) -> None:
    from collections import Counter

    dist = Counter(it.get("type") for it in items)
    routes = Counter(it.get("expected_route") for it in items)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "",
        "## 知识库与评测集摘要",
        "",
        f"更新时间: {now}",
        f"- 已索引文档数: {len(docs)}",
        f"- 评测问题总数: {len(items)}",
        f"- 类型分布: detail={dist.get('detail', 0)}, summary={dist.get('summary', 0)}, "
        f"self={dist.get('self', 0)}",
        f"- 期望路由: search={routes.get('search', 0)}, "
        f"lookup+summarize={routes.get('lookup+summarize', 0)}, "
        f"memory={routes.get('memory', 0)}",
        f"- 输出文件: `benchmarks/eval_set.jsonl`",
        "",
    ]
    DATASET_MD.parent.mkdir(parents=True, exist_ok=True)
    if DATASET_MD.exists():
        prev = DATASET_MD.read_text(encoding="utf-8")
        # replace previous summary section if present
        marker = "## 知识库与评测集摘要"
        if marker in prev:
            prev = prev.split(marker)[0].rstrip() + "\n"
        DATASET_MD.write_text(prev + "\n".join(lines), encoding="utf-8")
    else:
        DATASET_MD.write_text(
            "# 00 数据集灌库报告\n\n(尚未运行 ingest)\n" + "\n".join(lines),
            encoding="utf-8",
        )
    print(f"Updated {DATASET_MD}")


def main() -> int:
    docs = load_indexed_docs()
    print(f"indexed documents: {len(docs)}")
    if not docs:
        print("No indexed documents; nothing to build.")
        OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSONL.write_text("", encoding="utf-8")
        append_dataset_summary([], docs)
        return 1

    chat = build_chat_completion_client()
    emb = build_embedding_client()

    # Resume: load existing records if any
    records: list[dict] = []
    done_doc_ids: set[str] = set()
    self_count = 0
    qid = 0
    if OUT_JSONL.exists():
        for line in OUT_JSONL.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            records.append(rec)
            rid = rec.get("id") or ""
            m = re.match(r"q(\d+)", str(rid))
            if m:
                qid = max(qid, int(m.group(1)))
            if rec.get("type") == "self":
                self_count += 1
            elif rec.get("document_id"):
                # at least one non-self question for this doc
                done_doc_ids.add(rec["document_id"])
        print(
            f"resume: loaded {len(records)} existing records; "
            f"{len(done_doc_ids)} docs done; self={self_count}; next qid={qid + 1}"
        )

    for doc in docs:
        did = doc["id"]
        if did in done_doc_ids:
            print(f"\n=== document {did} video={doc.get('video_id')} === SKIP (already in eval_set)")
            continue
        print(f"\n=== document {did} video={doc.get('video_id')} ===")
        try:
            md = read_markdown(doc)
            if not md.strip():
                print("  empty markdown; skip")
                continue
            chunks = fetch_chunks(did)
            print(f"  md_chars={len(md)} chunks={len(chunks)}")
            qa_items = generate_qa_for_doc(chat, doc, md)
            print(f"  generated {len(qa_items)} questions")
            for it in qa_items:
                qid += 1
                qtype = it["type"]
                relevant = map_relevant_chunks(
                    emb,
                    it["question"],
                    it.get("answer_hint") or "",
                    did,
                    chunks,
                    qtype,
                )
                records.append(
                    {
                        "id": f"q{qid:03d}",
                        "video_id": doc.get("video_id"),
                        "document_id": did,
                        "question": it["question"],
                        "type": qtype,
                        "expected_route": expected_route(qtype),
                        "relevant_chunks": relevant,
                        "notes": it.get("answer_hint") or "",
                    }
                )
            done_doc_ids.add(did)
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED after retries: {type(exc).__name__}: {exc}; continue next doc")
            continue

    if self_count < SELF_TARGET:
        print(f"\n=== self/memory questions (have {self_count}, target {SELF_TARGET}) ===")
        try:
            self_items = generate_self_questions(chat, docs)
            # only add enough to reach SELF_TARGET
            need = SELF_TARGET - self_count
            for it in self_items[:need]:
                qid += 1
                self_count += 1
                records.append(
                    {
                        "id": f"q{qid:03d}",
                        "video_id": None,
                        "document_id": None,
                        "question": it["question"],
                        "type": "self",
                        "expected_route": "memory",
                        "relevant_chunks": [],
                        "notes": "self/memory across whole KB",
                    }
                )
        except Exception as exc:  # noqa: BLE001
            print(f"  self questions FAILED: {type(exc).__name__}: {exc}")
    else:
        print(f"\n=== self/memory questions SKIP (already have {self_count}) ===")

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"\nWrote {OUT_JSONL} ({len(records)} questions)")
    append_dataset_summary(records, docs)

    from collections import Counter

    dist = Counter(r["type"] for r in records)
    print(f"type dist: {dict(dist)}")
    if len(records) < 40:
        print(
            f"WARN: only {len(records)} questions (target 40-60). "
            "Need more indexed docs or raise per-doc count."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
