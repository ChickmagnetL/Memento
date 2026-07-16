# 独立服务与配置

重推理能力拆成独立进程；主 backend 只通过 **OpenAI 兼容 HTTP** 调用它们。  
配置以 **Settings + SQLite preset** 为运行时真相源。

## ASR 服务

| 项 | 值 |
|----|-----|
| 目录 | `services/asr/` |
| 默认地址 | `0.0.0.0:8001` |
| 常用 env | `ASR_HOST` / `ASR_PORT` / `ASR_DEVICE` / `MOONSHINE_VOICE_CACHE` |
| 部署 | `python deploy.py [--device cpu\|cuda\|mps\|auto]`：建 `.venv`、装依赖、下模型 |
| 启动 | `bash run.sh` 或由 backend supervisor / node bootstrap 拉起 |

### API（OpenAI Whisper 兼容）

- `GET /health`（根路径，**不是** `/v1/health`）
- `GET /v1/models` — 磁盘上已安装的模型
- `POST /v1/audio/transcriptions` — multipart：`file`、`model`、`response_format`
  - `text` → `{"text"}`
  - 其它（含 `verbose_json`）→ 简化结构 `{"text","segments":[{"start","text"}]}`

### 模型路由

- SenseVoice：`iic/SenseVoiceSmall`（别名 `sensevoice-small`）
- Moonshine Voice（spec 全集）：`tiny-en`、`base-en`、`tiny-streaming-en`、`small-streaming-en`、`medium-streaming-en`  
  请求侧可用 `moonshine_voice/{spec}` 或裸 spec
- 首次请求 lazy-load，缓存于 `services/asr/models/`

### Backend 如何用

- 客户端：`backend/core/video/asr_client.py`（`AsrServiceClient`）
- 配置：`settings.models.asr`（`endpoint` / `api_key` / `model` / `protocol`）
- 业务 endpoint 通常含 `/v1`，例如 `http://localhost:8001/v1`
- 协议：
  - `transcriptions` → `{endpoint}/audio/transcriptions`
  - `chat_audio` → `{endpoint}/chat/completions`（部分云厂商）
- 健康检查会先 **剥掉** endpoint 的 `/v1` path，再请求 `{base}/health`

**有限条件下的懒启动**（`backend/core/video/asr_supervisor.py`）：

1. 仅 `transcriptions` 协议会进入 supervisor；`chat_audio` 要求 endpoint 已经运行
2. 仅 hostname 为 `localhost` / `127.0.0.1` / `::1` 才可能 spawn
3. 已健康则立即返回
4. 否则按平台检查 ASR 启动器：macOS / Linux 使用 **`services/asr/.venv/bin/uvicorn`**，Windows 使用 **`services/asr/.venv/Scripts/uvicorn.exe`**
5. 启动器缺失、服务启动输出和运行时错误会写入 **`services/asr/logs/server.log`**
6. 存在则在 `127.0.0.1:<port>` spawn（port 来自 endpoint）
7. 默认最多等 **120s**，超时抛错
8. backend lifespan / `atexit` 调用 `shutdown()` 回收子进程

应用内 ASR 管理 API 前缀：`/api/asr`（deploy status / deploy / progress、local 模型管理等）。

## Embedding 服务

| 项 | 值 |
|----|-----|
| 目录 | `services/embedding/` |
| 默认地址 | `0.0.0.0:8003` |
| 常用 env | `EMBEDDING_HOST` / `EMBEDDING_PORT` / `EMBEDDING_DEVICE` |
| 部署 | `python deploy.py [--device ...] [--model ...]` |
| 默认模型 | `BAAI/bge-m3`（sentence-transformers，输出 1024 维） |

### API（OpenAI 兼容）

- `GET /health`
- `GET /v1/models`
- `POST /v1/embeddings` — JSON：`{"model","input":[...]}`，向量默认 L2 normalize

### Backend 如何用

- `CloudEmbeddingClient`：`POST {endpoint}/embeddings`
- 构造时 **endpoint / api_key / model 均不能为空**（本地服务不校验 key，但 backend 仍要求非空，可填占位如 `local`）
- Settings 指向本地服务时用 `http://<host>:8003/v1`（**需含 `/v1`**）
- 默认 yaml 常指向 Ollama（如 `http://localhost:11434/v1`）；以当前激活 preset 为准
- backend **不**懒启动 embedding 服务

独立服务默认的 BGE-M3 为 1024 维，而 `RAGConfig.vector_size` 默认 768。首次使用前须把两者配成一致；已有 Qdrant 集合须通过 switch / reindex 重建，不能只改 `rag.vector_size`。

## Remote Node（bootstrap）

路径：`services/node/bootstrap.py`  
**不依赖** Memento backend，只编排本机 `services/asr` 与 `services/embedding`。

