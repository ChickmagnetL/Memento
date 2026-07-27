# 03 检索延迟：hybrid vs pure_vector vs pure_bm25

生成时间: 2026-07-26 20:13:38 UTC
Embedding: `Qwen/Qwen3-Embedding-0.6B` @ `http://localhost:8003/v1`
数据规模: 50 videos / 2040 chunks / dim 1024
评测说明: detail 题（非空 relevant_chunks）覆盖全 50 个视频的语料范围，用于测量各 retriever 配置在当前库规模下的检索延迟分布。
评测题数: detail + non-empty relevant_chunks = **53**
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

- hybrid mean / P50 / P95 = **2759.4** / **2750.6** / **2843.7** ms
- pure_vector mean / P50 / P95 = **121.6** / **118.9** / **152.6** ms
- pure_bm25 mean / P50 / P95 = **2809.3** / **2773.2** / **2967.3** ms

## 汇总表

| config | n_samples | mean_ms | p50_ms | p95_ms | min_ms | max_ms |
|--------|-----------|---------|--------|--------|--------|--------|
| `hybrid` | 265 | 2759.4 | 2750.6 | 2843.7 | 2712.7 | 2917.8 |
| `pure_vector` | 265 | 121.6 | 118.9 | 152.6 | 93.8 | 185.9 |
| `pure_bm25` | 265 | 2809.3 | 2773.2 | 2967.3 | 2710.8 | 3761.4 |

## 说明

- **已知瓶颈**：HybridRetriever 每次 query 会经 `scroll_all_points()` 重建 BM25 语料，hybrid / pure_bm25 延迟显著高于 pure_vector 属预期。
- **pure_bm25** 仍走 HybridRetriever（vector weight=0），实现上仍会 embed 查询。
- **E2E chat 延迟**：跳过。 原因：best-effort skip; flaky chat SSE not required for Phase 3; retrieval latency only
- smoke embed dim: 1024；Qdrant point count 校验: 2040
