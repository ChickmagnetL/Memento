# 存储与检索

Memento 的本地持久化分三块：**业务 SQLite**、**配置 SQLite**、**嵌入式 Qdrant**，外加 knowledge 目录下的 markdown 原文。

## 数据目录

根目录：`settings.storage.data_dir`（resolve 后为绝对路径）。

- 开发态：相对路径按 `MEMENTO_PROJECT_ROOT`（默认仓库根）解析
- Windows 打包态：`<安装根>/data/storage`
- 其它平台打包态：Electron `<userData>/data`

打包态路径由 Electron 通过 `STORAGE__DATA_DIR` 覆盖 YAML / 数据库中可能存在的相对路径。

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
- `chat_sessions` / `chat_messages`：会话历史（编辑截断、删除配对、停止不落半截 assistant 等行为见 [Chat 会话、编辑与停止](./chat-sessions-and-editing.md)）
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
| 摘要集合 | `document_summaries` | 每个已有 L3 `brief` 的文档至多一个点 |

- 距离：COSINE
- `vector_size` 默认 **768**（`RAGConfig` / settings 默认值），必须与当前 embedding 输出维度一致
- 主集合 payload 常见字段：`document_id`、`video_id`、`platform`、`chunk_index`、`title_path`、`text`、`start_timestamp`；旧点缺少 `platform` 时，检索只会尝试从 B 站 / 抖音 `video_id` 兼容推断
- 摘要集合 payload：`document_id`、`title`、`brief`

**默认值冲突**：独立 Embedding 服务默认模型 `BAAI/bge-m3` 输出 **1024** 维，与 RAG 的 768 默认值不兼容。首次用该服务前应把 `rag.vector_size` 配为 1024；若集合已经创建，仅修改配置不会调整已有集合，须通过 embedding switch / reindex 流程重建。

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

BM25 语料当前在每次查询时通过 Qdrant 全量 scroll 重建。返回结果的 `score` 不是 RRF 融合分：有向量命中时保留原始向量相似度，仅 BM25 命中时使用 `1/rank`；RRF 只决定排序。

对外：`POST /api/search`；对话工具 `search_knowledge` 走同一检索能力。

## Embedding 客户端

- 工厂：`backend/core/models/factory.py` → `build_embedding_client()`
- 生产实现类：`CloudEmbeddingClient`（`backend/core/rag/embedding.py`）
- 协议：OpenAI 兼容 `POST {endpoint}/embeddings`
- 可指向：云厂商、Ollama、本仓库 `services/embedding`、Remote Node（都是 endpoint 目标，不是第二套 client）
- 低层客户端要求 `endpoint` / `api_key` / `model` 均非空；工厂会为 loopback endpoint 自动补 `local` 占位，云端或局域网 endpoint 仍须配置非空 key

## Embedding 切换与重建

当前 switch 流程以**向量维度**决定是否重建：

1. Settings preview：探测新维度 vs 当前 Qdrant 维度
2. 同维度：当前实现会直接激活 preset，**不**启 reindex
   这只在新旧 preset 使用完全相同或明确兼容的 embedding 空间时才安全。不同模型、版本或不兼容服务即使维度相同，向量也不能混用；当前流程不会识别这种情况，应避免直接切换并另行完整重建
3. 跨维度：需 `confirm_reindex=true` → `EmbeddingReindexJobManager` 后台单任务  
   激活 preset → 重建主集合与摘要集合 → 重索引所有 `indexed` 文档及 summary  
   失败文档：删向量点 + 重置索引状态；任务可处于 `completed_with_errors`

**后台任务限制**：reindex job 和进度只保存在 backend 进程内存中，不能在重启后续跑。任务会先激活新 preset、重建（清空）两个集合，再逐文档写回；执行期间须保持 backend 运行，中断可能留下部分重建的索引，需要重新实施完整重建。

主要路由（前缀 `/api/settings`）：

- `POST /models/embedding/presets/{id}/switch-preview`
- `POST /models/embedding/presets/{id}/switch-preview-config`
- `POST /models/embedding/presets/{id}/switch`
- `GET /embedding-reindex-jobs/active`
- `GET /embedding-reindex-jobs/{job_id}`

embedding **禁止** 直接 `PUT .../active`，须走 switch 流程。

## 文档删除与重新导入

`DELETE /api/videos/{video_id}` 只删除导入记录，并把关联 document 的 `video_id` 置空；document 记录、markdown 和向量都会保留。它与下面的文档删除不是同一语义。

`DELETE /api/documents/{id}` 总会删除 document 数据库记录和主集合中的 L1 切块；是否删除磁盘文件由 `delete_source_file` 控制：

- 默认 `false`：保留当前 `file_path` 指向的 markdown，之后可在知识库页面使用「Scan unimported」扫描并重新导入
- `true`：同时删除当前 `file_path` 指向的 markdown，不能再从该文件重新导入
- 未导入扫描当前只覆盖 `{data_dir}/knowledge/{platform}/raw/*.md`；cleaned 文件本身不在扫描范围内。已清洗视频通常仍保留 canonical raw 文件，重新导入时创建的是指向该 raw 文件的新 document 记录和新 ID，后续仍需重新 clean / index

**当前限制**：删除接口只清理主集合中的 L1 点，不会删除 `document_summaries` 中的 L3 点。因此 `lookup_documents` 仍可能返回已删除的旧 document ID；重新导入也不会复用或自动清理该旧摘要点。

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
