# Memento RAG 基准测试 · 结果总览（mimo-v2.5-pro baseline）

> 评测集：`benchmarks/eval_set.jsonl` v2（145 题 / 6 类型，50 视频全覆盖，frozen 2026-07-27，按 `EVAL_SPEC.md` 规范）。
> Chat 端点：`mimo-v2.5-pro` @ `https://fufu.iqach.top/v1`（`bench_chat.env`，gitignored）。
> Embedding：`Qwen/Qwen3-Embedding-0.6B` @ `http://localhost:8003/v1`（Apple Silicon GPU mps，batch64 ≈ 0.69s）。
> 语料：50 视频 / 50 文档 / 2040 chunks / 1024 dim（COSINE）。
> 跑分日期：embedding 类（01 / 03 / 05）= 2026-07-26；chat 类（02 / 04）= 2026-07-27。
> 本轮 02 启用 retry 修复、04 启用 reply-persistence 修复（详见各 phase Findings）。
> 单次跑分（single run），concurrency=5；02 含 retry（12 retries / 7 questions，全恢复）、04 reply 文本已持久化以备审计。

## 状态

- ✅ 5 个 phase 全部跑完，明细见 `01_retrieval_ab.md` / `02_architecture.md` / `03_latency.md` / `04_routing.md` / `05_scale.md`。
- 各 phase 的 .md headline 均与对应 .json 交叉核对一致（详见文末「一致性」）。

---

## 数据规模（05_scale，2026-07-26）

- 视频数：**51** / 文档数：**50**（50 个 video 有 document；metadata.db 多 1 条无 document 的 video 行）
- chunk 总数：**2040**（每文档 min 8 / mean 40.8 / max 189）
- 平均 chunk 字符数：**908**（min 190 / max 1761）
- 向量维度：**1024**（distance=COSINE）
- L2 summary 覆盖：**50/50（100%）**；L3 brief 覆盖：**50/50（100%）**

来源：`05_scale.md`

---

## 检索 A/B（01_retrieval_ab，2026-07-26）

- 单视频检索题（detail + multi_evidence，非空 relevant_chunks）：**72**（chunk 级 Recall/Precision/MRR）
- multi_hop 切片（跨文档金标）：**10**，单独报告
- top_k = 10

### Headline：hybrid vs pure_vector（Recall@5）

- hybrid **0.8773** vs pure_vector **0.8403** —— 绝对提升 **+0.0370**（3.70pp）/ 相对提升 **+4.41%**

### 宏平均（单视频，n=72）

| 配置 | Recall@5 | Recall@10 | Precision@5 | MRR |
|------|----------|-----------|-------------|-----|
| hybrid（默认） | **0.8773** | **0.9583** | 0.2194 | **0.7922** |
| pure_vector | 0.8403 | 0.9329 | 0.2111 | 0.7812 |
| pure_bm25 | 0.7731 | 0.8542 | 0.1889 | 0.6795 |

### multi_hop 切片（跨文档，n=10，单独报告）

| 配置 | Recall@5 | Recall@10 | MRR |
|------|----------|-----------|-----|
| hybrid | 0.2250 | 0.3033 | 0.4476 |
| pure_vector | 0.2750 | 0.3250 | 0.3893 |
| pure_bm25 | 0.3367 | 0.3817 | 0.6100 |

→ 跨文档多跳对所有检索器都难（R@5 普遍 < 0.35）；BM25 在专有名词锚点上最强。

来源：`01_retrieval_ab.md`

---

## 分层 vs 平铺（02_architecture，2026-07-27）

- 49 道 summary 题（`summary_eligible=true`），Layered（L2/L3 + lookup/summarize）vs Flat（L1 直检 + search_knowledge），LLM judge 1–5 分。
- scored = **48/49** | agent_errors = 0（retry 修复后 0 错误，详见 Findings #3）| judge_errors = 1（`q_summary_BV1ub421J7jv_01` HTTP 504）
- wall_time = 2397.5s（concurrency=5；含 12 retries / 7 questions，全恢复）

### Headline

- Layered mean = **4.688** vs Flat mean = **4.854**（Δ = **−0.167**）
- 上轮 Δ=−0.531 因 4 道 Layered 空回复（端点瞬时故障）被拉低；retry 修复后这 4 题全部恢复（1→5），真实 Δ=−0.167。

来源：`02_architecture.md`（score distribution / win-tie-loss 详见该文件）

---

## 延迟（03_latency，2026-07-26）

- 评测题：detail 53 题 × 5 runs × 3 配置（n_samples=265/config），top_k=5

| 配置 | mean (ms) | P50 (ms) | P95 (ms) |
|------|-----------|----------|----------|
| hybrid | 2759.4 | **2750.6** | 2843.7 |
| pure_vector | 121.6 | **118.9** | 152.6 |
| pure_bm25 | 2809.3 | **2773.2** | 2967.3 |

→ hybrid / bm25 的 ~2.7s 瓶颈来自 `HybridRetriever` 每次 query 调 `scroll_all_points()` 重建 BM25 语料；pure_vector 仅 ~120ms。**实现瓶颈，非 embedding 侧。**

来源：`03_latency.md`

---

