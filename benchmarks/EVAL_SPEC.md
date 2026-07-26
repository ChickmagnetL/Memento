# Memento RAG 评测出题规范

出题与金标的**唯一**规范。执行 AI 只按本文操作。

`BENCHMARK_TASKS.md` 仅为早期跑通基准的临时任务稿（灌库、脚本相位等），**不是**出题标准；正式评测集按本文建成并冻结后，不再依赖该文件。

---

## 1. 任务目标

在约 50 视频的基准知识库上，构建约 **100 题**（允许 80–120）的评测集，用于：

- 检索：Recall@k / MRR（仅细节类有 chunk 金标的题）
- 路由：`expected_route` 是否与 Agent 实际工具一致
- 总结（L2/L3 就绪后）：分层 vs 平铺（仅 `summary` 且 `summary_eligible=true`）

产出文件：`benchmarks/eval_set.jsonl`（一行一题 JSON）。

写入正式集前，将旧的探索性 `eval_set.jsonl` 归档为 `eval_set.old.jsonl`（一次性操作，归档后旧文件不再被任何评测引用）。

出题原料统一使用 `benchmarks/eval_build/corpus_manifest/`（每视频一个文件含标题 / L2 / L3 / 全部 chunk；`_index.md` 为总表），不直接读数据库。

---

## 2. 规模与覆盖

| 规则 | 要求 |
|------|------|
| 总题量 | 100 ± 20 |
| 视频覆盖 | **每个视频至少 1 道** `detail`；能做则 2 道 |
| 禁止 | 只给部分视频出题、其余仅当干扰却无任何金标题 |
| 长视频 | 优先多给 `detail` / `multi_evidence` |
| 短视频 | 至少 1 道 `detail` |

### 题型配比（按 100 题）

| type | 条数 | 占比 |
|------|------|------|
| `detail` | 45–55 | 每视频先满足「≥1 detail」再分配剩余 |
| `multi_evidence` | 8–12 | |
| `multi_hop` | 8–12 | 少而精 |
| `summary` | 15–20 | 题面必须可消歧；无 L2/L3 时 `summary_eligible=false` |
| `unanswerable` | 8–12 | |
| `memory` | 4–8 | 必须带 `seed_memories` |

`easy` 难度的 `detail` 不超过全部 `detail` 的 30%。

---

## 3. 题型

### 3.0 视频点名规则总表（先看这张表再出题）

「点名」指题面出现视频标题、《xx》、「那期讲 xx 的视频」、课程期数等能直接锁定视频的表述。

| type | 能否点名视频 | 原因 |
|------|--------------|------|
| `detail` / `multi_evidence` | **禁止** | 定位视频本身是检索考点；真实用户不知道答案在哪期 |
| `multi_hop` | 只准概念级锚点（如「GFS 和 Raft」） | 比较对象必须出现，但不许给出处 |
| `summary` | **必须** | 总结是对着确定的某期视频发起的动作，不点名即废题 |
| `unanswerable` | 默认**不点名**；仅 `reject_false_premise` 可用「讲 xx 的视频里说…」作错误归因场景 | 无金标可送，但点名会不自然 |
| `memory` | 禁止（题面不得含库内主题词诱饵） | 答案来自记忆，不来自视频 |

泛指的「视频里 / 作者 / 讲者」不算点名，允许使用。

### 3.1 `detail`

- 答案在**单一视频**的少量 chunk 内
- `expected_route`: `search`
- `relevant_chunks` 非空；gold chunk 必须能核验答案
- 题面必须改写，禁止大段照抄字幕
- **题面禁止点名视频**（标题 / 「在《xx》视频里」/「那期讲 xx 的视频」）——真实用户不知道答案在哪个视频，定位视频本身是检索考点
- 唯一性靠**内容锚点**保证（视频特有术语 / 数字 / 场景），出题时须确认该事实在全库唯一；若同一事实多视频冲突，换题或多标金标

