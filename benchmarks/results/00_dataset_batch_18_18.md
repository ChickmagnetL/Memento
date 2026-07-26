# 00 数据集灌库报告

生成时间: 2026-07-24 14:21:29 UTC
BASE_URL: `http://127.0.0.1:8010`
范围: videos 18–18 (1-based, of 50 total)
模式: subtitle-only (NO ASR)
成功(含已就绪跳过): 0 / 1，失败: 1

| # | 标签 | 状态 | video_id | document_id | chunk_count | 错误/备注 |
|---|------|------|----------|-------------|-------------|-----------|
| 18 | 如何增肌 | failed | `3ub8RBE7BC8` | `f21f689cb37443c685d4100709b4bb19` | 0 | clean failed: clean failed: 502 {"detail":"Chat API failed: HTTP 500: sensitive_words_detected (request id: 202607241420479693831718268d9d63SCpnrMT)"}; index failed: index failed: 502 {"detail":"Embedding API failed: HTTP request failed: timed out"}; local_batch failed: Storage folder /Users/leo/development/memento/.claude/worktrees/rag-benchmarks/bench_data/qdrant is already accessed by another instance of Qdrant client. If you require concurrent access, use Qdrant server instead. |

## URL 清单

18. [如何增肌](https://www.youtube.com/watch?v=3ub8RBE7BC8)
