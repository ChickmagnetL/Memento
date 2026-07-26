#!/usr/bin/env python3
"""One-off: serially POST /api/documents/{id}/index for raw docs. Skip if already indexed."""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8010"
TIMEOUT = httpx.Timeout(3600.0, connect=30.0)  # up to 60 min per doc
RESULTS = Path(__file__).resolve().parent / "results" / "00_index_raw_serial.md"
LOG_JSON = Path(__file__).resolve().parent / "results" / "00_index_raw_serial.json"

# (video_id, document_id)
DOCS = [
    ("BV1M2421T7qk", "59380011d41f448f9e55653e67182b49"),
    ("BV1ub421J7jv", "06f4abbb549844a788757fe10c98d6c9"),
    ("cfXTQmFRjWU", "ebb04accd832482f8597d0ab7c18f5c2"),
    ("2qf6ry-YjwU", "acf4e85089bd4989bb26d761bf008123"),
    ("BV1QGXABxEbq", "5fd698d82dc94839a98e3a9b64321fa8"),
    ("64Zp3tzNbpE", "c72da92dfc8e4375bd056c5ad82423c0"),
    ("BV1hN596zEas", "6d0acacb84924ed9a3f6bbc1f3714cff"),
    ("EpIgvowZr00", "31282017576140cd8231eca72f90849f"),
    ("BV11o4y1s7VY", "b199b0778031446384eaaecb0d6680a6"),
    ("BV1dMGm6xET9", "f667f8fa51be489b9cddc69e4daf580d"),
    ("BV1LAVh6UEQz", "30bd49876f5f4632a24ece6cc69b3b26"),
    ("Cl0QYkez-BE", "b4309e724a594f8f94621245f955358b"),
    ("BV1Dm7J6XEEh", "17888c4cf23c48bf8ac2bbd263384e6e"),
    ("BV1z8zPYjE4j", "b5e0b56b48c74aec8d0fa551261f65cb"),
    ("BV1HR7o6CE8q", "f02984e6ca05481d806123e59d4c372a"),
    ("BV1hA7K6jER9", "9b2d8b5ea83749849b1a003c3de79cda"),
    ("ej6cygeB2X0", "418e8370da6c4e43a5a6d864914ddcc5"),
    ("3ub8RBE7BC8", "f21f689cb37443c685d4100709b4bb19"),
    ("cQP8WApzIQQ", "18599259b34241d8ac872db3983b3174"),
]


def log(msg: str) -> None:
    print(msg, flush=True)

def wait_health(client: httpx.Client, tries: int = 30) -> None:
    last = None
    for i in range(tries):
        try:
            h = client.get(f"{BASE}/api/health")
            if h.status_code == 200:
                return
            last = f"status={h.status_code}"
        except Exception as e:
            last = str(e)
        time.sleep(2)
    raise RuntimeError(f"backend health failed: {last}")



def list_docs(client: httpx.Client) -> dict[str, dict]:
    r = client.get(f"{BASE}/api/documents")
    r.raise_for_status()
    return {d["id"]: d for d in r.json()}


def get_doc(client: httpx.Client, doc_id: str) -> dict | None:
    # single-doc GET may be 405; always use list
    return list_docs(client).get(doc_id)


def write_report(rows: list[dict], note: str = "") -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    ok = sum(1 for r in rows if r.get("outcome") in ("indexed", "skipped_already_indexed"))
    failed = [r for r in rows if r.get("outcome") not in ("indexed", "skipped_already_indexed")]
    lines = [
        "# Index raw serial",
        "",
        f"- time: {now}",
        f"- total: {len(rows)}",
        f"- ok/skipped: {ok}",
        f"- failed: {len(failed)}",
        "",
    ]
    if note:
        lines += [note, ""]
    lines += [
        "| # | video_id | document_id | before | after | chunks | secs | outcome | error |",
        "|---|----------|-------------|--------|-------|--------|------|---------|-------|",
    ]
    for i, r in enumerate(rows, 1):
        lines.append(
            f"| {i} | {r.get('video_id','')} | `{r.get('document_id','')}` | "
            f"{r.get('before_status','')} | {r.get('after_status','')} | "
            f"{r.get('chunk_count','')} | {r.get('secs','')} | {r.get('outcome','')} | "
            f"{(r.get('error') or '').replace('|','/')} |"
        )
    lines += ["", "## Failed only", ""]
    if not failed:
        lines.append("(none)")
    else:
        for r in failed:
            lines.append(
                f"- {r.get('video_id')}: {r.get('outcome')} {r.get('error') or ''} "
                f"(status={r.get('after_status')} chunks={r.get('chunk_count')})"
            )
    lines.append("")
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text("\n".join(lines), encoding="utf-8")
    LOG_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"wrote {RESULTS}")