### 3.2 `multi_evidence`

- 同一视频内需要 **≥2** 个 chunk 才能答完整
- `expected_route`: `search`
- `relevant_chunks.length >= 2`
- 禁止把两个无关事实用「以及」拼成假多证据
- 题面同样**禁止点名视频**（同 3.1）

### 3.3 `multi_hop`

- 必须结合 **≥2 个视频**
- `expected_route`: `search`
- 题面点名**被比较的两个概念/对象**（概念级锚点，如「GFS 和 Raft」）；**不点视频标题或课程期数**；禁止「那两期」
- 金标含两侧文档或 chunk；去掉任一侧后标准答案不成立
- **题面最多两问（每侧一问）**；禁止三问及以上，保证全部 multi_hop 题难度结构一致、成功率可比

### 3.4 `summary`

- 整片或明确章节的概览
- `expected_route`: `lookup+summarize`
- `relevant_chunks` 可 `[]`
- 必填 `reference_points`（3–7 条要点）
- 必填 `summary_eligible`（bool）
- **题面禁止**：「这期视频」「本视频」「这篇」「刚才那个」等无锚点指代
- **题面必须**含可消歧锚点（标题关键词、讲者、独特主题）
- `summary_eligible=false`：可写入 jsonl，但**不得**进入分层/总结正式计分，直到该文档 L2 或 L3 存在且主题正确后再改为 `true`

### 3.5 `unanswerable`

- 话题可相关，但库中无答案，或题设前提为假
- `expected_route`: `refuse`
- 必填 `expected_behavior`（如 `insufficient_information` 或 `reject_false_premise`）
- `relevant_chunks` 为 `[]`
- 可选 `near_miss_docs`
- 禁止纯无关闲聊（如「人生的意义」）
- 点名规则见 §3.0：`insufficient_information` 型不点名；`reject_false_premise` 型可引用「讲 xx 的视频」作错误归因场景

### 3.6 `memory`

- 答案依赖预置记忆，**不能**仅靠视频库答完
- `expected_route`: `memory`
- 必填 `seed_memories`（string 数组）与 `answer_key`
- 题面禁止堆砌库内高频主题词作为主诱饵（避免合理走 search）

---

## 4. 字段 Schema

每行一个 JSON 对象。

### 4.1 所有题必填

```json
{
  "id": "q_detail_<video_id>_01",
  "type": "detail",
  "question": "",
  "language": "zh",
  "video_id": "",
  "document_id": "",
  "expected_route": "search",
  "difficulty": "medium",
  "answer_key": "",
  "source": "llm_draft+human_edit"
}
```

| 字段 | 取值 |
|------|------|
| `id` | 稳定唯一；单视频题 `q_<type>_<video_id>_<nn>`；全局题（multi_hop / unanswerable / memory）用 `q_<type>_global_<nn>` |
| `type` | `detail` \| `multi_evidence` \| `multi_hop` \| `summary` \| `unanswerable` \| `memory` |
| `language` | `zh` \| `en` \| `mixed` |
| `expected_route` | `search` \| `lookup+summarize` \| `memory` \| `refuse` |
| `difficulty` | `easy` \| `medium` \| `hard` |
| `source` | `human` \| `llm_draft+human_edit` |

单数 `video_id` / `document_id` 的取值规则：

- 单视频题：填该视频
- `multi_hop`：用复数字段 `video_ids` / `document_ids`，单数字段置 `null`
- `memory`：置 `null`
- `unanswerable`：若锚定某个具体视频（近似命中型）填该视频，纯全局则置 `null`

`answer_key` 各类型含义：detail/multi_evidence/multi_hop/memory 为可核验答案要点；`summary` 填一句话主旨（详细要点在 `reference_points`）；`unanswerable` 填期望行为的简述（如「应说明库中未覆盖」）。

### 4.2 按类型追加

