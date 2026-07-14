# 系统总览

Memento 把 **B 站 / 抖音 / 公开 YouTube 视频** 变成 **可检索的本地知识库**，再通过对话回答「视频里讲了什么」。
形态是 **单用户桌面应用**（开发态也可 web + 本地 backend）。

## 进程与目录边界

```
┌──────────────────── Electron / 浏览器 ────────────────────┐
│  frontend (Next.js)  ·  desktop/main.js 拉起 sidecar      │
└────────────────────────────┬─────────────────────────────┘
                             │ HTTP :8000
┌────────────────────────────▼─────────────────────────────┐
│  backend (FastAPI)                                        │
│  · 业务 API / 配置 / 聊天 Agent / 视频处理编排            │
│  · metadata.db + memento.db + 嵌入式 Qdrant               │
└───────┬───────────────────┬───────────────────┬──────────┘
        │ 本地可懒启动      │ OpenAI 兼容 HTTP  │ venv 存在时
        ▼                   ▼                   ▼
 services/asr:8001    models.chat / embedding  services/douyin_fetcher:8002
 （仅 loopback）      （默认常为 Ollama/云；   （抖音元数据/下载辅助）
 services/embedding:8003  也可指到本地/远端 :8003）
 （可选本地服务）
```

| 部分 | 路径 | 职责 |
|------|------|------|
| 后端 API | `backend/` | 唯一业务真相源：视频、文档、检索、会话、设置 |
| 前端 | `frontend/` | UI；经 HTTP 调 backend |
| 桌面壳 | `desktop/` | 启动 backend；douyin_fetcher 的 venv 存在时一并拉起 |
| ASR 服务 | `services/asr/` | 独立 venv；OpenAI 兼容转写 |
| Embedding 服务 | `services/embedding/` | 可选本地向量服务；默认应用配置常指向 Ollama 等 |
| Remote Node | `services/node/` | 在另一台机器上部署并启动 ASR+Embedding |
| 抖音辅助 | `services/douyin_fetcher/` | 抖音元数据 / 下载相关 sidecar |

重模型（torch / funasr / sentence-transformers）**不进主 backend 进程**，避免污染依赖与打包体积。  
backend **不会**懒启动 embedding。ASR 懒启动也只覆盖本地 loopback、`transcriptions` 协议，且当前 supervisor 依赖 macOS / Linux 风格的 `services/asr/.venv/bin/uvicorn`；其它情况须预先启动服务。

## 主数据流（用户分步触发，非自动串链）

下列是 **用户（或 UI）分别触发** 的阶段。process **不会**自动 clean/index。

1. **导入**：粘贴 URL → `POST /api/videos` → video `pending`
   导入时按 host 识别平台。B 站处理需要可直接解析 BV 号的 `/video/BV...` URL，抖音需要 URL 路径或查询参数中带可解析的 `aweme_id`；YouTube 支持公开单视频的 `youtube.com/watch`、`youtu.be` 和 `youtube.com/shorts` URL，并在导入时读取视频 ID、标题、频道名称、频道 ID 和时长
2. **处理**：`POST /api/videos/{id}/process`  
   - B 站默认只取软字幕；无字幕失败；可选 `?subtitle_fallback=asr` 再走 ASR  
   - 抖音主路径为下载 + ASR  
   - YouTube 默认优先中文字幕，同一语言优先创作者字幕；没有可用中文字幕时由用户选择其他语言字幕或 `?subtitle_fallback=asr`。当前不提供 YouTube 登录，不处理受限内容
   - 成功：写 raw markdown + document `raw`，video `completed`  
   - 失败：video `failed`，**不**新建 document
3. **清洗 + 索引**（知识库侧另一步）：`POST /api/documents/{id}/clean`  
   - LLM 清洗正文，同次产出 L2 摘要 / L3 概括 → 写 cleaned → 切块 embedding → Qdrant  
   - 成功后 document `indexed`  
   - 也可单独 `POST .../index`：对当前 `file_path`（raw 或 cleaned）做 L1 入库，**不**生成 L2/L3  
   - 配置项 `video_processing.auto_clean` 存在但 **当前未接线**，清洗仍须单独触发
4. **对话**：Agent 工具  
   - 知识：`search_knowledge` / `lookup_documents` / `summarize_document`  
   - 记忆：`propose_memory`；每轮从 `memories` 表拼入 `<user_memory>`

更细的阶段见 [视频摄入流水线](./video-pipeline.md)；记忆三层见 [记忆系统架构](./memory-architecture.md)。

## 运行时数据落点

默认数据根：`settings.storage.data_dir`（配置 / 默认值见代码与 yaml）。

| 子路径 | 内容 |
|--------|------|
| `metadata.db` | 业务：videos、documents、chat_*、`memories` 等 |
| `memento.db` | 模型 preset 与 `app_config` |
| `qdrant/` | 向量集合磁盘存储 |
| `knowledge/{platform}/raw\|cleaned/` | 文稿 markdown |
| `videos/temp/` | 处理中临时媒体；`keep_videos` 时归档到 `videos/` |

详见 [存储与检索](./storage-and-retrieval.md)。

## 配置入口

- 应用内 **Settings**：chat / embedding / asr 的 endpoint、key、model、preset
- 文件层：`backend/config/default.yaml` → 根目录 `config.yaml` / `config.local.yaml`
- 运行时：`memento.db` 的 **active preset + app_config** 覆盖 yaml；**环境变量最后覆盖**

详见 [独立服务与配置](./services-and-config.md)。

## 关键代码入口

| 入口 | 说明 |
|------|------|
| `backend/main.py` | FastAPI 生命周期：库初始化、路由挂载 |
| `backend/api/*` | HTTP 面 |
| `backend/core/video/` | 平台抓取、ASR、清洗、pipeline |
| `backend/core/rag/` | 切块、索引、检索、摘要存储 |
| `backend/core/agent/` | 对话 Agent |
| `scripts/dev.sh` | 开发态一键启动 |
| `desktop/main.js` | 桌面壳 sidecar 管理 |

## 相关文档

- [视频摄入流水线](./video-pipeline.md)
- [存储与检索](./storage-and-retrieval.md)
- [记忆系统架构](./memory-architecture.md)
- [独立服务与配置](./services-and-config.md)
