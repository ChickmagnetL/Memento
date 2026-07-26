# 04 Agent 路由准确率

生成时间: 2026-07-24 04:32:37 UTC
Chat model: `gemini-3.5-flash` @ `https://api.42w.shop/v1`
Embedding: `Qwen/Qwen3-Embedding-0.6B` @ `http://localhost:8003/v1`
n = **48**（accuracy 分母含全部题；errors 计为 incorrect）
overall accuracy = **79.17%** (38/48)
n_errors = 0

## expected_route 分布

| route | n |
|-------|---|
| `search` | 34 |
| `lookup+summarize` | 10 |
| `memory` | 4 |

## 混淆矩阵（expected × predicted）

| expected \ predicted | `search` | `lookup+summarize` | `memory` |
|---|---|---|---|
| `search` | 27 | 0 | 7 |
| `lookup+summarize` | 1 | 9 | 0 |
| `memory` | 0 | 2 | 2 |

## 每类 Precision / Recall

| route | precision | recall | support |
|-------|-----------|--------|---------|
| `search` | 96.43% | 79.41% | 34 |
| `lookup+summarize` | 81.82% | 90.00% | 10 |
| `memory` | 22.22% | 50.00% | 4 |

## 失败用例

| id | question | expected | predicted | tools | error |
|----|----------|----------|-----------|-------|-------|
| q001 | 如果在GDP核算中采用支出法，其计算GDP的核心公式包含哪四个部分？ | `search` | `memory` | — | — |
| q002 | 根据世界银行估算，2024年中国按购买力平价（PPP）计算的GDP是多少万亿美元？ | `search` | `memory` | — | — |
| q003 | 为什么二手商品（如闲鱼上买卖二手自行车或二手房）的交易额不能算进GDP里？ | `search` | `memory` | — | — |
| q007 | 瑞士市值最高的三家公司中，属于医药行业的两家公司是哪两家？ | `search` | `memory` | — | — |
| q013 | What major shift does MCP introduce compared to tradition... | `lookup+summarize` | `search` | search_knowledge, search_knowledge | — |
| q021 | What are the four core properties that define SQL transac... | `search` | `memory` | — | — |
| q022 | What load balancing algorithm routes incoming traffic bas... | `search` | `memory` | — | — |
| q041 | Transformer 架构最早是由哪个团队在 2017 年提出的？ | `search` | `memory` | — | — |
| q046 | 我最近在 AI 与大模型工程（如 MCP 协议、Agent 和 Harness Engineering）方面学习了... | `memory` | `lookup+summarize` | lookup_documents, search_knowledge, lookup_documents, search_knowledge | — |
| q048 | 根据我学习过的数据库相关视频，我对 PostgreSQL 的哪些高级特性进行了了解？ | `memory` | `lookup+summarize` | lookup_documents, lookup_documents, summarize_document, search_knowledge, summarize_document, search_knowledge | — |

## Notes

- Seeded or reused profile memories for self questions (q045–q048).
- 3 docs may lack L2/L3 (增肌饮食 BV1ev411w7bs, GDP P-NmMX9rlYQ, 系统设计 oYxTTirKY8M); summary route still counts if lookup/summarize tools called.
- Route mapping: lookup_documents|summarize_document → lookup+summarize; else search_knowledge → search; else → memory. propose_memory ignored.
- Accuracy denominator = n_total (48); agent errors count as incorrect (predicted=error).
