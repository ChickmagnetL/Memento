import Link from "next/link";
import {
  ArrowRight,
  Captions,
  CircleHelp,
  Database,
  Link2,
  LogIn,
  MessageSquare,
  Settings2,
  Sparkles,
} from "lucide-react";

const STEPS = [
  {
    number: "01",
    icon: Settings2,
    title: "配置模型",
    description:
      "在 Settings 配置并启用 Chat 与 Embedding。Chat 用于清洗、摘要和回答，Embedding 用于建立索引和检索。",
    note: "ASR 按需配置：处理抖音时必需；bilibili 或 YouTube 没有合适字幕时才需要。",
    action: "打开 Settings",
    href: "/settings",
  },
  {
    number: "02",
    icon: LogIn,
    title: "按平台准备登录",
    description:
      "使用 bilibili 字幕前，请在 Login 完成 bilibili 登录。抖音登录可提高访问成功率，YouTube 无需登录。",
    note: "平台二维码登录只在 Memento 桌面应用中可用。",
    action: "打开 Login",
    href: "/login",
  },
  {
    number: "03",
    icon: Link2,
    title: "添加视频",
    description:
      "在 Home 粘贴视频链接并点击 Add video。添加完成后，在视频卡片上点击 Process 才会开始提取内容。",
    note: "支持 bilibili 完整 BV 视频页、抖音完整视频链接，以及公开的 YouTube 单视频 watch、youtu.be 或 Shorts 链接。",
    action: "前往 Home",
    href: "/",
  },
  {
    number: "04",
    icon: Captions,
    title: "处理字幕或音频",
    description:
      "bilibili 和 YouTube 会优先使用现有字幕；没有合适字幕时，可按提示使用其他语言的官方字幕或 ASR 转录。抖音会直接使用 ASR。",
    note: "如果 bilibili 提示未登录或登录过期，先前往 Login 完成登录，再回来重新点击 Process。",
    action: "检查平台登录",
    href: "/login",
  },
  {
    number: "05",
    icon: Database,
    title: "整理并建立索引",
    description:
      "处理成功后，文档会出现在 Knowledge Base 的 Not Indexed。推荐点击 Clean，系统会清洗转写、生成摘要并自动建立索引。",
    note: "如果只想快速检索原始转写，可以直接点击 Index。文档进入 Indexed 后，Chat 才能检索其中的内容。",
    action: "打开 Knowledge Base",
    href: "/knowledge",
  },
  {
    number: "06",
    icon: MessageSquare,
    title: "开始提问",
    description:
      "进入 Chat，直接询问视频中的细节、观点或时间点，也可以让 Memento 总结视频或查找哪些视频讨论过某个主题。",
    note: "经过 Clean 的文档包含摘要，更适合总结和主题探索；回答中的来源链接可在桌面端打开对应视频。",
    action: "开始对话",
    href: "/chat",
  },
];

const TROUBLESHOOTING = [
  {
    question: "视频无法处理",
    answer:
      "如果是 bilibili，先检查 Login 中的登录状态；如果是抖音或需要转录的视频，检查 Settings 中的 ASR。修复后回到 Home，再次点击 Process。",
  },
  {
    question: "文档无法进入 Indexed",
    answer:
      "使用 Clean 时检查 Chat 和 Embedding，使用 Index 时检查 Embedding。修复配置后，回到 Knowledge Base 重新点击 Clean 或 Index。",
  },
  {
    question: "Chat 找不到视频内容",
    answer:
      "确认目标文档已经位于 Knowledge Base 的 Indexed。需要总结或概览视频时，优先使用经过 Clean 的文档。",
  },
  {
    question: "支持哪些服务端点？",
    answer:
      "Endpoint 填 OpenAI-compatible API 的基地址，通常以 /v1 结尾。Chat 使用 /chat/completions，Embedding 使用 /embeddings；ASR 的 transcriptions 协议使用 /audio/transcriptions，chat_audio 协议使用支持音频输入的 /chat/completions。Get Model List 使用 /models。具体请求路径由 Memento 自动追加，不要填进 Endpoint。",
  },
  {
    question: "怎样使用内置本地 ASR？",
    answer:
      "在 Settings → ASR 点击 Deploy。安装完成后，Endpoint 使用 http://localhost:8001/v1，Protocol 选择 transcriptions，Model 填已安装模型的 ID，再 Save 或 Activate 当前预设。本地服务会在第一次转录时自动启动。",
  },
  {
    question: "怎样使用外部 ASR 服务？",
    answer:
      "先启动可访问的局域网或云端 ASR 服务，再在 ASR 预设中填写基地址、API Key（如需要）和 Model ID。服务提供 /audio/transcriptions 时选择 transcriptions；提供支持音频输入的 /chat/completions 时选择 chat_audio。Save 或 Activate 后即可使用，外部服务需要自行保持运行。",
  },
];

