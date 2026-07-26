# 01 检索 A/B：混合 vs 纯向量 vs 纯 BM25

生成时间: 2026-07-24 03:56:05 UTC
Embedding: `Qwen/Qwen3-Embedding-0.6B` @ `http://localhost:8003/v1`
数据规模: 10 videos / 323 chunks / dim 1024
评测题: detail + non-empty relevant_chunks = **34** （跳过 summary/self；chunk 级 Recall/Precision/MRR 仅对 detail）
top_k 检索: 10；指标 k ∈ [5, 10]

## 配置

| name | impl | weights |
|------|------|---------|
| `hybrid` | HybridRetriever | `{"bm25": 0.3, "vector": 0.7}` |
| `pure_vector` | VectorRetriever | `—` |
| `pure_bm25` | HybridRetriever | `{"bm25": 1.0, "vector": 0.0}` |

## Headline：hybrid vs pure_vector（Recall@5）

- hybrid Recall@5 = **0.9510** (95.10%)
- pure_vector Recall@5 = **0.9412** (94.12%)
- **绝对提升** = 0.0098 (0.98% points)  |  **相对提升** = **1.04%**

## 宏平均指标（macro over questions）

| config | Recall@5 | Recall@10 | Precision@5 | Precision@10 | MRR |
|--------|----------|-----------|-------------|--------------|-----|
| `hybrid` | 0.9510 | 0.9902 | 0.3471 | 0.1853 | 0.9142 |
| `pure_vector` | 0.9412 | 0.9804 | 0.3529 | 0.1824 | 0.8905 |
| `pure_bm25` | 0.8039 | 0.8725 | 0.2882 | 0.1588 | 0.8086 |

## 切片：jargon / 专有名词倾向 vs general semantic

启发式：题干含英文技术缩写/产品名（PostgreSQL、MCP、GDP、API 等）或中英混排专有词 → jargon；否则 general。

| config | slice | n | Recall@5 | Recall@10 | Precision@5 | Precision@10 | MRR |
|--------|-------|---|----------|-----------|-------------|--------------|-----|
| `hybrid` | jargon | 22 | 0.9545 | 0.9848 | 0.3364 | 0.1773 | 0.9205 |
| `hybrid` | general | 12 | 0.9444 | 1.0000 | 0.3667 | 0.2000 | 0.9028 |
| `pure_vector` | jargon | 22 | 0.9242 | 0.9697 | 0.3364 | 0.1727 | 0.8838 |
| `pure_vector` | general | 12 | 0.9722 | 1.0000 | 0.3833 | 0.2000 | 0.9028 |
| `pure_bm25` | jargon | 22 | 0.8636 | 0.9545 | 0.3000 | 0.1682 | 0.8633 |
| `pure_bm25` | general | 12 | 0.6944 | 0.7222 | 0.2667 | 0.1417 | 0.7083 |

## 说明

- 命中定义：结果 `(document_id, chunk_index)` 与 ground-truth relevant_chunks 集合求交。
- 每次 search 使用 top_k=10；Recall/Precision@5 取排名前 5；MRR 基于 top-10 首个命中秩（无命中则 0）。
- pure_bm25 仍走 HybridRetriever（vector weight=0），实现上仍会 embed 查询，属实现细节。
- smoke embed dim 抽样: 1024；Qdrant points: 323
