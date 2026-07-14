"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { MessageSquare, Plus, SendHorizontal } from "lucide-react";
import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorBanner } from "@/components/ui/error-banner";
import { VideoTimestampLink } from "@/components/VideoTimestampLink";
import { ChatSessionDropdown } from "@/components/chat/chat-session-dropdown";
import { DeleteSessionDialog } from "@/components/chat/delete-session-dialog";
import { MemoryPopover } from "@/components/chat/memory-popover";
import { MemoryProposalBubble } from "@/components/chat/memory-proposal-bubble";
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
  const [deletingSession, setDeletingSession] = useState(false);
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

  async function handleSelectSession(id: string) {
    if (state.pendingProposal) {
      rejectProposal();
    }
    await selectSession(id);
  }

  function handleNewChat() {
    if (state.pendingProposal) {
      rejectProposal();
    }
    handleNew();
  }

  const isStreaming = state.generating !== null;

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      <header className="grid h-14 shrink-0 grid-cols-[1fr_minmax(0,auto)_1fr] items-center border-b border-border px-6">
        <div />
        <div className="flex min-w-0 items-center justify-center gap-1">
          <ChatSessionDropdown
            sessions={state.sessions}
            activeId={state.activeId}
            onSelect={handleSelectSession}
            onNew={handleNewChat}
            onDeleteRequest={(session) => setPendingDelete(session)}
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={handleNewChat}
            aria-label="New Chat"
            title="New Chat"
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        <div className="desktop-window-controls-safe flex justify-end">
          <MemoryPopover refreshKey={state.memoryRefreshKey} />
        </div>
      </header>

      <section className="min-h-0 flex-1 overflow-y-auto px-4 py-6">
        <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col gap-4">
          {activeMessages.length === 0 && !state.generating ? (
            <EmptyState
              icon={MessageSquare}
              title="The important thing is not to stop questioning."
              description="Albert Einstein"
              className="flex-1"
            />
          ) : (
            activeMessages.map((message, index) => (
              <div
                key={index}
                className={
                  message.role === "user"
                    ? "ml-auto max-w-[85%] break-words rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground [overflow-wrap:anywhere]"
                    : "mr-auto max-w-full overflow-hidden rounded-md bg-muted px-3 py-2 text-sm"
                }
              >
                {message.role === "assistant" ? (
                  <div className="prose prose-sm max-w-none break-words dark:prose-invert prose-pre:overflow-x-auto prose-pre:whitespace-pre-wrap prose-code:break-words prose-table:block prose-table:overflow-x-auto [overflow-wrap:anywhere]">
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
                          return <a className="break-words" href={href}>{children}</a>;
                        },
                      }}
                    >
                      {message.content}
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
        </div>
      </section>

      <div className="shrink-0 px-4 pb-6">
        <div className="mx-auto w-full max-w-3xl space-y-3">
          {state.error ? <ErrorBanner message={state.error} /> : null}

          <form className="flex gap-3" onSubmit={handleSubmit}>
            <input
              className="h-10 min-w-0 flex-1 rounded-md border border-input bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground"
              aria-label="Message"
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
      </div>

      <DeleteSessionDialog
        open={pendingDelete !== null}
        sessionTitle={pendingDelete?.title ?? ""}
        deleting={deletingSession}
        onCancel={() => {
          if (!deletingSession) {
            setPendingDelete(null);
          }
        }}
        onConfirm={async () => {
          if (!pendingDelete || deletingSession) return;

          setDeletingSession(true);
          try {
            if (pendingDelete.id === state.activeId && state.pendingProposal) {
              rejectProposal();
            }
            await requestDelete(pendingDelete);
            setPendingDelete(null);
          } finally {
            setDeletingSession(false);
          }
        }}
      />
    </div>
  );
}
