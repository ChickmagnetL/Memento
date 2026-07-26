# 02 架构 A/B：分层 Agent vs 平铺 Agent（summary 完整度）

生成时间: 2026-07-24 04:58:00 UTC
Chat agent model: `gemini-3.5-flash` @ `https://api.42w.shop/v1`
Judge model: `gemini-3.5-flash` @ `https://api.42w.shop/v1`
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

- Layered mean score = **3.700**
- Flat mean score = **3.500**
- Delta (layered − flat) = **0.200**
- Layered win / tie / loss = **3** / **4** / **3** (rates: 30.0% / 40.0% / 30.0%)

## Score distribution

| score | layered n | flat n |
|-------|-----------|--------|
| 1 | 3 | 0 |
| 2 | 0 | 3 |
| 3 | 0 | 2 |
| 4 | 1 | 2 |
| 5 | 6 | 3 |

## Per-question results

| id | video_id | lacks_L2/L3 | L score | F score | winner | L tools | F tools | lookup | summarize |
|----|----------|-------------|---------|---------|--------|---------|---------|--------|-----------|
| q004 | P-NmMX9rlYQ | Y | 1 | 3 | `flat` | lookup_documents, summarize_docum... | search_knowledge | Y | Y |
| q009 | -HOzOBmQ5ro |  | 4 | 4 | `tie` | lookup_documents, summarize_docum... | search_knowledge | Y | Y |
| q013 | 185XGEMefgc |  | 5 | 5 | `tie` | search_knowledge | search_knowledge |  |  |
| q018 | vkpS7WztTMc |  | 5 | 3 | `layered` | lookup_documents, summarize_document | search_knowledge | Y | Y |
| q019 | oYxTTirKY8M | Y | 5 | 5 | `tie` | lookup_documents, search_knowledge | search_knowledge | Y |  |
| q026 | BV1FUYQz7E4H |  | 5 | 5 | `tie` | lookup_documents, summarize_document | search_knowledge | Y | Y |
| q030 | BV14v4y1G7A3 |  | 5 | 4 | `layered` | lookup_documents, summarize_docum... | search_knowledge | Y | Y |
| q035 | BV1ev411w7bs | Y | 1 | 2 | `flat` | lookup_documents, summarize_document | search_knowledge | Y | Y |
| q040 | BV1Zk9FBwELs |  | 1 | 2 | `flat` | lookup_documents, summarize_document | search_knowledge | Y | Y |
| q044 | BV1E7wtzaEdq |  | 5 | 2 | `layered` | lookup_documents, summarize_document | search_knowledge | Y | Y |

## Sample Q&A pairs

### Sample 1: q018

**Q:** 这篇演讲的主要内容是什么？

**Notes:** 苏姿丰结合在MIT的求学与个人职业经历，鼓励毕业生勇敢面对难题、发挥工程师本能并在AI时代创造属于自己的运气

**Scores:** Layered=5 | Flat=3 | winner=`layered`
**Judge:** Answer B covers all key reference points including Lisa Su's MIT/career experiences, engineering instincts, facing challenges, and creating luck, whereas Answer A omits her personal background and specific key themes.

**Layered answer:**

这篇演讲是 **AMD CEO 苏姿丰（Lisa Su）在麻省理工学院（MIT）毕业典礼上的演讲**，核心内容如下：

* **求学与校训影响**：回顾了自己在 MIT 从本科到博士的求学历程，分享了 MIT “手脑并用（Mens et Manus）” 的校训如何塑造了她的工程师直觉，并在职业生涯中持续产生深远影响。
* **职业经历与挑战**：结合在 IBM 和 AMD 的工作与领导经历，鼓励毕业生不要害怕困难，要勇敢迎难而上、应对最艰难的挑战，以此创造属于自己的机遇与运气。
* **AI 的未来与使命**：阐述了 AI 在医疗等众多领域蕴藏的巨大潜力，并强调**技术本身无法决定未来**，只有兼具使命感与责任感的人才能引领时代的变革与发展。

**Flat answer:**

这篇演讲是 **AMD CEO 苏姿丰（Lisa Su）在麻省理工学院（MIT）2026届毕业典礼上的致辞**。

演讲的主要内容围绕 **AI 技术变革、技术与人的关系、以及对毕业生的寄语** 展开，核心要点如下：

---

