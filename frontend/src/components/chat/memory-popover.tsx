"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Brain, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorBanner } from "@/components/ui/error-banner";
import { deleteMemory, listMemories, type Memory } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

interface MemoryPopoverProps {
  refreshKey?: number;
}

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function MemoryPopover({ refreshKey }: MemoryPopoverProps) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [deletingIds, setDeletingIds] = useState<Set<string>>(() => new Set());
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const deletedIdsRef = useRef<Set<string>>(new Set());

  const closePopover = useCallback((restoreFocus = false) => {
    setOpen(false);

    if (restoreFocus) {
      window.setTimeout(() => triggerRef.current?.focus(), 0);
    }
  }, []);

  useEffect(() => {
    if (!open) return;

    function handlePointerDown(event: PointerEvent) {
      if (
        rootRef.current &&
        event.target instanceof Node &&
        !rootRef.current.contains(event.target)
      ) {
        closePopover();
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closePopover(true);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [closePopover, open]);

  useEffect(() => {
    if (!open) return;

    let cancelled = false;

    async function loadMemories() {
      setLoading(true);
      setError("");

      try {
        const nextMemories = await listMemories();

        if (!cancelled) {
          setMemories(
            nextMemories.filter((memory) => !deletedIdsRef.current.has(memory.id))
          );
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(getErrorMessage(loadError, t("Operation failed")));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadMemories();

    return () => {
      cancelled = true;
    };
  }, [open, refreshKey, t]);

  async function handleDelete(id: string) {
    setDeletingIds((current) => new Set(current).add(id));
    setError("");

    try {
      await deleteMemory(id);
      deletedIdsRef.current.add(id);
      setMemories((current) => current.filter((memory) => memory.id !== id));
    } catch (deleteError) {
      setError(getErrorMessage(deleteError, t("Operation failed")));
    } finally {
      setDeletingIds((current) => {
        const nextDeletingIds = new Set(current);
        nextDeletingIds.delete(id);
        return nextDeletingIds;
      });
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <Button
        ref={triggerRef}
        type="button"
        variant={open ? "secondary" : "ghost"}
        size="icon"
        className="text-[var(--color-text)]"
        onClick={() => setOpen((value) => !value)}
        aria-label={open ? t("Close memories") : t("Open memories")}
        aria-expanded={open}
        aria-haspopup="dialog"
        title={open ? t("Close memories") : t("Open memories")}
      >
        <Brain className="h-4 w-4" />
      </Button>

      {open ? (
        <div
          role="dialog"
          aria-label={t("Memories")}
          className="absolute right-0 top-11 z-30 w-[min(24rem,calc(100vw-var(--sidebar-width)-2rem))] max-w-sm rounded-md border border-border bg-background p-2 shadow-lg"
        >
          <div className="flex items-center gap-2 border-b border-border px-2 pb-2">
            <Brain className="h-4 w-4 text-[var(--color-text-muted)]" />
            <h2 className="text-sm font-semibold text-[var(--color-text)]">
              {t("Memories")}
            </h2>
          </div>

          {error ? (
            <div className="py-2">
              <ErrorBanner message={error} />
            </div>
          ) : null}

          <div
            className="max-h-[calc(100vh-6rem)] overflow-y-auto py-2"
            aria-live="polite"
          >
            {loading ? (
              <div className="px-3 py-6 text-center text-sm text-[var(--color-text-muted)]">
                {t("Loading memories...")}
              </div>
            ) : error && memories.length === 0 ? null : memories.length === 0 ? (
              <EmptyState
                icon={Brain}
                title={t("No memories yet")}
                description={t("Use /remember or let the agent propose memories.")}
                className="py-8"
              />
            ) : (
              memories.map((memory) => (
                <div
                  key={memory.id}
                  className="group mb-0.5 flex items-start gap-2 rounded-md px-2 py-2 text-sm text-[var(--color-text-muted)] hover:bg-[var(--color-bg-hover)] hover:text-[var(--color-text)]"
                >
                  <div className="min-w-0 flex-1 whitespace-pre-wrap break-words text-xs leading-relaxed">
                    {memory.content}
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 shrink-0 text-[var(--color-text-muted)] opacity-0 transition-colors hover:bg-background hover:text-destructive group-hover:opacity-100 focus:opacity-100"
                    onClick={() => handleDelete(memory.id)}
                    disabled={deletingIds.has(memory.id)}
                    aria-label={t("Delete memory")}
                    title={t("Delete memory")}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
