# Memento RAG 性能基准测试套件

## 0. 这是什么

为 Memento 的检索与对话问答管线建立一套**可复现的性能基准**。用途：

1. **回归基准**：今后任何对检索 / 分层架构 / Agent 的优化，都能用这套基准量化"改前 vs 改后"。
2. **架构选型依据**：用数据回答"混合检索 vs 单路检索""分层 vs 平铺"到底差多少。
3. 作为正式的工程产物，代码可合回 `main`，长期维护。

> 全程按"应用性能基准测试"来做。所有脚本放 `benchmarks/`，结果放 `benchmarks/results/`。

---

## 1. 执行原则（必读）

- **不修改 core 代码**。若某个基准必须改动 core 才能跑（例如构造"平铺"Agent 变体），把改动记在 `benchmarks/CHANGES.md`，并尽量以"可选开关 / 参数注入"方式实现，而非硬改。
- **每个数字都可复现**：记录数据规模、模型版本、权重配置、运行次数、时间戳。
- **直接 import 模块，不走 HTTP**（除非该基准明确要求端到端）。检索 / Agent 相关基准通过 `from core.rag... / from core.agent...` 直接调用，干净且无网络噪声。
- 每个脚本可独立运行（`python -m benchmarks.xxx`），并能输出结构化结果（同时写 `.md` 给人看、`.json` 给程序读）。

---

## 2. 被测系统速览（代码位置，省得你重新找）

| 概念 | 实现位置 | 说明 |
|---|---|---|
| 混合检索（BM25+向量+RRF） | `backend/core/rag/retrieval.py` `HybridRetriever` | 权重 `weights={"bm25":0.3,"vector":0.7}`，`search(query, top_k)` |
| 纯向量检索 | `backend/core/rag/retrieval.py` `VectorRetriever` | 真·纯向量基线（不跑 BM25） |
| RRF 融合 | `backend/core/rag/fusion.py` `rrf_fuse(k=60)` | |
| 中文分词（jieba） | `backend/core/rag/tokenize.py` `tokenize()` | BM25 用 |
| 三层文档 | L1=原文 chunk（Qdrant `documents`）/ L2=段落总结（SQLite `document_summaries.l2`）/ L3=一句话摘要（SQLite `l3` + Qdrant `document_summaries`） | `backend/core/rag/document_summary_store.py` |
| 对话 Agent + 工具 | `backend/core/agent/chat_agent.py` `build_agent(model)` | 三个工具：`search_knowledge`(L1) / `lookup_documents`(L3) / `summarize_document`(L2)；路由规则在 `SYSTEM_PROMPT` |
| 路由 system prompt | `backend/core/agent/chat_agent.py` `SYSTEM_PROMPT` | 规定了"细节问题→search / 总结类→lookup+summarize / 关于用户自己→memory" |
| 配置 | `backend/config/settings.py` `RAGConfig` | `top_k=5`、`hybrid_weights={"bm25":0.3,"vector":0.7}`、`chunk_size=800`、`overlap=80`、`vector_size=768` |
| 视频导入 API | `POST /api/videos`（建）+ `POST /api/videos/{id}/process`（抽取+索引） | `backend/api/videos.py` |
| 检索 API | `POST /api/search` `{query, top_k}` | `backend/api/search.py` |
| 对话 API | `POST /api/chat`（SSE） | `backend/api/chat.py` |
| Qdrant 存储 | `backend/storage/qdrant_client.py` `QdrantStore` | `scroll_all_points()`、`search_points()`、`search_summaries()` |
| 模型工厂 | `backend/core/models/factory.py` | `build_embedding_client()` / `build_chat_completion_client()`（OpenAI 兼容接口） |

---

## 3. 环境准备

