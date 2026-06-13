# Memento ASR Service

独立的 ASR（语音识别）服务，使用自己的 venv 隔离 funasr/torch 等重量级依赖。支持中文（SenseVoice）和英文（Moonshine）转录。

## 安装

```bash
bash setup.sh
```

## 启动

```bash
cd services/asr
.venv/bin/uvicorn server:app --port 8001
```

服务默认监听端口 **8001**。

## 模型缓存

模型文件存放在 `model_cache/` 目录，首次转录时自动下载，无需手动操作。

## 删除

```bash
rm -rf .venv model_cache
```
