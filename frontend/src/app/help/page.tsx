"use client";

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
import { useLanguage } from "@/lib/i18n";

const STEPS = [
  {
    number: "01",
    icon: Settings2,
    title: "Configure models",
    description:
      "Configure and enable Chat and Embedding in Settings. Chat is used to clean, summarize, and answer questions, while Embedding is used to build the index and retrieve content.",
    note: "Configure ASR as needed: it is required for Douyin, and only needed for bilibili or YouTube when suitable subtitles are unavailable.",
    action: "Open Settings",
    href: "/settings",
  },
  {
    number: "02",
    icon: LogIn,
    title: "Prepare platform logins",
    description:
      "Before using bilibili subtitles, sign in to bilibili from Login. Signing in to Douyin can improve access reliability, while YouTube does not require a login.",
    note: "QR code login is only available in the Memento desktop app.",
    action: "Open Login",
    href: "/login",
  },
  {
    number: "03",
    icon: Link2,
    title: "Add a video",
    description:
      "Paste a video URL on Home and click Add video. After it is added, click Process on its video card to start extracting content.",
    note: "Supports full bilibili BV video pages, full Douyin video links, and public YouTube single-video watch, youtu.be, or Shorts links.",
    action: "Go to Home",
    href: "/",
  },
  {
    number: "04",
    icon: Captions,
    title: "Process subtitles or audio",
    description:
      "bilibili and YouTube prioritize existing subtitles. If suitable subtitles are unavailable, use other-language official subtitles or ASR transcription when prompted. Douyin uses ASR directly.",
    note: "If bilibili says you are not signed in or your login has expired, sign in from Login, then return and click Process again.",
    action: "Check platform login",
    href: "/login",
  },
  {
    number: "05",
    icon: Database,
    title: "Organize and build the index",
    description:
      "After processing succeeds, the document appears under Not Indexed in the Knowledge Base. We recommend clicking Clean, which cleans the transcript, generates a summary, and builds the index automatically.",
    note: "If you only want to quickly search the original transcript, click Index directly. Chat can retrieve a document's content after it moves to Indexed.",
    action: "Open Knowledge Base",
    href: "/knowledge",
  },
  {
    number: "06",
    icon: MessageSquare,
    title: "Start asking questions",
    description:
      "Go to Chat and ask about details, opinions, or timestamps in a video. You can also ask Memento to summarize a video or find which videos discuss a topic.",
    note: "Documents processed with Clean include summaries, making them better for summarization and topic exploration. Source links in answers can open the corresponding video in the desktop app.",
    action: "Start chatting",
    href: "/chat",
  },
];

const TROUBLESHOOTING = [
  {
    question: "A video cannot be processed",
    answer:
      "For bilibili, first check the login status in Login. For Douyin or videos that need transcription, check ASR in Settings. After fixing the issue, return to Home and click Process again.",
  },
  {
    question: "A document cannot move to Indexed",
    answer:
      "When using Clean, check Chat and Embedding. When using Index, check Embedding. After fixing the configuration, return to the Knowledge Base and click Clean or Index again.",
  },
  {
    question: "Chat cannot find video content",
    answer:
      "Make sure the document is under Indexed in the Knowledge Base. For a summary or overview of a video, prefer a document that has been processed with Clean.",
  },
  {
    question: "Which service endpoints are supported?",
    answer:
      "For Endpoint, enter the base URL of an OpenAI-compatible API, usually ending in /v1. Chat uses /chat/completions, Embedding uses /embeddings, the ASR transcriptions protocol uses /audio/transcriptions, and the chat_audio protocol uses /chat/completions with audio input support. Get Model List uses /models. Memento appends the request path automatically, so do not include it in Endpoint.",
  },
  {
    question: "How do I use the built-in local ASR?",
    answer:
      "In Settings → ASR, click Deploy. After installation, use http://localhost:8001/v1 for Endpoint, select transcriptions for Protocol, enter the installed model ID for Model, then Save or Activate the current preset. The local service starts automatically on the first transcription.",
  },
  {
    question: "How do I use an external ASR service?",
    answer:
      "First start an accessible LAN or cloud ASR service, then enter its base URL, API Key (if needed), and Model ID in the ASR preset. Select transcriptions if the service provides /audio/transcriptions, or chat_audio if it provides /chat/completions with audio input support. The service is ready after you Save or Activate the preset, and you must keep the external service running.",
  },
];

export default function HelpPage() {
  const { t } = useLanguage();

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
            {t("Memento Guide")}
          </div>
          <h1 className="max-w-2xl text-3xl font-semibold tracking-tight sm:text-4xl">
            {t("From a video to an evidence-based answer")}
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-muted-foreground sm:text-base">
            {t("Complete the required configuration, then follow the guide to process videos, build the index, and start asking questions.")}
          </p>
          <Link
            href="/settings"
            className="mt-7 inline-flex h-9 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
          >
            {t("Start with configuration")}
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>

      <section className="mt-10" aria-labelledby="workflow-title">
        <div className="mb-5 flex items-end justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-primary">
              {t("Getting started")}
            </p>
            <h2 id="workflow-title" className="mt-1 text-xl font-semibold tracking-tight">
              {t("Instructions")}
            </h2>
          </div>
          <p className="hidden text-sm text-muted-foreground sm:block">
            {t("Configure · Login · Add · Process · Index · Ask")}
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
              <h3 className="mt-5 text-base font-semibold">{t(title)}</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{t(description)}</p>
              <p className="mt-4 flex-1 border-t border-border pt-4 text-sm leading-6 text-muted-foreground">
                {t(note)}
              </p>
              <Link href={href} className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-foreground transition-colors group-hover:text-primary">
                {t(action)}
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
              {t("Troubleshooting")}
            </p>
            <h2 id="troubleshooting-title" className="text-xl font-semibold tracking-tight">
              {t("Where are you stuck?")}
            </h2>
          </div>
        </div>

        <div className="divide-y divide-border rounded-xl border border-border bg-card px-5">
          {TROUBLESHOOTING.map(({ question, answer }) => (
            <details key={question} className="group py-4 first:pt-5 last:pb-5">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-sm font-medium marker:content-none">
                {t(question)}
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground transition-transform group-open:rotate-45">
                  +
                </span>
              </summary>
              <p className="max-w-3xl pt-3 pr-10 text-sm leading-6 text-muted-foreground">
                {t(answer)}
              </p>
            </details>
          ))}
        </div>
      </section>
    </div>
  );
}