1. **Python 环境**：用 `backend/venv`（已存在）。所有脚本从 `backend/` 目录运行，保证 `from core...` / `from config...` 可导入。
2. **Embedding 服务必须可用**：检索依赖向量。确认 `build_embedding_client()` 能成功 embed（调用一次 `embed(["ping"])` 不报错）。若是本地服务（如 localhost 的 OpenAI 兼容 server），先把它跑起来；若是云，确认 api_key 配好。**embedding 不可用 = 所有检索类基准作废**，必须先解决。
3. **Chat 模型必须可用**：Phase 2 / 4 需要 Agent 跑 LLM。确认 `build_chat_completion_client()` 可用。
4. **数据目录隔离**（重要）：用一个**专属的干净数据目录**跑基准，避免与既有数据混淆。运行前设：
   
   ```bash
   export STORAGE__DATA_DIR="$(pwd)/bench_data"
   ```
   （`STORAGE__DATA_DIR` 是 settings.py 支持的 env 覆盖。）这样 Qdrant / SQLite 都落在 `bench_data/`，与主仓库分离，跑完可整目录删除。
5. **ASR 可选**：尽量挑**自带字幕**的视频（B 站 / YouTube 大多有），避免把 ASR 纳入基准变量。只有当某视频无字幕时才走 ASR，并在数据集里标注。

> 先跑一个 smoke：`python -c "from core.models.factory import build_embedding_client as b; print(b().embed(['hello'])[0][:5])"` 能打印向量即 embedding 链路通。

---

## 4. ⚠️ 执行前请填写：测试视频清单

