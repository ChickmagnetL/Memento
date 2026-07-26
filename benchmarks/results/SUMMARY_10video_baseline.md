# Memento RAG 基准测试 · 结果总览

- 数据规模：10 视频 / 10 文档 / 323 chunk / 评测集 **42** 题（Fix A 后）
- 运行时间：重跑 2026-07-24 05:59–06:56 UTC；模型：embedding=`Qwen/Qwen3-Embedding-0.6B`，chat=`gemini-3.5-flash`
- 评测集：detail **28** 题, summary 10 题, self 4 题
- 基线备份：`*_pre_fix.md` / `*_pre_fix.json` / `SUMMARY_pre_fix.md`

## 检索 A/B（Recall@5 / Recall@10 / MRR）

| 配置 | Recall@5 | Recall@10 | MRR |
|------|---------|-----------|-----|
| 纯向量 | 94.05% | 96.43% | 0.8631 |
| 纯 BM25 | 85.71% | 90.48% | 0.7914 |
| 混合(默认) | 94.05% | 100.00% | 0.8929 |

→ 混合相对纯向量 Recall@5 提升：**+0.00%**（绝对 +0.00pp）；R@10 混合仍更高（100% vs 96.43%），MRR 混合更高（0.8929 vs 0.8631）

## 分层 vs 平铺（总结类问题完整度 1–5 分）

- Flat 均分：3.20 / Layered 均分：3.10 / 提升 **−0.10**
- Layered 胜率：**40%**（平局 30%，负 30%；4 win / 3 tie / 3 loss）

## 路由准确率

- 总准确率：**88.10%**（37/42）；detail **89.29%**（25/28）, summary **90.00%**（9/10）, self **75.00%**（3/4）
- n_errors = 1（q048 上游 503，计 incorrect）

## 延迟（ms）

- 检索(混合) P50/P95：528.5 / 565.6；端到端首 token / 完整：跳过 / 跳过
- 对照：纯向量 P50/P95 76.1 / 94.9；纯 BM25 526.0 / 551.0（hybrid 均值约 7× 纯向量）
- （本轮未重跑延迟；沿用 Fix 前 03_latency 结果）

## 规模快照

- chunk/文档 比：32.3（min 8 / max 189）；L2/L3 覆盖率：**100%**（10/10）；向量维度：1024

## 备注 / 已知问题

### Fix A — 评测集数据质量

- 操作：移除 6 题（常识/弱 grounding）、重标 8 题 GT、重写 1 题 → **48 → 42** 题（detail 34→28，summary 10，self 4）
- 备份：`benchmarks/eval_set.jsonl.pre_fix_a`；审计：`benchmarks/results/fix_a_audit.json`；脚本：`benchmarks/fix_eval_set.py`
- 目标：去掉「仅靠世界知识可答」的 search 题，并收紧 detail 的 relevant_chunks

### Fix B — L2/L3 覆盖

- 对 3 篇 raw 索引文档（增肌饮食 / GDP / 系统设计 2h）回填 summary + brief → L2/L3 **70% → 100%**
- 规模快照见 `05_scale.md`（2026-07-24 05:54 UTC）
- 注意：`architecture_ab.py` 仍硬编码旧的 `docs_lacking_l2_l3` 标签用于报告标注；SQLite 实际已 100% 覆盖

### 修复前后 Headline 对比

| 指标 | Fix 前 | Fix 后 | 变化 |
|------|--------|---------|------|
| 评测集题数 | 48（detail 34） | 42（detail 28） | −6 |
| 混合 R@5 | 95.10% | 94.05% | −1.05pp |
| 纯向量 R@5 | 94.12% | 94.05% | −0.07pp |
| 混合相对纯向量 R@5 | +1.04% | +0.00% | 持平 |
| 混合 R@10 | 99.02% | 100.00% | +0.98pp |
| 纯向量 R@10 | 98.04% | 96.43% | −1.61pp |
| Layered 均分 | 3.70 | 3.10 | −0.60 |
| Flat 均分 | 3.50 | 3.20 | −0.30 |
| Layered − Flat | +0.20 | −0.10 | 反转 |
| Layered 胜率 | 30% | 40% | +10pp |
| 路由总准确率 | 79.17%（38/48） | 88.10%（37/42） | +8.93pp |
| detail 路由 | 79.41% | 89.29% | +9.88pp |
| summary 路由 | 90.00% | 90.00% | 持平 |
| self 路由 | 50.00% | 75.00% | +25pp |
| L2/L3 覆盖 | 70%（7/10） | 100%（10/10） | +30pp |

### 其他已知问题（仍成立）

- B 站 5 条视频无软字幕，走 ASR fallback 灌库。
- 混合检索 R@5 与纯向量持平（Fix 后均 ≈94%），但混合在 R@10 / MRR 仍略优；jargon 切片上两者 R@5 同为 92.16%，general 同为 96.97%；BM25 在 jargon 上仍强（R@5 90.20% vs general 78.79%）。
- 混合检索延迟约 7× 纯向量：HybridRetriever 每次 query 经 `scroll_all_points()` 重建 BM25 语料，属已知实现瓶颈。
- 端到端 chat 延迟（首 token / 完整回复）本轮跳过，仅测检索层。
- 路由：Fix A 去掉常识题后 search 路由明显改善；仍有少量 search→memory 误判（q002/q003/q043）；self n=4 波动大；本轮 q048 因上游 503 计 incorrect。
- 架构：L2/L3 补齐后 Layered 胜率升至 40%，但均分未超过 Flat（3.10 vs 3.20）。模糊「这期视频讲什么」类题仍易错绑/幻觉（q004/q035/q040 低分）；Layered 在 lookup 成功但 summarize 内容不对时仍会低分。
- 向量维度实测为 **1024**（Qwen3-Embedding-0.6B smoke），非 768。
