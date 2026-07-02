"use client";

import { useEffect, useState } from "react";
import { Trash2, Brain } from "lucide-react";

import { Memory, listMemories, deleteMemory } from "@/lib/api";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorBanner } from "@/components/ui/error-banner";

interface MemoryPanelProps {
  refreshKey?: number;
}

export function MemoryPanel({ refreshKey }: MemoryPanelProps) {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        setMemories(await listMemories());
        setError("");
      } catch (e) {
        setError(e instanceof Error ? e.message : "Operation failed");
      }
    })();
  }, [refreshKey]);

  async function handleDelete(id: string) {
    try {
      await deleteMemory(id);
      setMemories((prev) => prev.filter((m) => m.id !== id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    }
  }

  return (
    <div className="flex h-full flex-col border-l border-border bg-[var(--color-bg-sidebar)]">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Brain className="h-4 w-4" />
        <h2 className="text-sm font-semibold">Memories</h2>
      </div>

      {error ? (
        <div className="px-3 py-2">
          <ErrorBanner message={error} />
        </div>
      ) : null}

      <div className="flex-1 overflow-y-auto px-2 py-2">
        {memories.length === 0 ? (
          <EmptyState
            icon={Brain}
            title="No memories yet"
            description="Use /remember or let the agent propose memories."
          />
        ) : (
          memories.map((memory) => (
            <div
              key={memory.id}
              className="group mb-0.5 flex items-start gap-2 rounded-md px-3 py-2 text-sm text-[var(--color-text-muted)] hover:bg-[var(--color-bg-hover)] hover:text-[var(--color-text)]"
            >
              <div className="flex-1 whitespace-pre-wrap break-words text-xs leading-relaxed">
                {memory.content}
              </div>
              <button
                className="mt-0.5 shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
                onClick={() => handleDelete(memory.id)}
                aria-label="Delete memory"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}