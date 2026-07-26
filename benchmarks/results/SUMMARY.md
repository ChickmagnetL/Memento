# Memento RAG 基准测试 · 结果总览

- 数据规模：**50** 视频 / **50** 文档 / **2040** chunk / 评测集 **42** 题
- 运行时间：2026-07-25（Phase1/3/5 约 01:37–01:54 UTC；Phase4 03:03 UTC；Phase2 03:12 UTC）；模型：embedding=`Qwen/Qwen3-Embedding-0.6B`，chat=`gemini-3.1-pro`
- 评测集：detail **28** 题, summary **10** 题, self **4** 题
- **评测题仅前 10 视频；语料 50 视频（后 40 为干扰）**
- 10 视频基线备份：`*_10video_baseline.{md,json}` / `SUMMARY_10video_baseline.md`（未覆盖）

## 检索 A/B（Recall@5 / Recall@10 / MRR）

| 配置 | Recall@5 | Recall@10 | MRR |
|------|---------|-----------|-----|
| 纯向量 | 0.9226 | 0.9524 | 0.8452 |
| 纯 BM25 | 0.8452 | 0.8690 | 0.7869 |
| 混合(默认) | 0.9405 | 0.9524 | 0.8690 |

→ 混合相对纯向量 Recall@5 提升：**+1.94%**（绝对 +0.0179 / +1.79pp）

来源：`01_retrieval_ab.md`（2026-07-25 01:37:05 UTC；50 videos / 2040 chunks / dim 1024；detail n=28）

## 分层 vs 平铺（总结类问题完整度 1–5 分）

- Flat 均分：**2.900** / Layered 均分：**3.500** / 提升 **+0.600**
- Layered 胜率：**30%**（3 win / 5 tie / 2 loss）
- wall_time：**75.4s**；concurrency=**5**；agent_errors=0；judge_errors=0
- 模型：chat/judge=`gemini-3.1-pro`

来源：`02_architecture.md`（2026-07-25 03:12:16 UTC；summary n=10）

## 路由准确率

- 总准确率：**83.33%**（35/42）；detail **89.29%**（25/28）, summary **90.00%**（9/10）, self **25.00%**（1/4）
- n_errors = **0**
- wall_time：**197.7s**；concurrency=**5**
- per-class recall：search 89.29% / lookup+summarize 90.00% / memory 25.00%
- 主要失败：search→memory/lookup 误判（q003/q008/q036）；self→lookup 误判（q045/q046/q048）；summary→search（q013）
- 备注：q036 曾触发 `sensitive_words_detected`（500），经 `agent_run_with_retry` 重试后完成

来源：`04_routing.md`（2026-07-25 03:03:06 UTC；n=42；chat=`gemini-3.1-pro`）

## 延迟（ms）

- 检索(混合) P50/P95：**2716.4 / 2775.5**；端到端首 token / 完整：**跳过 / 跳过**
- 对照：纯向量 P50/P95 **79.9 / 97.1**；纯 BM25 **3019.5 / 4233.9**
- hybrid mean ≈ 2724.6 ms（约 33× 纯向量）；已知瓶颈：HybridRetriever 每次 query `scroll_all_points()` 重建 BM25 语料

来源：`03_latency.md`（2026-07-25 01:54:39 UTC；28 queries × 5 runs；top_k=5）

## 规模快照

- chunk/文档 比：约 **40.8**（min 8 / max 189；points 2040 / docs 50）
- L2/L3 覆盖率：**12/50（24.0%）**（前 10 评测视频文档已覆盖 L2/L3；后 40 干扰文档多数无 summary）
- 向量维度：**1024**
- 说明：scale 文件视频计数可能显示 51，但索引语料为 **50 docs / 50 videos**

来源：`05_scale.md`（2026-07-25 01:40:00 UTC）

## 备注 / 已知问题

- **评测题仅前 10 视频；语料 50 视频（后 40 为干扰噪声）**，用于观察干扰下的检索/路由/总结表现。
- Phase 4/2 已用 **concurrency=5** 重跑；`routing_accuracy` 并发路径经 `agent_run_with_retry` 处理 429/5xx/524；未见需降到 concurrency=3 的锁冲突。
- 混合检索 R@5 在 50 库干扰下仍略优于纯向量（+1.94% 相对），R@10 两者持平 0.9524；BM25 在 jargon 切片仍相对强。
- 混合检索延迟显著高于纯向量（P50 ~2.7s vs ~80ms），属实现瓶颈而非 embedding 侧。
- 端到端 chat 延迟本轮跳过。
- 路由：detail/summary 仍高（~89–90%）；self 路由在本轮 gemini-3.1-pro 下偏弱（1/4），多误走 lookup/search。
- 架构：本轮 Layered 均分与胜率均优于 Flat（3.50 vs 2.90；胜率 30%，平局 50%）。部分 summary 题仍错绑视频（judge 给 1 分）。
- L2/L3 全库覆盖仅 24%（12/50）；`architecture_ab` 仍硬编码旧的 3 个 lacks 标签用于标注，与 SQLite 实际可能不完全一致。
- 上游网关偶发 `sensitive_words_detected`（HTTP 500）与 5xx；Phase4 靠 retry 消化；Phase2 本轮 agent/judge 无 error。
- 向量维度实测 **1024**（Qwen3-Embedding-0.6B）。
- 无 secrets 写入报告。
