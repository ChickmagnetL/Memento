<h1 align="center">Memento</h1>

<p align="center"><a href="./README.en.md">English</a> | 简体中文</p>

<p align="center"><strong>把视频变成可对话、可溯源的本地知识库。</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-macOS-000000?logo=apple&logoColor=white" alt="macOS">
  <img src="https://img.shields.io/badge/platform-Windows-0078D4?logo=windows&logoColor=white" alt="Windows">
  <img src="https://img.shields.io/badge/data-local--first-2E7D32" alt="Local First">
  <img src="https://img.shields.io/badge/sources-Bilibili%20%C2%B7%20Douyin%20%C2%B7%20YouTube-FF6699" alt="Bilibili · Douyin · YouTube">
</p>

<p align="center"><img src="asset/hero.png" width="100%" alt=""></p>

粘贴 B 站、抖音或 YouTube 视频链接，Memento 会自动提取字幕（没有字幕时进行语音转写），整理成属于你自己的知识库。之后可以像对话一样对这些视频内容提问、总结与检索——每个回答都附带视频时间戳，点击即可跳回原视频核验。

<p align="center">
  <a href="#它解决什么问题">它解决什么问题</a> ·
  <a href="#三大核心能力">三大核心能力</a> ·
  <a href="#其他特性">其他特性</a> ·
  <a href="#安装">安装</a> ·
  <a href="#快速上手">快速上手</a> ·
  <a href="#技术文档">技术文档</a> ·
  <a href="#常见问题">常见问题</a>
</p>

---

## 它解决什么问题

- **视频看过就忘**：看完大量教程、访谈、讲座，过两天想用却想不起是在哪一期讲过。
- **无法检索视频内容**：想问"那个视频里关于 XX 是怎么说的"，而视频本身不支持搜索。
- **不希望数据交给云端**：希望知识库保存在自己的电脑上。

## 三大核心能力

### 一、分层知识：无论问细节还是问整体，都不会遗漏信息

普通视频问答通常只能抓取几段最相关的字幕片段，在回答"这整期视频讲了什么"这类问题时往往不完整。Memento 为每个视频建立三层知识结构：

| 知识层级 | 内容 |
| :---: | :--- |
| **L1 原文** | 逐句字幕，每句附带时间戳，支撑对具体内容的精确定位与引用。 |
| **L2 总结** | 该视频的内容总结（约一两个段落的篇幅），完整梳理讲解的要点与脉络，用于在不重看的前提下掌握单个视频的全貌。 |
| **L3 简介** | 类似视频描述，用一句话说明这个视频讲的是什么。当知识库累积大量视频时，它用于快速判断某个视频是否与当前问题相关，从而发现目标。 |

提问时，AI 会根据问题类型自动选择查询层级：问细节时直接检索 L1 原文片段；问整体或探索性问题时，先用 L3 简介定位相关视频，需要深入时再读取 L2 总结展开。

### 二、自建模型服务，支持 GPU 加速

语音转写（ASR）与向量化（Embedding）是计算量较大的环节。Memento 将二者作为**独立服务**运行：它们拥有各自的隔离环境与进程，可以部署在本机，也可以整体部署到本机之外的其他机器上（例如借用局域网里带显卡主机的算力），主应用桌面端因此保持轻量。

- **GPU 加速** — 自动识别并使用 **NVIDIA GPU（CUDA）** 与 **Apple Silicon GPU（MPS）**，显著提升转写与向量化速度。
- **桌面端保持轻量** — 计算密集型工作交给独立服务，主应用专注于交互体验。

部署这两个服务有两种方式：

- **本机部署** — ASR 可在应用 Settings 中点击 Deploy 一键部署；两者也都可以用下方脚本在本机部署。
- **另一台机器部署** — 在目标机器上单独获取 `services` 目录并运行部署脚本，启动后在 Settings 中填入其服务地址即可使用。

单独下载 `services` 目录（不必克隆整个仓库）：

```bash
git clone --filter=blob:none --sparse https://github.com/ChickmagnetL/Memento.git
cd Memento
git sparse-checkout set services
python services/node/bootstrap.py
```

脚本运行在隔离环境中（跨平台、自动设备检测），会引导安装依赖并启动服务。此方式适用于选择「本地」模型的用户；若使用云端 API，则无需部署，可直接跳过。

### 三、回答可溯源：可验证，而非只能信任模型

每个答案都附带原视频的时间戳引用，点击即可从对应位置播放。用户可以随时回到内容出处核验，而无需完全依赖模型的生成结果。配合关键词与语义相结合的混合检索（两者互相补足盲区，兼顾命中率与相关性），使回答既准确，又可查证。

> 注：B 站与 YouTube 支持点击时间戳自动跳转到对应位置；抖音因平台自身不支持时间戳参数，点击后会打开视频，需手动定位到对应时间点。

<p align="center"><img src="asset/chat-citation.png" width="88%" alt=""></p>

<p align="center"><img src="asset/chat-citation_2.png" width="88%" alt=""></p>

## 其他特性

