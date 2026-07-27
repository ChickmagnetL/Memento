"""Ingest the Phase-0 benchmark video set into a running server on :8010.

Sequential pipeline: create -> check-subtitles -> process -> clean/index.
Subtitle-only (NO ASR). Resume-safe. Supports --start/--end batch ranges.
Writes benchmarks/results/00_dataset.md (full) or 00_dataset_batch_{s}_{e}.md.
Never prints secrets.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "backend"))
import bench_env  # noqa: F401

BASE_URL = "http://127.0.0.1:8010"
RESULTS_DIR = ROOT / "benchmarks" / "results"
LONG_TIMEOUT = 7200.0
DEFAULT_TIMEOUT = 120.0
SUBTITLE_PROCESS_MAX_ATTEMPTS = 10
INDEX_HTTP_MAX_ATTEMPTS = 5
# Local Qdrant open fights the running server on :8010. Default OFF.
ALLOW_LOCAL_BATCH = os.environ.get("BENCH_ALLOW_LOCAL_BATCH", "0") == "1"

# Order matches BENCHMARK_TASKS.md §4 (1-based indices).
VIDEOS: list[tuple[str, str]] = [
    ("https://www.bilibili.com/video/BV1FUYQz7E4H/?", "PostgreSQL 22min"),
    ("https://www.bilibili.com/video/BV14v4y1G7A3/?", "凯圣王一分化"),
    ("https://www.bilibili.com/video/BV1ev411w7bs/?", "增肌饮食"),
    ("https://www.bilibili.com/video/BV1Zk9FBwELs/?", "harness"),
    ("https://www.bilibili.com/video/BV1E7wtzaEdq/?", "AI 名词"),
    ("https://www.youtube.com/watch?v=P-NmMX9rlYQ", "GDP"),
    ("https://www.youtube.com/watch?v=-HOzOBmQ5ro", "瑞士经济"),
    ("https://www.youtube.com/watch?v=185XGEMefgc", "MCP VS API"),
    ("https://www.youtube.com/watch?v=vkpS7WztTMc", "苏姿丰"),
    ("https://www.youtube.com/watch?v=oYxTTirKY8M", "系统设计 2h"),
    ("https://www.youtube.com/watch?v=ej6cygeB2X0", "行为经济学 Thaler"),
    ("https://www.youtube.com/watch?v=Cl0QYkez-BE", "货币政策 Sims Sargent"),
    ("https://www.youtube.com/watch?v=iQyg-KypKAA", "L8 Principal Agentic Workflow"),
    ("https://www.youtube.com/watch?v=oKM-L_WiOhg", "特斯拉财报暴跌15%"),
    ("https://www.youtube.com/watch?v=cQP8WApzIQQ", "MIT 6.824 L1"),
    ("https://www.youtube.com/watch?v=EpIgvowZr00", "MIT 6.824 GFS"),
    ("https://www.youtube.com/watch?v=64Zp3tzNbpE", "MIT 6.824 Raft"),
    ("https://www.youtube.com/watch?v=3ub8RBE7BC8", "如何增肌"),
    ("https://www.youtube.com/watch?v=2qf6ry-YjwU", "自然健美备赛"),
    ("https://www.youtube.com/watch?v=cfXTQmFRjWU", "训练组数容量"),
    ("https://www.youtube.com/watch?v=lu_BObG6dj8", "progressive overload"),
    ("https://www.youtube.com/watch?v=ZlVBSZYaVF0", "hypertrophy volume"),
    ("https://www.youtube.com/watch?v=8BKbu_s8p1Q", "lean bulking"),
    ("https://www.youtube.com/watch?v=NS_GeXoboo4", "低预算增肌饮食"),
    ("https://www.youtube.com/watch?v=RmVL30sS2yU", "Nobel Acemoglu"),
    ("https://www.youtube.com/watch?v=-lcgyCG-olg", "Nobel Goldin"),
    ("https://www.youtube.com/watch?v=BBCp28YF-hg", "Nobel Bernanke 2022"),
    ("https://www.youtube.com/watch?v=31YTH1ywbS8", "Nobel Diamond"),
    ("https://www.youtube.com/watch?v=XvyMO7CmFlk", "Nobel Banerjee"),
    ("https://www.youtube.com/watch?v=wD48p6m8U-8", "Nobel Card"),
    ("https://www.youtube.com/watch?v=h1RkSuAs03Q", "Nobel Nordhaus"),
    ("https://www.youtube.com/watch?v=D3aHciiVdvQ", "Yale Shiller 金融"),
    ("https://www.youtube.com/watch?v=heBErnN3ZPk", "MIT 宏观 L1"),
    ("https://www.youtube.com/watch?v=b5H8D_wD2AY", "MIT 宏观 L4"),
    ("https://www.youtube.com/watch?v=W-Q9AOp2FW8", "FRONTLINE 2008 P1"),
    ("https://www.youtube.com/watch?v=PHe0bXAIuk0", "Dalio 经济机器"),
    ("https://www.bilibili.com/video/BV1654y1F7fZ/?", "新手健身忠告"),
    ("https://www.bilibili.com/video/BV1HR7o6CE8q/?", "背部训练私教"),
    ("https://www.bilibili.com/video/BV1z8zPYjE4j/?", "三分化饮食"),
    ("https://www.bilibili.com/video/BV1LAVh6UEQz/?", "蛋白质营养"),
    ("https://www.bilibili.com/video/BV11o4y1s7VY/?", "快速学习领域"),
    ("https://www.bilibili.com/video/BV1hN596zEas/?", "资本金融危机"),
    ("https://www.bilibili.com/video/BV1QGXABxEbq/?", "伊朗战争能源"),
    ("https://www.bilibili.com/video/BV1ub421J7jv/?", "美元日元人民币"),
    ("https://www.bilibili.com/video/BV1M2421T7qk/?", "全球经济形势"),
    ("https://www.bilibili.com/video/BV1mMHyz3Erk/?", "进程内存CPU"),
    ("https://www.bilibili.com/video/BV1hA7K6jER9/?", "电力四大赛道"),
    ("https://www.bilibili.com/video/BV1Dm7J6XEEh/?", "伊斯兰起源"),
    ("https://www.bilibili.com/video/BV1vtT46WEoW/?", "当行在泰国-曼谷"),
    ("https://www.bilibili.com/video/BV1dMGm6xET9/?", "中国家装变迁"),
]


def extract_video_key(url: str) -> str:
    """Extract a stable id key (BVid or YouTube v=) for URL matching."""
    u = (url or "").strip()
    m = re.search(r"(BV[\w]+)", u, re.IGNORECASE)
    if m:
        return m.group(1)
    parsed = urlparse(u)
    qs = parse_qs(parsed.query)
    if "v" in qs and qs["v"]:
        return qs["v"][0]
    # youtu.be/ID
    if "youtu.be" in (parsed.netloc or ""):
        return parsed.path.strip("/").split("/")[0]
    # fallback: strip trailing ? / #
    cleaned = u.split("#")[0].rstrip("?/ ")
    return cleaned


def urls_match(a: str, b: str) -> bool:
    if not a or not b:
        return False
    ka, kb = extract_video_key(a), extract_video_key(b)
    if ka and kb and ka == kb:
        return True
    na = a.split("#")[0].rstrip("?/ ").lower()
    nb = b.split("#")[0].rstrip("?/ ").lower()
    return na == nb or na.startswith(nb) or nb.startswith(na)


@dataclass
class Row:
    label: str
    url: str
    status: str = "pending"
    video_id: str = ""
    document_id: str = ""
    chunk_count: int = 0
    error: str = ""
    notes: str = ""
    index: int = 0  # 1-based global index in VIDEOS


def list_videos(client: httpx.Client) -> list[dict]:
    r = client.get(f"{BASE_URL}/api/videos", timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []


def list_documents(client: httpx.Client) -> list[dict]:
    r = client.get(f"{BASE_URL}/api/documents", timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []


def docs_for_video(docs: list[dict], video_id: str) -> list[dict]:
    return [d for d in docs if d.get("video_id") == video_id]


def is_ready(doc: dict) -> bool:
    status = (doc.get("status") or "").lower()
    chunks = int(doc.get("chunk_count") or 0)
    return status == "indexed" and chunks > 0


def find_existing_video(videos: list[dict], url: str) -> dict | None:
    for v in videos:
        if urls_match(v.get("url") or "", url):
            return v
    return None


def ensure_video(client: httpx.Client, url: str) -> dict:
    videos = list_videos(client)
    existing = find_existing_video(videos, url)
    if existing:
        print(f"  reuse existing video id={existing.get('id')} status={existing.get('status')}")
        return existing

    print(f"  POST /api/videos url={url}")
    r = client.post(
        f"{BASE_URL}/api/videos",
        json={"url": url},
        timeout=DEFAULT_TIMEOUT,
    )
    if r.status_code in (200, 201):
        return r.json()

    # Duplicate may surface as 409 or 500 IntegrityError
    print(f"  create failed status={r.status_code}: {r.text[:300]}")
    videos = list_videos(client)
    existing = find_existing_video(videos, url)
    if existing:
        print(f"  recovered via list: id={existing.get('id')}")
        return existing
    raise RuntimeError(f"create video failed and not found in list: {r.status_code} {r.text[:200]}")


def check_subtitles(client: httpx.Client, video_id: str) -> dict:
    print(f"  GET /api/videos/{video_id}/check-subtitles")
    r = client.get(
        f"{BASE_URL}/api/videos/{video_id}/check-subtitles",
        timeout=DEFAULT_TIMEOUT,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"check-subtitles failed: {r.status_code} {r.text[:300]}")
    return r.json()


def process_video(client: httpx.Client, video_id: str) -> dict:
    """Process with soft subtitles only. NO ASR — never passes subtitle_fallback."""
    params = {"allow_non_chinese": "true"}
    assert "subtitle_fallback" not in params  # NO ASR
    print(f"  POST /api/videos/{video_id}/process allow_non_chinese=true (subtitle-only, NO ASR)")
    r = client.post(
        f"{BASE_URL}/api/videos/{video_id}/process",
        params=params,
        timeout=LONG_TIMEOUT,
    )
    if r.status_code < 400:
        body = r.json()
        if (body.get("status") or "").lower() != "failed":
            return body
        err_text = (body.get("error_message") or "status=failed")[:500]
        raise RuntimeError(f"process returned status=failed: {err_text}")

    err_text = r.text[:500]
    raise RuntimeError(f"process failed: {r.status_code} {err_text}")


def clean_document(client: httpx.Client, document_id: str) -> dict:
    print(f"  POST /api/documents/{document_id}/clean")
    r = client.post(
        f"{BASE_URL}/api/documents/{document_id}/clean",
        timeout=LONG_TIMEOUT,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"clean failed: {r.status_code} {r.text[:300]}")
    return r.json()


def index_document(client: httpx.Client, document_id: str) -> dict:
    """HTTP index with retries. Never opens local Qdrant unless BENCH_ALLOW_LOCAL_BATCH=1."""
    last_err: str | None = None
    for attempt in range(1, INDEX_HTTP_MAX_ATTEMPTS + 1):
        print(
            f"  POST /api/documents/{document_id}/index "
            f"(attempt {attempt}/{INDEX_HTTP_MAX_ATTEMPTS})"
        )
        try:
            r = client.post(
                f"{BASE_URL}/api/documents/{document_id}/index",
                timeout=LONG_TIMEOUT,
            )
            if r.status_code < 400:
                return r.json()
            last_err = f"index failed: {r.status_code} {r.text[:300]}"
        except Exception as exc:  # noqa: BLE001
            last_err = f"index request error: {exc}"
        if attempt >= INDEX_HTTP_MAX_ATTEMPTS:
            break
        sleep_s = min(60, 5 * attempt)
        print(f"  index retryable failure, sleep {sleep_s}s: {(last_err or '')[:200]}")
        time.sleep(sleep_s)
    raise RuntimeError(last_err or "index failed")


def pick_document(client: httpx.Client, video_id: str) -> dict | None:
    docs = docs_for_video(list_documents(client), video_id)
    if not docs:
        return None
    # Prefer indexed with chunks, else first
    for d in docs:
        if is_ready(d):
            return d
    return docs[0]


# Auth-only hard fails: do not call process. Everything else tries process with retries
# (precheck is informational / flaky; process with allow_non_chinese can still work).
HARD_FAIL_REASONS = frozenset({"not_logged_in", "auth_expired"})
# Soft reasons we explicitly expect to proceed despite has_subtitles=false.
TRY_ANYWAY_REASONS = frozenset(
    {"non_chinese_subtitles", "no_subtitles", "subtitle_unstable", "upstream_error"}
)


def is_retryable_process_error(err: str) -> bool:
    """True if process failure looks like flaky subtitles/network (retry up to 10).

    Permanent hard fails (no retry): create-metadata 422 / cannot import URL,
    auth expired / not logged in. non_chinese is not a failure (allow_non_chinese).
    Still NO ASR.
    """
    text = (err or "").lower()
    permanent_markers = (
        "not_logged_in",
        "auth_expired",
        "auth failure",
        "not logged in",
        "422",
        "cannot import",
        "create video failed",
    )
    if any(m in text for m in permanent_markers):
        return False
    retryable_markers = (
        "no_subtitles",
        "subtitle_unstable",
        "upstream",
        "timeout",
        "timed out",
        "connection",
        "connect",
        "5xx",
        "502",
        "503",
        "504",
        "500",
        "usable soft subtitles",
        "soft subtitle",
        "network",
        "temporarily",
        "status=failed",
        "process failed",
        "process returned status=failed",
    )
    return any(m in text for m in retryable_markers)


def process_one(client: httpx.Client, url: str, label: str, index: int) -> Row:
    row = Row(label=label, url=url, index=index)
    print(f"\n=== [{index}] [{label}] {url} ===")
    try:
        videos = list_videos(client)
        existing = find_existing_video(videos, url)
        if existing:
            vid = existing.get("id") or ""
            row.video_id = vid
            doc = pick_document(client, vid)
            if doc and is_ready(doc) and (existing.get("status") or "").lower() == "completed":
                row.status = "skipped_ready"
                row.document_id = doc.get("id") or ""
                row.chunk_count = int(doc.get("chunk_count") or 0)
                row.notes = "already completed+indexed"
                print(f"  SKIP ready video={vid} doc={row.document_id} chunks={row.chunk_count}")
                return row

        video = ensure_video(client, url)
        row.video_id = video.get("id") or ""
        if not row.video_id:
            raise RuntimeError("missing video id")
        vstatus = (video.get("status") or "").lower()

        doc = pick_document(client, row.video_id) if row.video_id else None
        if doc and is_ready(doc) and vstatus == "completed":
            row.status = "skipped_ready"
            row.document_id = doc.get("id") or ""
            row.chunk_count = int(doc.get("chunk_count") or 0)
            row.notes = "already completed+indexed"
            print(f"  SKIP ready video={row.video_id} doc={row.document_id}")
            return row

        # pending/failed reclaim: claim_video_for_processing accepts pending+failed
        # (and completed). No PATCH status reset needed before process.
        if vstatus != "completed":
            # Precheck is informational. Hard-fail only on auth; otherwise try process
            # with allow_non_chinese=true (NO ASR), retry up to 10 on flaky subtitle/network.
            sub = check_subtitles(client, row.video_id)
            reason = sub.get("reason") or sub.get("detail") or "unknown"
            langs = sub.get("available_languages") or []
            has = bool(sub.get("has_subtitles"))

            if reason in HARD_FAIL_REASONS:
                raise RuntimeError(f"subtitle precheck auth failure: {reason}")

            if has:
                print(f"  precheck ok has_subtitles=true reason={reason} langs={langs}")
            else:
                # Soft-fail / flaky precheck: do not hard-fail; go to process retries.
                tag = "try_anyway" if reason in TRY_ANYWAY_REASONS else "unknown"
                print(
                    f"  precheck reason={reason} ({tag}) langs={langs}; "
                    "proceeding despite precheck (allow_non_chinese, NO ASR)"
                )

            last_err: str | None = None
            for attempt in range(1, SUBTITLE_PROCESS_MAX_ATTEMPTS + 1):
                print(
                    f"  subtitle process attempt "
                    f"{attempt}/{SUBTITLE_PROCESS_MAX_ATTEMPTS}"
                )
                try:
                    video = process_video(client, row.video_id)
                    row.video_id = video.get("id") or row.video_id
                    vstatus = (video.get("status") or "").lower()
                    if vstatus == "failed":
                        raise RuntimeError(
                            video.get("error_message") or "video status=failed"
                        )
                    last_err = None
                    break
                except Exception as proc_exc:  # noqa: BLE001
                    last_err = str(proc_exc)
                    if not is_retryable_process_error(last_err):
                        raise
                    if attempt >= SUBTITLE_PROCESS_MAX_ATTEMPTS:
                        raise RuntimeError(
                            f"skipped_after_10_subtitle_retries: {last_err}"
                        ) from proc_exc
                    sleep_s = min(30, 2 * attempt)
                    print(
                        f"  process retryable failure, sleep {sleep_s}s: "
                        f"{last_err[:200]}"
                    )
                    time.sleep(sleep_s)

        doc = pick_document(client, row.video_id)
        if not doc:
            # process should create document; re-list once
            doc = pick_document(client, row.video_id)
        if not doc:
            raise RuntimeError("no document found after process")

        row.document_id = doc.get("id") or ""
        if not is_ready(doc):
            clean_err: str | None = None
            result_doc: dict | None = None
            doc_status = (doc.get("status") or "").lower()

            def _http_index_or_raise(prefix: str) -> dict:
                try:
                    return index_document(client, row.document_id)
                except Exception as index_exc:  # noqa: BLE001
                    if not ALLOW_LOCAL_BATCH:
                        raise RuntimeError(
                            f"{prefix}index failed after "
                            f"{INDEX_HTTP_MAX_ATTEMPTS} HTTP retries: {index_exc}"
                        ) from index_exc
                    print(
                        f"  HTTP index failed, BENCH_ALLOW_LOCAL_BATCH=1 "
                        f"trying local batch index: {index_exc}"
                    )
                    from index_large_doc import index_document_batched_sync

                    out = index_document_batched_sync(row.document_id)
                    row.notes = f"local_batch_index after: {str(index_exc)[:200]}"
                    return out

            # raw docs: skip clean (chat often hangs/fails); HTTP index only.
            if doc_status == "raw":
                print("  doc status=raw; skip clean, HTTP index directly (NO ASR)")
                result_doc = _http_index_or_raise("")
                row.notes = (row.notes or "indexed_raw_skip_clean").strip()
            else:
                try:
                    result_doc = clean_document(client, row.document_id)
                except Exception as clean_exc:  # noqa: BLE001
                    clean_err = str(clean_exc)[:300]
                    print(f"  clean failed, fallback to raw index: {clean_err}")
                    result_doc = _http_index_or_raise(f"clean failed: {clean_err}; ")

            if result_doc:
                row.chunk_count = int(result_doc.get("chunk_count") or 0)
                row.document_id = result_doc.get("id") or row.document_id

            if not is_ready(result_doc or {}) and row.chunk_count == 0:
                # clean may have returned without indexing; force HTTP index
                if result_doc is not None and clean_err is None and doc_status != "raw":
                    print("  clean returned non-indexed doc; forcing HTTP index")
                    try:
                        result_doc = index_document(client, row.document_id)
                        row.chunk_count = int(result_doc.get("chunk_count") or 0)
                        row.document_id = result_doc.get("id") or row.document_id
                    except Exception as index_exc:  # noqa: BLE001
                        print(f"  post-clean index failed: {index_exc}")
                doc2 = pick_document(client, row.video_id)
                if doc2:
                    row.chunk_count = int(doc2.get("chunk_count") or 0)
                    row.document_id = doc2.get("id") or row.document_id
                    result_doc = doc2

            if not is_ready(result_doc or {}) and row.chunk_count == 0:
                raise RuntimeError(
                    f"document not indexed after clean/index status="
                    f"{(result_doc or {}).get('status')} chunks={row.chunk_count}"
                    + (f" (clean_err={clean_err})" if clean_err else "")
                )

            if clean_err and "local_batch" not in (row.notes or ""):
                # clean failed but HTTP index (or re-fetch) succeeded with chunks
                row.notes = f"clean_failed_indexed_raw: {clean_err}"
        else:
            row.chunk_count = int(doc.get("chunk_count") or 0)

        row.status = "success"
        print(f"  OK video={row.video_id} doc={row.document_id} chunks={row.chunk_count}")
    except Exception as exc:  # noqa: BLE001 - record per-video failure
        row.status = "failed"
        row.error = str(exc)[:500]
        print(f"  FAIL: {row.error}")
    return row


def report_path(start: int, end: int, batch_tag: str | None) -> Path:
    """Full range writes 00_dataset.md; partial range writes batch file."""
    full = start == 1 and end == len(VIDEOS)
    if full and not batch_tag:
        return RESULTS_DIR / "00_dataset.md"
    if batch_tag:
        return RESULTS_DIR / f"00_dataset_batch_{batch_tag}.md"
    return RESULTS_DIR / f"00_dataset_batch_{start}_{end}.md"


def write_report(rows: list[Row], out_path: Path, start: int, end: int) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ok = sum(1 for r in rows if r.status in ("success", "skipped_ready"))
    fail = sum(1 for r in rows if r.status == "failed")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# 00 数据集灌库报告",
        "",
        f"生成时间: {now}",
        f"BASE_URL: `{BASE_URL}`",
        f"范围: videos {start}–{end} (1-based, of {len(VIDEOS)} total)",
        f"模式: subtitle-only (NO ASR)",
        f"成功(含已就绪跳过): {ok} / {len(rows)}，失败: {fail}",
        "",
        "| # | 标签 | 状态 | video_id | document_id | chunk_count | 错误/备注 |",
        "|---|------|------|----------|-------------|-------------|-----------|",
    ]
    for r in rows:
        err = (r.error or r.notes or "").replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {r.index} | {r.label} | {r.status} | `{r.video_id}` | `{r.document_id}` | "
            f"{r.chunk_count} | {err} |"
        )

    retry_exhausted = [
        r
        for r in rows
        if r.status == "failed"
        and "skipped_after_10_subtitle_retries" in ((r.error or "") + (r.notes or ""))
    ]
    lines.append("")
    lines.append("## 需人工复核（字幕10次仍失败）")
    lines.append("")
    if not retry_exhausted:
        lines.append("_（本批次无）_")
    else:
        lines.append("| # | label | url | last_error |")
        lines.append("|---|-------|-----|------------|")
        for r in retry_exhausted:
            err = (r.error or r.notes or "").replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {r.index} | {r.label} | {r.url} | {err} |")
        lines.append("")
        lines.append(
            "失败编号: " + ", ".join(f"#{r.index}" for r in retry_exhausted)
        )

    all_failed = [r for r in rows if r.status == "failed"]
    if all_failed:
        lines.append("")
        lines.append(
            "全部失败编号: " + ", ".join(f"#{r.index}" for r in all_failed)
        )

    lines.append("")
    lines.append("## URL 清单")
    lines.append("")
    for r in rows:
        lines.append(f"{r.index}. [{r.label}]({r.url})")
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {out_path}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingest benchmark videos (subtitle-only, no ASR).")
    p.add_argument("--start", type=int, default=1, help="1-based inclusive start index (default 1)")
    p.add_argument(
        "--end",
        type=int,
        default=None,
        help=f"1-based inclusive end index (default {len(VIDEOS)})",
    )
    p.add_argument(
        "--batch-tag",
        type=str,
        default=None,
        help="Optional report filename suffix: 00_dataset_batch_{tag}.md",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    start = args.start
    end = args.end if args.end is not None else len(VIDEOS)

    if start < 1 or end > len(VIDEOS) or start > end:
        print(
            f"ERROR: invalid range start={start} end={end}; "
            f"valid 1..{len(VIDEOS)} with start<=end"
        )
        return 2

    slice_videos = VIDEOS[start - 1 : end]
    out_path = report_path(start, end, args.batch_tag)

    print(
        f"Ingest starting BASE_URL={BASE_URL} range={start}-{end} "
        f"count={len(slice_videos)} report={out_path.name} mode=subtitle-only"
    )
    rows: list[Row] = []
    with httpx.Client() as client:
        # Health probe
        try:
            h = client.get(f"{BASE_URL}/api/health", timeout=10.0)
            print(f"health status={h.status_code}")
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: health check failed: {exc}")

        for offset, (url, label) in enumerate(slice_videos):
            idx = start + offset
            rows.append(process_one(client, url, label, idx))

    write_report(rows, out_path, start, end)
    ok = sum(1 for r in rows if r.status in ("success", "skipped_ready"))
    fail = sum(1 for r in rows if r.status == "failed")
    print(f"\nSummary: ok={ok} fail={fail} total={len(rows)} range={start}-{end}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