**detail / multi_evidence**

```json
{
  "relevant_chunks": [
    {"document_id": "<doc_id>", "chunk_index": 0}
  ]
}
```

**multi_hop**

```json
{
  "video_ids": ["<id_a>", "<id_b>"],
  "document_ids": ["<doc_a>", "<doc_b>"],
  "relevant_chunks": [
    {"document_id": "<doc_a>", "chunk_index": 1},
    {"document_id": "<doc_b>", "chunk_index": 3}
  ]
}
```

**summary**

```json
{
  "relevant_chunks": [],
  "reference_points": ["要点1", "要点2", "要点3"],
  "summary_eligible": false
}
```

**unanswerable**

```json
{
  "relevant_chunks": [],
  "expected_behavior": "insufficient_information",
  "near_miss_docs": []
}
```

**memory**

```json
{
  "relevant_chunks": [],
  "seed_memories": ["预置记忆文本"],
  "answer_key": "期望回答要点"
}
```

### 4.3 可选

```json
{
  "tags": ["jargon", "hard_negative", "long_video"],
  "notes": "出题备注，仅供人读"
}
```

---

## 5. 出题步骤

对每个视频（或全局题）严格按序：

1. 读取该视频标题、`document_id`、chunk 列表（或字幕）
2. 先确定要考查的事实 / 对比 / 知识缺口（不要先盯原句挖空）
3. 写 `question`（用户口吻、改写）
4. 填写金标字段（`relevant_chunks` / `reference_points` / `seed_memories` 等）
5. 对照 §6 逐项勾选；任一失败则重写，不得入库
6. 对照 §7 泄漏规则；失败则重写
7. 写入 `eval_set.jsonl`

全局题（`multi_hop` / `unanswerable` / `memory`）在单视频 detail 配额完成后再补。

LLM 仅可起草；**每条入库前必须按 §6、§7 审核通过**（执行 AI 自审亦须显式过清单，不得批量未审写入）。

---

## 6. 入库前检查清单

### 6.1 通用

- [ ] 题面单独可读，不依赖未提供的对话上文
- [ ] 非纯百科常识题（优先视频特有数字、表述、结构、对比）
- [ ] `type` 与 `expected_route` 匹配（见 §3）
- [ ] 必填字段完整（见 §4）

### 6.2 detail / multi_evidence

- [ ] 每个 gold chunk 打开后确实含答案
- [ ] 无 §7 所列字面照抄
- [ ] **题面未点名视频**（无标题、无「那期讲 xx 的视频」式引导）
- [ ] 所考事实在全库唯一（或已多标金标）
- [ ] `multi_evidence`：去掉任一 gold chunk 后答案不完整

### 6.3 multi_hop

- [ ] 题面含 ≥2 个来源锚点
- [ ] 单侧视频不足以回答
- [ ] 题面不超过两问（每侧一问）

### 6.4 summary

- [ ] 无无锚点指代词
- [ ] 有消歧锚点
- [ ] `reference_points` 为 3–7 条且来自该片
- [ ] `summary_eligible` 与当前库一致（L2/L3 未就绪或不正确 → `false`）

### 6.5 unanswerable

- [ ] 已确认库中无答或前提为假
- [ ] 属于合理相关提问，非纯无关

### 6.6 memory

- [ ] `seed_memories` 足以支撑 `answer_key` 主要点
- [ ] 仅视频库不足以完整回答
- [ ] 题面未以库内高频主题词为主诱饵

---

## 7. 泄漏与难度规则

适用于 `detail`、`multi_evidence`（`multi_hop` 的两侧证据同样适用）。

1. **禁止**题面与任一 gold chunk 连续照抄：≥8 个汉字，或 ≥5 个英文实词内容词  
2. **禁止**把字幕原句改成疑问句即交差  
3. 专有名词锚点可保留必要的 1–2 个；不得整句复述  
4. BM25 冒烟：仅用题面对候选 `detail` 集跑纯 BM25 top5，若 **>70%** 的题被完全命中全部 gold chunk，判定题面整体仍偏关键词化，须批量加难改写后重测，通过才可冻结  