## 1. 技术与人的关系：AI 无法决定要解决什么问题
苏姿丰指出，未来 10 年的技术发现将超越过去 30 年的总和，但**决定未来走向的并非技术本身，而是优秀的人**。
> 无论 AI 多么强大，[00:05 AI 无法决定哪些问题值得去解决](memento://play?platform=youtube&video_id=vkpS7WztTMc&t=5)。世界不仅需要掌握强力工具的人，更需要有方向感、判断力和勇气、明确知道“工具该用于何处”的人。

---

## 2. 面对未知与困难的信念
作为 MIT 校友，她鼓励 graduates 保持信心与面对未知的勇气：
> 在未来的岁月里，你一定会走进某个自己完全摸不着头脑的房间或领域，但要记住：[14:42 你以前就经历过这种时刻，去弄懂它、解决它](memento://play?platform=youtube&video_id=vkpS7WztTMc&t=882)。

---

## 3. 祝福与表达感谢
* **向亲友致谢：** 提醒毕业生感谢一路支持和陪伴他们的家人与爱人，[14:24 这份成就同样属于他们](memento://play?platform=youtube&video_id=vkpS7WztTMc&t=864)。
* **对毕业生的祝贺：** [14:59 表达作为校友的自豪与深切祝福](memento://play?platform=youtube&video_id=vkpS7WztTMc&t=899)，祝贺 2026 届全体毕业生。

### Sample 2: q030

**Q:** 这篇视频主要为健身新手讲解了哪些核心理论与训练建议？

**Notes:** 提高心肺、筛查问题、熟悉动作模式、高频中等强度一分化训练以及评估BMI与体脂率，并附带一套适合新手的训练计划

**Scores:** Layered=5 | Flat=4 | winner=`layered`
**Judge:** Answer B covers all key points from the rubric including the assessment of BMI and body fat percentage, whereas Answer A misses the BMI/body fat evaluation point.

**Layered answer:**

基于视频内容，凯小王为健身新手梳理了 **五大核心认知理论**，并结合这些理论提供了一套具体可操作的 **训练建议与计划**，旨在帮助小白安全、高效地入门。

---

## 核心认知理论

在正式开始力量训练前，新手需要明确以下 5 点核心认知：

1. **心肺功能是运动的基石**：不论是增肌还是减脂，刚进健身房都应先从有氧运动开始提升心肺。良好的心肺功能不仅能提高运动表现，还能在力量训练中有效防止低血糖的发生 [[00:03] 心肺重要性](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=3).
2. **筛查并改善身体问题**：大部分人由于长期久坐，普遍存在关节活动度受限（如髋关节、足背屈）和体态问题，盲目上重量极易受伤。
3. **重视动作模式与肌肉记忆的积累**：健身动作需要像练习篮球投篮一样通过成千上万次的重复来建立肌肉记忆。新手不要心急，应沉浸于动作细节，通过重复来掌握正确的发力 [[06:33] 熟悉动作模式](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=393).
4. **高频中等强度的“一分化训练”**：新手由于神经募集肌肉的能力较差，无法在单次训练中达到极高强度，因此不适用大神的低频力竭训练。相反，**高频率、中等强度的一分化全身训练**能积累更多重复次数，最适合新手快速进步 [[08:03] 一分化理论](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=483).
5. **结合 BMI 与体脂率评估身材与方向**：通过“田字格”精准定位自己。例如，“高BMI、高体脂”的人完全可以同时进行增肌和减脂；而体重轻但体脂高的“瘦胖子”（低BMI、高体脂）不应盲目节食或大量有氧，而应通过力量训练来塑造肌肉形态 [[10:33] 增肌减脂与身材评估](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=633)。

---

## 新手训练建议与计划

视频提供了一套适合新手执行 **1-2个月** 的一分化全身训练计划，频率为 **练二歇一** 或 **练一歇一**。每个动作做 **3组**（第一组15次，后两组各12次），**每组保留 2-3 次余量，切记不要推到绝对力竭** [[17:33] 计划概述与卧推](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=1053)。

为了安全避坑，计划中特意用**稳定性高、轨迹固定的器械**代替了高难度的自由重量动作：

* **胸部（卧推）**：作为上肢大复合动作以调动大肌肉群。注意不要含胸，肘关节不要超伸锁死，杠铃推到最后应垂直于肩部上方 [[17:33] 卧推要领](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=1053)。
* **背部（坐姿龙门架划船）**：*替代俯身杠铃划船或硬拉*。因为新手后链稳定性不足，俯身极易导致腰酸。坐姿龙门架划船能减轻腰椎压力，高效募集背部肌肉，感受肩胛的内收与下回旋 [[22:03] 坐姿划船](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=1323)。
* **腿部（倒蹬/腿举）**：*替代自由深蹲*。针对新手髋关节和足背屈活动度受限的问题，倒蹬器械安全性高、腰椎压力极低。**注意：** 蹬起时膝盖绝对不能完全锁死超伸，下放时腰部要紧贴靠背，不能为了追求过深而让腰部离开椅面 [[24:03] 倒蹬要领](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=1443)。
* **肩部（史密斯推肩）**：*替代侧平举*。侧平举力臂长且需要极高的肩胛控制，新手容易斜方肌代偿。史密斯推肩轨迹固定，小臂应放在肩胛面（与身体呈约15度夹角），下放至鼻子高度即可，向上推至肘关节微屈 [[26:33] 史密斯推肩](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=1593)。
* **手臂与核心**：计划还包含杠铃弯举、龙门架下压及核心综合训练 [[17:33] 计划概述](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=1053)。

**关于减脂的额外建议：** 
如果以减脂为主要目标，可以在这套力量计划结束后加做有氧，或者在早上做有氧；但不建议新手刚开始就尝试“空腹有氧”，以防发生低血糖的危险 [[16:33] 减脂有氧建议](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=993)。

**Flat answer:**

根据视频讲解，新手健身的核心理论与训练建议主要包含以下 **4 个核心理论** 与具体的 **训练计划建议**：

---

## 核心理论与原则

### 1. 优先建立心肺基础，避免高风险有氧
* **核心观点**：有氧运动是所有运动的基础。良好的心肺功能不仅能提升运动表现，还能提高安全性，防止训练中出现低血糖 [00:03](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=3)。
* **避坑建议**：新手切忌盲目尝试高强度的 HIIT、塔巴塔或跳跃类爆发力训练，这在缺乏关节稳定性和动作模式时风险极高 [01:03](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=63)。
* **推荐心率区间**：建议控制在 **50%–60% 最大心率**（最大心率 ≈ $220 - \text{年龄}$），大体重人群可从游泳、慢走过渡到快走 [01:03](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=63)。

### 2. 训练前筛查基础身体问题
* **核心观点**：关节活动度和稳定性决定了训练效果 [02:03](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=123)。
* **建议**：训练前要先评估是否存在圆肩驼背、骨盆前倾、腰椎问题或足背屈受限等情况，纠正或避开高危动作后再进行强度训练 [02:03](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=123)。

### 3. 重视动作模式的积累
* **核心观点**：健身动作是一种肌肉记忆，需要重复数百上千次才能真正掌握 [06:33](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=393)。
* **建议**：训练时要沉浸集中，关注发力细节与收缩感，切忌盲目追求大重量，动作变形容易导致伤病 [06:33](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=393)。

### 4. 采用“高频中等强度”的一分化训练
* **核心观点**：新手肌肉募集能力较弱，局部刺激不深，不需要套用大神的低频高强度训练（如五分化或绝对极限力竭）[08:03](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=483)。
* **建议**：建议使用**一分化训练**（全身训练），以高频率（如一周 4–5 次，练一歇一或练二歇一）和中等强度积累动作次数，熟练后再过渡到两分化或三分化 [08:03](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=483)。

---

## 新手 1-2 个月训练计划建议

视频建议新手优先使用安全性高、轨迹固定的器械，避开对腰椎剪切力大或要求极高稳定性的动作 [17:33](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=1053)：

* **胸部（卧推）**：大复合动作，建议做 3 组（15次 / 12次 / 12次），每组保留 2-3 次余量不力竭，避免关节锁死 [17:33](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=1053)。
* **背部（坐姿龙门架划船）**：相比俯身杠铃划船，龙门架坐姿划船腰椎压力低，能更安全高效地感受背部收缩 [22:03](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=1323)。
* **腿部（倒蹬/腿举）**：替代自由深蹲/硬拉，对受限的髋关节与足背屈更加友好，腰椎更安全；注意蹬起时膝盖绝对不能过伸锁死 [24:03](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=1443)。
* **肩部（史密斯推肩）**：轨迹固定，比侧平举更少出现斜方肌代偿，能在肩胛面内安全提高肩部力量 [26:33](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=1593)。
* **手臂与核心**：搭配杠铃弯举、龙门架下压及核心综合训练 [17:33](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=1053)。

### Sample 3: q044

**Q:** 这期视频的主要内容是什么？

**Notes:** 从底层工程视角梳理并讲解从大模型（LLM）到 Agent Skill 等核心 AI 概念的底层逻辑与关联

**Scores:** Layered=5 | Flat=2 | winner=`layered`
**Judge:** Answer A directly and accurately captures all key points from an engineering perspective, whereas Answer B incorrectly claims no video was specified and includes irrelevant content.

**Layered answer:**

这期视频（**《从 LLM 到 Agent Skill，一期视频带你打通底层逻辑！》**）从工程视角出发，系统且通俗地拆解了当前 AI 领域的核心概念与底层架构，主要涵盖以下几个核心模块：

---

## 核心内容大纲

* **LLM 的底层运行逻辑**  
  剖析大语言模型的本质，讲解基于 Transformer 的“文字接龙”预测机制。

* **Tokenizer 与 Token 计算**  
  介绍 Tokenizer 如何对文本进行编码与解码，以及 Token 消耗与计算的具体原理。

* **Context 与记忆机制**  
  讲解 Context（上下文）与 Context Window（上下文窗口）如何为大模型提供临时记忆能力。

* **Prompt 工程与约束**  
  对比 User Prompt 与 System Prompt 的作用，说明如何控制与约束大模型的输出行为。

* **工具调用与 MCP 协议**  
  阐述模型如何与外部环境交互（Tool Calling），以及统一工具接入标准的 **MCP (Model Context Protocol)** 协议。

* **Agent 与 Agent Skill**  
  深入讲解具备自主规划与工具调用能力的 Agent，以及如何通过说明文档控制 Agent 行为规则的 Agent Skill。

---

总的来说，这期视频帮助观众打通了从基础语言模型到复杂 Agent 应用落地的完整技术认知体系。

**Flat answer:**

您没有指定具体的视频。知识库中包含多期不同主题的视频，主要包括以下几内容方向：

## 1. 人工智能与大模型底层逻辑
在视频[《从 LLM 到 Agent Skill，一期视频带你打通底层逻辑！》](memento://play?platform=bilibili&video_id=BV1E7wtzaEdq)中，主要讲解了：
* **Context Window（上下文窗口）**：介绍了上下文窗口的概念及主流大模型（如 GPT-4.5、Gemini 1.5 Pro、Claude 3.5 Sonnet）的 Token 容量范围[10:14](memento://play?platform=bilibili&video_id=BV1E7wtzaEdq&t=614)。
* **RAG（检索增强生成）**：讲解了面对超长文档时，如何通过 RAG 抽取出最相关的片段传给大模型，避免超出窗口限制并降低成本[11:14](memento://play?platform=bilibili&video_id=BV1E7wtzaEdq&t=674)。
* **Prompt（提示词）与 Prompt 工程**：解释了 Prompt 的定义以及清晰表达的重要性[11:45](memento://play?platform=bilibili&video_id=BV1E7wtzaEdq&t=705)，并区分了 User Prompt（用户提示词）与 System Prompt（系统提示词）的区别[13:15](memento://play?platform=bilibili&video_id=BV1E7wtzaEdq&t=795)。

---

## 2. 健身训练（新手一分化训练）
在视频[《【新手入门】帮你省去50节私教费！一分化训练 理论+计划+讲解》](memento://play?platform=bilibili&video_id=BV14v4y1G7A3)中，主要针对健身新手讲解了：
* **动作模式与重复积累**：强调健身需要静心并积累足够的重复次数来建立肌肉记忆，而不是急于使用大重量[06:33](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=393)。
* **高频中等强度原则**：说明新手为什么适合做高频中等强度的一分化训练，帮助肌肉建立募集感并避免伤病[08:03](memento://play?platform=bilibili&video_id=BV14v4y1G7A3&t=483)。

---

## 3. 增肌饮食与营养补充
在视频[《保姆式增肌饮食分享/比例/碳蛋脂算法》](memento://play?platform=bilibili&video_id=BV1ev411w7bs)中，主要讲解了：
* **水分补充与评判标准**：强调每天摄入 3～3.5 升水的重要性，并介绍通过尿液颜色判断身体水合状态的方法[23:18](memento://play?platform=bilibili&video_id=BV1ev411w7bs&t=1398)。
* **七大营养素与蔬菜摄入**：提醒增肌者不能只关注蛋白质和米饭，还需要通过多色蔬菜补充维矿和抗氧化物质以帮助身体恢复[23:48](memento://play?platform=bilibili&video_id=BV1ev411w7bs&t=1428)。

---

如果您想询问某具体视频的详细内容，请提供具体的视频名称或主题。

## Docs lacking L2/L3

Known video_ids without reliable L2/L3 in this corpus: `BV1ev411w7bs`, `P-NmMX9rlYQ`, `oYxTTirKY8M`
- Questions tagged lacks_l2_l3: **3**
- Layered may still call lookup/summarize; summarize may generate on the fly or return thin content. Flat must synthesize from search chunks only.

## Notes

- Blind LLM-as-judge: answers randomized as A/B; scores mapped back to layered/flat.
- Flat agent has only search_knowledge; Layered has search + lookup + summarize + propose_memory.
- Docs lacking L2/L3 tags: ['BV1ev411w7bs', 'P-NmMX9rlYQ', 'oYxTTirKY8M']
- Judge.complete called via asyncio.to_thread to avoid nested event loop.
