# Memento

Memento 是一款把视频内容转化为可检索知识库的桌面应用。粘贴 B 站、抖音或公开 YouTube 单视频链接，应用会优先提取字幕；没有可用字幕时，你可以确认改用语音转录。AI 清洗后入库，之后你就可以像对话一样，从这些视频内容里检索和提问。

目前 Memento 还没有打包好的安装包，需要克隆仓库后用一条命令启动（详见下文）。

## 运行 Memento

Memento 当前以开发态方式运行（暂未提供 .dmg / .exe 安装包）。准备好环境后，一条命令即可启动桌面应用。

### 一次性准备

1. 安装基础依赖：Python 3.10+、Node 18+、ffmpeg（音频提取必需，macOS 用 `brew install ffmpeg`）和 Deno（完整 YouTube 支持必需，macOS 用 `brew install deno`）。
2. 后端 Python 环境：
```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..
```
3. 前端依赖：
```bash
cd frontend && npm install && cd ..
```

> 桌面壳依赖（`desktop/node_modules`）如果缺失，启动脚本会自动 `npm install`，无需手动处理。

### 启动

```bash
./scripts/dev.sh
```

`dev.sh` 会拉起前端与桌面壳；桌面壳会再启动后端（端口 8000）和抖音抓取服务，ASR 服务按需懒启动（首次转录音频时才拉起）。关闭窗口或 Ctrl-C 会一并回收所有进程。打开后即进入桌面应用界面。

## 配置模型

首次使用前，在应用内的 **Settings** 页面配置两类模型（都必需）：

- **对话模型（chat）**：用于 Chat 页面的问答。
- **嵌入模型（embedding）**：用于把视频内容向量化入库。

两者既可以用云端 API（如 DeepSeek、硅基流动、OpenAI 兼容接口），也可以用本地 Ollama。Settings 里用「预设」管理多套配置。

> 如果你想在本机或另一台 GPU 机器上自建 ASR + Embedding 服务，可以用统一入口 `services/node/bootstrap.py`（跨平台、隔离环境、自动设备检测，固定端口 ASR=16888 / Embedding=16889），详见 [`services/node/README.md`](services/node/README.md)。这条仅在你选「本地」provider 时才需要；用云端 API 的话跳过。

## 使用流程

1. 打开应用进入 **Home**，粘贴 B 站、抖音或公开 YouTube 单视频链接，添加视频。
2. 在导入的视频上点「处理」，提取字幕；没有可用字幕时，由你选择是否下载音频并使用 ASR 转录。
3. 进入 **Knowledge Base（知识库）**，选中生成的文档，清理并入库（向量化）。
4. 进入 **Chat（对话）**，针对已入库的内容提问；点击回答中的时间戳可从视频对应位置播放。

## 常见问题

- **内置教程**：侧边栏的 **Help** 页面有完整的应用使用教程。
- **B 站字幕需要 cookie**：B 站的 AI 字幕通常需要 cookie。在 Settings 里配置 B 站 cookie 即可（切勿把真实 cookie 提交到代码库）。
- **YouTube 支持范围**：支持公开单视频的 `youtube.com/watch`、`youtu.be` 和 `youtube.com/shorts` 链接。导入时会读取标题、频道和时长，处理时默认优先中文字幕；同一语言同时存在创作者字幕和自动字幕时优先创作者字幕。当前不提供 YouTube 登录，也不支持私有、会员、年龄或地区限制内容。
- **打包 YouTube 运行条件**：开发环境由系统提供 Deno，`backend/requirements.txt` 会安装 EJS 组件；桌面安装包的构建流程必须同时带上 Deno 可执行文件和 `yt-dlp-ejs`，仓库现有资源暂存与后端打包脚本已包含这两项。
- **用 Ollama 跑本地模型**：在 Settings 里把 provider 选为 ollama，先拉取模型：
```bash
ollama pull qwen3
ollama pull qwen3-embedding:0.6b
```
`qwen3-embedding:0.6b` 输出 1024 维向量。
