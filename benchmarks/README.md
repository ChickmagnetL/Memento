# RAG Benchmarks · 运行手册 (Runbook)

> 目标读者：一个对仓库零认知的新 session 或人。从冷启动到结果落盘，按本文走即可。
> 真相源：`benchmarks/results/SUMMARY.md`（基线结果）。本文件只讲「怎么跑」，不重述结果数字。

## 1. What this is

Memento RAG 基准测试：在一个 50 视频 / 2040 chunks 的知识库上评测五个维度 ——
**01 检索 A/B**（hybrid vs pure_vector vs pure_bm25）、**03 延迟**、**04 路由准确率**、
**02 分层 vs 平铺架构 A/B**、**05 数据规模快照**。冻结评测集 **145 题**
（`benchmarks/eval_set.jsonl`，frozen 2026-07-27，规范见 `benchmarks/EVAL_SPEC.md`）。
当前基线 commit：`d3f03a4`。

## 2. Prerequisites

### a. Embedding 服务（:8003）

位于 `services/embedding/`。**默认 CPU**；Apple Silicon 必须覆盖为 `mps` 才能用 GPU：

```
EMBEDDING_DEVICE=mps bash services/embedding/run.sh
```

`run.sh` 里 `EMBEDDING_DEVICE="${EMBEDDING_DEVICE:-cpu}"` —— 不覆盖会跑 CPU、很慢。
起来后验证：

```
curl -s http://localhost:8003/v1/models | head
```

### b. 语料 `bench_data/`

需 50 视频已入库。检查 `bench_data/qdrant/` 与 `bench_data/metadata.db` 是否非空。
如果空，按顺序补：

**ingest**（字幕 only、无 ASR，逐条 create→check-subtitles→process→index；可断点续跑，支持 `--start/--end`）。
ingest 需要后端 server 在 :8010 运行 —— 另开一个终端起 server，再跑 ingest：

```
# 终端 A：起后端 server (127.0.0.1:8010)
set -a; source benchmarks/bench_chat.env; set +a
python3 -m benchmarks.run_server
```

```
# 终端 B：ingest
python3 -m benchmarks.ingest_videos 2>&1 | tee benchmarks/results/00_dataset.log
```

**L2/L3 摘要回填**：`backfill_summaries` 直连 chat 模型（不经 server），幂等、跳过已填的 doc，
大文档走 map-reduce。05 的 L2/L3 100% 覆盖就靠它。如果 `05_scale.json` 显示 L2/L3 覆盖不满：

```
set -a; source benchmarks/bench_chat.env; set +a
python3 -m benchmarks.backfill_summaries 2>&1 | tee benchmarks/results/00_backfill_l2l3.log
```

### c. 评测集

`benchmarks/eval_set.jsonl` + `benchmarks/eval_set_meta.json` —— **已提交**，145 题。
类型分布（`eval_set_meta.json`）：detail 53 / multi_evidence 19 / multi_hop 10 / summary 49 / unanswerable 9 / memory 5。

## 3. Chat 端点配置

benchmark 通过 `bench_env.py` 复用桌面 app 的 chat 预设，但允许 env var 覆盖。
三个 env var：`MODELS__CHAT__MODEL` / `MODELS__CHAT__ENDPOINT` / `MODELS__CHAT__API_KEY`。
Secrets 放在 `benchmarks/bench_chat.env`（**gitignored —— 绝不提交真 key**）。

Setup：

```
cp benchmarks/bench_chat.env.example benchmarks/bench_chat.env
# 编辑 benchmarks/bench_chat.env，填入你的 endpoint / model / key
```

验证加载（从 worktree 根目录跑）：

```
set -a; source benchmarks/bench_chat.env; set +a
python3 -c "import sys; sys.path.insert(0,'backend'); import benchmarks.bench_env; from config.settings import get_settings; print(get_settings().models.chat.model, get_settings().models.chat.endpoint)"
```

应打印出你填的 model 和 endpoint。`bench_env.py` 只在 env 未设时才回退到桌面 app 的 `memento.db` 预设 —— 所以 `source bench_chat.env` 的优先级最高。

## 4. 跑全量前先验端点容量（IMPORTANT）

历史教训：未经验证的端点会在 70 分钟的全量跑分中途爆 429 风暴或被内容审核拦截，浪费一整轮。
本轮见过两种失败模式：

- (a) 转售 `new-api` 网关会在经济/政治类内容上注入 `sensitive_words_detected`（即使原内容无害）；
- (b) 紧的 per-minute 配额（某端点 10 req/min 硬上限）。

跑全量前，先发 ~150 个请求 @ concurrency 5 数 429。
**推荐标准：≥150 reqs @ concurrency 5 且 0 个 429 才上全量。**

