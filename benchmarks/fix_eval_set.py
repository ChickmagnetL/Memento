"""Fix A: clean benchmarks/eval_set.jsonl for RAG routing/retrieval quality.

Idempotent re-application of audit decisions from a manual span audit against
indexed markdown + Qdrant chunk payloads (see benchmarks/results/fix_a_audit.json).

Policy
------
1. REMOVE detail questions that are pure common knowledge (or only weakly
   grounded) so agents correctly skip tools but expected_route=search would
   mark them wrong.
2. RELABEL relevant_chunks to indices whose text contains the answer span.
3. REWRITE questions whose notes invent details not present in the transcript.
4. KEEP all summary (lookup+summarize, empty GT) and self (memory, empty GT).

Does NOT re-chunk or re-index. Only touches eval_set.jsonl (+ backup/docs).

Usage
-----
  export MEMENTO_PROJECT_ROOT=/Users/leo/development/memento
  export STORAGE__DATA_DIR=.../rag-benchmarks/bench_data
  export PYTHONPATH=.../rag-benchmarks/backend
  /path/to/venv/bin/python benchmarks/fix_eval_set.py
"""

from __future__ import annotations

import json
import shutil
import sys
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "benchmarks" / "eval_set.jsonl"
BAK = ROOT / "benchmarks" / "eval_set.jsonl.pre_fix_a"
AUDIT = ROOT / "benchmarks" / "results" / "fix_a_audit.json"
DATASET_MD = ROOT / "benchmarks" / "results" / "00_dataset.md"

# Prefer applying against the pre-fix backup so re-runs are stable.
SOURCE_CANDIDATES = [BAK, EVAL]

REMOVE = {
    "q001": (
        "pure_common_knowledge",
        "GDP 支出法公式（C+I+G+进出口）为教科书常识；虽在视频中出现，"
        "但 LLM 无需检索即可答对，污染 search 路由评测。",
    ),
    "q020": (
        "pure_common_knowledge",
        "DNS 将域名映射到 IP 为通用系统知识，任何 LLM 无需视频即可答对。",
    ),
    "q021": (
        "pure_common_knowledge",
        "SQL 事务 ACID 四性质为教科书常识。",
    ),
    "q022": (
        "pure_common_knowledge",
        "round robin 负载均衡为通用系统知识。",
    ),
    "q041": (
        "pure_common_knowledge",
        "Transformer 由 Google 团队于 2017 年提出为广为人知的常识；视频仅一笔带过。",
    ),
    "q042": (
        "pure_common_knowledge_and_weak_grounding",
        "BPE 为 NLP 常识；视频仅以「可看另一期」方式顺带提到，非本片核心可检索事实。",
    ),
}

# document_id is filled from source row at apply time
REWRITE = {
    "q024": {
        "reason": "answer_span_not_in_transcript",
        "detail": (
            "原文未点名 postgresql.conf / pg_hba.conf，只说两个配置文件；"
            "listen_addresses 改为 * 在 chunk 1 中有明确跨度。"
        ),
        "new_question": (
            "视频中在 Ubuntu 服务器上放开 PostgreSQL 远程连接时，"
            "第一个配置文件里需要把 listen_addresses 改成什么？"
        ),
        "new_notes": "星号 *（表示监听所有可用网络）",
        "new_chunk_indices": [1],
    },
}

RELABEL = {
    "q003": ([5, 4, 3], "二手/闲鱼/所有权流转/增值 主要落在 chunk 3–5；原 GT 含较弱的 chunk 2。"),
    "q007": ([11], "罗氏/诺华/市值前三 集中在 chunk 11；原 GT 含不相关 chunk 17/12。"),
    "q008": ([13, 12], "双轨制/学徒 在 chunk 12–13；去掉无命中的 chunk 14。"),
    "q028": ([6, 3], "倒蹬 vs 深蹲硬拉 主答案在 chunk 6；chunk 3 含活动度背景；去掉弱相关 chunk 4。"),
    "q029": ([5], "高BMI高体脂→增肌减脂可同时进行 完整在 chunk 5。"),
    "q036": ([1], "70%→95% 与改进点在 chunk 1；原 GT 指向后期总结块。"),
    "q038": ([6, 7, 11], "六层定义从 chunk 6 起，续层在 7，总结在 11；去掉弱相关 chunk 1。"),
    "q039": ([8], "Context Reset / 上下文焦虑 完整在 chunk 8。"),
}


