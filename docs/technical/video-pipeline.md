# 视频摄入流水线

从 URL 到「可对话检索」不是一条全自动长链，而是 **几次明确的 API 步骤**。  
处理请求本身是 **同步阻塞** 的（无视频处理队列）；用 claim 防止并发重复处理。

## 端到端阶段

```
POST /api/videos
   → video: pending（尽量补全元数据）

POST /api/videos/{id}/process[?subtitle_fallback=asr]
   成功 → raw markdown + document: raw + video: completed
   失败 → video: failed（通常不新建 document；见 error_message）

POST /api/documents/{id}/clean   （用户/UI 另一步，process 不会自动触发）
   成功 → cleaned markdown + L2/L3 + 同请求 index → document: indexed
   注意：写盘 / 改 file_path 后若 index 失败，可能留下 cleaned 文件而 status 仍为 raw
```

也可单独 `POST /api/documents/{id}/index`：读取 **当前** `document.file_path`（raw 或 cleaned）做 L1 切块入库，**不**校验是否 cleaned，也 **不**生成 L2/L3。

| 目标 | 需要 |
|------|------|
| L1 可检索 | `index` 或 clean 内自动 index → `indexed` |
| 推荐完整路径（清洗 + L2/L3 + L1） | process → **clean** |
| 仅 process | raw 文稿 + document `raw`，向量库无该文档点 |

配置项 `video_processing.auto_clean` 默认存在但 **代码未接线**。

## 平台差异

| | B 站 | 抖音 |
|--|------|------|
| URL 识别 | bilibili.com / b23.tv | douyin.com / iesdouyin.com |
| 主路径 | 软字幕（CC）优先 | **无字幕主路径**，直接 ASR |
| 元数据 | B 站 API（title / author / duration 等） | 能解析 `aweme_id` 且配置了 fetcher 时，经 `services/douyin_fetcher`（默认 :8002）补全；否则降级为 URL/默认 title |
| 音频下载 | `AudioDownloader`（yt-dlp） | `DouyinAudioDownloader` + fetcher |
| 字幕预检 | `GET .../check-subtitles`（受 cookie 影响） | 固定 `has_subtitles: true`（无软字幕轨语义） |

## 字幕优先 vs ASR 兜底

- **默认 `process`**：`allow_asr_fallback=False`
  - B 站：只取字幕；没有字幕（含需登录 cookie）→ 失败
  - 抖音：始终走下载 + ASR
- **可选**：`?subtitle_fallback=asr` → B 站字幕为空时再下载音频并调用 ASR
- ASR 客户端读 `settings.models.asr`（默认 `http://localhost:8001/v1`，模型 `iic/SenseVoiceSmall`，协议 `transcriptions`）
- 本地 loopback 且 ASR 未起时，backend 可通过 **supervisor 懒启动**（见 [独立服务与配置](./services-and-config.md)）

**重处理**：claim 允许 `pending | failed | completed`。对已 `completed` 的视频再 process 时，会重置 **canonical raw** 文档的索引状态（删 Qdrant 点、document → `raw`）。

## AI 清洗（clean）

入口：`POST /api/documents/{id}/clean` → `TranscriptCleaner`

- 只把 `## Transcript` 之后的正文送给 LLM；文首元数据 header 原样保留
- 模型输出 JSON 三字段：
  - `cleaned_text`：清洗后时间戳正文（合并相邻行、去语气词、纠错与标点）
  - `summary`：L2 段落摘要（约 150–300 字）
  - `brief`：L3 一句话概括（≤60 字）
- 成功路径顺序：写 `knowledge/{platform}/cleaned/{video_id}.md` → 更新 `document.file_path` → 持久化 L2/L3 → **同请求内** index

## 文档状态

| 实体 | 状态 | 含义 |
|------|------|------|
| video | `pending` | 已导入未处理 |
| video | `processing` | 已被 claim，处理中 |
| video | `completed` | 文稿提取成功 |
| video | `failed` | 处理失败（见 `error_message`） |
| document | `raw` | 有文稿，未（再）入库向量 |
| document | `indexed` | 已入 Qdrant |

说明：没有单独的 `cleaned` 文档状态；是否清洗看磁盘路径与 `file_path`（raw vs cleaned）。

## 磁盘路径约定

```
{data_dir}/knowledge/{platform}/raw/{video_id}.md
{data_dir}/knowledge/{platform}/cleaned/{video_id}.md
```

`platform` 为 bilibili / douyin 等。

## 与记忆 / 检索的衔接

- clean 时写入的 L2/L3 支撑对话工具 `lookup_documents` / `summarize_document`
- L1 切块进入主向量集合，供 `search_knowledge` / 混合检索
- 设计意图见 [记忆系统架构](./memory-architecture.md)；索引细节见 [存储与检索](./storage-and-retrieval.md)

## 关键代码路径

| 职责 | 路径 |
|------|------|
| 创建 / process / 字幕预检 | `backend/api/videos.py` |
| Cookie / 刷新 token（`/api/video-processing`） | `backend/api/video_processing.py` |
| clean / index | `backend/api/documents.py` |
| 流水线编排 | `backend/core/video/pipeline.py` |
| B 站字幕 | `backend/core/video/bilibili.py` |
| 抖音下载 | `backend/core/video/douyin.py` |
| ASR 客户端 | `backend/core/video/asr_client.py` |
| ASR 懒启动 | `backend/core/video/asr_supervisor.py` |
| B 站音频下载 | `backend/core/video/audio.py` |
| raw markdown | `backend/core/video/markdown.py` |
| AI cleaner | `backend/core/video/cleaner.py` |
| 路径约定 | `backend/core/documents/paths.py` |
| 索引器 | `backend/core/rag/indexer.py` |
| L2/L3 存储 | `backend/core/rag/document_summary_store.py` |
| 抖音 sidecar | `services/douyin_fetcher/` |
| 本地 ASR | `services/asr/` |

## 相关文档

- [系统总览](./system-overview.md)
- [存储与检索](./storage-and-retrieval.md)
- [独立服务与配置](./services-and-config.md)
