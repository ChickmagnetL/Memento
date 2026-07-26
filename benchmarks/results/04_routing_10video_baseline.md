# 04 Agent 路由准确率

生成时间: 2026-07-24 06:36:05 UTC
Chat model: `gemini-3.5-flash` @ `https://api.42w.shop/v1`
Embedding: `Qwen/Qwen3-Embedding-0.6B` @ `http://localhost:8003/v1`
n = **42**（accuracy 分母含全部题；errors 计为 incorrect）
overall accuracy = **88.10%** (37/42)
n_errors = 1

## expected_route 分布

| route | n |
|-------|---|
| `search` | 28 |
| `lookup+summarize` | 10 |
| `memory` | 4 |

## 混淆矩阵（expected × predicted）

| expected \ predicted | `search` | `lookup+summarize` | `memory` |
|---|---|---|---|
| `search` | 25 | 0 | 3 |
| `lookup+summarize` | 1 | 9 | 0 |
| `memory` | 0 | 0 | 3 |

另有 **1** 题 predicted=`error`/`null`（未计入矩阵单元格，计为 incorrect）。

## 每类 Precision / Recall

| route | precision | recall | support |
|-------|-----------|--------|---------|
| `search` | 96.15% | 89.29% | 28 |
| `lookup+summarize` | 100.00% | 90.00% | 10 |
| `memory` | 50.00% | 100.00% | 3 |

## 失败用例

| id | question | expected | predicted | tools | error |
|----|----------|----------|-----------|-------|-------|
| q002 | 根据世界银行估算，2024年中国按购买力平价（PPP）计算的GDP是多少万亿美元？ | `search` | `memory` | — | — |
| q003 | 为什么二手商品（如闲鱼上买卖二手自行车或二手房）的交易额不能算进GDP里？ | `search` | `memory` | — | — |
| q013 | What major shift does MCP introduce compared to tradition... | `lookup+summarize` | `search` | search_knowledge, search_knowledge | — |
| q043 | 在创建 Agent Skill 时，技能文件夹内部保存的核心指令文件名必须叫什么？ | `search` | `memory` | — | — |
| q048 | 根据我学习过的数据库相关视频，我对 PostgreSQL 的哪些高级特性进行了了解？ | `memory` | `error` | — | ModelHTTPError: status_code: 503, mod... |

## Notes

- Seeded or reused profile memories for self questions (q045–q048).
- 3 docs may lack L2/L3 (增肌饮食 BV1ev411w7bs, GDP P-NmMX9rlYQ, 系统设计 oYxTTirKY8M); summary route still counts if lookup/summarize tools called.
- Route mapping: lookup_documents|summarize_document → lookup+summarize; else search_knowledge → search; else → memory. propose_memory ignored.
- Accuracy denominator = n_total (48); agent errors count as incorrect (predicted=error).
