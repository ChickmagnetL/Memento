# 02 架构 A/B：分层 Agent vs 平铺 Agent（summary 完整度）

生成时间: 2026-07-25 03:12:16 UTC
Chat agent model: `gemini-3.1-pro` @ `https://api.42w.shop/v1`
Judge model: `gemini-3.1-pro` @ `https://api.42w.shop/v1`
Embedding: `Qwen/Qwen3-Embedding-0.6B` @ `http://localhost:8003/v1`
n summary questions = **10**
scored = **10** | agent_errors = 0 | judge_errors = 0

## Rubric

```
Score 1–5 for answer completeness on a summary/overview question:
5 = Covers nearly all key points from the source topic; accurate; well structured overview
4 = Covers most key points; minor gaps or slight inaccuracy
3 = Partial coverage; several important points missing or vague
2 = Thin or mostly off-topic; major gaps
1 = Empty, refusal, hallucination-heavy, or fails to answer
Also consider: factual accuracy relative to provided key points (notes); do not reward inventing content not grounded in the answer's claims about the video.
```

## Headline metrics

- Layered mean score = **3.500**
- Flat mean score = **2.900**
- Delta (layered − flat) = **0.600**
- Layered win / tie / loss = **3** / **5** / **2** (rates: 30.0% / 50.0% / 20.0%)

## Score distribution

| score | layered n | flat n |
|-------|-----------|--------|
| 1 | 3 | 4 |
| 2 | 1 | 1 |
| 3 | 0 | 1 |
| 4 | 0 | 0 |
| 5 | 6 | 4 |

## Per-question results

| id | video_id | lacks_L2/L3 | L score | F score | winner | L tools | F tools | lookup | summarize |
|----|----------|-------------|---------|---------|--------|---------|---------|--------|-----------|
| q004 | P-NmMX9rlYQ | Y | 1 | 1 | `tie` | lookup_documents, summarize_document | search_knowledge | Y | Y |
| q009 | -HOzOBmQ5ro |  | 5 | 5 | `tie` | lookup_documents, summarize_document | search_knowledge | Y | Y |
| q013 | 185XGEMefgc |  | 5 | 5 | `tie` | search_knowledge | search_knowledge |  |  |
| q018 | vkpS7WztTMc |  | 5 | 1 | `layered` | lookup_documents, summarize_document | search_knowledge | Y | Y |
| q019 | oYxTTirKY8M | Y | 2 | 5 | `flat` | lookup_documents, summarize_document | search_knowledge | Y | Y |
| q026 | BV1FUYQz7E4H |  | 5 | 3 | `layered` | lookup_documents, summarize_document | search_knowledge | Y | Y |
| q030 | BV14v4y1G7A3 |  | 5 | 5 | `tie` | lookup_documents, summarize_docum... | search_knowledge | Y | Y |
| q035 | BV1ev411w7bs | Y | 1 | 2 | `flat` | lookup_documents, summarize_document | search_knowledge | Y | Y |
| q040 | BV1Zk9FBwELs |  | 1 | 1 | `tie` | lookup_documents, summarize_document | search_knowledge | Y | Y |
| q044 | BV1E7wtzaEdq |  | 5 | 1 | `layered` | lookup_documents, summarize_document | search_knowledge | Y | Y |

## Sample Q&A pairs

### Sample 1: q018

**Q:** 这篇演讲的主要内容是什么？

**Notes:** 苏姿丰结合在MIT的求学与个人职业经历，鼓励毕业生勇敢面对难题、发挥工程师本能并在AI时代创造属于自己的运气

**Scores:** Layered=5 | Flat=1 | winner=`layered`
**Judge:** Answer A correctly identifies and fully covers the key points of Lisa Su's MIT commencement speech, while Answer B summarizes an entirely unrelated video.

**Layered answer:**

由于知识库中有多篇演讲相关的视频内容，请问您指的是哪一篇演讲？

