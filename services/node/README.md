# Memento 远程节点（ASR + Embedding）

`services/node/bootstrap.py` 是 Memento 远程节点的统一入口，用于在一台机器（本机、局域网 GPU 主机或云主机）上一键部署并启动 ASR 与 Embedding 两个服务。它运行在自己的隔离环境里（uv + Python 3.12 + 各服务独立 venv），完全不碰系统 Python，跨平台支持 macOS / Windows / Linux。

## 前置要求

- 一台装有 **Python 3.10+** 的机器（`python` 命令可执行即可）。
- 联网（首次会下载 uv、依赖与模型）。
- uv 会被脚本自动引导安装，无需手动准备。

## 快速开始

```bash
python services/node/bootstrap.py
```

会弹出方向键菜单（↑/↓ 选择，Enter 确认，Ctrl+C 退出）：

| 序号 | 菜单项 | 作用 |
| --- | --- | --- |
| 0 | 查看状态 | 探测设备、各 venv 的 torch、已安装模型清单 |
| 1 | 部署环境（修环境 + 可选装模型） | 创建/修复 venv、依赖、torch，并多选下载模型 |
| 2 | 卸载模型 | 交互式卸载已安装的 ASR / Embedding 模型缓存 |
| 3 | 冷启动服务 | 启动 ASR(16888) + Embedding(16889)，不预加载模型 |
| 4 | 热启动服务 | 启动两个服务，并对每个 POST /v1/warmup 预加载模型 |
| 5 | 退出 | 退出菜单 |

**冷启动 vs 热启动**：两者都会把 ASR 与 Embedding 拉起在固定端口（16888 / 16889）。区别在于热启动会在服务就绪后额外调用 `/v1/warmup` 把模型权重提前载入显存/内存——首次请求延迟更低，但启动更慢、更吃内存。冷启动则等到首次推理时才加载模型。

## 命令行用法

菜单背后是三个子命令，可脚本化调用：

```bash
# 探测设备 + 已安装模型状态
python services/node/bootstrap.py probe

# 非交互部署：装环境 + 指定模型（逗号分隔）
python services/node/bootstrap.py deploy --asr sensevoice-small,moonshine-medium-streaming-en
python services/node/bootstrap.py deploy --embedding BAAI/bge-m3,Qwen/Qwen3-Embedding-0.6B

# 启动服务（冷启动）
python services/node/bootstrap.py serve

# 启动服务并预热（热启动）
python services/node/bootstrap.py serve --warm
```

说明：
- `--asr` 接 ASR 模型 slug（见下表），`--embedding` 接 model_id 或 slug，逗号分隔；不传且 stdin 是终端时进入交互多选。
- 设备由 bootstrap 自动探测（CUDA 优先 → Apple Silicon MPS → CPU），bootstrap 子命令本身不接受 `--device`。若需强制指定设备，走底层独立部署脚本 `services/asr/deploy.py --device cuda` / `services/embedding/deploy.py --device cuda`。

## 支持的模型

ASR：

| slug | 标签 | 体积 | 语言 |
| --- | --- | --- | --- |
| sensevoice-small | SenseVoice Small | 0.9GB | 中文 |
| moonshine-tiny-en | Moonshine Tiny EN | 71MB | 英文 |
| moonshine-base-en | Moonshine Base EN | 238MB | 英文 |
| moonshine-tiny-streaming-en | Moonshine Tiny Streaming EN | 80MB | 英文 |
| moonshine-small-streaming-en | Moonshine Small Streaming EN | 235MB | 英文 |
| moonshine-medium-streaming-en | Moonshine Medium Streaming EN | 429MB | 英文 |

Embedding：

| slug | model_id |
| --- | --- |
| bge-m3 | BAAI/bge-m3 |
| qwen3-embedding-0.6b | Qwen/Qwen3-Embedding-0.6B |

## 端口

由 `node_app/ports.py` 固定写死，不可在 bootstrap 层覆盖：

- ASR：**16888**
- Embedding：**16889**

## 在 Memento Settings 里配置

`serve` 启动后会打印局域网 endpoint，把它填进 Memento Settings：

- **ASR**（provider 选 `local`）：endpoint `http://<局域网IP>:16888/v1`，key 任意非空，model 填 `iic/SenseVoiceSmall` 或已装的 `moonshine_voice/<spec>`。
- **Embedding**（provider 选 `cloud`）：endpoint `http://<局域网IP>:16889/v1`，key 任意非空，model 填 `BAAI/bge-m3` 等。

endpoint 必须带 `/v1` 后缀。

## 设备

- 设备按 venv 自动探测：有 `nvidia-smi` → CUDA；Apple Silicon → MPS；否则 CPU。
- 中文 ASR（SenseVoice）可走 CUDA / MPS 加速。
- 英文 Moonshine 受上游 `moonshine_voice` 包限制，实际只能跑在 CPU 上。

## 国内网络

- pip 默认走清华源（`pypi.tuna.tsinghua.edu.cn`），可用 `PIP_INDEX_URL=""` 关闭。
- HuggingFace 默认官方源优先，失败时自动兜底到 `hf-mirror.com`（可用 `HF_ENDPOINT` 覆盖）。
- SenseVoice 走 modelscope 下载。

## 卸载与清理

```bash
# 卸载模型（只删模型缓存，保留 venv）
# 用菜单「卸载模型」，或直接删目录：
rm -rf services/asr/models services/embedding/models

# 彻底清理（连环境一起删）
rm -rf services/*/.venv services/*/models
```
