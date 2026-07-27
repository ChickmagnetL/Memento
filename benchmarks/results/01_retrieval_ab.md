# 01 检索 A/B：混合 vs 纯向量 vs 纯 BM25

生成时间: 2026-07-26 19:48:18 UTC
Embedding: `Qwen/Qwen3-Embedding-0.6B` @ `http://localhost:8003/v1`
数据规模: 50 videos / 2040 chunks / dim 1024
评测说明: 单视频检索题（detail + multi_evidence）覆盖全 50 个视频；multi_hop 单独切片报告（金标跨 ≥2 个文档）。
单视频检索题 (detail + multi_evidence, 非空 relevant_chunks): **72**（chunk 级 Recall/Precision/MRR）
multi_hop 切片题 (跨文档金标): **10**（单独报告）
top_k 检索: 10；指标 k ∈ [5, 10]

## 配置

| name | impl | weights |
|------|------|---------|
| `hybrid` | HybridRetriever | `{"bm25": 0.3, "vector": 0.7}` |
| `pure_vector` | VectorRetriever | `—` |
| `pure_bm25` | HybridRetriever | `{"bm25": 1.0, "vector": 0.0}` |

## Headline：hybrid vs pure_vector（Recall@5）

- hybrid Recall@5 = **0.8773** (87.73%)
- pure_vector Recall@5 = **0.8403** (84.03%)
- **绝对提升** = 0.0370 (3.70% points)  |  **相对提升** = **4.41%**

## 宏平均指标（macro over questions）

| config | Recall@5 | Recall@10 | Precision@5 | Precision@10 | MRR |
|--------|----------|-----------|-------------|--------------|-----|
| `hybrid` | 0.8773 | 0.9583 | 0.2194 | 0.1236 | 0.7922 |
| `pure_vector` | 0.8403 | 0.9329 | 0.2111 | 0.1194 | 0.7812 |
| `pure_bm25` | 0.7731 | 0.8542 | 0.1889 | 0.1069 | 0.6795 |

## 切片：jargon / 专有名词倾向 vs general semantic

启发式：题干含英文技术缩写/产品名（PostgreSQL、MCP、GDP、API 等）或中英混排专有词 → jargon；否则 general。

| config | slice | n | Recall@5 | Recall@10 | Precision@5 | Precision@10 | MRR |
|--------|-------|---|----------|-----------|-------------|--------------|-----|
| `hybrid` | jargon | 11 | 0.9091 | 0.9545 | 0.2364 | 0.1273 | 0.8818 |
| `hybrid` | general | 61 | 0.8716 | 0.9590 | 0.2164 | 0.1230 | 0.7761 |
| `pure_vector` | jargon | 11 | 0.8636 | 0.9091 | 0.2182 | 0.1182 | 0.8615 |
| `pure_vector` | general | 61 | 0.8361 | 0.9372 | 0.2098 | 0.1197 | 0.7667 |
| `pure_bm25` | jargon | 11 | 0.8636 | 0.9091 | 0.2182 | 0.1182 | 0.8766 |
| `pure_bm25` | general | 61 | 0.7568 | 0.8443 | 0.1836 | 0.1049 | 0.6440 |

## multi_hop 切片（跨文档金标，单独报告，不计入上面的单视频 macro）

| config | n | Recall@5 | Recall@10 | MRR |
|--------|---|----------|-----------|-----|
| `hybrid` | 10 | 0.2250 | 0.3033 | 0.4476 |
| `pure_vector` | 10 | 0.2750 | 0.3250 | 0.3893 |
| `pure_bm25` | 10 | 0.3367 | 0.3817 | 0.6100 |

## 说明

- 命中定义：结果 `(document_id, chunk_index)` 与 ground-truth relevant_chunks 集合求交。
- 每次 search 使用 top_k=10；Recall/Precision@5 取排名前 5；MRR 基于 top-10 首个命中秩（无命中则 0）。
- pure_bm25 仍走 HybridRetriever（vector weight=0），实现上仍会 embed 查询，属实现细节。
- 单视频 macro = detail + multi_evidence 的题级宏平均；multi_hop 因跨 ≥2 文档，单独切片报告（金标按各 chunk 自身 document_id 计 key，单侧命中也能正确计分）。
- smoke embed dim 抽样: 1024；Qdrant points: 2040