以下是相关的演讲视频及其主要内容：

---

## 1. AMD CEO 苏姿丰 MIT 毕业典礼演讲
* **视频标题**：半导体女王 AMD CEO苏姿丰Lisa Su:AI未来10年新发现将超过去30年总和！如何创造属于自己的运气？
* **主要内容**：
  * **求学与职业经历**：回顾其在 MIT 本科至博士的求学历程，分享“手脑并用（Mens et Manus）”校训对工程师直觉与职业生涯的深远影响。
  * **应对挑战**：结合在 IBM 和 AMD 的经验，鼓励毕业生迎难而上、勇敢挑战最棘手的问题。
  * **AI 前景与责任**：阐述 AI 在医疗等领域的巨大潜能，强调技术本身无法决定未来，需要兼具使命感与责任感的人来引领时代发展。

---

## 2. 威廉·诺德豪斯 2018 诺贝尔经济学奖演讲
* **视频标题**：Prize lecture: William D. Nordhaus, Prize in Economic Sciences 2018
* **主要内容**：
  * **气候与经济分析**：阐述气候变化与经济增长的紧密联系，指出气候变化是由于能源市场未对二氧化碳定价而导致的巨大“市场失灵”。
  * **DICE 模型与碳定价**：介绍其开发的 DICE 综合评估模型，强调解决气候问题的核心在于通过实施碳税或碳定价来提高排放成本。
  * **气候俱乐部方案**：为解决国际减排中的“搭便车”难题，提出“气候俱乐部”模式，主张对非成员国征收惩罚性关税以推动全球协同减排。

---

如果您想了解其中某一篇演讲的具体细节或特定片段，请随时告诉我！

**Flat answer:**

这篇演讲（视频《我是如何快速学习一个领域的》）的核心内容是分享**如何高效学习、梳理繁杂信息以及快速建立知识体系的方法论与技巧**。

主要内容可分为以下几个关键部分：

---