| # | 平台 | 链接 | 是否有字幕 | 备注（主题/时长） |
|---|---|---|---|---|
| 1 | B 站 | https://www.bilibili.com/video/BV1FUYQz7E4H/? | 有 | PostgreSQL数据库 / 22分钟 |
| 2 | B 站 | https://www.bilibili.com/video/BV14v4y1G7A3/? | 有 | 凯圣王一分化新手入门 |
| 3 | B 站 | https://www.bilibili.com/video/BV1ev411w7bs/? | 有 | 增肌饮食思路 |
| 4 | B 站 | https://www.bilibili.com/video/BV1Zk9FBwELs/? | 有 | harness 是什么 |
| 5 | B 站 | https://www.bilibili.com/video/BV1E7wtzaEdq/? | 有 | AI 名词解释 |
| 6 | YouTube | https://www.youtube.com/watch?v=P-NmMX9rlYQ | 有 | 了解 GDP |
| 7 | YouTube | https://www.youtube.com/watch?v=-HOzOBmQ5ro | 有 | 瑞士经济 |
| 8 | YouTube | https://www.youtube.com/watch?v=185XGEMefgc | 有 | MCP VS API |
| 9 | YouTube | https://www.youtube.com/watch?v=vkpS7WztTMc | 有 | 苏姿丰演讲 |
| 10 | YouTube | https://www.youtube.com/watch?v=oYxTTirKY8M | 有 | 系统设计/2 小时 |
| 11 | YouTube | https://www.youtube.com/watch?v=ej6cygeB2X0 | 有 | 行为经济学 Nobel 讲座 Thaler / ~35min |
| 12 | YouTube | https://www.youtube.com/watch?v=Cl0QYkez-BE | 有 | 货币政策 Nobel 讲座 Sims & Sargent / ~47min |
| 13 | YouTube | https://www.youtube.com/watch?v=iQyg-KypKAA | 有 | L8 Principal's Agentic Engineering Workflow |
| 14 | YouTube | https://www.youtube.com/watch?v=oKM-L_WiOhg | 有 | 特斯拉財報後股價暴跌15%，一切都結束了？ |
| 15 | YouTube | https://www.youtube.com/watch?v=cQP8WApzIQQ | 有 | MIT 6.824 分布式系统 L1: Introduction / 1h20m |
| 16 | YouTube | https://www.youtube.com/watch?v=EpIgvowZr00 | 有 | MIT 6.824 分布式系统 L3: GFS / 1h22m |
| 17 | YouTube | https://www.youtube.com/watch?v=64Zp3tzNbpE | 有 | MIT 6.824 分布式系统 L6: Raft / 1h20m |
| 18 | YouTube | https://www.youtube.com/watch?v=3ub8RBE7BC8 | 有 | 增肌科学：如何增肌 / 34min（干扰：健身） |
| 19 | YouTube | https://www.youtube.com/watch?v=2qf6ry-YjwU | 有 | 自然健美赛前峰值与备赛 / 41min（干扰：健身） |
| 20 | YouTube | https://www.youtube.com/watch?v=cfXTQmFRjWU | 有 | 训练组数与容量科学 / 26min（干扰：健身） |
| 21 | YouTube | https://www.youtube.com/watch?v=lu_BObG6dj8 | 有 | 增肌五级解释 progressive overload / 22min（干扰：健身） |
| 22 | YouTube | https://www.youtube.com/watch?v=ZlVBSZYaVF0 | 有 | 个人 hypertrophy volume（MEV/MAV/MRV）/ 22min（干扰：健身） |
| 23 | YouTube | https://www.youtube.com/watch?v=8BKbu_s8p1Q | 有 | 增肌减脂饮食 lean bulking / 18min（干扰：营养） |
| 24 | YouTube | https://www.youtube.com/watch?v=NS_GeXoboo4 | 有 | 低预算健康增肌饮食 / 18min（干扰：营养） |
| 25 | YouTube | https://www.youtube.com/watch?v=RmVL30sS2yU | 有 | Nobel 2024 Acemoglu 制度与长期繁荣 / 36min（干扰：经济） |
| 26 | YouTube | https://www.youtube.com/watch?v=-lcgyCG-olg | 有 | Nobel 2023 Goldin 性别与劳动力市场 / 31min（干扰：经济） |
| 27 | YouTube | https://www.youtube.com/watch?v=BBCp28YF-hg | 有 | Nobel 2022 Bernanke 银行与危机 / 32min（干扰：经济） |
| 28 | YouTube | https://www.youtube.com/watch?v=31YTH1ywbS8 | 有 | Nobel 2022 Diamond 金融中介与流动性 / 36min（干扰：经济） |
| 29 | YouTube | https://www.youtube.com/watch?v=XvyMO7CmFlk | 有 | Nobel 2019 Banerjee 减贫实验方法 / 34min（干扰：经济） |
| 30 | YouTube | https://www.youtube.com/watch?v=wD48p6m8U-8 | 有 | Nobel 2021 Card 自然实验与劳动 / 22min（干扰：经济） |
| 31 | YouTube | https://www.youtube.com/watch?v=h1RkSuAs03Q | 有 | Nobel 2018 Nordhaus 气候经济学 / 33min（干扰：经济） |
| 32 | YouTube | https://www.youtube.com/watch?v=D3aHciiVdvQ | 有 | Yale Shiller 金融市场导论 / 1h14m（干扰：金融） |
| 33 | YouTube | https://www.youtube.com/watch?v=heBErnN3ZPk | 有 | MIT 宏观经济学 L1 导论 / 30min（干扰：宏观） |
| 34 | YouTube | https://www.youtube.com/watch?v=b5H8D_wD2AY | 有 | MIT 宏观经济学 L4 金融市场 / 52min（干扰：宏观） |
| 35 | YouTube | https://www.youtube.com/watch?v=W-Q9AOp2FW8 | 有 | FRONTLINE 2008 金融危机纪录片 P1 / 53min（干扰：金融危机） |
| 36 | YouTube | https://www.youtube.com/watch?v=PHe0bXAIuk0 | 有 | Ray Dalio 经济机器如何运行 / 31min（干扰：宏观） |
| 37 | B 站 | https://www.bilibili.com/video/BV1654y1F7fZ/? | 有 | 新手健身忠告 |
| 38 | B 站 | https://www.bilibili.com/video/BV1HR7o6CE8q/? | 有 | 保姆级私教视角之背部训练 |
| 39 | B 站 | https://www.bilibili.com/video/BV1z8zPYjE4j/? | 有 | 三分化-饮食详解 |
| 40 | B 站 | https://www.bilibili.com/video/BV1LAVh6UEQz/? | 有 | 蛋白质营养拆解及运动应用 |
| 41 | B 站 | https://www.bilibili.com/video/BV11o4y1s7VY/? | 有 | 如何快速学习一个领域的 |
| 42 | B 站 | https://www.bilibili.com/video/BV1hN596zEas/? | 有 | 资本是如何接连引爆多个国家的金融危机的？ |
| 43 | B 站 | https://www.bilibili.com/video/BV1QGXABxEbq/? | 有 | 伊朗战争，和全球能源格局 |
| 44 | B 站 | https://www.bilibili.com/video/BV1ub421J7jv/? | 有 | 美元、日元、人民币…为什么涨/跌？ \| 美元跌宕50年 |
| 45 | B 站 | https://www.bilibili.com/video/BV1M2421T7qk/? | 有 | 一口气了解全球经济形势 |
| 46 | B 站 | https://www.bilibili.com/video/BV1mMHyz3Erk/? | 有 | 16分钟讲明白：程序、进程、内存和CPU到底啥关系？\| 静态文件 / 地址空间 / 计算机底层 |
| 47 | B 站 | https://www.bilibili.com/video/BV1hA7K6jER9/? | 有 | “夏炒电”还没结束？一口气看懂电力4大赛道：水电、火电、风光、核电，72家发电企业，谁是避险之王？ |
| 48 | B 站 | https://www.bilibili.com/video/BV1Dm7J6XEEh/? | 有 | 【历史】穆斯林从何而来？深度追溯1400年前，伊斯兰的起源(1/4) |
| 49 | B 站 | https://www.bilibili.com/video/BV1vtT46WEoW/? | 有 | 「当行在泰国(上)」拥有巨巨巨大贫富差距的城市——曼谷！真实的曼谷究竟是什么样？ |
| 50 | B 站 | https://www.bilibili.com/video/BV1dMGm6xET9/? | 有 | 几代人的回忆！一口气看完75年中国家装变迁史！ |

