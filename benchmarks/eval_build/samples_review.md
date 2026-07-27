# 样题人工审阅文档

共 14 题，按视频分组。每题给出：题面 / 类型 / 金标位置（chunk index + 支撑句）/ 出题理由与反泄漏说明。

> **视频点名规则（EVAL_SPEC §3.0）**：
> - `detail` / `multi_evidence` / `memory`：**禁止**点名视频
> - `multi_hop`：只准概念级锚点（如「GFS 和 Raft」），不点标题/期数
> - `summary`：**必须**点名（总结是对着确定视频发起的动作）
> - `unanswerable`：默认不点名，仅假前提型可用「讲 xx 的视频里说…」
>
> 因此下文 summary 题保留「那期讲 xx 的视频」属规范要求，不是笔误；后续批量出题以 §3.0 为准。

---

## 视频 A：BV1mMHyz3Erk 《16分钟讲明白：程序、进程、内存和CPU到底啥关系？》（zh，短视频，CS）

### q_detail_BV1mMHyz3Erk_01（detail / medium）

**题面**：程序加载运行、变成进程之后，操作系统另外分配给它、用来存放运行期间产生的数据的那部分内存，视频里称之为什么？

**金标**：chunk 0（video_id: BV1mMHyz3Erk）
支撑句：“操作系统负责分配这部分内存，分配给进程的内存有一个特殊的名字，进程的地址空间”

**出题理由**：考查“地址空间”这一核心术语的定义，是视频前两分钟就给出的关键概念，检索区分度高。反泄漏：题面用“运行期间产生的数据”改写了原句“存储用户输入和临时结果”，未连续照抄。

---

### q_detail_BV1mMHyz3Erk_02（detail / medium）

**题面**：作者说自己去看了Linux内核源码后发现，操作系统里用来跟踪单个进程信息的这种数据结构，代码里实际起的名字是什么英文单词，而不是直接叫“进程”？

**金标**：chunk 8
支撑句：“这个结构被称为任务task，而不是进程process，之所以这样称呼，是因为LINUX使用任务一词来表示执行的基本单位，在单个数据结构中包含了线程和进程”

**出题理由**：考查一个视频里明确给出、但容易被忽略的“冷知识”细节（PCB在Linux里叫task），属于视频特有的表述，不是百科常识。反泄漏：题面用“作者说自己去看了源码后发现”重新组织了叙述视角。

---

### q_summary_BV1mMHyz3Erk_01（summary / medium，summary_eligible=true）

**题面**：那期用「程序、进程、内存和CPU」为题、还讲了PCB（进程控制块）和上下文切换机制的视频，整体是按哪几条主线把这些概念串起来讲的？

**reference_points**：程序 vs 进程的区别 / 进程的地址空间 / 上下文切换的机制与目的（安全性+正确性）/ PCB的组成 / Linux中task结构

**出题理由**：全片概览题，用标题关键词+“PCB”“上下文切换”两个独特术语作消歧锚点，避免“这期视频讲了什么”式的无锚点提问。该视频L2/L3均已就绪且主题准确，故 `summary_eligible=true`。

---

## 视频 B：cQP8WApzIQQ 《MIT 6.824 Lecture 1: Introduction》（en，长课程视频）

### q_detail_cQP8WApzIQQ_01（detail / medium）

**Question**：Based on the lecture, why might someone deliberately run their part of a computation on a separate machine from a collaborator's part, even though it would be simpler to run everything in one place?

**金标**：chunk 4
支撑句：“the final reason that people build this stuff is ... in order to achieve some sort of security goal ... You may want to split up the computation ... they only talk to each other through some sort of narrow narrowly defined network protocol.”

**出题理由**：考查构建分布式系统四大动机之一——安全隔离——这是容易被忽视的第四条理由（前三条是性能、容错、物理分布）。反泄漏：未连续复制“malicious”“bugs in it”等原句实词串。

---

### q_detail_cQP8WApzIQQ_02（detail / easy）

**Question**：The lecture explains a way to split a key-value store's data across many servers so each one holds only part of it, in order to gain parallel throughput. What one-word term is used for this data-splitting technique?

**金标**：chunk 20
支撑句：“this is a what's often called a sharded ... key value service ... sharding refers to splitting up the data, partitioning the data among multiple servers in order to get uh parallel speed up.”

**出题理由**：术语题，答案唯一且明确（sharding），难度定为easy。

---

### q_multi_evidence_cQP8WApzIQQ_01（multi_evidence / medium）

**Question**：In the lecture's scalability example (a front-end tier talking to a shared backend data store), what's the first fix engineers reach for as user traffic grows, and what component eventually stops that fix from working?

**金标**：chunk 37 + chunk 39
- chunk 37 支撑“先加更多web server分流用户”
- chunk 39 支撑“数据库最终变成瓶颈，加web server不再有效”

**出题理由**：这是讲座里一个完整的“先加前端服务器→数据库成为瓶颈”叙事，必须结合两个chunk才能完整回答（单独看37不知道最终瓶颈是什么，单独看39不知道最初用的什么解法），不是把两个无关事实硬凑。

