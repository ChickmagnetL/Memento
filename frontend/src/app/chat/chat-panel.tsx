"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { SendHorizontal, MessageSquare } from "lucide-react";
import ReactMarkdown, { defaultUrlTransform } from "react-markdown";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorBanner } from "@/components/ui/error-banner";
import { VideoTimestampLink } from "@/components/VideoTimestampLink";
import { SessionList } from "@/components/chat/session-list";
import { DeleteSessionDialog } from "@/components/chat/delete-session-dialog";
import {
  ChatSession,
  listSessions,
  getSessionMessages,
  deleteSession,
  sendChatMessage,
} from "@/lib/api";

const LAST_SESSION_KEY = "memento-last-chat-session";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export function ChatPanel() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<ChatSession | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // On mount: load sessions + restore last active.
  useEffect(() => {
    (async () => {
      try {
        const list = await listSessions();
        setSessions(list);
        const last = localStorage.getItem(LAST_SESSION_KEY);
        const restoreId =
          last && list.some((s) => s.id === last) ? last : null;
        if (restoreId) {
          await selectSession(restoreId);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Operation failed");
      }
    })();
    // Mount-only: load sessions + restore last active.
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function selectSession(id: string) {
    try {
      const msgs = await getSessionMessages(id);
      setMessages(msgs.map((m) => ({ role: m.role, content: m.content })));
      setActiveId(id);
      localStorage.setItem(LAST_SESSION_KEY, id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    }
  }

  function handleNew() {
    // Don't create on backend yet — first message triggers creation.
    setMessages([]);
    setActiveId(null);
    localStorage.removeItem(LAST_SESSION_KEY);
  }

  function handleDelete(session: ChatSession) {
    setPendingDelete(session);
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    const target = pendingDelete;
    try {
      await deleteSession(target.id);
      const list = await listSessions();
      setSessions(list);
      if (activeId === target.id) {
        handleNew();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setPendingDelete(null);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = input.trim();
    if (!message || isStreaming) {
      return;
    }

    setError("");
    setInput("");
    setIsStreaming(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: message },
      { role: "assistant", content: "" },
    ]);

    const appendDelta = (delta: string) => {
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        next[next.length - 1] = {
          ...last,
          content: last.content + delta,
        };
        return next;
      });
    };

    try {
      await sendChatMessage(message, activeId, {
        onDelta: appendDelta,
        onDone: async (sessionId) => {
          setActiveId(sessionId);
          localStorage.setItem(LAST_SESSION_KEY, sessionId);
          try {
            setSessions(await listSessions());
          } catch {
            /* non-fatal: title backfill may lag */
          }
        },
        onError: (msg) => setError(msg),
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setIsStreaming(false);
    }
  }

  return (
    <div className="flex h-full w-full">
      <SessionList
        sessions={sessions}
        activeId={activeId}
        onSelect={(id) => selectSession(id)}
        onNew={handleNew}
        onDeleteRequest={handleDelete}
      />
      <div className="mx-auto flex h-full w-full max-w-4xl flex-col px-8 py-8">
        <header className="space-y-1 pb-6">
          <h1 className="text-xl font-semibold">Chat</h1>
        </header>

        <section className="flex flex-1 flex-col gap-4 overflow-y-auto pb-6">
          {messages.length === 0 ? (
            <EmptyState
              icon={MessageSquare}
              title="Ask about your indexed videos"
              description="Answers cite timestamps like [02:35]."
            />
          ) : (
            messages.map((message, index) => (
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
                      {message.content || (isStreaming ? "…" : "")}
                    </ReactMarkdown>
                  </div>
                ) : (
                  message.content
                )}
              </div>
            ))
          )}
          <div ref={scrollRef} />
        </section>

        {error ? <ErrorBanner message={error} /> : null}

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

      <DeleteSessionDialog
        open={pendingDelete !== null}
        sessionTitle={pendingDelete?.title ?? ""}
        onCancel={() => setPendingDelete(null)}
        onConfirm={confirmDelete}
      />
    </div>
  );
}
