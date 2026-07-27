"""One-off: export per-video question-writing manifests for the RAG benchmark corpus.

Reads bench_data/metadata.db (sqlite) and bench_data/qdrant (embedded, read-only
usage) and writes one markdown file per video plus an _index.md into
benchmarks/eval_build/corpus_manifest/.

Run: /Users/leo/development/memento/backend/venv/bin/python export_manifest.py
"""

from __future__ import annotations

import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "bench_data" / "metadata.db"
QDRANT_PATH = ROOT / "bench_data" / "qdrant"
OUT_DIR = Path(__file__).resolve().parent / "corpus_manifest"

CJK_RE = re.compile(r"[一-鿿]")
CJK_RUN_RE = re.compile(r"[一-鿿]{2,}")
LATIN_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]{2,}")

EN_STOPWORDS = {
    "the", "and", "for", "you", "your", "that", "this", "with", "are", "was",
    "were", "have", "has", "had", "not", "but", "can", "will", "what", "how",
    "why", "when", "where", "who", "all", "one", "two", "from", "they", "them",
    "there", "here", "just", "like", "get", "got", "going", "want", "really",
    "about", "out", "into", "then", "than", "more", "some", "very", "also",
    "its", "his", "her", "our", "their", "these", "those", "which", "been",
    "does", "did", "doing", "because", "right", "know", "think", "thing",
    "things", "make", "made", "way", "now", "actually", "video", "transcript",
    "youtube", "com", "www", "https", "http",
}

ZH_STOP_BIGRAMS = {
    "我们", "你们", "他们", "这个", "那个", "一个", "什么", "怎么", "为什",
    "所以", "因为", "但是", "然后", "就是", "还是", "如果", "可以", "没有",
    "不是", "这样", "那样", "的话", "时候", "现在", "非常", "其实", "觉得",
    "视频", "大家", "一下", "这些", "那些", "以及", "或者", "通过", "进行",
    "作者", "内容", "本期", "讲解", "介绍", "分享", "本视",
}


def strip_title_prefix(text: str, title_path: str | None) -> str:
    """Chunk text is stored as '<title_path>\n\n<body>'. Return the body."""
    if title_path and text.startswith(title_path):
        return text[len(title_path):].lstrip("\n ")
    # Fallback: drop first line if it looks like a heading path
    if "\n" in text and " > " in text.split("\n", 1)[0]:
        return text.split("\n", 1)[1].lstrip("\n ")
    return text


def language_guess(text: str) -> str:
    cjk = len(CJK_RE.findall(text))
    latin = len(re.findall(r"[A-Za-z]", text))
    total = cjk + latin
    if total == 0:
        return "en"
    ratio = cjk / total
    if ratio > 0.6:
        return "zh"
    if ratio < 0.05:
        return "en"
    return "mixed"


def extract_keywords(text: str, top_n: int = 30) -> set[str]:
    """Cheap topic keywords: CJK bigrams from runs + latin words, stopword-filtered."""
    kws: Counter[str] = Counter()
    for run in CJK_RUN_RE.findall(text):
        for i in range(len(run) - 1):
            bg = run[i : i + 2]
            if bg not in ZH_STOP_BIGRAMS:
                kws[bg] += 1
    for w in LATIN_WORD_RE.findall(text):
        lw = w.lower()
        if lw not in EN_STOPWORDS:
            kws[lw] += 1
    return {k for k, _ in kws.most_common(top_n)}


def keyword_hits(keywords: set[str], text: str) -> int:
    low = text.lower()
    return sum(1 for k in keywords if k in low)


# Phrases indicating a chunk/section-level summary was stored as the whole-video L2.
SECTION_PHRASES = [
    "this document section",
    "this section covers",
    "this section focuses",
    "document section covers",
    "本节内容",
    "该章节",
    "这一部分主要",
    "本部分内容",
]


def latin_tokens(text: str) -> set[str]:
    return {
        w.lower()
        for w in LATIN_WORD_RE.findall(text)
        if w.lower() not in EN_STOPWORDS
    }


