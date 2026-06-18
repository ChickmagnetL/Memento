# Memento ASR Service

独立的 ASR（语音识别）服务，使用自己的 venv 隔离 funasr/torch 等重量级依赖。ASR 模型由后端 Settings 或请求中的 `model` 配置决定，省略时默认使用 `iic/SenseVoiceSmall`。

Settings 中的 ASR Model 同时决定使用哪个后端：`moonshine_voice/*` 模型使用 Moonshine Voice，其他模型使用 FunASR。Phase 0 Moonshine medium 对应的模型字符串是 `moonshine_voice/medium-streaming-en`。

## 安装

```bash
bash setup.sh
```

`setup.sh` 安装默认 FunASR 依赖，默认模型为 `iic/SenseVoiceSmall`。

Moonshine Voice 是可选后端。使用 `moonshine_voice/medium-streaming-en` 模型前，需要在 ASR venv 中额外安装：

```bash
cd services/asr
.venv/bin/pip install -r requirements-moonshine.txt
```

## 启动

```bash
cd services/asr
.venv/bin/uvicorn server:app --port 8001
```

服务默认监听端口 **8001**。

## 模型缓存

FunASR 模型文件存放在 `model_cache/` 目录，首次转录时自动下载，无需手动操作。Moonshine Voice 的下载和缓存行为由 `moonshine-voice` 包管理，不使用本服务的 `model_cache/`。

## 删除

```bash
rm -rf .venv model_cache
```
