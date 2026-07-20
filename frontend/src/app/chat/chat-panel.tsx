"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { Check, CircleStop, MessageSquare, Pencil, Plus, SendHorizontal, Trash2, X } from "lucide-react";
import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorBanner } from "@/components/ui/error-banner";
import { VideoTimestampLink } from "@/components/VideoTimestampLink";
import { ChatSessionDropdown } from "@/components/chat/chat-session-dropdown";
import { DeleteMessageDialog } from "@/components/chat/delete-message-dialog";
import { DeleteSessionDialog } from "@/components/chat/delete-session-dialog";
import { MemoryPopover } from "@/components/chat/memory-popover";
import { MemoryProposalBubble } from "@/components/chat/memory-proposal-bubble";
import { StatusIndicator } from "@/components/chat/status-indicator";
import { useChatStore } from "@/lib/chat-store";
import { useLanguage } from "@/lib/i18n";

export function ChatPanel() {
  const { t } = useLanguage();
  const {
    state,
    activeMessages,
    selectSession,
    handleNew,
    sendMessage,
    editMessage,
    deleteMessage,
    retractLast,
    setComposerInput,
    rememberCommand,
    acceptProposal,
    rejectProposal,
    requestDelete,
  } = useChatStore();
  const [input, setInput] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState("");
  const [pendingDeleteMessageId, setPendingDeleteMessageId] = useState<string | null>(null);
  const [deletingMessage, setDeletingMessage] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<typeof state.sessions[number] | null>(null);
  const [deletingSession, setDeletingSession] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeMessages, state.generating]);

  // When RETRACT_LAST sets composerInput, reflect it in the local input box once.
  useEffect(() => {
    if (state.composerInput) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- sync store composerInput into local input once
      setInput(state.composerInput);
      setComposerInput("");
    }
  }, [state.composerInput, setComposerInput]);

  // ESC stops + retracts the in-flight turn (only while generating).
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      if (!state.generating) return;
      event.preventDefault();
      retractLast();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [state.generating, retractLast]);

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
      <header className="desktop-titlebar grid h-14 shrink-0 grid-cols-[1fr_minmax(0,auto)_1fr] items-center border-b border-border px-6">
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
            aria-label={t("New Chat")}
            title={t("New Chat")}
          >
            <Plus className="h-4 w-4" />
          </Button>
          <MemoryPopover refreshKey={state.memoryRefreshKey} />
        </div>
        <div />
      </header>

      <section className="min-h-0 flex-1 overflow-y-auto px-4 py-6">
        <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col gap-4">
          {activeMessages.length === 0 && !state.generating ? (
            <EmptyState
              icon={MessageSquare}
              title={t("The important thing is not to stop questioning.")}
              description={t("Albert Einstein")}
              className="flex-1"
            />
          ) : (
            activeMessages.map((message) => {
              const isUser = message.role === "user";
              const isEditing = editingId === message.id;

              if (isUser) {
                return (
                  <div key={message.id} className="group ml-auto flex max-w-[85%] items-end gap-1">
                    {!isEditing ? (
                      <div className="flex shrink-0 gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6"
                          disabled={isStreaming}
                          aria-label={t("Edit")}
                          title={t("Edit")}
                          onClick={() => {
                            setEditingId(message.id);
                            setEditDraft(message.content);
                          }}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6"
                          disabled={isStreaming}
                          aria-label={t("Delete")}
                          title={t("Delete")}
                          onClick={() => setPendingDeleteMessageId(message.id)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    ) : null}
                    <div className="min-w-0 break-words rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground [overflow-wrap:anywhere]">
                      {isEditing ? (
                        <div className="flex flex-col gap-2">
                          <textarea
                            className="min-h-[60px] w-full resize-y rounded-md border border-input bg-background px-2 py-1 text-sm text-foreground"
                            value={editDraft}
                            onChange={(e) => setEditDraft(e.target.value)}
                            aria-label={t("Edit message")}
                          />
                          <div className="flex justify-end gap-2">
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              aria-label={t("Cancel")}
                              onClick={() => {
                                setEditingId(null);
                                setEditDraft("");
                              }}
                            >
                              <X className="h-4 w-4" />
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              aria-label={t("Confirm")}
                              disabled={!editDraft.trim() || isStreaming}
                              onClick={() => {
                                const trimmed = editDraft.trim();
                                if (!trimmed) return;
                                setEditingId(null);
                                setEditDraft("");
                                void editMessage(message.id, trimmed);
                              }}
                            >
                              <Check className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <div className="whitespace-pre-wrap break-words">{message.content}</div>
                      )}
                    </div>
                  </div>
                );
              }

              return (
                <div
                  key={message.id}
                  className="group mr-auto max-w-full overflow-hidden rounded-md bg-muted px-3 py-2 text-sm"
                >
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
                </div>
              );
            })
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
              aria-label={t("Message")}
              placeholder={t("Ask your knowledge base...")}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              disabled={isStreaming}
            />
            {isStreaming ? (
              <Button
                type="button"
                onClick={retractLast}
                aria-label={t("Stop")}
                title={t("Stop")}
              >
                <CircleStop className="mr-1 h-4 w-4" />
                {t("Stop")}
              </Button>
            ) : (
              <Button type="submit" disabled={!input.trim()}>
                <SendHorizontal className="mr-1 h-4 w-4" />
                {t("Send")}
              </Button>
            )}
          </form>
        </div>
      </div>

      <DeleteMessageDialog
        open={pendingDeleteMessageId !== null}
        deleting={deletingMessage}
        onCancel={() => {
          if (!deletingMessage) {
            setPendingDeleteMessageId(null);
          }
        }}
        onConfirm={async () => {
          if (!pendingDeleteMessageId || deletingMessage) return;
          setDeletingMessage(true);
          try {
            await deleteMessage(pendingDeleteMessageId);
            setPendingDeleteMessageId(null);
          } finally {
            setDeletingMessage(false);
          }
        }}
      />

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