def _load_source() -> tuple[Path, list[dict]]:
    for p in SOURCE_CANDIDATES:
        if p.exists():
            rows = [
                json.loads(line)
                for line in p.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            return p, rows
    raise FileNotFoundError(f"no eval set found among {SOURCE_CANDIDATES}")


def _chunks(doc_id: str, indices: list[int]) -> list[dict]:
    return [{"document_id": doc_id, "chunk_index": i} for i in indices]


def apply(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    by_id = {r["id"]: r for r in rows}
    out: list[dict] = []
    actions: list[dict] = []

    for r in rows:
        qid = r["id"]
        if qid in REMOVE:
            reason, detail = REMOVE[qid]
            actions.append(
                {
                    "id": qid,
                    "action": "remove",
                    "reason": reason,
                    "detail": detail,
                    "question": r["question"],
                    "type": r["type"],
                    "expected_route": r["expected_route"],
                    "video_id": r.get("video_id"),
                }
            )
            continue

        nr = deepcopy(r)

        if qid in REWRITE:
            rw = REWRITE[qid]
            old_q, old_notes, old_gt = r["question"], r.get("notes"), r.get("relevant_chunks")
            nr["question"] = rw["new_question"]
            nr["notes"] = rw["new_notes"]
            nr["relevant_chunks"] = _chunks(r["document_id"], rw["new_chunk_indices"])
            actions.append(
                {
                    "id": qid,
                    "action": "rewrite",
                    "reason": rw["reason"],
                    "detail": rw["detail"],
                    "old_question": old_q,
                    "new_question": nr["question"],
                    "old_notes": old_notes,
                    "new_notes": nr["notes"],
                    "old_relevant_chunks": old_gt,
                    "new_relevant_chunks": nr["relevant_chunks"],
                }
            )

        if qid in RELABEL:
            indices, detail = RELABEL[qid]
            old_gt = nr.get("relevant_chunks")
            # if this row came from already-fixed eval (no old GT), still set target
            if qid in by_id and qid not in REWRITE:
                # prefer original GT from source for audit when available
                old_gt = r.get("relevant_chunks")
            nr["relevant_chunks"] = _chunks(r["document_id"], indices)
            actions.append(
                {
                    "id": qid,
                    "action": "relabel_gt",
                    "detail": detail,
                    "old_relevant_chunks": old_gt,
                    "new_relevant_chunks": nr["relevant_chunks"],
                }
            )

        if nr["type"] == "detail" and not nr.get("relevant_chunks"):
            raise RuntimeError(f"detail {qid} would have empty relevant_chunks")

        out.append(nr)

    return out, actions


def _update_dataset_md(
    *,
    input_count: int,
    out: list[dict],
    actions: list[dict],
) -> None:
    types = Counter(r["type"] for r in out)
    routes = Counter(r["expected_route"] for r in out)
    removed_ids = [a["id"] for a in actions if a["action"] == "remove"]
    rewrite_ids = [a["id"] for a in actions if a["action"] == "rewrite"]
    relabel_ids = [a["id"] for a in actions if a["action"] == "relabel_gt"]
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    section = f"""

## Fix A — eval_set 数据质量清洗

更新时间: {ts}

### 操作摘要

| 操作 | 数量 | ID |
|------|------|-----|
| 移除 (常识/弱 grounding) | {len(removed_ids)} | {", ".join(removed_ids)} |
| 重写 (对齐 transcript) | {len(rewrite_ids)} | {", ".join(rewrite_ids) or "—"} |
| 重标 GT chunks | {len(relabel_ids)} | {", ".join(relabel_ids)} |
| 保留 summary | 10 | 全部保留 |
| 保留 self | 4 | 全部保留 |

### 移除明细

"""
    for a in actions:
        if a["action"] != "remove":
            continue
        section += f"- **{a['id']}** (`{a.get('video_id')}`): {a['detail']}\n"

    section += "\n### 重写明细\n\n"
    for a in actions:
        if a["action"] != "rewrite":
            continue
        section += (
            f"- **{a['id']}**: {a['detail']}\n"
            f"  - 旧问: {a['old_question']}\n"
            f"  - 新问: {a['new_question']}\n"
            f"  - 新 notes: {a['new_notes']}\n"
            f"  - 新 GT: `{json.dumps(a['new_relevant_chunks'], ensure_ascii=False)}`\n"
        )

    section += "\n### 重标 GT 明细\n\n"
    for a in actions:
        if a["action"] != "relabel_gt":
            continue
        old_idx = [c["chunk_index"] for c in (a.get("old_relevant_chunks") or [])]
        new_idx = [c["chunk_index"] for c in a["new_relevant_chunks"]]
        section += f"- **{a['id']}**: {old_idx} → {new_idx} — {a['detail']}\n"

    section += f"""
### 清洗后评测集分布

- 评测问题总数: **{len(out)}**（清洗前 {input_count}）
- 类型分布: detail={types.get('detail', 0)}, summary={types.get('summary', 0)}, self={types.get('self', 0)}
- 期望路由: search={routes.get('search', 0)}, lookup+summarize={routes.get('lookup+summarize', 0)}, memory={routes.get('memory', 0)}
- 备份: `benchmarks/eval_set.jsonl.pre_fix_a`
- 审计日志: `benchmarks/results/fix_a_audit.json`
- 可复现脚本: `benchmarks/fix_eval_set.py`

### 质量标准（Fix A 后）

- 每道剩余 **detail** 题均：`relevant_chunks` 非空，且答案跨度可在对应视频 transcript/chunk 中核对。
- summary / self 保持空 GT（by design）。
- 已剔除「仅靠世界知识即可答、会把 search 路由拉偏」的 detail 题。
"""

    md = DATASET_MD.read_text(encoding="utf-8") if DATASET_MD.exists() else ""
    marker = "\n## Fix A — eval_set 数据质量清洗\n"
    if marker in md:
        md = md.split(marker)[0].rstrip() + "\n"
    DATASET_MD.parent.mkdir(parents=True, exist_ok=True)
    DATASET_MD.write_text(md + section, encoding="utf-8")


def main() -> int:
    source_path, rows = _load_source()
    print(f"source: {source_path} ({len(rows)} rows)")

    if not BAK.exists() and source_path == EVAL:
        shutil.copy2(EVAL, BAK)
        print(f"backup -> {BAK}")
    elif BAK.exists():
        print(f"backup ok: {BAK}")

    out, actions = apply(rows)

    with EVAL.open("w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    types = Counter(r["type"] for r in out)
    routes = Counter(r["expected_route"] for r in out)
    removed_ids = [a["id"] for a in actions if a["action"] == "remove"]
    rewrite_ids = [a["id"] for a in actions if a["action"] == "rewrite"]
    relabel_ids = [a["id"] for a in actions if a["action"] == "relabel_gt"]

    audit = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source_path),
        "source_backup": str(BAK),
        "input_count": len(rows),
        "output_count": len(out),
        "removed_count": len(removed_ids),
        "removed_ids": removed_ids,
        "relabeled_count": len(relabel_ids),
        "relabeled_ids": relabel_ids,
        "rewritten_count": len(rewrite_ids),
        "rewritten_ids": rewrite_ids,
        "final_type_distribution": dict(types),
        "final_expected_route_distribution": dict(routes),
        "actions": actions,
        "policy": {
            "remove": (
                "Out-of-KB or pure common-knowledge detail Qs that any LLM "
                "answers without retrieval (pollute expected_route=search)."
            ),
            "relabel": "Prefer chunks that contain the answer span from indexed payloads.",
            "rewrite": (
                "Only when answer notes invent content not in transcript; "
                "rewrite into video-specific grounded detail."
            ),
            "keep_summary_self": "summary and self/memory kept with empty GT by design.",
        },
    }
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    _update_dataset_md(input_count=len(rows), out=out, actions=actions)

    print(f"wrote {EVAL} ({len(out)} rows)")
    print(f"removed={removed_ids}")
    print(f"rewritten={rewrite_ids}")
    print(f"relabeled={relabel_ids}")
    print(f"types={dict(types)} routes={dict(routes)}")
    print(f"audit={AUDIT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
