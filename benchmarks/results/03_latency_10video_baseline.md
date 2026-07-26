# 03 检索延迟：hybrid vs pure_vector vs pure_bm25

生成时间: 2026-07-24 04:19:39 UTC
Embedding: `Qwen/Qwen3-Embedding-0.6B` @ `http://localhost:8003/v1`
数据规模: 10 videos / 323 chunks / dim 1024
评测题数: detail + non-empty relevant_chunks = **34**
N runs / query: **5**；top_k=**5**；warmup: **True**（每个 config 正式计时前 1 次不计时 search）
分位数: nearest-rank，`idx = round((p/100)*(n-1))`；聚合范围 = 全部 timed runs（queries × N）
Qdrant points: **323**

## 配置

| name | impl | weights |
|------|------|---------|
| `hybrid` | HybridRetriever | `{"bm25": 0.3, "vector": 0.7}` |
| `pure_vector` | VectorRetriever | `—` |
| `pure_bm25` | HybridRetriever | `{"bm25": 1.0, "vector": 0.0}` |

## Headline：hybrid 延迟

- hybrid mean / P50 / P95 = **532.8** / **528.5** / **565.6** ms
- pure_vector mean / P50 / P95 = **77.4** / **76.1** / **94.9** ms
- pure_bm25 mean / P50 / P95 = **529.7** / **526.0** / **551.0** ms

## 汇总表

| config | n_samples | mean_ms | p50_ms | p95_ms | min_ms | max_ms |
|--------|-----------|---------|--------|--------|--------|--------|
| `hybrid` | 170 | 532.8 | 528.5 | 565.6 | 506.2 | 677.1 |
| `pure_vector` | 170 | 77.4 | 76.1 | 94.9 | 61.7 | 107.5 |
| `pure_bm25` | 170 | 529.7 | 526.0 | 551.0 | 503.8 | 639.9 |

## 说明

- **已知瓶颈**：HybridRetriever 每次 query 会经 `scroll_all_points()` 重建 BM25 语料，hybrid / pure_bm25 延迟显著高于 pure_vector 属预期。
- **pure_bm25** 仍走 HybridRetriever（vector weight=0），实现上仍会 embed 查询。
- **E2E chat 延迟**：跳过。 原因：best-effort skip; flaky chat SSE not required for Phase 3; retrieval latency only
- smoke embed dim: 1024；Qdrant point count 校验: 323
