# 存储与检索

Memento 的本地持久化分三块：**业务 SQLite**、**配置 SQLite**、**嵌入式 Qdrant**，外加 knowledge 目录下的 markdown 原文。

## 数据目录

根目录：`settings.storage.data_dir`（resolve 后为绝对路径）。

| 路径 | 用途 |
|------|------|
| `{data_dir}/metadata.db` | 业务连接（`app.state.sqlite`） |
| `{data_dir}/memento.db` | 配置连接（preset + `app_config`） |
| `{data_dir}/qdrant/` | Qdrant 磁盘存储 |
| `{data_dir}/knowledge/{platform}/raw/` | 原始转写 markdown |
| `{data_dir}/knowledge/{platform}/cleaned/` | 清洗后 markdown |
| `{data_dir}/videos/temp/` | 处理中临时媒体 |
| `{data_dir}/videos/` | `keep_videos=true` 时归档的媒体 |
| `{data_dir}/local_asr_models.json` | 本地 ASR 模型管理状态（若使用） |

启动初始化见 `backend/main.py` 的 lifespan。

## 两个 SQLite 库

两库都用 **同一份** `schema.sql` 初始化（文件里会建全表），但 **运行时连接职责分离**：

### metadata.db（业务连接）

主要读写：

- `videos`：导入记录与处理状态
- `documents`：文稿记录；`status` 为 `raw | indexed`；含 `chunk_count`、`summary`、`brief` 等
- `chat_sessions` / `chat_messages`：会话历史
- `memories`：用户记忆 / 学习画像条目

### memento.db（配置连接）

主要读写：

- `model_presets` + `active_preset`：chat / embedding / asr 多套配置与当前激活项
- `app_config`：storage / rag / video_processing 等段

`get_settings()` 在 yaml 基础上用该库覆盖。  
schema 中另有历史表 `config`（key/value），**当前代码未使用**；配置以 `app_config` 为准。

## Qdrant 集合

| 集合 | 默认名 | 内容 |
|------|--------|------|
| 主集合 | `documents` | L1 切块向量 |
| 摘要集合 | `document_summaries` | 每文档一个点：L3 `brief` 向量 |

- 距离：COSINE
- `vector_size` 默认 **768**（`RAGConfig` / settings 默认值），必须与当前 embedding 输出维度一致
- 主集合 payload 常见字段：`document_id`、`video_id`、`chunk_index`、`title_path`、`text`、`start_timestamp`
- 摘要集合 payload：`document_id`、`title`、`brief`

**不变量**：摘要向量与原文切块分集合存放，细节检索不会被摘要「抢走」位置。

## 切块（chunking）

实现：`backend/core/rag/chunking.py` → `chunk_markdown()`

- 按 `#` 文档标题与 `##` 小节分段（**不**递归 `###` 及更深）；跳过纯元数据引言
- 段内按行贪心聚合：`chunk_size=800`，`overlap=80`（字符）
- chunk 文本带 `title_path` 前缀（`doc_title` 或 `doc_title > section`）；抽取首个 `[MM:SS]` / `[HH:MM:SS]` 作为 `start_timestamp`
- 由 `DocumentIndexer.index()` 调用

## 索引

`DocumentIndexer.index`（`backend/core/rag/indexer.py`）：

1. 读文档当前 `file_path`（raw 或 cleaned，以 DB 为准）
2. `chunk_markdown` → embedding 批量向量
3. 删除该 document 的旧点 → upsert 新点
4. 标记 document `indexed` 并更新 `chunk_count`

clean 成功路径会自动 index；也可单独触发 index API（不生成 L2/L3）。

## 混合检索（Hybrid）

`HybridRetriever`（`backend/core/rag/retrieval.py`）大致步骤：

1. 查询文本 embedding → 向量检索取 `top_k * 2`
2. 拉取语料做 **BM25Plus**（jieba 分词，见 `tokenize.py`）取 `top_k * 2`
3. **加权 RRF** 融合（`fusion.py`，k=60）：默认权重 `bm25:0.3`、`vector:0.7`（`settings.rag.hybrid_weights`，可配置覆盖）
4. 截断为 `top_k` 返回

对外：`POST /api/search`；对话工具 `search_knowledge` 走同一检索能力。

## Embedding 客户端

- 工厂：`backend/core/models/factory.py` → `build_embedding_client()`
- 生产实现类：`CloudEmbeddingClient`（`backend/core/rag/embedding.py`）
- 协议：OpenAI 兼容 `POST {endpoint}/embeddings`
- 可指向：云厂商、Ollama、本仓库 `services/embedding`、Remote Node（都是 endpoint 目标，不是第二套 client）
- 构造要求 `endpoint` / `api_key` / `model` 均非空；本地无真实 key 时填占位（如 `local`）

## 维度切换与重建

当切换 embedding 模型导致 **向量维度变化** 时：

1. Settings preview：探测新维度 vs 当前 Qdrant 维度
2. 同维度：可直接激活 preset，**不**启 reindex
3. 跨维度：需 `confirm_reindex=true` → `EmbeddingReindexJobManager` 后台单任务  
   激活 preset → 重建主集合与摘要集合 → 重索引所有 `indexed` 文档及 summary  
   失败文档：删向量点 + 重置索引状态；任务可处于 `completed_with_errors`

主要路由（前缀 `/api/settings`）：

- `POST /models/embedding/presets/{id}/switch-preview`
- `POST /models/embedding/presets/{id}/switch-preview-config`
- `POST /models/embedding/presets/{id}/switch`
- `GET /embedding-reindex-jobs/active`
- `GET /embedding-reindex-jobs/{job_id}`

embedding **禁止** 直接 `PUT .../active`，须走 switch 流程。

## 关键代码入口

| 主题 | 路径 |
|------|------|
| 生命周期初始化 | `backend/main.py` |
| 配置加载 | `backend/config/settings.py` |
| Schema | `backend/storage/schema.sql` |
| SQLite 客户端 | `backend/storage/sqlite_client.py` |
| Qdrant 封装 | `backend/storage/qdrant_client.py` |
| 切块 | `backend/core/rag/chunking.py` |
| 索引 | `backend/core/rag/indexer.py` |
| 混合检索 | `backend/core/rag/retrieval.py` |
| 分词 / BM25 | `backend/core/rag/tokenize.py` |
| RRF | `backend/core/rag/fusion.py` |
| Embedding 客户端 | `backend/core/rag/embedding.py` |
| Embedding 工厂 | `backend/core/models/factory.py` |
| 摘要存储 | `backend/core/rag/document_summary_store.py` |
| 维度重建 | `backend/core/rag/embedding_reindex.py` |
| Knowledge 路径 | `backend/core/documents/paths.py` |
| 搜索 API | `backend/api/search.py` |

## 相关文档

- [系统总览](./system-overview.md)
- [视频摄入流水线](./video-pipeline.md)
- [记忆系统架构](./memory-architecture.md)
- [独立服务与配置](./services-and-config.md)
