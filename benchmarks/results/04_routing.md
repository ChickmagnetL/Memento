# 04 Agent 路由准确率

生成时间: 2026-07-27 09:02:31 UTC
Chat model: `mimo-v2.5-pro` @ `https://fufu.iqach.top/v1`
Embedding: `Qwen/Qwen3-Embedding-0.6B` @ `http://localhost:8003/v1`
n = **145**（accuracy 分母含全部题；errors 计为 incorrect）
overall accuracy = **84.83%** (123/145)
n_errors = 0

## expected_route 分布

| route | n |
|-------|---|
| `search` | 82 |
| `lookup+summarize` | 49 |
| `memory` | 5 |
| `refuse` | 9 |

## 混淆矩阵（expected × predicted）

| expected \ predicted | `search` | `lookup+summarize` | `memory` | `refuse` |
|---|---|---|---|---|
| `search` | 81 | 1 | 0 | 0 |
| `lookup+summarize` | 9 | 40 | 0 | 0 |
| `memory` | 1 | 1 | 2 | 1 |
| `refuse` | 4 | 5 | 0 | 0 |

## 每类 Precision / Recall

| route | precision | recall | support |
|-------|-----------|--------|---------|
| `search` | 85.26% | 98.78% | 82 |
| `lookup+summarize` | 85.11% | 81.63% | 49 |
| `memory` | 100.00% | 40.00% | 5 |
| `refuse` | 0.00% | 0.00% | 9 |

## 失败用例