---

## 8. 指标使用边界

| 用途 | 可用的题 | 条件 |
|------|----------|------|
| 检索 R@k / MRR | `detail`, `multi_evidence` | `relevant_chunks` 非空 |
| 检索多跳（另报） | `multi_hop` | 有多文档金标 |
| 路由准确率 | 全部 type | memory 题评测前注入 `seed_memories`；全部 memory 题的 seed 合并后不得互相矛盾 |
| 分层 vs 平铺 | 仅 `summary` | `summary_eligible=true` |
| 拒答 | `unanswerable` | 单独统计，不计 R@k |

禁止：

- 用空 `relevant_chunks` 的 summary/memory 算 chunk 召回
- 用 `summary_eligible=false` 的题报分层均分

---

## 9. 示例（格式与正误）

### detail — 不合格

题面与字幕同句结构、同关键词串，仅末尾改问号。

### detail — 合格

题面改写表述与问法；`answer_key` 可唯一核验；`relevant_chunks` 指向含该信息的 chunk。

### summary — 不合格

```text
这期视频主要讲解了什么主题？
```

### summary — 合格

```text
讲瑞士经济的那期内容，视频从哪几条主线解释其经济为何既富裕又相对稳定？
```

并含 `reference_points` 与正确的 `summary_eligible`。

### multi_hop — 不合格

```text
Raft 是什么？
```

### multi_hop — 合格

题面点名两期课程/视频，要求对比只有两侧合起来才成立的差异；两侧均有金标。

### unanswerable — 不合格

```text
人生的意义是什么？
```

### unanswerable — 合格

与库内主题相近、但明确未覆盖的具体问题；`expected_behavior` 写清。

### memory — 不合格

```text
我最近在 MCP 和 PostgreSQL 方面学了什么？
```

### memory — 合格

先定义 `seed_memories`（如备考重点），题面依赖该记忆做选择/计划；视频库 alone 不够。

---

## 10. 冻结

1. 全量通过 §6、§7 后写入正式 `benchmarks/eval_set.jsonl`
2. 同目录写简短 `eval_set_meta.json`：

```json
{
  "n_total": 0,
  "by_type": {},
  "n_videos_covered_by_detail": 0,
  "n_summary_eligible": 0,
  "corpus_videos": 50,
  "frozen_at": "YYYY-MM-DD"
}
```

3. 冻结后禁止因模型分数不好而删除难题或改松金标  
4. 允许修正：chunk 标错、`summary_eligible` 随 L2/L3 回填更新、为新视频追加题  
5. 变更后更新 `eval_set_meta.json`；正式跑分结果文件须带时间戳或不得与旧报告混用且不说明

---

## 11. 执行顺序

```text
1. 为全部视频产出 detail（满足每视频 ≥1）
2. 按配比补 multi_evidence、unanswerable、multi_hop、memory
3. 写 summary 题面与 reference_points；无合格 L2/L3 则 summary_eligible=false
4. 全量过 §6、§7
5. 写 eval_set.jsonl + eval_set_meta.json 并冻结
6. L2/L3 回填并校验主题后：将对应 summary_eligible 改为 true
7. 再跑分层类评测；检索/路由可在步骤 5 后先跑
```

---

## 12. 完成标准

- [ ] 题量 80–120  
- [ ] 每个视频 ≥1 道 `detail`  
- [ ] 配比落在 §2 表内（允许小幅偏差，须在 meta 说明）  
- [ ] 无不合格 summary 指代题进入分层计分池  
- [ ] 无未审 LLM 草稿直接入库  
- [ ] `eval_set.jsonl` 与 `eval_set_meta.json` 已写且字段合法  
