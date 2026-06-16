"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { SendHorizontal, MessageSquare } from "lucide-react";
import ReactMarkdown from "react-markdown";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorBanner } from "@/components/ui/error-banner";
import { sendChatMessage } from "@/lib/api";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const sessionIdRef = useRef<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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
      await sendChatMessage(message, sessionIdRef.current, {
        onDelta: appendDelta,
        onDone: (sessionId) => {
          sessionIdRef.current = sessionId;
        },
        onError: (message) => setError(message),
      });
    } catch {
      setError("Chat failed. Is the backend running?");
    } finally {
      setIsStreaming(false);
    }
  }

  return (
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
                  <ReactMarkdown>
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
  );
}
