"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, Plus, Search, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { ChatSession } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ChatSessionDropdownProps {
  sessions: ChatSession[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDeleteRequest: (session: ChatSession) => void;
}

function getSessionTitle(session?: ChatSession | null) {
  return session?.title?.trim() || "New Chat";
}

export function ChatSessionDropdown({
  sessions,
  activeId,
  onSelect,
  onNew,
  onDeleteRequest,
}: ChatSessionDropdownProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === activeId) ?? null,
    [activeId, sessions]
  );
  const currentTitle = getSessionTitle(activeSession);

  const filteredSessions = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return sessions;

    return sessions.filter((session) =>
      getSessionTitle(session).toLowerCase().includes(normalizedQuery)
    );
  }, [query, sessions]);

  const closeDropdown = useCallback((restoreFocus = false) => {
    setOpen(false);
    setQuery("");

    if (restoreFocus) {
      window.setTimeout(() => triggerRef.current?.focus(), 0);
    }
  }, []);

  function handleSelect(id: string) {
    closeDropdown();
    onSelect(id);
  }

  function handleNew() {
    closeDropdown();
    onNew();
  }

  function handleDelete(session: ChatSession) {
    closeDropdown();
    onDeleteRequest(session);
  }

  useEffect(() => {
    if (!open) return;

    function handlePointerDown(event: PointerEvent) {
      if (
        rootRef.current &&
        event.target instanceof Node &&
        !rootRef.current.contains(event.target)
      ) {
        closeDropdown();
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closeDropdown(true);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [closeDropdown, open]);

  useEffect(() => {
    if (open) {
      inputRef.current?.focus();
    }
  }, [open]);

  return (
    <div ref={rootRef} className="relative flex justify-center">
      <Button
        ref={triggerRef}
        type="button"
        variant="ghost"
        className="max-w-[min(calc(100vw-2rem),22rem)] px-3 text-[var(--color-text)]"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="dialog"
        title={currentTitle}
      >
        <span className="min-w-0 truncate">{currentTitle}</span>
        <ChevronDown
          className={cn("h-4 w-4 transition-transform", open && "rotate-180")}
        />
      </Button>

      {open && (
        <div
          role="dialog"
          aria-label="Select conversation"
          className="absolute left-1/2 top-full z-50 mt-2 w-[min(24rem,calc(100vw-var(--sidebar-width)-2rem))] max-w-sm -translate-x-1/2 rounded-md border border-border bg-background p-2 shadow-lg"
        >
          <div className="relative mb-2">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-muted)]" />
            <input
              ref={inputRef}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              aria-label="Search conversations"
              placeholder="Search conversations"
              className="h-9 w-full rounded-md border border-input bg-background py-2 pl-9 pr-3 text-sm text-[var(--color-text)] outline-none transition-colors placeholder:text-[var(--color-text-muted)] focus:border-ring focus:ring-1 focus:ring-ring"
            />
          </div>

          <Button
            type="button"
            variant="ghost"
            className="mb-2 w-full justify-start px-3 text-[var(--color-text)]"
            onClick={handleNew}
          >
            <Plus className="h-4 w-4" />
            New Chat
          </Button>

          <div className="max-h-72 overflow-y-auto">
            {filteredSessions.length === 0 ? (
              <div className="px-3 py-6 text-center text-sm text-[var(--color-text-muted)]">
                No conversations found
              </div>
            ) : (
              filteredSessions.map((session) => {
                const displayTitle = getSessionTitle(session);

                return (
                  <div
                    key={session.id}
                    className={cn(
                      "group mb-0.5 flex items-center gap-2 rounded-md px-2 py-1 text-sm transition-colors",
                      session.id === activeId
                        ? "bg-[var(--color-bg-hover)] text-[var(--color-text)]"
                        : "text-[var(--color-text-muted)] hover:bg-[var(--color-bg-hover)] hover:text-[var(--color-text)]"
                    )}
                  >
                    <button
                      type="button"
                      className="min-w-0 flex-1 truncate px-1 py-1.5 text-left"
                      onClick={() => handleSelect(session.id)}
                      aria-current={
                        session.id === activeId ? "true" : undefined
                      }
                      title={displayTitle}
                    >
                      {displayTitle}
                    </button>
                    <button
                      type="button"
                      className="rounded-md p-1 text-[var(--color-text-muted)] opacity-0 transition-colors hover:bg-background hover:text-destructive group-hover:opacity-100 focus:opacity-100"
                      onClick={() => handleDelete(session)}
                      aria-label={`Delete ${displayTitle}`}
                      title={`Delete ${displayTitle}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
