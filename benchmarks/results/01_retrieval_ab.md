# 01 检索 A/B：混合 vs 纯向量 vs 纯 BM25

生成时间: 2026-07-25 01:37:05 UTC
Embedding: `Qwen/Qwen3-Embedding-0.6B` @ `http://localhost:8003/v1`
数据规模: 50 videos / 2040 chunks / dim 1024
评测说明: eval_set detail 题仅覆盖前 10 个视频；当前语料为 50 视频（额外 40 为干扰噪声）
评测题: detail + non-empty relevant_chunks = **28** （跳过 summary/self；chunk 级 Recall/Precision/MRR 仅对 detail）
top_k 检索: 10；指标 k ∈ [5, 10]

## 配置

| name | impl | weights |
|------|------|---------|
| `hybrid` | HybridRetriever | `{"bm25": 0.3, "vector": 0.7}` |
| `pure_vector` | VectorRetriever | `—` |
| `pure_bm25` | HybridRetriever | `{"bm25": 1.0, "vector": 0.0}` |

## Headline：hybrid vs pure_vector（Recall@5）

- hybrid Recall@5 = **0.9405** (94.05%)
- pure_vector Recall@5 = **0.9226** (92.26%)
- **绝对提升** = 0.0179 (1.79% points)  |  **相对提升** = **1.94%**

## 宏平均指标（macro over questions）

| config | Recall@5 | Recall@10 | Precision@5 | Precision@10 | MRR |
|--------|----------|-----------|-------------|--------------|-----|
| `hybrid` | 0.9405 | 0.9524 | 0.2643 | 0.1357 | 0.8690 |
| `pure_vector` | 0.9226 | 0.9524 | 0.2571 | 0.1357 | 0.8452 |
| `pure_bm25` | 0.8452 | 0.8690 | 0.2286 | 0.1214 | 0.7869 |

## 切片：jargon / 专有名词倾向 vs general semantic

启发式：题干含英文技术缩写/产品名（PostgreSQL、MCP、GDP、API 等）或中英混排专有词 → jargon；否则 general。

| config | slice | n | Recall@5 | Recall@10 | Precision@5 | Precision@10 | MRR |
|--------|-------|---|----------|-----------|-------------|--------------|-----|
| `hybrid` | jargon | 17 | 0.9216 | 0.9412 | 0.2471 | 0.1294 | 0.8824 |
| `hybrid` | general | 11 | 0.9697 | 0.9697 | 0.2909 | 0.1455 | 0.8485 |
| `pure_vector` | jargon | 17 | 0.9216 | 0.9412 | 0.2471 | 0.1294 | 0.8431 |
| `pure_vector` | general | 11 | 0.9242 | 0.9697 | 0.2727 | 0.1455 | 0.8485 |
| `pure_bm25` | jargon | 17 | 0.9020 | 0.9216 | 0.2353 | 0.1235 | 0.8549 |
| `pure_bm25` | general | 11 | 0.7576 | 0.7879 | 0.2182 | 0.1182 | 0.6818 |

## 说明

- 命中定义：结果 `(document_id, chunk_index)` 与 ground-truth relevant_chunks 集合求交。
- 每次 search 使用 top_k=10；Recall/Precision@5 取排名前 5；MRR 基于 top-10 首个命中秩（无命中则 0）。
- pure_bm25 仍走 HybridRetriever（vector weight=0），实现上仍会 embed 查询，属实现细节。
- smoke embed dim 抽样: 1024；Qdrant points: 2040