### 1. 建立结构化思维与知识框架
* **从线状逻辑到网状体系**：学习初期建立的可能只是局部或线性的逻辑，但随着知识不断积累，它会逐渐演变成“知识树”或网状体系 [12:38 框架体系的建立](memento://play?platform=bilibili&video_id=BV11o4y1s7VY&t=758)。
* **向专家学习核心框架**：很多细节可以在网上查到，但大佬脑海里的“知识树”和系统框架才是最宝贵的价值 [13:14 学习大佬的框架](memento://play?platform=bilibili&video_id=BV11o4y1s7VY&t=794)。
* **结构化思维实操**：以“5000元预算挑选笔记本电脑”为例，展示了如何通过明确自身核心需求（如轻便、续航、护眼等）来进行结构化思考，避免盲目消费 [15:02 结构化思维练习](memento://play?platform=bilibili&video_id=BV11o4y1s7VY&t=902)。

---

### 2. 长文章与论文的“两遍阅读法”
在处理长文章或复杂资料（例如研究硅谷银行案例）时，建议分为两步 [13:34 读书与资料梳理](memento://play?platform=bilibili&video_id=BV11o4y1s7VY&t=814)：
1. **第一遍抓大框**：忽略所有非必要的细节，重点看摘要、核心数据与关键脉络，快速掌握全局 [13:40 第一遍看大框](memento://play?platform=bilibili&video_id=BV11o4y1s7VY&t=820)。
2. **第二遍补细节**：带着具体问题有针对性地补充所需细节 [14:15 第二遍补充细节](memento://play?platform=bilibili&video_id=BV11o4y1s7VY&t=855)。

---

### 3. 以输出倒逼输入（费曼学习法）
* **强迫自身输出**：无论是做视频、做项目演示（Presentation），还是在复习时闭上书本用一张纸梳理知识点，输出环节都能极大提高知识吸收与巩固记忆的效率 [14:20 增加输出环节](memento://play?platform=bilibili&video_id=BV11o4y1s7VY&t=860)。

### Sample 2: q026

**Q:** 本视频主要介绍了PostgreSQL数据库的哪些内容？

**Notes:** 从安装入门开始，介绍了Postgres的多样数据类型、对象关系特性、JSON/向量存储、全文检索、定时任务及各类扩展插件等强大功能

**Scores:** Layered=5 | Flat=3 | winner=`layered`
**Judge:** Answer B covers all key points including full-text search, vector storage, and scheduled tasks, whereas Answer A misses several of these core topics.

**Layered answer:**

本视频（《PostgreSQL能存万物！这还是你认识的数据库吗？》）主要介绍了 PostgreSQL 的以下核心内容：

*   **基础配置与架构管理**：Postgres 在 Ubuntu 上的快速安装配置，以及基于 Schema 的权限控制。
*   **高级与面向对象特性**：原生支持网络网段、几何运算、自定义数据类型与表继承等面向对象特性。
*   **JSON 与 NoSQL 替代**：利用 JSONB 数据类型高效存储和查询非结构化数据，替代传统 NoSQL 数据库。
*   **全文检索能力**：原生全文搜索支持，以及结合 **PGroonga** 插件实现更强的中英文全文检索。
*   **AI 与向量检索（RAG）**：结合 **pgvector** 扩展与 LangChain 框架，支持大模型 RAG 应用中的向量检索。
*   **定时任务与缓存优化**：利用 **pg_cron** 插件直接在数据库内执行定时任务；利用 **UNLOGGED 临时表** 实现高性能缓存，替代部分 Redis 场景。
*   **多场景扩展生态**：借助丰富生态将 PostgreSQL 转化为全能后端平台，包括：
    *   **PostgREST / pg_graphql**：自动生成 RESTful 或 GraphQL API。
    *   **Apache AGE**：提供图数据库能力。
    *   **TimescaleDB**：提供高性能时序数据库能力。

**Flat answer:**

这期视频主要将 PostgreSQL 介绍为一个超越传统关系型数据库的**全能后端聚合平台**，详细讲解了它的核心设计理念、丰富特性以及实际安装配置：

### 1. 核心定位与设计理念
* **开源对象关系型数据库 (Object-Relational Database)**：PostgreSQL 结合了传统数据库的严谨关系形式与面向对象的编程思想，在数据库层面直接提供对对象的支持，以此解决开发中常见的“阻抗不匹配”难题 [[03:29]](memento://play?platform=bilibili&video_id=BV1FUYQz7E4H&t=209)。
* **追求 SQL 标准与功能丰富**：比起追求快速应用的数据库（如 MySQL），Postgres 更侧重功能最丰富、最符合 SQL 标准，支持表结构修改语句事务管理、部分索引、可延迟约束等高级特性 [[00:32]](memento://play?platform=bilibili&video_id=BV1FUYQz7E4H&t=32)。
* **多层级结构**：采用 `数据库 -> schema -> 表` 的三级结构，区别于传统的两级结构 [[03:29]](memento://play?platform=bilibili&video_id=BV1FUYQz7E4H&t=209)。

---

### 2. 内置丰富数据类型与面向对象特性
* **丰富的数据类型**：内置上百种数据类型，包括多种带/不带时区的时间类型、网段（如 `CIDR`）、IP 地址、MAC 地址以及几何图形（点、线、多边形等，支持简单几何运算）[[03:29]](memento://play?platform=bilibili&video_id=BV1FUYQz7E4H&t=209)。
* **自定义类型与多维数组**：支持使用 SQL 自定义复合类型（如 `employee`），并支持数组或多维数组字段 [[03:29]](memento://play?platform=bilibili&video_id=BV1FUYQz7E4H&t=209)。
* **表继承与多态**：支持表之间的继承（如 `developer` 表继承自 `employee` 表），子表数据会自动同步至父表，以此模拟面向对象中的多态性 [[03:29]](memento://play?platform=bilibili&video_id=BV1FUYQz7E4H&t=209)。

---

### 3. NoSQL 与 JSONB 支持
* **替代非结构化数据库**：原生支持 `JSONB`（二进制 JSON）类型，可实现非结构化数据的灵活存储与嵌套 [[07:06]](memento://play?platform=bilibili&video_id=BV1FUYQz7E4H&t=426)。
* **高效索引**：支持对提取的 JSON 字段建立表达式 B-Tree 索引，或直接对整个 JSON 字段建立 GIN 索引，大幅提升查询效率，很大程度上能替代 MongoDB 等文档数据库 [[07:06]](memento://play?platform=bilibili&video_id=BV1FUYQz7E4H&t=426)。

---

### 4. 强大的扩展生态 (Extensions)
* **Apache AGE**：通过扩展引入图数据库能力，支持 Cypher 语言查询好友关系网或电网等，无需额外部署图数据库 [[21:09]](memento://play?platform=bilibili&video_id=BV1FUYQz7E4H&t=1269)。
* **TimescaleDB**：赋予 Postgres 时序数据库的能力，非常适合物联网及金融等高频时序数据的处理 [[21:09]](memento://play?platform=bilibili&video_id=BV1FUYQz7E4H&t=1269)。
* **GraphQL**：支持使用 GraphQL 扩展进行查询，直接返回 JSON 对象 [[21:09]](memento://play?platform=bilibili&video_id=BV1FUYQz7E4H&t=1269)。

---

### 5. 快速上手与安装配置
* 示范了在 Linux (Ubuntu) 环境下通过 `apt` 快速安装 PostgreSQL 及官方插件包 `postgresql-contrib` [[01:14]](memento://play?platform=bilibili&video_id=BV1FUYQz7E4H&t=74)。
* 介绍了通过切换 `postgres` 用户登录 `psql` 命令行，以及修改配置文件（`listen_addresses` 和 IPv4 允许连接网段）以放开远程连接的详细步骤 [[01:14]](memento://play?platform=bilibili&video_id=BV1FUYQz7E4H&t=74)。

### Sample 3: q044

**Q:** 这期视频的主要内容是什么？

**Notes:** 从底层工程视角梳理并讲解从大模型（LLM）到 Agent Skill 等核心 AI 概念的底层逻辑与关联

**Scores:** Layered=5 | Flat=1 | winner=`layered`
**Judge:** Answer B accurately covers the reference key points regarding the underlying engineering logic from LLMs to Agent Skills, whereas Answer A summarizes a completely different video about learning methods.

**Layered answer:**

如果您问的是 **《从 LLM 到 Agent Skill，一期视频带你打通底层逻辑！》** 这期视频，它的主要内容如下：

本视频从**工程视角**出发，系统且通俗地拆解了当前 AI 领域的核心概念与底层架构，主要包括以下模块：

* **LLM 运行逻辑**：介绍了基于 Transformer 的“下一个 Token 预测”（文字接龙）机制。
* **Tokenizer 与 Token**：讲解了文本的编码解码原理以及 Token 的计算方式。
* **Context & Context Window**：剖析了由上下文构成的临时记忆机制及其容量限制。
* **Prompt 工程**：阐述了 User Prompt 与 System Prompt 对大模型输出的规范与约束。
* **Tool 与 MCP 协议**：延伸至大模型与外部环境的交互，以及统一接口接入标准 Model Context Protocol (MCP)。
* **Agent 与 Agent Skill**：深入讲解了具备自主规划与工具调用能力的 Agent，以及如何通过规范文档（Agent Skill）控制 Agent 的行为逻辑与规则。

总体帮助观众建立起从底层 Token 到上层 Agent 应用的完整 AI 技术认知体系。

---

*如果您指的是其他视频（如 MCP vs API、PostgreSQL 或健身训练等），请随时告诉我！*

**Flat answer:**

这期视频（《我是如何快速学习一个领域的》）主要分享了**快速学习和搭建知识体系的核心方法**，强调学习的关键在于构建知识“树”与结构化思维。具体内容包含以下几个方面：

---

### 1. 建立框架与结构化思维
* **搭建知识“树”**：学习新内容时，要么是建立一棵全新的知识“树”，要么是在原有的树上添枝加叶。大佬之所以厉害，是因为脑海中拥有清晰的框架和体系，即使忘记细节，也能快速解决问题 ([12:38 框架逻辑与知识树](memento://play?platform=bilibili&video_id=BV11o4y1s7VY&t=758), [16:09 知识树的构建](memento://play?platform=bilibili&video_id=BV11o4y1s7VY&t=969))。
* **注重框架而非细节**：向高手请教或学习时，应优先挖掘框架逻辑，因为具体细节通常很容易搜索得到 ([13:14 挖掘大佬的框架思维](memento://play?platform=bilibili&video_id=BV11o4y1s7VY&t=794))。

---

### 2. 长文章/论文的“两遍阅读法”
* **第一遍抓大框**：忽略繁琐细节，优先寻找摘要、资产负债表、核心脉络等关键性框架信息 ([13:37 第一遍读大框](memento://play?platform=bilibili&video_id=BV11o4y1s7VY&t=817))。
* **第二遍补充细节**：在理清大体逻辑后，再根据具体需要解答的问题把细节补充进去 ([14:15 第二遍补充细节](memento://play?platform=bilibili&video_id=BV11o4y1s7VY&t=855))。

---

### 3. 通过“输出”深化吸收
* **主动输出强化记忆**：复习或学习时，可以合上书本，在纸上梳理知识点和脉络；或者在工作/学习中通过做 Presentation、整理项目来倒逼自己输出 ([14:20 输出提升吸收效率](memento://play?platform=bilibili&video_id=BV11o4y1s7VY&t=860))。
* **自己增加输出环节**：在没有人监督的情况下，可以主动设计输出练习，帮助深层巩固知识 ([14:49 增加输出环节](memento://play?platform=bilibili&video_id=BV11o4y1s7VY&t=889))。

---

### 4. 结构化思维的实际应用与产品体验
* **应用案例**：视频以“5000元预算买笔记本电脑”为例，演示了如何用结构化思维梳理轻便、续航、颜值、护眼等核心需求 ([14:53 结构化思维买电脑案例](memento://play?platform=bilibili&video_id=BV11o4y1s7VY&t=893))。
* **产品展示**：展示了符合相关需求的华为 MateBook E Go 笔记本，并演示了利用手写与缩放绘图功能来梳理知识框架主干的完整过程 ([15:32 笔记本展示](memento://play?platform=bilibili&video_id=BV11o4y1s7VY&t=932), [15:48 缩放主干回溯细节](memento://play?platform=bilibili&video_id=BV11o4y1s7VY&t=948))。

## Docs lacking L2/L3

Known video_ids without reliable L2/L3 in this corpus: `BV1ev411w7bs`, `P-NmMX9rlYQ`, `oYxTTirKY8M`
- Questions tagged lacks_l2_l3: **3**
- Layered may still call lookup/summarize; summarize may generate on the fly or return thin content. Flat must synthesize from search chunks only.

## Notes

- Blind LLM-as-judge: answers randomized as A/B; scores mapped back to layered/flat.
- Flat agent has only search_knowledge; Layered has search + lookup + summarize + propose_memory.
- Docs lacking L2/L3 tags: ['BV1ev411w7bs', 'P-NmMX9rlYQ', 'oYxTTirKY8M']
- Judge.complete called via asyncio.to_thread to avoid nested event loop.
- Bounded concurrency=5 across questions via asyncio.Semaphore; within each question layered+flat run concurrently then judge sequential. No store lock — concurrent Qdrant/SQLite reads may race and reduce effective concurrency if the store is not concurrent-safe.
- wall_time_s=75.37, concurrency=5