| id | question | expected | predicted | tools | error |
|----|----------|----------|-----------|-------|-------|
| q_detail_b5H8D_wD2AY_01 | In this lecture on how central banks determine interest r... | `search` | `lookup+summarize` | search_knowledge, lookup_documents, search_knowledge, lookup_documents | — |
| q_summary_185XGEMefgc_01 | In the explainer that lays out MCP (Model Context Protoco... | `lookup+summarize` | `search` | search_knowledge, search_knowledge, search_knowledge, search_knowledge | — |
| q_summary_3ub8RBE7BC8_01 | In the Renaissance Periodization guide to gaining muscle ... | `lookup+summarize` | `search` | search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge | — |
| q_summary_64Zp3tzNbpE_01 | In MIT 6.824 Lecture 6 on fault tolerance with Raft for s... | `lookup+summarize` | `search` | search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge | — |
| q_summary_8BKbu_s8p1Q_01 | In the full day of eating that Jeff Nippard walks through... | `lookup+summarize` | `search` | search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge | — |
| q_summary_Cl0QYkez-BE_01 | In the 2011 Nobel Memorial Prize lectures by Thomas Sarge... | `lookup+summarize` | `search` | search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge | — |
| q_summary_PHe0bXAIuk0_01 | In Ray Dalio's roughly half-hour 'How the Economic Machin... | `lookup+summarize` | `search` | search_knowledge, search_knowledge, search_knowledge, search_knowledge | — |
| q_summary_RmVL30sS2yU_01 | In Daron Acemoglu's 2024 Nobel Prize lecture on inclusive... | `lookup+summarize` | `search` | search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge | — |
| q_summary_cQP8WApzIQQ_01 | MIT 6.824分布式系统课由Robert Morris主讲的那节开篇课——覆盖课程安排、并以MapReduce... | `lookup+summarize` | `search` | search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge | — |
| q_summary_wD48p6m8U-8_01 | In David Card's Sveriges Riksbank (Nobel) Prize lecture —... | `lookup+summarize` | `search` | search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge | — |
| q_unanswerable_global_01 | 操作系统做CPU调度的时候，具体用的是什么算法？比如是轮转调度还是优先级调度，视频里有讲过吗？ | `refuse` | `lookup+summarize` | search_knowledge, search_knowledge, search_knowledge, search_knowledge, lookup_documents, lookup_documents | — |
| q_unanswerable_global_02 | GFS那节课里说，Google的论文一开始就为了避免单点故障，设计了自动故障切换的多副本Master集群，对吗？具... | `refuse` | `search` | search_knowledge, search_knowledge, search_knowledge, search_knowledge | — |
| q_unanswerable_global_03 | Raft协议里，当节点的日志越攒越多时，是怎么做日志压缩（snapshot）来控制日志体积增长的？ | `refuse` | `lookup+summarize` | search_knowledge, search_knowledge, search_knowledge, lookup_documents, search_knowledge, lookup_documents, search_knowledge, lookup_documents, search_knowledge, lookup_documents, search_knowledge, search_knowledge | — |
| q_unanswerable_global_04 | 数据库为了让查询更快而建的索引，具体是靠什么样的树形数据结构（比如B树）来实现快速查找的？ | `refuse` | `search` | search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge | — |
| q_unanswerable_global_05 | 大模型在预训练阶段，具体是通过怎样的训练过程（比如损失函数、反向传播这些机制）一步步学会预测下一个词的？ | `refuse` | `lookup+summarize` | search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, lookup_documents, lookup_documents | — |
| q_unanswerable_global_06 | 如果训练目标是练力量（比如冲击个人最大重量PR），而不是单纯练维度，那训练量和组数安排该怎么调整？ | `refuse` | `search` | search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge | — |
| q_unanswerable_global_07 | 讲MCP和API区别的那期视频里说，MCP的目标就是要彻底取代传统API，以后开发者都不用再关心API了，对吗？ | `refuse` | `lookup+summarize` | search_knowledge, lookup_documents, search_knowledge, lookup_documents | — |
| q_unanswerable_global_08 | 讲Harness Engineering的那期视频里说，决定一个AI系统能不能稳定交付的核心其实是模型能力本身，外... | `refuse` | `lookup+summarize` | search_knowledge, lookup_documents, search_knowledge, lookup_documents | — |
| q_unanswerable_global_09 | 讲Dalio经济机器运作原理的那期视频里说，去杠杆的时候只要一直印钱扩大流动性就没什么风险、不会有副作用，对吗？ | `refuse` | `search` | search_knowledge, search_knowledge, search_knowledge, search_knowledge | — |
| q_memory_global_01 | 两周后就要面试了，按我之前跟你说过的复习进度，接下来这几天我应该优先补哪块内容？ | `memory` | `lookup+summarize` | search_knowledge, search_knowledge, lookup_documents, search_knowledge, search_knowledge, lookup_documents, summarize_document, summarize_document | — |
| q_memory_global_04 | 面试前最后这三天，你觉得我还要不要再看新的分布式系统相关视频，还是应该做别的事？ | `memory` | `refuse` | — | — |
| q_memory_global_05 | 我今晚下班已经很累了，还想抓紧再补一点分布式系统的内容，你觉得我现在适合看哪种视频？ | `memory` | `search` | search_knowledge, search_knowledge, search_knowledge, search_knowledge | — |

## Notes

- Memory route: 8 seed_memories from memory-type rows ensured in DB (idempotent insert); DB now has n=12.
- Route mapping: lookup_documents|summarize_document → lookup+summarize; else search_knowledge → search; else inspect reply text — refusal signal → refuse, otherwise memory. propose_memory ignored.
- Accuracy denominator = n_total (counts read live from eval_set.jsonl); agent errors count as incorrect (predicted=error).
- Corpus is 50-video; eval questions span all videos (per EVAL_SPEC §2).
- Bounded concurrency=5 via asyncio.Semaphore; no store lock — concurrent Qdrant/SQLite reads may race and reduce effective concurrency if the store is not concurrent-safe.
- Transient API retry: max_retries=3, backoff_s=[30, 60, 120], retryable_status=[429, 500, 502, 503, 504, 524]; inter-question sleep=1.5s.
- wall_time_s=1579.68, concurrency=5
