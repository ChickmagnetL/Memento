# Memento 技术 Wiki

本目录是 Memento 的**技术说明文档**集合，面向「以后要查清楚系统怎么工作」的场景。  

## 怎么读

| 你想了解… | 先看 |
|-----------|------|
| 整个产品由哪些部分组成 | [系统总览](./system-overview.md) |
| 视频从 URL 到可检索知识 | [视频摄入流水线](./video-pipeline.md) |
| 数据落在哪、怎么切块检索 | [存储与检索](./storage-and-retrieval.md) |
| 对话为什么分三层记忆 | [记忆系统架构](./memory-architecture.md) |
| ASR / Embedding 独立服务与配置 | [独立服务与配置](./services-and-config.md) |

## 文档列表

| 文档 | 说明 | 状态 |
|------|------|------|
| [system-overview.md](./system-overview.md) | 产品形态、进程边界、主数据流 | 已核对 |
| [video-pipeline.md](./video-pipeline.md) | B 站 / 抖音 / YouTube 导入、字幕、ASR、清洗、索引 | 已核对 |
| [storage-and-retrieval.md](./storage-and-retrieval.md) | SQLite / Qdrant / chunk / hybrid retrieval | 已核对 |
| [memory-architecture.md](./memory-architecture.md) | 会话历史 · 知识摘要层 · 个人偏好 | 已核对 |
| [services-and-config.md](./services-and-config.md) | ASR、Embedding、Remote Node、Settings | 已核对 |

## 目录约定

1. **只放可复用的技术说明**：架构、模块边界、数据布局、协议、部署方式。
2. **一篇一个主题**；交叉引用用相对链接，不复制大段正文。
3. **命名**：`kebab-case.md`；中文标题写在文内一级标题。
4. **索引只维护本 README**：新增文档时同步改「文档列表」与「怎么读」。
5. **实现细节以代码为准**：文档描述设计意图与稳定接口；细节漂移时优先改文档。

## 建议后续补全

- Chat Agent 工具与 SSE 协议
- 前端页面结构与 API 客户端
- Electron 桌面壳打包与 sidecar
- 抖音 fetcher 服务细节
- 数据生命周期补强（孤立摘要清理 / 物理文件统一管理）