def main() -> int:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    docs = [
        dict(r)
        for r in conn.execute(
            "SELECT d.id AS document_id, d.video_id, d.title AS doc_title, "
            "d.author, d.summary, d.brief, d.chunk_count, "
            "v.platform, v.title AS video_title, v.duration, v.url "
            "FROM documents d LEFT JOIN videos v ON d.video_id = v.id "
            "ORDER BY d.video_id"
        )
    ]
    conn.close()

    from qdrant_client import QdrantClient

    client = QdrantClient(path=str(QDRANT_PATH))
    chunks_by_doc: dict[str, list[dict]] = defaultdict(list)
    offset = None
    n_points = 0
    while True:
        points, offset = client.scroll(
            collection_name="documents",
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for p in points:
            pl = dict(p.payload or {})
            did = pl.get("document_id")
            if did:
                chunks_by_doc[did].append(pl)
                n_points += 1
        if offset is None:
            break
    client.close()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    index_rows = []
    n_l2 = n_l3 = n_suspect = 0
    n_chunks_total = 0
    lang_dist: Counter[str] = Counter()
    errors: list[str] = []

    for d in docs:
        did = d["document_id"]
        vid = d["video_id"] or did
        title = d["video_title"] or d["doc_title"] or "(untitled)"
        summary = (d["summary"] or "").strip()
        brief = (d["brief"] or "").strip()
        chunks = sorted(chunks_by_doc.get(did, []), key=lambda c: c.get("chunk_index", 0))
        n_chunks_total += len(chunks)
        if len(chunks) != (d["chunk_count"] or 0):
            errors.append(
                f"{vid}: qdrant chunks={len(chunks)} != sqlite chunk_count={d['chunk_count']}"
            )

        bodies = [
            strip_title_prefix(c.get("text") or "", c.get("title_path")) for c in chunks
        ]
        full_body = "\n".join(bodies)
        lang = language_guess(full_body if full_body.strip() else title)
        lang_dist[lang] += 1

        # --- L2/L3 topic-consistency heuristic ---
        title_kws = extract_keywords(title, top_n=15)
        body_kws = extract_keywords(full_body, top_n=30)
        signal_kws = title_kws | body_kws
        suspect = False
        reason = ""
        if not summary:
            suspect = True
            reason = "L2 summary missing"
        else:
            low_sum = summary.lower()
            hit_phrase = next((p for p in SECTION_PHRASES if p in low_sum), None)
            if hit_phrase:
                suspect = True
                reason = (
                    f"L2 reads as a section-level summary, not whole-video "
                    f"(phrase: '{hit_phrase}')"
                )
            else:
                t_hits = keyword_hits(title_kws, summary)
                b_hits = keyword_hits(body_kws, summary)
                if t_hits == 0 and b_hits <= 2:
                    sum_lang = language_guess(summary)
                    if sum_lang != lang:
                        shared = latin_tokens(summary) & latin_tokens(full_body)
                        if len(shared) < 3:
                            suspect = True
                            reason = (
                                f"cross-language L2 ({lang} content, {sum_lang} "
                                f"summary); keyword check inconclusive, verify manually"
                            )
                    else:
                        suspect = True
                        reason = "L2 shares no obvious topic keywords with title/chunks"
        if not suspect and not brief:
            suspect = True
            reason = "L3 brief missing"
        elif not suspect and brief:
            l3_hits = keyword_hits(signal_kws, brief)
            if l3_hits == 0:
                l3_lang = language_guess(brief)
                if l3_lang != lang:
                    suspect = True
                    reason = (
                        f"cross-language L3 ({lang} content, {l3_lang} brief); "
                        f"keyword check inconclusive, verify manually"
                    )
                else:
                    suspect = True
                    reason = "L3 shares no keywords with title/chunks"

        if summary:
            n_l2 += 1
        if brief:
            n_l3 += 1
        if suspect:
            n_suspect += 1

        # --- per-video markdown ---
        dur = d["duration"]
        dur_str = f"{dur}s ({dur // 60}m{dur % 60:02d}s)" if isinstance(dur, int) else "unknown"
        lines = [
            f"# {title}",
            f"- video_id: {vid}",
            f"- document_id: {did}",
            f"- platform: {d['platform'] or 'unknown'}",
            f"- duration: {dur_str}",
            f"- chunk_count: {len(chunks)}",
            f"- language_guess: {lang}",
            "",
            "## L3 brief",
            brief or "(missing)",
            "",
            "## L2 summary",
            summary or "(missing)",
            "",
            "## Chunks",
        ]
        for c in chunks:
            ts = c.get("start_timestamp")
            ts_str = f" [{ts}]" if ts else ""
            lines.append(f"### chunk {c.get('chunk_index')}{ts_str}")
            lines.append((c.get("text") or "").rstrip())
        (OUT_DIR / f"{vid}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

        index_rows.append(
            {
                "video_id": vid,
                "title": title,
                "chunk_count": len(chunks),
                "lang": lang,
                "l2_ok": "yes" if summary else "no",
                "suspect": "yes" if suspect else "no",
                "reason": reason,
            }
        )

    # --- _index.md ---
    idx = [
        "# Corpus manifest index",
        "",
        f"- n_docs: {len(docs)}",
        f"- n_chunks_total: {n_chunks_total}",
        f"- n_l2_present: {n_l2}",
        f"- n_l3_present: {n_l3}",
        f"- n_suspect: {n_suspect}",
        f"- language distribution: "
        + ", ".join(f"{k}={v}" for k, v in sorted(lang_dist.items())),
        "",
        "| video_id | title | chunk_count | language_guess | l2_ok | l2_suspect | reason |",
        "|----------|-------|-------------|----------------|-------|------------|--------|",
    ]
    for r in index_rows:
        t = r["title"].replace("|", "\\|")
        idx.append(
            f"| {r['video_id']} | {t} | {r['chunk_count']} | {r['lang']} | "
            f"{r['l2_ok']} | {r['suspect']} | {r['reason']} |"
        )
    (OUT_DIR / "_index.md").write_text("\n".join(idx) + "\n", encoding="utf-8")

    # --- final report ---
    print(f"n_docs={len(docs)}")
    print(f"n_chunks_total={n_chunks_total} (qdrant points seen: {n_points})")
    print(f"n_l2_present={n_l2}")
    print(f"n_l3_present={n_l3}")
    print(f"n_suspect={n_suspect}")
    print("language_distribution:", dict(sorted(lang_dist.items())))
    for r in index_rows:
        if r["suspect"] == "yes":
            print(f"  SUSPECT {r['video_id']}: {r['reason']}")
    for e in errors:
        print(f"  MISMATCH {e}")
    print(f"wrote {len(index_rows)} video files + _index.md -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
