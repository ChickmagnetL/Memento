"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { SendHorizontal, MessageSquare } from "lucide-react";
import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorBanner } from "@/components/ui/error-banner";
import { VideoTimestampLink } from "@/components/VideoTimestampLink";
import { SessionList } from "@/components/chat/session-list";
import { DeleteSessionDialog } from "@/components/chat/delete-session-dialog";
import { MemoryProposalBubble } from "@/components/chat/memory-proposal-bubble";
import { MemoryPanel } from "@/components/chat/memory-panel";
import { StatusIndicator } from "@/components/chat/status-indicator";
import { useChatStore } from "@/lib/chat-store";

export function ChatPanel() {
  const {
    state,
    activeMessages,
    selectSession,
    handleNew,
    sendMessage,
    rememberCommand,
    acceptProposal,
    rejectProposal,
    requestDelete,
  } = useChatStore();
  const [input, setInput] = useState("");
  const [pendingDelete, setPendingDelete] = useState<typeof state.sessions[number] | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeMessages, state.generating]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = input.trim();
    if (!message || state.generating) return;

    if (message.startsWith("/remember ")) {
      const content = message.slice("/remember ".length).trim();
      if (content) {
        await rememberCommand(content, message);
      }
      setInput("");
      return;
    }

    setInput("");
    await sendMessage(message);
  }

  const isStreaming = state.generating !== null;

  return (
    <div className="flex h-full w-full">
      <SessionList
        sessions={state.sessions}
        activeId={state.activeId}
        onSelect={(id) => selectSession(id)}
        onNew={handleNew}
        onDeleteRequest={(session) => setPendingDelete(session)}
      />
      <div className="mx-auto flex h-full w-full max-w-4xl flex-col px-8 py-8">
        <header className="space-y-1 pb-6">
          <h1 className="text-xl font-semibold">Chat</h1>
        </header>

        <section className="flex flex-1 flex-col gap-4 overflow-y-auto pb-6">
          {activeMessages.length === 0 && !state.generating ? (
            <EmptyState
              icon={MessageSquare}
              title="Ask about your indexed videos"
              description="Answers cite timestamps like [02:35]."
            />
          ) : (
            activeMessages.map((message, index) => (
              <div
                key={index}
                className={
                  message.role === "user"
                    ? "ml-auto max-w-[85%] rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground"
                    : "mr-auto max-w-[85%] rounded-md bg-muted px-3 py-2 text-sm"
                }
              >
                {message.role === "assistant" ? (
                  <div className="prose prose-sm max-w-none dark:prose-invert">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      urlTransform={(value) =>
                        value.startsWith("memento://") ? value : defaultUrlTransform(value)
                      }
                      components={{
                        a: ({ href, children }) => {
                          if (href?.startsWith("memento://")) {
                            return <VideoTimestampLink href={href}>{children}</VideoTimestampLink>;
                          }
                          return <a href={href}>{children}</a>;
                        },
                      }}
                    >
                      {message.content || (isStreaming && index === activeMessages.length - 1 ? "" : "")}
                    </ReactMarkdown>
                  </div>
                ) : (
                  message.content
                )}
              </div>
            ))
          )}
          {state.generating ? (
            <StatusIndicator status={state.generating.status} tool={state.generating.tool} />
          ) : null}
          {state.pendingProposal ? (
            <MemoryProposalBubble
              key={state.pendingProposal.content}
              content={state.pendingProposal.content}
              onAccept={acceptProposal}
              onReject={rejectProposal}
            />
          ) : null}
          <div ref={scrollRef} />
        </section>

        {state.error ? <ErrorBanner message={state.error} /> : null}

        <form className="flex gap-3" onSubmit={handleSubmit}>
          <input
            className="h-10 flex-1 rounded-md border border-input bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground"
            placeholder="Ask your knowledge base..."
            value={input}
            onChange={(event) => setInput(event.target.value)}
            disabled={isStreaming}
          />
          <Button type="submit" disabled={isStreaming || !input.trim()}>
            <SendHorizontal className="mr-1 h-4 w-4" />
            Send
          </Button>
        </form>
      </div>

      <div className="w-56">
        <MemoryPanel refreshKey={state.memoryRefreshKey} />
      </div>

      <DeleteSessionDialog
        open={pendingDelete !== null}
        sessionTitle={pendingDelete?.title ?? ""}
        onCancel={() => setPendingDelete(null)}
        onConfirm={async () => {
          if (pendingDelete) {
            await requestDelete(pendingDelete);
            setPendingDelete(null);
          }
        }}
      />
    </div>
  );
}
