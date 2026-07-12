# Memento ASR 服务

独立 ASR 服务，使用自己的 venv 隔离 funasr/torch 等重量级依赖。接口兼容 OpenAI Whisper 风格的 `/v1/audio/transcriptions`，可本机、局域网或云主机独立部署。

> 推荐通过统一入口 `services/node/bootstrap.py` 运行（跨平台、隔离环境、自动探测设备）。本目录下的 `deploy.py` / `run.sh` 是更底层的独立路径，需要时再用。

## 推荐：通过 bootstrap 运行

```bash
python services/node/bootstrap.py   # 选「部署环境」装模型，再选「热启动服务」
```

通过 bootstrap 启动时，端口固定为 **16888**，设备按 venv 自动探测（CUDA / MPS / CPU）。

## 独立部署（底层路径）

```bash
cd services/asr
python deploy.py
```

`deploy.py` 会创建 `.venv`、安装 `requirements.txt`、按平台装 torch，并下载默认模型（`iic/SenseVoiceSmall` + `moonshine_voice/medium-streaming-en`）。设备默认 `auto`（自动探测），可用 `--device` 强制：

```bash
python deploy.py --device cuda                                              # 强制 CUDA
python deploy.py --device cpu                                               # 强制 CPU
python deploy.py --models sensevoice-small,moonshine-base-en                # 只装指定模型
python deploy.py --env-only                                                 # 只修环境，不下载模型
```

可选 slug：`sensevoice-small`、`moonshine-tiny-en`、`moonshine-base-en`、`moonshine-tiny-streaming-en`、`moonshine-small-streaming-en`、`moonshine-medium-streaming-en`。

## 启动（独立）

```bash
cd services/asr
bash run.sh
```

`run.sh` 默认监听 `0.0.0.0:8001`（注意：与 bootstrap 的 16888 不同），便于 LAN GPU 主机使用。可用环境变量覆盖：

```bash
ASR_HOST=127.0.0.1 ASR_PORT=8001 bash run.sh
```

## API

```bash
curl -X POST http://localhost:16888/v1/audio/transcriptions \
  -F model=iic/SenseVoiceSmall \
  -F response_format=verbose_json \
  -F file=@audio.wav
```

（独立 `run.sh` 启动时把端口换成 8001。）

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
rm -rf .venv models
```