```
set -a; source benchmarks/bench_chat.env; set +a
python3 - <<'PYEOF'
import asyncio, os, collections, time, httpx
endpoint=os.environ["MODELS__CHAT__ENDPOINT"]
model=os.environ["MODELS__CHAT__MODEL"]
key=os.environ["MODELS__CHAT__API_KEY"]
url=endpoint.rstrip("/")+"/chat/completions"
headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"}
body={"model":model,"messages":[{"role":"user","content":"ping"}],"max_tokens":8}
async def one(c):
    try:
        r=await c.post(url,headers=headers,json=body,timeout=60)
        return r.status_code
    except Exception as e:
        return f"ERR:{type(e).__name__}"
async def main():
    codes=collections.Counter()
    sem=asyncio.Semaphore(5)
    async with httpx.AsyncClient() as c:
        async def task():
            async with sem:
                return await one(c)
        t0=time.time()
        for code in await asyncio.gather(*[task() for _ in range(150)]):
            codes[code]+=1
    print(f"150 reqs in {time.time()-t0:.1f}s @ concurrency 5")
    print(dict(codes))
    n429=codes.get(429,0)
    print("OK: endpoint safe for full run" if n429==0 else f"FAIL: {n429} x 429 — 换端点再试")
asyncio.run(main())
PYEOF
```

## 5. 跑分顺序与命令

按 **01 → 03 → 04 → 02 → 05** 顺序（先快后慢，便于早发现环境问题）。
**01/03/05 不调 chat 模型（快，分钟级）；02/04 调 chat 模型（慢，各约 25–45 min）。**

每个 phase 都先 `source bench_chat.env`（对不调 chat 的 phase 也无害，统一流程）：

```
set -a; source benchmarks/bench_chat.env; set +a
python3 -m benchmarks.<module> 2>&1 | tee benchmarks/results/<NN>_run.log
```

| 顺序 | module | 写入文件 | 调 chat? | 大致耗时 |
|---|---|---|---|---|
| 01 | `retrieval_ab` | `results/01_retrieval_ab.{md,json}` | 否 | 分钟级 |
| 03 | `latency` | `results/03_latency.{md,json}` | 否 | 分钟级 |
| 04 | `routing_accuracy` | `results/04_routing.{md,json}` | 是 | ~26 min |
| 02 | `architecture_ab` | `results/02_architecture.{md,json}` | 是 | ~40 min |
| 05 | `scale_snapshot` | `results/05_scale.{md,json}` | 否 | 秒级 |

> 02/04 默认 `--concurrency 5`（`asyncio.Semaphore`），可改。02 每个 question 内 layered/flat 并发、judge 串行。
> 02 已含 per-question retry（与 04 同 backoff 30/60/120s、MAX_RETRIES=3）—— 瞬时空回复会自动重试恢复。

## 6. Constraints / gotchas

- **同一时间只能一个 benchmark 进程**：Qdrant 以本地 on-disk 模式跑（`QdrantClient(path=...)`），单进程锁。
  两个 session 并发会撞 `AlreadyLocked`。开跑前确认没有别的 benchmark 进程、也没有别的 Claude session 在用本 worktree。
- **mimo-v2.5-pro 是 reasoning 模型**，偶发空 content（吃光 max_tokens 预算）。02 现已 per-question retry（与 04 对齐），瞬时空回复自动恢复。
- **02 的 judge 是同一个 chat 模型**（self-judge 偏差，未控变量）—— 分数只作相对比较，绝对值意义有限。
- **03 延迟**：`HybridRetriever` 每次 query 调 `scroll_all_points()` 重建 BM25 语料（已知 perf bug，未修）——
  hybrid ~2.8s vs pure_vector ~0.12s。瓶颈在检索实现侧，非 embedding 侧。
- **结果为单次跑分（single run）**；要更稳的数字请跑 3 次取均值。

## 7. Results & interpretation

Canonical summary：`benchmarks/results/SUMMARY.md`。各 phase 细节在 `NN_*.{md,json}`。

当前基线（commit `d3f03a4`，mimo-v2.5-pro @ `https://fufu.iqach.top/v1`）：

- **01**：hybrid Recall@5 = **0.877** vs pure_vector 0.840（+3.70pp）；multi_hop 切片 n=10，R@5=0.225。
- **02**：Layered mean **4.688** vs Flat mean **4.854**，Δ = **−0.167**（基本打平）。
- **03**：hybrid p50 ≈ **2.76s**（mean 2759ms）/ pure_vector p50 118.9ms。
- **04**：overall accuracy **84.83%**（123/145）；refuse **0/9** —— agent 从不 refuse，是真实行为非分类器伪影。
- **05**：51 视频 / 50 文档 / 2040 chunks / 1024 dim COSINE；L2 summary 50/50 (100%)、L3 brief 50/50 (100%)。

## 8. Known eval-set blemishes

- summary 占 49/145 = **34%**，超过 `EVAL_SPEC.md` 目标的 15–20% —— summary 类过密，可能放大 02/04 中 summary 子集的权重。
- 4 道 unanswerable 题疑被误标为 `expected_route=refuse`：它们是 false-premise 题，正确行为是纠正前提（agent 确实这么做了），却被标成 refuse —— 04 的 refuse recall=0/9 部分由这 4 题贡献。详见 `SUMMARY.md` Findings #1。
- multi_hop 仅 10 题、R@5=0.225 —— 跨文档多跳对所有检索器都难，可能是题太难而非检索器太差。
