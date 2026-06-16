"use client";

import ReactMarkdown from "react-markdown";

const GUIDE = `下面是一次完整的使用流程，从提交视频到提问对话。

## 使用说明

1. **提交视频** — 在 Video Intake 粘贴 B 站或抖音视频链接，点击 *Add video*。
2. **处理视频** — 在视频列表中点击 *Process*，提取字幕或通过 ASR 转录音频。
3. **入库索引** — 进入 Knowledge Base，选中生成的文档点击 *Index*，向量化后即可被检索。
4. **提问对话** — 进入 Chat，针对已入库的视频内容提问，进行问答。

## 常见问题

**支持哪些平台？**
B 站与抖音。B 站优先使用软字幕；若没有字幕，则回退到 ASR 转录。

**为什么处理失败？**
常见原因：字幕抓取失败、ASR 服务未启动、或网络异常。可查看后端日志定位。

**模型没有配置怎么办？**
进入 Settings 配置 chat 与 embedding 模型，或使用 Ollama 本地模型。两者均为必需。

**处理要多久？**
取决于视频时长以及是否已有现成字幕。已有软字幕时几乎即时，ASR 转录则按音频时长线性增长。
`;

const components = {
  h1: ({ ...props }) => (
    <h1 className="text-xl font-semibold tracking-tight" {...props} />
  ),
  h2: ({ ...props }) => (
    <h2 className="text-lg font-semibold pt-2" {...props} />
  ),
  p: ({ ...props }) => (
    <p className="text-sm text-[var(--color-text-muted)] leading-relaxed" {...props} />
  ),
  ol: ({ ...props }) => (
    <ol className="list-decimal space-y-2 pl-5 text-sm" {...props} />
  ),
  ul: ({ ...props }) => (
    <ul className="list-disc space-y-2 pl-5 text-sm" {...props} />
  ),
  li: ({ ...props }) => <li className="leading-relaxed" {...props} />,
  strong: ({ ...props }) => (
    <strong className="font-semibold text-[var(--color-text)]" {...props} />
  ),
};

export default function HelpPage() {
  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-8 py-8">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold">Help</h1>
        <p className="text-sm text-[var(--color-text-muted)]">
          快速上手 Memento 的视频知识库流程。
        </p>
      </header>
      <article className="space-y-2">
        <ReactMarkdown components={components}>{GUIDE}</ReactMarkdown>
      </article>
    </div>
  );
}
