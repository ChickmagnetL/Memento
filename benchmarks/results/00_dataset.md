# 00 数据集灌库报告

生成时间: 2026-07-24 03:14:50 UTC（系统设计 2h 于本地 batch index 补跑成功）
BASE_URL: `http://127.0.0.1:8010`
成功(含已就绪跳过): 10 / 10，失败: 0

| # | 标签 | 状态 | video_id | document_id | chunk_count | 错误/备注 |
|---|------|------|----------|-------------|-------------|-----------|
| 1 | PostgreSQL 22min | success | `BV1FUYQz7E4H` | `1661a6ae3c5949dfb420de3690f673f5` | 12 |  |
| 2 | 凯圣王一分化 | success | `BV14v4y1G7A3` | `6912e2f626554fddb0b07fd5d0c45149` | 8 |  |
| 3 | 增肌饮食 | success | `BV1ev411w7bs` | `ef6d166a52274710bc3472332c916664` | 18 | clean_failed_indexed_raw: clean failed: 500 {"detail":"Cleaned output must be valid JSON"} |
| 4 | harness | success | `BV1Zk9FBwELs` | `5b0275d76ecd40d8a8a515bec5e535ae` | 12 |  |
| 5 | AI 名词 | success | `BV1E7wtzaEdq` | `4eddb0234a6846c69bc2ca2e9bb427e5` | 18 |  |
| 6 | GDP | success | `P-NmMX9rlYQ` | `f78e77740180456381e76204b57dfdb8` | 21 | clean_failed_indexed_raw: clean failed: 500 {"detail":"Cleaned output timestamps must come from source timestamps"} |
| 7 | 瑞士经济 | skipped_ready | `-HOzOBmQ5ro` | `ebc78c155d43433e9f417bbf36ddecf9` | 21 | already completed+indexed |
| 8 | MCP VS API | success | `185XGEMefgc` | `ec3ce6678c7f4467ab867d8a548295cf` | 9 |  |
| 9 | 苏姿丰 | skipped_ready | `vkpS7WztTMc` | `22a2c7c7da0c438ea6cd1c1ef7b2d633` | 15 | already completed+indexed |
| 10 | 系统设计 2h | success | `oYxTTirKY8M` | `d903d515ad124b8999552c522aee0cd7` | 189 | local_batch_index (HTTP embed timeout; clean 413) |

## URL 清单