| 命令 | 作用 |
|------|------|
| `probe` | 探测 device + 模型是否已缓存 |
| `deploy` | 对缺失的服务跑各自 `deploy.py` |
| `serve` | 启动 ASR:16888 + Embedding:16889，打印局域网配置提示 |

典型用法：GPU / 另一台机器当推理节点，主应用 Settings 填：

```
ASR:       http://<lan-ip>:16888/v1
Embedding: http://<lan-ip>:16889/v1
```

`probe` 的实现位于 `services/node/node_app/diag.py`，用于检查主机加速设备、已安装模型以及两个服务 venv 的 torch device；当前不做网络连通性或延迟测试。

## 配置系统

### 模型字段（chat / embedding / asr）

```
endpoint, api_key, model, protocol
```

`protocol` 主要用于 ASR：`transcriptions` | `chat_audio`。

### 加载优先级（后者覆盖前者）

1. `backend/config/default.yaml`
2. 项目根 `config.yaml`
3. `config.local.yaml`（通常 gitignore）
4. SQLite `memento.db` 中的 active preset + `app_config`
5. 环境变量（Pydantic nested，如 `MODELS__CHAT__ENDPOINT` 一类；以 `settings.py` 为准）

启动时 `migrate_config_to_db`：若 `model_presets` **已有数据则跳过**；否则只读取项目根 **`config.local.yaml`** 迁入 DB（models + 部分 app 段），成功后将该文件改名为 `config.local.yaml.bak`。  
**不会**从 `default.yaml` / `config.yaml` 迁移。

### Preset

- 每个服务名（chat / embedding / asr）可有多套 preset，一套 active
- embedding 切换须走 preview / switch；跨维度需要确认 reindex，同维度也只有在新旧 embedding 空间明确兼容时才能安全跳过重建（见 [存储与检索](./storage-and-retrieval.md)）
- embedding **禁止** 直接 `PUT /models/embedding/active`

### Settings API 概览（`/api/settings`）

| 能力 | 说明 |
|------|------|
| 读写 models | 三服务配置；列表脱敏，另有取明文 key 接口 |
| status | chat/embedding 配置完备性；ASR 探 health |
| presets CRUD | 按服务管理多套配置 |
| list-models | `POST .../presets/{id}/list-models` 等 |
| active / switch | chat/asr 可激活；embedding 走 switch-preview / switch-preview-config / switch |
| embedding reindex jobs | active 与按 id 查询 |

## 桌面壳要点

路径：`desktop/main.js`

1. douyin_fetcher venv 存在时启动（:8002）
2. 若 `GET http://localhost:8000/api/health` 未就绪则 spawn backend（约 30s 超时）
3. 打包态启动 `resources/frontend/server.js` 并等待 `127.0.0.1:3123`；开发态前端由外部 Next dev server 提供，默认 `http://localhost:3000`
4. 健康后 `loadURL(MEMENTO_FRONTEND_URL)`；未覆盖时按开发态 / 打包态分别使用 3000 / 3123
5. 退出时结束 sidecar

| | 开发态 | 打包态（以 main.js 为准） |
|--|--------|---------------------------|
| Backend | `MEMENTO_BACKEND_CMD` / venv uvicorn；未覆盖时可用开发产物 `backend/dist/memento-backend/memento-backend` | `process.resourcesPath/backend/memento-backend[.exe]` |
| Frontend | 外部 Next dev server；`MEMENTO_FRONTEND_URL` 默认 :3000 | Electron 启动 `process.resourcesPath/frontend/server.js`，默认监听 127.0.0.1:3123，再通过 URL 加载 |
| 项目根 | `MEMENTO_PROJECT_ROOT` 传给 backend | 冻结路径规则见 backend 打包入口 |

完整的 YouTube 支持要求 `yt-dlp` 同时能发现 JavaScript 运行时与 EJS 组件。开发态由系统 `PATH` 提供 Deno，后端依赖中的 `yt-dlp[default]` 安装 `yt-dlp-ejs`；打包态由 `scripts/stage-desktop-resources.mjs` 把锁定的 Deno 可执行文件放入 `resources/bin`，`desktop/main.js` 将该目录加入 backend 的 `PATH`，同时 `scripts/build-backend.sh` 通过 PyInstaller 收集 `yt_dlp_ejs`。两项缺一都不能视为完整的 YouTube 打包运行条件。

开发一键脚本：`scripts/dev.sh`。

## 端口速查

| 服务 | 默认端口 |
|------|----------|
| Backend API | 8000 |
| ASR | 8001 |
| Douyin fetcher | 8002 |
| Embedding 本地服务 | 8003 |
| Frontend dev | 3000 |
| Frontend 打包态 | 3123 |
| Ollama（常见外部 embedding/chat） | 11434 |

## 相关文档

- [系统总览](./system-overview.md)
- [视频摄入流水线](./video-pipeline.md)
- [存储与检索](./storage-and-retrieval.md)
