"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

export type Language = "en" | "zh-CN";

const STORAGE_KEY = "memento-language";

const zhCN: Record<string, string> = {
  "Home": "首页",
  "Knowledge Base": "知识库",
  "Chat": "聊天",
  "Login": "登录",
  "Settings": "设置",
  "Help": "帮助",
  "Expand sidebar": "展开侧边栏",
  "Collapse sidebar": "收起侧边栏",
  "Operation failed": "操作失败",
  "Video": "视频",
  "Paste a Bilibili, Douyin, or YouTube URL": "粘贴哔哩哔哩、抖音或 YouTube 视频链接",
  "Saving...": "正在保存...",
  "Add video": "添加视频",
  "Imported videos": "已导入的视频",
  "All imported records, ordered by import time.": "全部导入记录，按导入时间排序。",
  "Scroll or click a card to focus.": "滚动或点击卡片进行查看。",
  "Toggle list view": "切换列表视图",
  "Completed": "已完成",
  "Failed": "失败",
  "Processing": "处理中",
  "Pending": "等待处理",
  "Platform": "平台",
  "Author": "作者",
  "Unknown author": "未知作者",
  "Imported": "导入时间",
  "Checking...": "正在检查...",
  "Processing...": "正在处理...",
  "Re-process": "重新处理",
  "Process": "处理",
  "Delete": "删除",
  "No videos yet. Paste a Bilibili or Douyin URL above to get started.": "还没有视频，请在上方粘贴哔哩哔哩或抖音视频链接开始使用。",
  "Language": "语言",
  "General": "通用",
  "Choose the language used by the application.": "选择应用界面使用的语言。",
  "Embedding": "嵌入模型",
  "Endpoint": "服务端点",
  "API Key": "API 密钥",
  "Model": "模型",
  "Protocol": "协议",
  "Requests {url}": "请求地址：{url}",
  "Local ASR installed": "本地 ASR 已安装",
  "Local ASR not installed": "本地 ASR 未安装",
  "Local ASR Model Settings": "本地 ASR 模型设置",
  "Deploy": "部署",
  "Close": "关闭",
  "ASR Environment": "ASR 环境",
  "Environment ready": "环境已就绪",
  "Environment not installed": "环境未安装",
  "Environment size: ~{size}": "环境大小：约 {size}",
  "Environment size: —": "环境大小：—",
  "Uninstall Environment": "卸载环境",
  "Install Environment": "安装环境",
  "Family": "系列",
  "Size": "大小",
  "SenseVoice (Chinese)": "SenseVoice（中文）",
  "Moonshine Voice (English)": "Moonshine Voice（英文）",
  "Uninstall": "卸载",
  "Install": "安装",
  "Loading…": "正在加载…",
  "Cancel": "取消",
  "Active": "使用中",
  "Preset actions": "预设操作",
  "Rename": "重命名",
  "Not set": "未设置",
  "Show model options": "显示模型选项",
  "Getting Models...": "正在获取模型...",
  "Get Model List": "获取模型列表",
  "Hide API key": "隐藏 API 密钥",
  "Show API key": "显示 API 密钥",
  "Save": "保存",
  "Activate": "启用",
  "New Chat": "新对话",
  "The important thing is not to stop questioning.": "重要的是不要停止提问。",
  "Albert Einstein": "阿尔伯特·爱因斯坦",
  "Message": "消息",
  "Ask your knowledge base...": "向你的知识库提问...",
  "Send": "发送",
  "Select conversation": "选择对话",
  "Search conversations": "搜索对话",
  "No conversations found": "未找到对话",
  "Delete {title}": "删除“{title}”",
  "Delete conversation": "删除对话",
  "Delete conversation?": "删除对话？",
  "This conversation and all its messages will be permanently deleted.": "此对话及其全部消息将被永久删除。",
  "Deleting...": "正在删除...",
  "Close memories": "关闭记忆",
  "Open memories": "打开记忆",
  "Memories": "记忆",
  "Loading memories...": "正在加载记忆...",
  "No memories yet": "暂无记忆",
  "Use /remember or let the agent propose memories.": "使用 /remember，或让智能体提出记忆建议。",
  "Delete memory": "删除记忆",
  "Memory proposal": "记忆建议",
  "Reject": "拒绝",
  "Edit": "编辑",
  "Accept": "接受",
  "Confirm": "确认",
  "Thinking…": "正在思考…",
  "Calling tool: {tool}…": "正在调用工具：{tool}…",
  "Calling tool…": "正在调用工具…",
  "Got it — remembered.": "好的，已经记住了。",
  "{count} model available.": "有 {count} 个可用模型。",
  "{count} models available.": "有 {count} 个可用模型。",
  "No models returned.": "未返回任何模型。",
  "Switching embedding preset...": "正在切换嵌入模型预设...",
  "Switching preset...": "正在切换预设...",
  "Cannot delete embedding presets while an embedding reindex job is running.": "嵌入索引重建任务运行时无法删除嵌入模型预设。",
  "Cannot delete the last preset.": "无法删除最后一个预设。",
  "Cannot save embedding presets while an embedding reindex job is running.": "嵌入索引重建任务运行时无法保存嵌入模型预设。",
  "Saving and checking embedding preset...": "正在保存并检查嵌入模型预设...",
  "Saved.": "已保存。",
  "Saving": "正在保存",
  "Activating": "正在启用",
  "Confirm save": "确认保存",
  "Confirm activate": "确认启用",
  "Embedding reindex status: {status}": "嵌入索引重建状态：{status}",
  "Preset: {preset}": "预设：{preset}",
  "Stage: {stage}": "阶段：{stage}",
  "Progress: {processed} / {total} documents": "进度：{processed} / {total} 个文档",
  "Failed documents:": "失败的文档：",
  "{action} {preset} will rebuild the embedding index.": "{action} {preset} 将重建嵌入索引。",
  "Dimension {current} to {next}. {count} indexed documents will be reprocessed.": "维度从 {current} 变更为 {next}。将重新处理 {count} 个已索引文档。",
  "New preset": "新建预设",
  "Logged in": "已登录",
  "Not logged in": "未登录",
  "Login with QR code": "使用二维码登录",
  "Relogin": "重新登录",
  "Failed to load settings": "加载设置失败",
  "{platform} login successful": "{platform} 登录成功",
  "Failed to save login credentials": "保存登录凭证失败",
  "{platform} credentials refreshed": "{platform} 凭证已刷新",
  "Failed to save refreshed credentials": "保存刷新凭证失败",
  "This feature is only available in the Electron desktop app.": "此功能仅在 Electron 桌面应用中可用。",
  "Clearing login status...": "正在清除登录状态...",
  "Failed to clear login status": "清除登录状态失败",
  "Log in to video platforms with a QR code to access content that requires an account": "使用二维码登录视频平台，以访问需要账号的内容",
  "Loading...": "正在加载...",
  "Untitled": "无标题",
  "Not indexed": "未建立索引",
  "Indexed ({count} chunks, {date})": "已建立索引（{count} 个分块，{date}）",
  "Preview": "预览",
  "Clean": "整理",
  "Index": "建立索引",
  "Chunk preview ({count})": "分块预览（{count}）",
  "Scanning...": "正在扫描...",
  "Scan unimported": "扫描未导入文档",
  "Import to knowledge base ({count})": "导入知识库（{count}）",
  "Deselect all": "取消全选",
  "Select all": "全选",
  "(untitled)": "（无标题）",
  "Not Indexed": "未建立索引",
  "Indexed": "已建立索引",
  "No documents yet": "还没有文档",
  "No indexed documents": "还没有已建立索引的文档",
  "Import a video to get started": "导入一个视频开始使用",
  "Index a document first": "请先为文档建立索引",
  "Delete document": "删除文档",
  "Delete {fileName} from the knowledge base? Indexed chunks will be removed. The source file is kept unless you choose to delete it below.": "要从知识库中删除 {fileName} 吗？已索引的分块将被移除。除非在下方选择同时删除，否则源文件会保留。",
  "Also delete the source file": "同时删除源文件",
  "Sign in required": "需要登录",
  "Login expired": "登录已过期",
  "Subtitles temporarily unavailable": "字幕暂时不可用",
  "Couldn't fetch subtitles": "无法获取字幕",
  "No Chinese subtitles": "没有中文字幕",
  "No subtitles available": "没有可用字幕",
  "Sign in is required to fetch subtitles for this video.": "需要登录后才能获取此视频的字幕。",
  "Your login session has expired. Sign in again to fetch subtitles.": "登录状态已过期，请重新登录后获取字幕。",
  "Subtitles are temporarily unavailable. Please try again.": "字幕暂时不可用，请重试。",
  "We couldn't fetch subtitles due to an upstream error.": "由于上游服务出错，无法获取字幕。",
  "This video has official subtitles, but none are in Chinese.": "此视频有官方字幕，但没有中文字幕。",
  "No CC subtitles are available for this video.": "此视频没有可用的 CC 字幕。",
  "Subtitle options": "字幕选项",
  "Available: {languages}.": "可用语言：{languages}。",
  "Video: {title}": "视频：{title}",
  "Use official subtitles": "使用官方字幕",
  "Go to Login": "前往登录",
  "Retry": "重试",
  "Use ASR transcription": "使用 ASR 转录",
  "Memento Guide": "Memento 使用指南",
  "From a video to an evidence-based answer": "从一段视频，到有依据的回答",
  "Complete the required configuration, then follow the guide to process videos, build the index, and start asking questions.": "完成必要配置后，按照指南处理视频、建立索引并开始提问。",
  "Start with configuration": "从配置开始",
  "Getting started": "快速开始",
  "Instructions": "使用说明",
  "Configure · Login · Add · Process · Index · Ask": "配置 · 登录 · 添加 · 处理 · 索引 · 提问",
  "Configure models": "配置模型",
  "Configure and enable Chat and Embedding in Settings. Chat is used to clean, summarize, and answer questions, while Embedding is used to build the index and retrieve content.": "在设置中配置并启用 Chat 和 Embedding。Chat 用于整理、总结和回答问题，Embedding 用于建立索引和检索内容。",
  "Configure ASR as needed: it is required for Douyin, and only needed for bilibili or YouTube when suitable subtitles are unavailable.": "按需配置 ASR：抖音必须使用；哔哩哔哩或 YouTube 仅在没有合适字幕时需要。",
  "Open Settings": "打开设置",
  "Prepare platform logins": "准备平台登录",
  "Before using bilibili subtitles, sign in to bilibili from Login. Signing in to Douyin can improve access reliability, while YouTube does not require a login.": "使用哔哩哔哩字幕前，请先在登录页登录哔哩哔哩。登录抖音可提高访问稳定性，YouTube 无需登录。",
  "QR code login is only available in the Memento desktop app.": "二维码登录仅在 Memento 桌面应用中可用。",
  "Open Login": "打开登录页",
  "Add a video": "添加视频",
  "Paste a video URL on Home and click Add video. After it is added, click Process on its video card to start extracting content.": "在首页粘贴视频链接并点击“添加视频”。添加后，在视频卡片上点击“处理”开始提取内容。",
  "Supports full bilibili BV video pages, full Douyin video links, and public YouTube single-video watch, youtu.be, or Shorts links.": "支持完整的哔哩哔哩 BV 视频页、完整抖音视频链接，以及公开的 YouTube 单视频、youtu.be 或 Shorts 链接。",
  "Go to Home": "前往首页",
  "Process subtitles or audio": "处理字幕或音频",
  "bilibili and YouTube prioritize existing subtitles. If suitable subtitles are unavailable, use other-language official subtitles or ASR transcription when prompted. Douyin uses ASR directly.": "哔哩哔哩和 YouTube 会优先使用现有字幕。没有合适字幕时，可按提示使用其他语言的官方字幕或 ASR 转录；抖音直接使用 ASR。",
  "If bilibili says you are not signed in or your login has expired, sign in from Login, then return and click Process again.": "如果哔哩哔哩提示未登录或登录已过期，请在登录页完成登录，然后返回并再次点击“处理”。",
  "Check platform login": "检查平台登录",
  "Organize and build the index": "整理并建立索引",
  "After processing succeeds, the document appears under Not Indexed in the Knowledge Base. We recommend clicking Clean, which cleans the transcript, generates a summary, and builds the index automatically.": "处理成功后，文档会出现在知识库的“未建立索引”中。建议点击“整理”，系统会整理转录文本、生成摘要并自动建立索引。",
  "If you only want to quickly search the original transcript, click Index directly. Chat can retrieve a document's content after it moves to Indexed.": "如果只想快速搜索原始转录文本，可直接点击“建立索引”。文档进入“已建立索引”后，Chat 即可检索其内容。",
  "Open Knowledge Base": "打开知识库",
  "Start asking questions": "开始提问",
  "Go to Chat and ask about details, opinions, or timestamps in a video. You can also ask Memento to summarize a video or find which videos discuss a topic.": "前往 Chat，询问视频中的细节、观点或时间点。也可以让 Memento 总结视频，或查找讨论某个主题的视频。",
  "Documents processed with Clean include summaries, making them better for summarization and topic exploration. Source links in answers can open the corresponding video in the desktop app.": "经过“整理”的文档包含摘要，更适合总结和主题探索。回答中的来源链接可在桌面应用中打开对应视频。",
  "Start chatting": "开始对话",
  "Troubleshooting": "问题排查",
  "Where are you stuck?": "遇到了什么问题？",
  "A video cannot be processed": "视频无法处理",
  "For bilibili, first check the login status in Login. For Douyin or videos that need transcription, check ASR in Settings. After fixing the issue, return to Home and click Process again.": "哔哩哔哩视频请先检查登录页中的登录状态；抖音或需要转录的视频请检查设置中的 ASR。解决问题后返回首页，再次点击“处理”。",
  "A document cannot move to Indexed": "文档无法进入已建立索引状态",
  "When using Clean, check Chat and Embedding. When using Index, check Embedding. After fixing the configuration, return to the Knowledge Base and click Clean or Index again.": "使用“整理”时请检查 Chat 和 Embedding；使用“建立索引”时请检查 Embedding。修复配置后返回知识库，再次点击相应操作。",
  "Chat cannot find video content": "Chat 找不到视频内容",
  "Make sure the document is under Indexed in the Knowledge Base. For a summary or overview of a video, prefer a document that has been processed with Clean.": "请确认文档位于知识库的“已建立索引”中。如需视频摘要或概览，优先使用经过“整理”的文档。",
  "Which service endpoints are supported?": "支持哪些服务端点？",
  "For Endpoint, enter the base URL of an OpenAI-compatible API, usually ending in /v1. Chat uses /chat/completions, Embedding uses /embeddings, the ASR transcriptions protocol uses /audio/transcriptions, and the chat_audio protocol uses /chat/completions with audio input support. Get Model List uses /models. Memento appends the request path automatically, so do not include it in Endpoint.": "Endpoint 请填写兼容 OpenAI API 的基础地址，通常以 /v1 结尾。Chat 使用 /chat/completions，Embedding 使用 /embeddings，ASR 的 transcriptions 协议使用 /audio/transcriptions，chat_audio 协议使用支持音频输入的 /chat/completions。“获取模型列表”使用 /models。Memento 会自动追加请求路径，请勿在 Endpoint 中重复填写。",
  "How do I use the built-in local ASR?": "怎样使用内置本地 ASR？",
  "In Settings → ASR, click Deploy. After installation, use http://localhost:8001/v1 for Endpoint, select transcriptions for Protocol, enter the installed model ID for Model, then Save or Activate the current preset. The local service starts automatically on the first transcription.": "在设置 → ASR 中点击“部署”。安装完成后，将 Endpoint 设为 http://localhost:8001/v1，Protocol 选择 transcriptions，在 Model 中填写已安装的模型 ID，然后保存或启用当前预设。本地服务会在首次转录时自动启动。",
  "How do I use an external ASR service?": "怎样使用外部 ASR 服务？",
  "First start an accessible LAN or cloud ASR service, then enter its base URL, API Key (if needed), and Model ID in the ASR preset. Select transcriptions if the service provides /audio/transcriptions, or chat_audio if it provides /chat/completions with audio input support. The service is ready after you Save or Activate the preset, and you must keep the external service running.": "先启动可访问的局域网或云端 ASR 服务，然后在 ASR 预设中填写其基础地址、API Key（如需要）和模型 ID。服务提供 /audio/transcriptions 时选择 transcriptions；提供支持音频输入的 /chat/completions 时选择 chat_audio。保存或启用预设后即可使用，并需保持外部服务运行。",
};

function interpolate(text: string, values?: Record<string, string | number>) {
  if (!values) return text;
  return text.replace(/\{(\w+)\}/g, (match, key: string) =>
    values[key] === undefined ? match : String(values[key]),
  );
}

interface LanguageContextValue {
  language: Language;
  setLanguage: (language: Language) => void;
  t: (source: string, values?: Record<string, string | number>) => string;
}

const LanguageContext = createContext<LanguageContextValue>({
  language: "en",
  setLanguage: () => {},
  t: (source, values) => interpolate(source, values),
});

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<Language>("en");

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    const detected: Language = navigator.language.toLowerCase().startsWith("zh")
      ? "zh-CN"
      : "en";
    const initial = stored === "en" || stored === "zh-CN" ? stored : detected;
    // Persisted UI preference; read after mount to avoid SSR hydration mismatch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLanguageState(initial);
  }, []);

  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  const value = useMemo<LanguageContextValue>(() => ({
    language,
    setLanguage(next) {
      localStorage.setItem(STORAGE_KEY, next);
      setLanguageState(next);
    },
    t(source, values) {
      const text = language === "zh-CN" ? (zhCN[source] ?? source) : source;
      return interpolate(text, values);
    },
  }), [language]);

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  return useContext(LanguageContext);
}