1. [PostgreSQL 22min](https://www.bilibili.com/video/BV1FUYQz7E4H/?)
2. [凯圣王一分化](https://www.bilibili.com/video/BV14v4y1G7A3/?)
3. [增肌饮食](https://www.bilibili.com/video/BV1ev411w7bs/?)
4. [harness](https://www.bilibili.com/video/BV1Zk9FBwELs/?)
5. [AI 名词](https://www.bilibili.com/video/BV1E7wtzaEdq/?)
6. [GDP](https://www.youtube.com/watch?v=P-NmMX9rlYQ)
7. [瑞士经济](https://www.youtube.com/watch?v=-HOzOBmQ5ro)
8. [MCP VS API](https://www.youtube.com/watch?v=185XGEMefgc)
9. [苏姿丰](https://www.youtube.com/watch?v=vkpS7WztTMc)
10. [系统设计 2h](https://www.youtube.com/watch?v=oYxTTirKY8M)

## 知识库与评测集摘要

更新时间: 2026-07-24 03:46:48 UTC
- 已索引文档数: 10
- 评测问题总数: 48
- 类型分布: detail=34, summary=10, self=4
- 期望路由: search=34, lookup+summarize=10, memory=4
- 输出文件: `benchmarks/eval_set.jsonl`


## Fix A — eval_set 数据质量清洗

更新时间: 2026-07-24 05:44:44 UTC

### 操作摘要

| 操作 | 数量 | ID |
|------|------|-----|
| 移除 (常识/弱 grounding) | 6 | q001, q020, q021, q022, q041, q042 |
| 重写 (对齐 transcript) | 1 | q024 |
| 重标 GT chunks | 8 | q003, q007, q008, q028, q029, q036, q038, q039 |
| 保留 summary | 10 | 全部保留 |
| 保留 self | 4 | 全部保留 |

### 移除明细

- **q001** (`P-NmMX9rlYQ`): GDP 支出法公式（C+I+G+进出口）为教科书常识；虽在视频中出现，但 LLM 无需检索即可答对，污染 search 路由评测。
- **q020** (`oYxTTirKY8M`): DNS 将域名映射到 IP 为通用系统知识，任何 LLM 无需视频即可答对。
- **q021** (`oYxTTirKY8M`): SQL 事务 ACID 四性质为教科书常识。
- **q022** (`oYxTTirKY8M`): round robin 负载均衡为通用系统知识。
- **q041** (`BV1E7wtzaEdq`): Transformer 由 Google 团队于 2017 年提出为广为人知的常识；视频仅一笔带过。
- **q042** (`BV1E7wtzaEdq`): BPE 为 NLP 常识；视频仅以「可看另一期」方式顺带提到，非本片核心可检索事实。

### 重写明细

- **q024**: 原文未点名 postgresql.conf / pg_hba.conf，只说两个配置文件；listen_addresses 改为 * 在 chunk 1 中有明确跨度。
  - 旧问: 视频中在Ubuntu服务器上开启PostgreSQL远程连接时修改了哪两个配置文件？
  - 新问: 视频中在 Ubuntu 服务器上放开 PostgreSQL 远程连接时，第一个配置文件里需要把 listen_addresses 改成什么？
  - 新 notes: 星号 *（表示监听所有可用网络）
  - 新 GT: `[{"document_id": "1661a6ae3c5949dfb420de3690f673f5", "chunk_index": 1}]`

### 重标 GT 明细

- **q003**: [3, 2, 5] → [5, 4, 3] — 二手/闲鱼/所有权流转/增值 主要落在 chunk 3–5；原 GT 含较弱的 chunk 2。
- **q007**: [11, 17, 12] → [11] — 罗氏/诺华/市值前三 集中在 chunk 11；原 GT 含不相关 chunk 17/12。
- **q008**: [13, 12, 14] → [13, 12] — 双轨制/学徒 在 chunk 12–13；去掉无命中的 chunk 14。
- **q028**: [6, 3, 4] → [6, 3] — 倒蹬 vs 深蹲硬拉 主答案在 chunk 6；chunk 3 含活动度背景；去掉弱相关 chunk 4。
- **q029**: [5, 1, 4] → [5] — 高BMI高体脂→增肌减脂可同时进行 完整在 chunk 5。
- **q036**: [10, 7, 11] → [1] — 70%→95% 与改进点在 chunk 1；原 GT 指向后期总结块。
- **q038**: [6, 1, 7] → [6, 7, 11] — 六层定义从 chunk 6 起，续层在 7，总结在 11；去掉弱相关 chunk 1。
- **q039**: [8, 4, 3] → [8] — Context Reset / 上下文焦虑 完整在 chunk 8。

### 清洗后评测集分布

- 评测问题总数: **42**（清洗前 48）
- 类型分布: detail=28, summary=10, self=4
- 期望路由: search=28, lookup+summarize=10, memory=4
- 备份: `benchmarks/eval_set.jsonl.pre_fix_a`
- 审计日志: `benchmarks/results/fix_a_audit.json`
- 可复现脚本: `benchmarks/fix_eval_set.py`

### 质量标准（Fix A 后）

- 每道剩余 **detail** 题均：`relevant_chunks` 非空，且答案跨度可在对应视频 transcript/chunk 中核对。
- summary / self 保持空 GT（by design）。
- 已剔除「仅靠世界知识即可答、会把 search 路由拉偏」的 detail 题。
