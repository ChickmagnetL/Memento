"use client";

import { Plus, Trash2 } from "lucide-react";

import { ChatSession } from "@/lib/api";
import { cn } from "@/lib/utils";

interface SessionListProps {
  sessions: ChatSession[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDeleteRequest: (session: ChatSession) => void;
}

export function SessionList({
  sessions,
  activeId,
  onSelect,
  onNew,
  onDeleteRequest,
}: SessionListProps) {
  return (
    <div className="flex h-full w-56 flex-col border-r border-border bg-[var(--color-bg-sidebar)]">
      <button
        onClick={onNew}
        className="m-2 flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-[var(--color-text)] transition-colors hover:bg-[var(--color-bg-hover)]"
      >
        <Plus className="h-4 w-4" />
        New Chat
      </button>
      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {sessions.map((session) => (
          <div
            key={session.id}
            className={cn(
              "group mb-0.5 flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
              session.id === activeId
                ? "bg-[var(--color-bg-hover)] text-[var(--color-text)]"
                : "text-[var(--color-text-muted)] hover:bg-[var(--color-bg-hover)] hover:text-[var(--color-text)]"
            )}
          >
            <button
              className="flex-1 truncate text-left"
              onClick={() => onSelect(session.id)}
              title={session.title}
            >
              {session.title}
            </button>
            <button
              className="opacity-0 transition-opacity group-hover:opacity-100"
              onClick={() => onDeleteRequest(session)}
              aria-label="Delete conversation"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
