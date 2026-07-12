# Memento Embedding 服务

独立、兼容 OpenAI 接口的 Embedding 服务，运行在自有 venv 中。

> 推荐通过统一入口 `services/node/bootstrap.py` 运行本服务（跨平台、隔离环境、自动探测设备）。本目录下的 `deploy.py` / `run.sh` 是更底层的独立部署路径。

## 推荐：通过 bootstrap 运行

```bash
python services/node/bootstrap.py   # 选「部署环境」装模型，再选「热启动服务」
```

通过 bootstrap 启动时，端口固定为 **16889**，设备按各 venv 自动探测（CUDA / MPS / CPU）。

## 独立部署（底层路径）

```bash
cd services/embedding
python deploy.py
```

`deploy.py` 会创建 `.venv`、安装 `requirements.txt` + torch，并下载默认模型 `BAAI/bge-m3`。设备默认 `auto`（自动探测），可用 `--device` 强制指定：

```bash
python deploy.py --device cuda                       # 强制 CUDA
python deploy.py --device mps                        # 强制 Apple Silicon MPS
python deploy.py --model BAAI/bge-m3                 # 显式指定模型（默认值）
python deploy.py --model Qwen/Qwen3-Embedding-0.6B   # 目录里的另一个模型
python deploy.py --env-only                          # 只装环境，跳过模型下载
python deploy.py --force-model                       # 清空缓存重新下载
```

可选模型：`BAAI/bge-m3`、`Qwen/Qwen3-Embedding-0.6B`。

## 独立启动

```bash
bash run.sh
```

`run.sh` 默认 host `0.0.0.0`、端口 `8003`、设备 `cpu`（注意：与 bootstrap 的固定端口 16889 不同）。可用环境变量覆盖：

```bash
EMBEDDING_HOST=127.0.0.1 EMBEDDING_PORT=8003 EMBEDDING_DEVICE=cuda bash run.sh
```

## API

提供兼容 OpenAI 的 `/v1/embeddings`、`/v1/models`、`/v1/warmup`、`/health` 接口。

### POST /v1/embeddings

```bash
curl -X POST http://localhost:16889/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model": "BAAI/bge-m3", "input": ["hello world"]}'
```

（独立 `run.sh` 启动时端口用 8003。）

返回：
```json
{
  "data": [
    {"index": 0, "embedding": [0.1, 0.2, ...]}
  ],
  "model": "BAAI/bge-m3",
  "usage": {"prompt_tokens": 0, "total_tokens": 0}
}
```

### GET /v1/models

```bash
curl http://localhost:16889/v1/models
```

返回已安装的模型，如 `{"data": [{"id": "BAAI/bge-m3", ...}, {"id": "Qwen/Qwen3-Embedding-0.6B", ...}]}`。

### GET /health

```bash
curl http://localhost:16889/health
```

## 在 Memento Settings 里配置

进入 Memento Settings → Embedding 预设：
- **Provider**：`cloud`
- **Endpoint**：`http://<本机IP>:16889/v1`
- **API Key**：任意非空字符串（如 `not-needed`）
- **Model**：`BAAI/bge-m3`

注意：endpoint 必须带 `/v1` 后缀。

## 卸载

```bash
rm -rf .venv models
```
