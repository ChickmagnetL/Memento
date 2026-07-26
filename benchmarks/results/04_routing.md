# 04 Agent 路由准确率

生成时间: 2026-07-25 03:03:06 UTC
Chat model: `gemini-3.1-pro` @ `https://api.42w.shop/v1`
Embedding: `Qwen/Qwen3-Embedding-0.6B` @ `http://localhost:8003/v1`
n = **42**（accuracy 分母含全部题；errors 计为 incorrect）
overall accuracy = **83.33%** (35/42)
n_errors = 0

## expected_route 分布

| route | n |
|-------|---|
| `search` | 28 |
| `lookup+summarize` | 10 |
| `memory` | 4 |

## 混淆矩阵（expected × predicted）

| expected \ predicted | `search` | `lookup+summarize` | `memory` |
|---|---|---|---|
| `search` | 25 | 2 | 1 |
| `lookup+summarize` | 1 | 9 | 0 |
| `memory` | 0 | 3 | 1 |

## 每类 Precision / Recall

| route | precision | recall | support |
|-------|-----------|--------|---------|
| `search` | 96.15% | 89.29% | 28 |
| `lookup+summarize` | 64.29% | 90.00% | 10 |
| `memory` | 50.00% | 25.00% | 4 |

## 失败用例

| id | question | expected | predicted | tools | error |
|----|----------|----------|-----------|-------|-------|
| q003 | 为什么二手商品（如闲鱼上买卖二手自行车或二手房）的交易额不能算进GDP里？ | `search` | `memory` | — | — |
| q008 | 瑞士的教育体系采取了什么制度，使得三分之二的学生在完成九年义务教育后直接进入企业当学徒？ | `search` | `lookup+summarize` | lookup_documents, lookup_documents, search_knowledge, search_knowledge | — |
| q013 | What major shift does MCP introduce compared to tradition... | `lookup+summarize` | `search` | search_knowledge, search_knowledge | — |
| q036 | 作者帮助朋友将 Agent 任务成功率从不到 70% 提升到 95% 以上，改进的关键点在于什么？ | `search` | `lookup+summarize` | search_knowledge, search_knowledge, search_knowledge, search_knowledge, lookup_documents, lookup_documents, summarize_document, summarize_document, search_knowledge, search_knowledge | — |
| q045 | 根据我最近看过的视频，我的主要学习兴趣和关注领域有哪些？ | `memory` | `lookup+summarize` | lookup_documents, lookup_documents | — |
| q046 | 我最近在 AI 与大模型工程（如 MCP 协议、Agent 和 Harness Engineering）方面学习了... | `memory` | `lookup+summarize` | lookup_documents, search_knowledge, lookup_documents, search_knowledge | — |
| q048 | 根据我学习过的数据库相关视频，我对 PostgreSQL 的哪些高级特性进行了了解？ | `memory` | `lookup+summarize` | lookup_documents, lookup_documents, summarize_document, search_knowledge, summarize_document, search_knowledge | — |

## Notes

- Seeded or reused profile memories for self questions (q045–q048).
- 3 docs may lack L2/L3 (增肌饮食 BV1ev411w7bs, GDP P-NmMX9rlYQ, 系统设计 oYxTTirKY8M); summary route still counts if lookup/summarize tools called.
- Route mapping: lookup_documents|summarize_document → lookup+summarize; else search_knowledge → search; else → memory. propose_memory ignored.
- Accuracy denominator = n_total (42: detail 28, summary 10, self 4); agent errors count as incorrect (predicted=error).
- Corpus is 50-video with noise docs; eval questions target first-10 videos only.
- Bounded concurrency=5 via asyncio.Semaphore; no store lock — concurrent Qdrant/SQLite reads may race and reduce effective concurrency if the store is not concurrent-safe.
- Transient API retry: max_retries=3, backoff_s=[30, 60, 120], retryable_status=[429, 500, 502, 503, 504, 524]; inter-question sleep=1.5s.
- wall_time_s=197.66, concurrency=5