填好后，把本 worktree 交给执行 AI，从 Phase 0 开始。

---

## Phase 0 — 构建数据集与评测集

**目标**：把上面的视频灌成一个干净的基准知识库，并为每个指标准备好 ground-truth 评测集。

### 0.1 灌库
对每个视频链接：
1. 起 backend（`uvicorn main:app --port 8000`，需带 fetcher 服务；或直接用现有 `scripts/dev.sh` 起整套——但注意 ASR 懒加载）。
2. `POST /api/videos` 创建 → 拿 `video_id`。
3. `POST /api/videos/{video_id}/process` 触发字幕抽取 / ASR / 清洗 / 分块 / 向量化 / 入库。
4. 轮询直到该视频 status 完成且文档已索引。
5. 失败的视频记录在 `benchmarks/results/00_dataset.md`，不计入下游。

产出：`bench_data/` 下一个完整的 KB（SQLite + Qdrant）。

### 0.2 规模快照（顺便做掉，对应 Phase 5）
写 `benchmarks/scale_snapshot.py`，输出到 `results/05_scale.md`：
- 视频数、文档数（SQLite `documents`）
- chunk 总数（`QdrantStore.scroll_all_points()` 长度，或 `documents` collection 点数）
- L2/L3 覆盖率（有 summary 的文档数 / 总文档数）
- 每文档 chunk 数分布（min/mean/max）、平均 chunk 字符数
- 向量维度、距离度量（从 Qdrant meta）

### 0.3 构建评测集（ground truth，最关键）
这是所有检索类指标的基础。为**每个视频**生成若干问答对，并标注 ground truth：

- **问题类型要覆盖三类**（后面路由 / 完整度基准要用）：
  - `detail`：细节题（某个具体点 / 数字 / 步骤）→ 期望命中某段 chunk
  - `summary`：总结 / 概览题（"这个视频主要讲什么""提到了哪几个核心概念"）→ 期望走 lookup+summarize
  - `self`：关于用户自己（"我最近在学什么"）→ 期望走 memory（这题不进检索评测，只进路由评测）
- 每条问题标注：
  - `relevant_chunks`：能回答它的 chunk key 列表 `(document_id, chunk_index)`，以及/或 `relevant_timestamp`。这是召回率分母。
  - `expected_route`：`search` / `lookup+summarize` / `memory`