---

### q_summary_cQP8WApzIQQ_01（summary / medium，summary_eligible=true）

**题面**：MIT 6.824分布式系统课由Robert Morris主讲的那节开篇课——覆盖课程安排、并以MapReduce收尾作为案例研究的那节——里，老师给出的构建分布式系统的核心动机有哪些？课程后续会反复出现的几个交叉主题又是什么？

**reference_points**：四大构建动机（性能/容错/物理分布/安全）/ 并发与局部故障是难点根源 / 课程结构（论文+两次考试+四个lab）/ 贯穿全课程的交叉主题（实现工具、可扩展性、容错、一致性）/ 以MapReduce收尾作案例研究

**出题理由**：用课程编号+讲者姓名+“以MapReduce收尾”这个具体特征做消歧锚点，与同语料库里的GFS课、Raft课区分开。该视频时长最长（116个chunk），是长视频优先出summary/detail的典型对象。

---

## 视频 C：BV1z8zPYjE4j 《三分化-饮食详解》（zh，健身饮食赛道，含约10个同题材干扰视频）

**反干扰核查说明**：已核对 `_index.md` 中健身/饮食题材的全部姊妹视频（2qf6ry-YjwU、3ub8RBE7BC8、8BKbu_s8p1Q、BV14v4y1G7A3、BV1654y1F7fZ、BV1HR7o6CE8q、BV1LAVh6UEQz、BV1ev411w7bs、cfXTQmFRjWU、lu_BObG6dj8、NS_GeXoboo4、ZlVBSZYaVF0），用 grep 精确匹配了本视频出现的具体数字/术语组合（“200~300”“500~700”“5:2.5:2.5”“碳水后置”），确认这些数字组合仅出现在本视频，其余视频未命中（BV1ev411w7bs虽也讲增肌饮食比例，但用的是6:2:2/5:2:3的不同比例体系，且未使用“碳水后置”一词）。

### q_detail_BV1z8zPYjE4j_01（detail / medium，hard_negative）

**题面**：增肌期把热量按训练日和休息日区别开安排的话，训练日建议保持多大的热量盈余、休息日又可以有多大的能量亏空？

（注：已按规范去掉「在这期专门讲三分化……的视频里」点名，定位视频本身即为考点；「训练日/休息日差异化热量」这一概念 + 具体区间数字在全库唯一）

**金标**：chunk 3
支撑句：“在训练日的时候，你要有200~300大卡的一个热量的盈余...在休息日也就是不训练那天，你可以有500~700大卡的能量亏空”

**出题理由**：这是全视频反复强调的“核心技巧”数字，具体到区间值，能天然区分开同题材的其他增肌/减脂视频（它们给出的是完全不同的比例或数值体系）。

---

### q_detail_BV1z8zPYjE4j_02（detail / medium，hard_negative + jargon）

**题面**：作者提到的「碳水后置」技巧，具体是指把全天多大比例以上的碳水化合物集中安排在训练后摄入？

**金标**：chunk 14
支撑句：“碳水的后置...我们要把我们这一天一大部分的碳水量，30%以上的碳水量放在你的训练后”

**出题理由**：“碳水后置”是本视频反复强调的核心技巧术语，具体到“30%”这个数字，姊妹视频（如BV1ev411w7bs）虽提到训练后吃快碳但未给出该术语和该阈值，唯一命中本视频。

---

### q_summary_BV1z8zPYjE4j_01（summary / medium，hard_negative，summary_eligible=true）

**题面**：那期专门为「三分化」训练配套讲饮食策略、特别提到训练日/休息日热量差异和「碳水后置」技巧的视频，整体是从哪几个方面给出饮食建议的？

**reference_points**：热量动态盈余/亏空 / 宏量营养素5:2.5:2.5比例 / 蛋白质分餐原则 / 碳水后置技巧 / 饮水与蔬菜脂肪等辅助细节

**出题理由**：消歧锚点用了标题关键词「三分化」+两个独特细节（训练日/休息日热量差异、碳水后置），避免与同赛道其他视频混淆。

---

## 全局题

### q_multi_hop_global_01（multi_hop / hard）

**Question**：GFS and Raft take very different stances on letting a single entity make a critical decision after a failure. What real-world limitation did GFS's single-master design eventually run into as Google's usage grew, and how does Raft avoid ever depending on one single server to decide who takes over?

（注：已按规范统一为「每侧一问、共两问」，并去掉课程/期数点名，只保留 GFS、Raft 概念级锚点）

**金标**：
- GFS侧：chunk 101（video_id: EpIgvowZr00）—— “the master had to have a table entry for every file in every chunk ... the master just ran out of memory ran out of RAM to store the files.”
- Raft侧：chunk 2 + chunk 16（video_id: 64Zp3tzNbpE）—— chunk 2: “the bad thing about having a single entity decide like who the primary is is that it itself as a single point of failure”；chunk 16: “the big insight ... is the idea of a majority vote”

