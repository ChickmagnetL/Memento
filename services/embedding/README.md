# Memento Embedding Service

Standalone OpenAI-compatible embedding server in its own venv.

## Install

```bash
cd services/embedding
python deploy.py
```

CUDA: `python deploy.py --device cuda`
MPS: `python deploy.py --device mps`
Custom model: `python deploy.py --model BAAI/bge-base-zh-v1.5`

## Start

```bash
bash run.sh
```

Defaults: host=0.0.0.0, port=8003, device=cpu.
Override: `EMBEDDING_HOST=127.0.0.1 EMBEDDING_PORT=8003 EMBEDDING_DEVICE=cuda bash run.sh`

## API

OpenAI-compatible `/v1/embeddings` and `/v1/models` endpoints.

### POST /v1/embeddings

```bash
curl -X POST http://localhost:8003/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model": "all-MiniLM-L6-v2", "input": ["hello world"]}'
```

Returns:
```json
{
  "data": [
    {"index": 0, "embedding": [0.1, 0.2, ...]}
  ],
  "model": "all-MiniLM-L6-v2",
  "usage": {"prompt_tokens": 0, "total_tokens": 0}
}
```

### GET /v1/models

```bash
curl http://localhost:8003/v1/models
```

Returns: `{"data": [{"id": "all-MiniLM-L6-v2", ...}]}`

### GET /health

```bash
curl http://localhost:8003/health
```

## Memento Settings

In Memento Settings → Embedding preset, configure:
- **Provider**: `cloud`
- **Endpoint**: `http://<this-machine-ip>:8003/v1`
- **API Key**: any non-empty string (e.g. `not-needed`)
- **Model**: `all-MiniLM-L6-v2`

Note: the endpoint must include `/v1` suffix.

## Remove

```bash
rm -rf .venv
```