**生成方式建议**：读每个视频的 cleaned markdown，让 chat 模型基于全文生成 Q&A 并反查命中哪段 chunk 作为 ground truth；人工 / LLM 复核一遍标注质量。保存为 `benchmarks/eval_set.jsonl`（每行一题）。

> 评测集质量直接决定后面所有数字的可信度。宁可题少质高（每视频 3–5 题），不要题多质低。目标总量 40–60 题。

---

## Phase 1 — 检索 A/B：混合 vs 单路（核心）

**问题**：混合检索相对纯向量 / 纯 BM25，召回到底好多少？

### 方法
直接 import `HybridRetriever` / `VectorRetriever`，对 `eval_set.jsonl` 里所有 `detail` / `summary` 题跑四档：

| 配置 | 实现 |
|---|---|
| **混合**（默认） | `HybridRetriever(weights={"bm25":0.3,"vector":0.7})` |
| **纯向量** | `VectorRetriever`（推荐，干净基线）或 `HybridRetriever(weights={"bm25":0.0,"vector":1.0})` |
| **纯 BM25** | `HybridRetriever(weights={"bm25":1.0,"vector":0.0})`（测试里 `test_retrieval.py:147` 就是这么隔离 BM25 的） |

> 注意：`HybridRetriever._search_sync` 每次查询都会 `scroll_all_points()` 重建 BM25 语料（MVP 实现）。跑纯向量基线优先用 `VectorRetriever`，避免这部分开销污染延迟数字。

### 指标（对每档，k 取 5 和 10）
- **Recall@k** = |命中 relevant_chunks ∩ top-k| / |relevant_chunks|（主指标）
- **Precision@k** = |命中 ∩ top-k| / k
- **MRR**（第一个命中 relevant 的倒数排名）
- 按"中文专有名词题 / 普通语义题"切片统计（专有名词题最能体现 BM25 价值——这是简历里"弥补纯向量在专有名词命中短板"这条主张的证据）

### 产出
`benchmarks/retrieval_ab.py` → `results/01_retrieval_ab.md`（四档 × 多指标对比表）+ `.json`。
**重点对比**：混合 vs 纯向量的 Recall@5 提升幅度（绝对值 + 相对%）。

---

## Phase 2 — 分层 vs 平铺：回答完整度（核心）

**问题**：三层 Agent 路由相对"只有全文检索"的平铺方案，在总结 / 概览类问题上，回答完整度好多少？

### 方法
构造两个 Agent 变体（直接 import `build_agent`，注入同一个 chat 模型）：
- **Layered**（当前架构）：`build_agent` 注册全部三个工具（search / lookup / summarize）。
- **Flat**（对照）：构造一个**只注册 `search_knowledge`** 的 Agent 变体（在 `benchmarks/` 里写 `build_flat_agent`，复用 `chat_agent.py` 的 system prompt 与 search 工具实现，去掉 lookup/summarize）。

对 `eval_set.jsonl` 里所有 `summary` 类问题，两个 Agent 各跑一遍（同样的历史、同样的 memory 注入），收集回答。

### 指标
回答完整度没有单一客观分，用 **LLM-as-judge 盲评**：
- 用一个**独立**的 chat 模型当评委，对每条回答按 rubric 打 1–5 分（覆盖度、是否遗漏要点、是否准确），不告知来源。
- 也可统计：Layered 是否真的触发了 `lookup_documents` + `summarize_document`（看 tool call 事件）。
- 主指标：**Layered 平均分 − Flat 平均分**，以及 Layered 胜/平/负的比例。

### 产出
`benchmarks/architecture_ab.py` → `results/02_architecture.md`（打分分布、胜率、典型样例）+ `.json`。
> 这是主观性最强的基准，务必把 rubric、评委模型、若干样例回答都附上，保证可质疑、可复现。

---

## Phase 3 — 延迟基准

**问题**：检索 / 端到端问答有多快？

### 方法
- **检索延迟**：对 Phase 1 的四档分别计时 `retriever.search(query, top_k)`，每题跑 N 次（如 5 次）取分布。注意 BM25 每次重建语料的开销（这是当前实现的已知瓶颈，可作为后续优化点记录）。
- **端到端问答延迟**：走真实链路 `POST /api/chat`（SSE），计两个点：首 token 时间（TTFT）、完整回答时间。对 N 个问题取分布。