export default function HelpPage() {
  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-8 sm:px-8 lg:py-10">
      <section className="relative overflow-hidden rounded-2xl border border-border bg-card px-6 py-8 sm:px-10 sm:py-10">
        <div
          className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-primary/10 blur-3xl"
          aria-hidden="true"
        />
        <div className="relative max-w-3xl">
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <Sparkles className="h-3.5 w-3.5" />
            Memento 使用指南
          </div>
          <h1 className="max-w-2xl text-3xl font-semibold tracking-tight sm:text-4xl">
            从一段视频，到一次有依据的回答
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-muted-foreground sm:text-base">
            先完成必要配置，再按照说明处理视频、建立索引并开始提问。
          </p>
          <Link
            href="/settings"
            className="mt-7 inline-flex h-9 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
          >
            从配置开始
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>

      <section className="mt-10" aria-labelledby="workflow-title">
        <div className="mb-5 flex items-end justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-primary">
              Getting started
            </p>
            <h2 id="workflow-title" className="mt-1 text-xl font-semibold tracking-tight">
              使用说明
            </h2>
          </div>
          <p className="hidden text-sm text-muted-foreground sm:block">
            配置 · 登录 · 添加 · 处理 · 索引 · 提问
          </p>
        </div>

        <div className="grid gap-3 lg:grid-cols-2">
          {STEPS.map(({ number, icon: Icon, title, description, note, action, href }) => (
            <article key={number} className="group flex flex-col rounded-xl border border-border bg-card p-5 transition-colors hover:border-primary/40 sm:p-6">
              <div className="flex items-center justify-between">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Icon className="h-4.5 w-4.5" strokeWidth={1.8} />
                </div>
                <span className="font-mono text-xs text-muted-foreground">{number}</span>
              </div>
              <h3 className="mt-5 text-base font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
              <p className="mt-4 flex-1 border-t border-border pt-4 text-sm leading-6 text-muted-foreground">
                {note}
              </p>
              <Link href={href} className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-foreground transition-colors group-hover:text-primary">
                {action}
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </article>
          ))}
        </div>
      </section>

      <section className="mt-10 pb-4" aria-labelledby="troubleshooting-title">
        <div className="mb-5 flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted text-muted-foreground">
            <CircleHelp className="h-4.5 w-4.5" />
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
              Troubleshooting
            </p>
            <h2 id="troubleshooting-title" className="text-xl font-semibold tracking-tight">
              卡在哪一步？
            </h2>
          </div>
        </div>

        <div className="divide-y divide-border rounded-xl border border-border bg-card px-5">
          {TROUBLESHOOTING.map(({ question, answer }) => (
            <details key={question} className="group py-4 first:pt-5 last:pb-5">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-sm font-medium marker:content-none">
                {question}
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground transition-transform group-open:rotate-45">
                  +
                </span>
              </summary>
              <p className="max-w-3xl pt-3 pr-10 text-sm leading-6 text-muted-foreground">
                {answer}
              </p>
            </details>
          ))}
        </div>
      </section>
    </div>
  );
}
