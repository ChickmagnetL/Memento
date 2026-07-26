# 03 检索延迟：hybrid vs pure_vector vs pure_bm25

生成时间: 2026-07-25 01:54:39 UTC
Embedding: `Qwen/Qwen3-Embedding-0.6B` @ `http://localhost:8003/v1`
数据规模: 50 videos / 2040 chunks / dim 1024
评测说明: eval_set detail 题仅覆盖前 10 个视频；当前语料为 50 视频（额外 40 为干扰噪声）
评测题数: detail + non-empty relevant_chunks = **28**
N runs / query: **5**；top_k=**5**；warmup: **True**（每个 config 正式计时前 1 次不计时 search）
分位数: nearest-rank，`idx = round((p/100)*(n-1))`；聚合范围 = 全部 timed runs（queries × N）
Qdrant points: **2040**

## 配置

| name | impl | weights |
|------|------|---------|
| `hybrid` | HybridRetriever | `{"bm25": 0.3, "vector": 0.7}` |
| `pure_vector` | VectorRetriever | `—` |
| `pure_bm25` | HybridRetriever | `{"bm25": 1.0, "vector": 0.0}` |

## Headline：hybrid 延迟

- hybrid mean / P50 / P95 = **2724.6** / **2716.4** / **2775.5** ms
- pure_vector mean / P50 / P95 = **81.5** / **79.9** / **97.1** ms
- pure_bm25 mean / P50 / P95 = **3190.3** / **3019.5** / **4233.9** ms

## 汇总表

| config | n_samples | mean_ms | p50_ms | p95_ms | min_ms | max_ms |
|--------|-----------|---------|--------|--------|--------|--------|
| `hybrid` | 140 | 2724.6 | 2716.4 | 2775.5 | 2684.1 | 3003.9 |
| `pure_vector` | 140 | 81.5 | 79.9 | 97.1 | 64.6 | 101.2 |
| `pure_bm25` | 140 | 3190.3 | 3019.5 | 4233.9 | 2713.0 | 5119.8 |

## 说明

- **已知瓶颈**：HybridRetriever 每次 query 会经 `scroll_all_points()` 重建 BM25 语料，hybrid / pure_bm25 延迟显著高于 pure_vector 属预期。
- **pure_bm25** 仍走 HybridRetriever（vector weight=0），实现上仍会 embed 查询。
- **E2E chat 延迟**：跳过。 原因：best-effort skip; flaky chat SSE not required for Phase 3; retrieval latency only
- smoke embed dim: 1024；Qdrant point count 校验: 2040