### 指标
每档 / 每链路给出 **mean / P50 / P95**（ms）。

### 产出
`benchmarks/latency.py` → `results/03_latency.md` + `.json`。

---

## Phase 4 — Agent 路由准确率

**问题**：Agent 是否按问题类型选对了工具？

### 方法
对 `eval_set.jsonl` 全量题（含 `detail` / `summary` / `self` 三类），跑 **Layered Agent**，捕获每次的 tool call（pydantic-ai 的 `FunctionToolCallEvent`，见 `api/chat.py` 已 import）。

把实际调用序列映射成 route：
- 只调 `search_knowledge` → `search`
- 调了 `lookup_documents` / `summarize_document` → `lookup+summarize`
- 没调工具、从 memory 回答 → `memory`

### 指标
- **路由准确率** = 预测 route == `expected_route` 的比例。
- **混淆矩阵**（3×3）+ 每类 precision/recall。
- 失败案例列出。

### 产出
`benchmarks/routing_accuracy.py` → `results/04_routing.md` + `.json`。

---

## Phase 5 — 规模快照

已在 Phase 0.2 完成；若 Phase 0 之后数据有变，在此重跑确认。最终落 `results/05_scale.md`。

---

## 5. 结果记录规范

`benchmarks/results/` 下文件清单：

| 文件 | 内容 |
|---|---|
| `00_dataset.md` | 灌库结果：成功/失败视频、最终 KB 规模、评测集题量与类型分布 |
| `01_retrieval_ab.md` | 检索 A/B 四档 × 指标对比 |
| `02_architecture.md` | 分层 vs 平铺 完整度打分 |
| `03_latency.md` | 延迟分布 |
| `04_routing.md` | 路由准确率 + 混淆矩阵 |
| `05_scale.md` | KB 规模快照 |
| `SUMMARY.md` | **总览**：把上面所有"头条数字"汇总到一页（格式见下） |

### `SUMMARY.md` 必须包含（一页纸，固定结构，便于程序读取）

```
# Memento RAG 基准测试 · 结果总览

- 数据规模：{N 视频} 视频 / {M 文档} 文档 / {K chunk} / 评测集 {Q 题}
- 运行时间：{timestamp}；模型：embedding={...}, chat={...}
- 评测集：detail {x} 题, summary {y} 题, self {z} 题

## 检索 A/B（Recall@5 / Recall@10 / MRR）
| 配置 | Recall@5 | Recall@10 | MRR |
| 纯向量 | ... | ... | ... |
| 纯 BM25 | ... | ... | ... |
| 混合(默认) | ... | ... | ... |
→ 混合相对纯向量 Recall@5 提升：{+X%}

## 分层 vs 平铺（总结类问题完整度 1–5 分）
- Flat 均分：{a} / Layered 均分：{b} / 提升 {+c}
- Layered 胜率：{w%}

## 路由准确率
- 总准确率：{acc%}；detail {..}, summary {..}, self {..}

## 延迟（ms）
- 检索(混合) P50/P95：{..}/{..}；端到端首 token / 完整：{..}/{..}

## 规模快照
- chunk/文档 比：{..}；L2/L3 覆盖率：{..}；向量维度：{768}

## 备注 / 已知问题
- ...
```

---

## 6. 执行顺序建议

1. 确认环境（§3，尤其 embedding）。
2. 维护者填好视频清单（§4）。
3. Phase 0（灌库 + 规模快照 + 评测集）——**评测集质量是地基，多花时间**。
4. Phase 1（检索 A/B）→ 出第一个可用数字。
5. Phase 3（延迟，轻量）。
6. Phase 4（路由）。
7. Phase 2（分层 vs 平铺，最重，需要 LLM judge）。
8. 汇总 `SUMMARY.md`。

每个 Phase 完成后 commit 一次（在 `worktree-rag-benchmarks` 分支上），便于回溯。
