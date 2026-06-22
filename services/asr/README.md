# Memento ASR Service

独立 ASR 服务，使用自己的 venv 隔离 funasr/torch 等重量级依赖。接口兼容 OpenAI Whisper 风格的 `/v1/audio/transcriptions`，可本机、局域网或云主机独立部署。

## 安装

```bash
cd services/asr
python deploy.py
```

部署器会创建 `.venv`、安装 `requirements.txt`、按平台安装 torch，并预下载两个绑定模型：

- `iic/SenseVoiceSmall`
- `moonshine_voice/medium-streaming-en`

CUDA 主机可显式指定：

```bash
python deploy.py --device cuda
```

## 启动

```bash
cd services/asr
bash run.sh
```

`run.sh` 默认监听 `0.0.0.0:8001`，便于 LAN GPU 主机使用。可用环境变量覆盖：

```bash
ASR_HOST=127.0.0.1 ASR_PORT=8001 bash run.sh
```

## API

```bash
curl -X POST http://localhost:8001/v1/audio/transcriptions \
  -F model=iic/SenseVoiceSmall \
  -F response_format=verbose_json \
  -F file=@audio.wav
```

返回：

```json
{
  "text": "完整文本",
  "segments": [
    {"start": 0.0, "text": "分段文本"}
  ]
}
```

## 删除

```bash
rm -rf .venv model_cache
```