- **一个链接入库** — 支持 B 站、抖音、公开 YouTube 单视频；有字幕时优先使用字幕，无字幕时可选择语音转写。
- **本地优先** — 知识库保存在本地，不强制依赖云端。
- **模型可替换** — 对话与向量化模型既可使用云端 API（DeepSeek、硅基流动、OpenAI 兼容接口），也可使用本地 Ollama。
- **记住用户偏好** — 跨会话保留使用习惯；长期偏好由 AI 提议、经用户确认后写入，避免静默记录错误或过时信息。

## 安装

### macOS

1. 下载 [Memento-macOS.dmg](https://github.com/ChickmagnetL/Memento/releases/latest/download/Memento-macOS.dmg)。
2. 打开 `.dmg`，将 Memento 拖入 Applications。
3. 由于应用未经签名，首次打开会被系统拦截。打开"终端"执行以下命令解除隔离属性，之后即可正常启动：

```bash
xattr -cr /Applications/Memento.app
```

### Windows

1. 下载 [Memento-Windows.exe](https://github.com/ChickmagnetL/Memento/releases/latest/download/Memento-Windows.exe) 安装包并运行，按提示完成安装。
2. 首次运行可能触发 SmartScreen 提示，点击"更多信息" → "仍要运行"即可。

## 快速上手

首次使用前，需要先在 **Settings** 中配置两类模型（均为必需）：

- **对话模型（chat）** — 负责聊天问答，以及入库前的字幕清洗与摘要生成。
- **嵌入模型（embedding）** — 负责将视频内容向量化入库。

两者均可使用云端 API 或本地 Ollama，通过 Settings 中的「预设」管理多套配置。完成配置后，即可按以下步骤使用：

1. **添加视频** — 在 Home 页面粘贴视频链接并添加。
2. **处理视频** — 点击「处理」提取字幕；无可用字幕时，可选择下载音频并进行语音转写。
3. **入库与提问** — 在 Knowledge Base 中选中文档完成入库（向量化），进入 Chat 提问；点击回答中的时间戳，可从视频对应位置播放。

## 技术文档

想深入了解系统设计，可查阅以下技术文档（仓库内 `docs/technical/` 与线上 Wiki 内容同步）：

- [系统总览](docs/technical/system-overview.md) — 各组成部分与运行架构
- [视频摄入流水线](docs/technical/video-pipeline.md) — 从链接到可检索知识的完整流程
- [存储与检索](docs/technical/storage-and-retrieval.md) — 数据落地、分块、混合检索与索引重建
- [记忆系统架构](docs/technical/memory-architecture.md) — 会话、分层知识与个人偏好的设计
- [独立服务与配置](docs/technical/services-and-config.md) — ASR / Embedding 服务与模型配置

在线版 Wiki：<https://chickmagnetl.github.io/Memento/#/>

## 常见问题

<details>
<summary><b>刚上手，有教程吗？</b></summary>

侧边栏的 **Help** 页面提供完整的应用使用教程，建议从那里开始。

</details>

<br>

<details>
<summary><b>数据保存在哪里？</b></summary>

对话记录、知识库、个人偏好等业务数据均保存在本机；模型调用则按 Settings 配置访问对应端点（本地或云端），两者相互独立。

</details>

<br>

<details>
<summary><b>需要联网吗？</b></summary>

导入视频时需访问对应平台获取内容；处理与对话时需访问模型端点。若使用本地模型，除首次下载外可离线使用。

</details>

<details>
<summary><b>模型使用收费吗？</b></summary>

取决于配置：使用云端 API（如 DeepSeek、硅基流动）按各服务商用量计费；使用本地模型（Ollama 或自建 ASR / Embedding 服务）除硬件成本外不额外收费。

</details>

<br>

<details>
<summary><b>没有字幕的视频怎么办？</b></summary>

可选择下载音频并通过 ASR 语音转写生成文稿，再清洗入库。

</details>

<details>
<summary><b>是否需要登录平台账户？</b></summary>

B 站、抖音的部分内容（如 AI 字幕）需要登录态。无需提前准备 cookie，应用内置了平台官方登录入口，可直接扫码或使用账号登录；无需登录时也可正常使用公开内容。

</details>

<br>

<details>
<summary><b>在应用里登录账户安全吗？</b></summary>

登录在平台官方页面完成，运行于应用内相互隔离的独立会话中，应用不接触明文密码。登录后仅保留用于抓取的会话凭证，并存储在本机。需注意，凭证与本机其他敏感数据一样，取决于本机自身的安全性。

</details>

<br>

<details>
<summary><b>YouTube 支持范围？</b></summary>

支持公开的 `youtube.com/watch`、`youtu.be`、`youtube.com/shorts` 链接；默认优先中文字幕，同一语言同时存在创作者字幕与自动字幕时优先采用创作者字幕。不支持登录，也不支持私有、会员、年龄或地区限制内容。

</details>

## 许可证

[MIT](https://github.com/ChickmagnetL/Probe/blob/main/LICENSE)

## 致谢

[Linux.Do](https://linux.do/) 社区