## 路由准确率（04_routing，2026-07-27）

- n = **145**（accuracy 分母含全部题；errors 计为 incorrect），n_errors = 0
- overall accuracy = **84.83%**（123/145）
- wall_time = 1579.7s（concurrency=5；reply 文本已持久化以备审计）

### expected_route 分布

| route | n |
|-------|---|
| search | 82 |
| lookup+summarize | 49 |
| memory | 5 |
| refuse | 9 |

### 每类 Precision / Recall

| route | precision | recall | support |
|-------|-----------|--------|---------|
| search | 85.3% | 98.8% | 82 |
| lookup+summarize | 85.1% | 81.6% | 49 |
| memory | 100.0% | 40.0% | 5 |
| refuse | 0.0% | 0.0% | 9 |

→ refuse=0/9 是真实行为（非分类器伪影）：agent 总给 substantive 答案；详见 Findings #1。混淆矩阵见 `04_routing.md`。

来源：`04_routing.md`

---

## Findings（本轮基线暴露的 3 个真实问题）

1. **Agent 从不 refuse（refuse 0/9，真实行为非分类器伪影）**：Agent 总给 substantive 答案。9 道 unanswerable 中，5 题 agent 先承认语料缺该主题（"目前没有…的视频"）再转向相关/通用内容；4 题为 false-premise 题，agent 正确纠正前提（"你记反了"/"恰恰相反"）——这 4 题在 eval set 中可能被误标为 expected_route=refuse（正确行为应是纠正前提）。Reply 文本已持久化以备审计。
2. **9/49 summary 题被路由错（l+s FN=9，较上轮 13 下降）**：lookup+summarize 期望 49 题，9 题被 agent 路由为其他类型（具体去向见 `04_routing.md` 混淆矩阵）。Agent 对 summary 类问题的"先 lookup 再 summarize"工具链识别仍不够。
3. **Layered 4 道题空回复 → RESOLVED by retry fix**：上轮 `q_summary_2qf6ry-YjwU_01` / `q_summary_8BKbu_s8p1Q_01` / `q_summary_BV11o4y1s7VY_01` / `q_summary_ej6cygeB2X0_01` 4 题 Layered 空回复（端点瞬时故障 `Connection error` / `Request timed out`）拉低 Δ 至 −0.531。本轮启用 retry 后 0 agent errors，4 题全部恢复（1→5），真实 Δ=**−0.167**（即上轮 −0.531 部分由端点抖动膨胀，非架构差异本身）。12 retries / 7 questions，全恢复。

---

## Caveats

- **Single run**：本结果为单次跑分、单一端点（`mimo-v2.5-pro` @ `fufu.iqach.top`）基线；未做多样本次数取均值。02 含 retry（12 retries / 7 questions，全恢复），04 reply 文本已持久化以备审计。
- **Self-judge bias**：02 的 Layered vs Flat 由 LLM judge 1–5 打分，存在 self-judge 偏差（同模型既当运动员又当裁判）；分数仅作相对比较，绝对值意义有限。
- **Small-N**：memory 类 support=5、multi_hop 切片 n=10，小样本下 P/R/Recall 等指标波动大、置信度低。
- **Layered-inflation（已解决）**：上轮 4 道 Layered 空回复（端点瞬时故障）拉低 Δ 至 −0.531；本轮 retry 修复后 0 agent errors，真实 Δ=−0.167（上轮 −0.531 由端点抖动膨胀，非架构差异本身）。

---

## 一致性（.md headline ↔ .json）

- **01 retrieval_ab**：CONSISTENT（n=72 / n_multi_hop=10；hybrid / pure_vector / pure_bm25 三配置 15 个单视频 macro + 9 个 multi_hop 单元全匹配）。
- **02 architecture**：CONSISTENT（n_total=49 / n_scored=48 / n_agent_errors=0 / n_judge_errors=1（`q_summary_BV1ub421J7jv_01` HTTP 504）；layered_mean=4.688 / flat_mean=4.854 / Δ=−0.167；wall_time_s=2397.5；retry 12/7 全恢复，4 道原空回复 1→5。score dist / win-tie-loss 详见 `02_architecture.md`）。
- **04 routing**：CONSISTENT（n_total=145 / n_correct=123 / overall_accuracy=0.8483；per-route P/R/support 全匹配：search 85.3%/98.8%/82、lookup+summarize 85.1%/81.6%/49、memory 100%/40%/5、refuse 0%/0%/9；refuse TP=0 / support=9 / recall=0 → refuse=0/9；wall_time_s=1579.7；reply 文本已持久化。混淆矩阵详见 `04_routing.md`）。

---

## 备注

- 评测集 v2 较旧版（42 题 / 前 10 视频）覆盖更公平：detail 全库 50 视频，summary 全 eligible，新增 multi_hop / unanswerable / memory 题型。
- 检索 hybrid vs pure_vector 在新题集上区分度更大（+4.41% 相对，旧版仅 +1.94%），主要因新 detail 题反泄漏更严格 + 干扰库下公平覆盖。
- Embedding 服务跑 GPU（mps）后，推理 CPU 占用从 95% 降至 0.1%，batch64 推理 0.69s。