**出题理由**：这是两节课之间真正的概念呼应——Raft lecture 明确点名了GFS这类“单实体决策”系统的问题，随后引出Raft用多数派投票取代单点决策。去掉GFS侧则不知道具体是什么局限（RAM耗尽），去掉Raft侧则不知道Raft具体怎么避免单点，缺一不可，题面点名了两侧课程（GFS lecture / Raft lecture）作锚点。

---

### q_unanswerable_global_01（unanswerable / medium，insufficient_information）

**题面**：操作系统做CPU调度的时候，具体用的是什么算法？比如是轮转调度还是优先级调度，视频里有讲过吗？

（注：已按 §3.0 去掉视频点名——insufficient_information 型不点名；「CPU调度」关键词仍会把检索引向该视频的近似命中陷阱，陷阱依然成立）

**近似命中依据**：chunk 9 —— “至此我们应该已经准备好深入探讨CPU调度了，这是未来一集的主题”

**出题理由**：这是一个精心设计的“近似命中”陷阱——视频明确提到了“CPU调度”这个话题（多次），容易被检索误判为相关命中，但视频本身明确说这是留给“未来一集”讲的内容，本片完全没有涉及具体调度算法。属于话题相关但库中确实无答案的合理提问。

---

### q_unanswerable_global_02（unanswerable / medium，reject_false_premise）

**题面**：GFS那节课里说，Google的论文一开始就为了避免单点故障，设计了自动故障切换的多副本Master集群，对吗？具体是怎么实现自动切换的？

**反驳依据**：chunk 102-103 —— “the master that was not an automatic story for master failover ... required human intervention to deal with a master that had sort of permanently crashed ... that could take tens of minutes or more”

**出题理由**：题设前提为假——讲座明确说GFS用的是单个master，且故障恢复不是自动的，需要人工介入，这恰恰是GFS后来被认为最严重的局限之一。题目模仿了“听说XX视频说了YY”的错误归因场景，正确行为是识别并反驳前提，而不是顺着假前提编造细节。

---

### q_memory_global_01（memory / medium）

**题面**：两周后就要面试了，按我之前跟你说过的复习进度，接下来这几天我应该优先补哪块内容？

**seed_memories**：
1. 用户正在为一场两周后的高级软件工程师技术面试做准备，重点考察分布式系统的一致性与容错设计
2. 用户目前已经过了Raft选主（leader election）机制部分，但对GFS的一致性弱保证以及它在实际生产环境中暴露的问题还比较陌生

**answer_key**：应优先复习GFS的弱一致性保证及其实际问题（单master内存瓶颈、无自动故障切换等），因为Raft部分已经过了、GFS部分还生疏。

**出题理由**：题面本身不包含“GFS”“一致性”等语料库高频词，只问“该补哪块”，答案完全依赖 seed_memories 里的两条个人进度信息（“已经过了Raft”“GFS还生疏”“两周后面试”），仅检索视频库无法回答——视频里没有任何关于“用户复习进度”的信息。未以关键词堆砌当主诱饵，符合memory题防止误走search路由的要求。

---

## 自审清单执行说明

对全部14题逐条执行了 EVAL_SPEC.md §6 检查清单：

- **§6.1 通用**：全部题面独立可读，未依赖未提供的上文；均含视频特有的具体数字/表述/结构（非百科常识题）；`type` 与 `expected_route` 一一核对匹配（detail/multi_evidence/multi_hop→search，summary→lookup+summarize，unanswerable→refuse，memory→memory）；必填字段按 §4 schema 逐条补全。
- **§6.2 detail/multi_evidence**：全部6道 detail + 1道 multi_evidence 的每个 gold chunk 均重新打开 manifest 原文核对，确认支撑句可核验答案（见上文逐题“支撑句”引用）；已按 §7 检查无≥8汉字/≥5英文实词连续照抄；multi_evidence 题（q_multi_evidence_cQP8WApzIQQ_01）已确认去掉任一 chunk 后答案不完整。
- **§6.3 multi_hop**：题面明确点名 "GFS lecture" 与 "Raft lecture" 两个来源锚点；已验证单侧视频不足以完整回答（GFS侧不知道Raft怎么避免单点，Raft侧不知道GFS具体遇到什么限制）。
- **§6.4 summary**：3道summary题均无「这期视频」类无锚点指代，均含标题关键词或独特细节作消歧锚点；reference_points 均为3-7条且逐条可追溯到该视频L2摘要或正文；三个视频L2/L3均已就绪且主题描述与正文一致（_index.md 中均标注 l2_ok=yes、非suspect），故 summary_eligible 均设为 true。
- **§6.5 unanswerable**：2道题分别对应 insufficient_information（视频提及话题但明确留待后续，库内无答案）和 reject_false_premise（前提与讲座内容直接矛盾）两种场景，均已用原文逐句核实“库中确实无答”或“前提确实为假”；均属合理相关提问，非纯无关闲聊。
- **§6.6 memory**：seed_memories（2条）足以支撑 answer_key 的核心要点（该补GFS一致性部分）；已确认仅靠视频库无法回答（视频库不含用户个人进度信息）；题面未以“GFS”“Raft”等库内高频词作为主诱饵。