def main() -> int:
    # health
    with httpx.Client(timeout=TIMEOUT) as client:
        wait_health(client)
        log("health ok")

        rows: list[dict] = []
        for i, (vid, doc_id) in enumerate(DOCS, 1):
            log(f"\n=== [{i}/{len(DOCS)}] {vid} {doc_id} ===")
            wait_health(client)
            row: dict = {
                "video_id": vid,
                "document_id": doc_id,
                "before_status": None,
                "after_status": None,
                "chunk_count": None,
                "secs": None,
                "outcome": None,
                "error": None,
            }
            try:
                d = get_doc(client, doc_id)
                if not d:
                    row["outcome"] = "missing"
                    row["error"] = "document not found"
                    log("  MISSING")
                    rows.append(row)
                    write_report(rows)
                    continue

                st = (d.get("status") or "").lower()
                ch = int(d.get("chunk_count") or 0)
                row["before_status"] = st
                row["chunk_count"] = ch
                log(f"  before status={st} chunks={ch}")

                if st == "indexed" and ch > 0:
                    row["after_status"] = st
                    row["outcome"] = "skipped_already_indexed"
                    log("  SKIP already indexed")
                    rows.append(row)
                    write_report(rows)
                    continue

                last_err = None
                body = {}
                body_text = ""
                total_secs = 0.0
                for attempt in range(1, 6):
                    # re-check skip before retry
                    d_chk = get_doc(client, doc_id)
                    if d_chk:
                        stc = (d_chk.get("status") or "").lower()
                        chc = int(d_chk.get("chunk_count") or 0)
                        if stc == "indexed" and chc > 0:
                            row["after_status"] = stc
                            row["chunk_count"] = chc
                            row["secs"] = round(total_secs, 1)
                            row["outcome"] = "indexed" if attempt > 1 else "skipped_already_indexed"
                            log(f"  ready status={stc} chunks={chc}")
                            break
                    t0 = time.time()
                    log(f"  POST /index attempt {attempt}/5 ...")
                    try:
                        r = client.post(f"{BASE}/api/documents/{doc_id}/index")
                        secs = round(time.time() - t0, 1)
                        total_secs += secs
                        row["secs"] = round(total_secs, 1)
                        body_text = r.text[:500]
                        log(f"  response {r.status_code} in {secs}s body={body_text[:200]}")
                        if r.status_code >= 400:
                            last_err = f"http_{r.status_code}: {body_text}"
                            # transient?
                            if r.status_code in (408, 429, 500, 502, 503, 504) and attempt < 5:
                                sleep_s = min(30 * attempt, 120)
                                log(f"  retry sleep {sleep_s}s")
                                time.sleep(sleep_s)
                                continue
                            row["outcome"] = f"http_{r.status_code}"
                            row["error"] = body_text
                            d2 = get_doc(client, doc_id) or {}
                            row["after_status"] = (d2.get("status") or "").lower()
                            row["chunk_count"] = int(d2.get("chunk_count") or 0)
                            break
                        try:
                            body = r.json()
                        except Exception:
                            body = {}
                        d2 = get_doc(client, doc_id) or body or {}
                        st2 = (body.get("status") or d2.get("status") or "").lower()
                        ch2 = int(body.get("chunk_count") or d2.get("chunk_count") or 0)
                        row["after_status"] = st2
                        row["chunk_count"] = ch2
                        if st2 == "indexed" and ch2 > 0:
                            row["outcome"] = "indexed"
                            log(f"  final status={st2} chunks={ch2} outcome=indexed")
                            break
                        last_err = f"incomplete status={st2} chunks={ch2} body={body_text[:200]}"
                        if attempt < 5:
                            sleep_s = min(30 * attempt, 120)
                            log(f"  incomplete, retry sleep {sleep_s}s")
                            time.sleep(sleep_s)
                            continue
                        row["outcome"] = "incomplete"
                        row["error"] = last_err
                    except Exception as e:
                        secs = round(time.time() - t0, 1)
                        total_secs += secs
                        row["secs"] = round(total_secs, 1)
                        last_err = f"{type(e).__name__}: {e}"
                        log(f"  exception {last_err}")
                        if attempt < 5:
                            sleep_s = min(30 * attempt, 120)
                            log(f"  retry sleep {sleep_s}s")
                            time.sleep(sleep_s)
                            continue
                        row["outcome"] = "exception"
                        row["error"] = last_err
                        d2 = get_doc(client, doc_id) or {}
                        row["after_status"] = (d2.get("status") or "").lower()
                        row["chunk_count"] = int(d2.get("chunk_count") or 0)
                else:
                    if not row.get("outcome"):
                        row["outcome"] = "failed"
                        row["error"] = last_err
                log(f"  done outcome={row.get('outcome')} status={row.get('after_status')} chunks={row.get('chunk_count')}")
            except Exception as e:
                row["outcome"] = "exception"
                row["error"] = f"{type(e).__name__}: {e}"
                log(f"  EXCEPTION {e}")
                try:
                    d2 = get_doc(client, doc_id) or {}
                    row["after_status"] = (d2.get("status") or "").lower()
                    row["chunk_count"] = int(d2.get("chunk_count") or 0)
                except Exception:
                    pass
            rows.append(row)
            write_report(rows)

    write_report(rows)
    failed = [r for r in rows if r.get("outcome") not in ("indexed", "skipped_already_indexed")]
    log(f"\nDONE ok={len(rows)-len(failed)} failed={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
