"use client";

type Status = "thinking" | "tool_call" | "streaming";

interface StatusIndicatorProps {
  status: Status;
  tool?: string;
}

export function StatusIndicator({ status, tool }: StatusIndicatorProps) {
  // streaming: no indicator (the growing assistant bubble is the feedback).
  if (status === "streaming") return null;

  const label =
    status === "thinking"
      ? "Thinking…"
      : tool
        ? `Calling tool: ${tool}…`
        : "Calling tool…";

  return (
    <div className="mr-auto flex items-center gap-1.5 rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground">
      <span className="flex gap-0.5">
        <span className="h-1 w-1 animate-bounce rounded-full bg-current [animation-delay:-0.3s]" />
        <span className="h-1 w-1 animate-bounce rounded-full bg-current [animation-delay:-0.15s]" />
        <span className="h-1 w-1 animate-bounce rounded-full bg-current" />
      </span>
      {label}
    </div>
  );
}
