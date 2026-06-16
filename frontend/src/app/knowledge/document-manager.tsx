"use client";

import { useState } from "react";
import { Database, Eye, Sparkles, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorBanner } from "@/components/ui/error-banner";
import {
  cleanDocument,
  deleteDocument,
  indexDocument,
  listDocuments,
  previewChunks,
  type ChunkPreview,
  type DocumentRecord,
} from "@/lib/api";

interface DocumentManagerProps {
  initialDocuments: DocumentRecord[];
}

export function DocumentManager({ initialDocuments }: DocumentManagerProps) {
  const [documents, setDocuments] =
    useState<DocumentRecord[]>(initialDocuments);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [preview, setPreview] = useState<{
    documentId: string;
    chunks: ChunkPreview[];
  } | null>(null);

  async function refresh() {
    setDocuments(await listDocuments());
  }

  async function withBusy(documentId: string, action: () => Promise<void>) {
    setError("");
    setBusyId(documentId);
    try {
      await action();
    } catch {
      setError("Operation failed. Check backend logs.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleIndex(documentId: string) {
    await withBusy(documentId, async () => {
      await indexDocument(documentId);
      await refresh();
    });
  }

  async function handlePreview(documentId: string) {
    await withBusy(documentId, async () => {
      const chunks = await previewChunks(documentId);
      setPreview({ documentId, chunks });
    });
  }

  async function handleDelete(documentId: string) {
    await withBusy(documentId, async () => {
      await deleteDocument(documentId);
      setPreview((current) =>
        current?.documentId === documentId ? null : current
      );
      await refresh();
    });
  }

  async function handleClean(documentId: string) {
    await withBusy(documentId, async () => {
      await cleanDocument(documentId);
      await refresh();
    });
  }

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-8 py-8">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold">Knowledge Base</h1>
      </header>

      {error ? <ErrorBanner message={error} /> : null}

      <section className="space-y-3">
        {documents.length === 0 ? (
          <EmptyState icon={Database} title="No documents yet" description="Process a video first." />
        ) : (
          documents.map((doc) => (
            <div
              key={doc.id}
              className="flex flex-col gap-2 rounded-md border border-border p-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0">
                <p className="truncate font-mono text-sm">{doc.file_path}</p>
                <p className="text-xs text-muted-foreground">
                  {doc.is_indexed
                    ? `Indexed (${doc.chunk_count} chunks, ${doc.indexed_at})`
                    : "Not indexed"}
                </p>
              </div>
              <div className="flex shrink-0 gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="w-[100px]"
                  disabled={busyId === doc.id}
                  onClick={() => handlePreview(doc.id)}
                >
                  <Eye className="mr-1 h-4 w-4" /> Preview
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-[100px]"
                  disabled={busyId === doc.id}
                  onClick={() => handleClean(doc.id)}
                >
                  <Sparkles className="mr-1 h-4 w-4" /> Clean
                </Button>
                <Button
                  size="sm"
                  className="w-[100px]"
                  disabled={busyId === doc.id}
                  onClick={() => handleIndex(doc.id)}
                >
                  <Database className="mr-1 h-4 w-4" />
                  {doc.is_indexed ? "Re-index" : "Index"}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-[100px]"
                  disabled={busyId === doc.id}
                  onClick={() => handleDelete(doc.id)}
                >
                  <Trash2 className="mr-1 h-4 w-4" /> Delete
                </Button>
              </div>
            </div>
          ))
        )}
      </section>

      {preview ? (
        <section className="space-y-3 rounded-md border border-border p-4">
          <h2 className="text-lg font-semibold">
            Chunk preview ({preview.chunks.length})
          </h2>
          {preview.chunks.map((chunk) => (
            <div
              key={chunk.chunk_index}
              className="rounded-md bg-muted p-3 text-sm"
            >
              <p className="mb-1 text-xs text-muted-foreground">
                #{chunk.chunk_index} · {chunk.title_path}
                {chunk.start_timestamp ? ` · [${chunk.start_timestamp}]` : ""}
              </p>
              <pre className="whitespace-pre-wrap font-sans">{chunk.text}</pre>
            </div>
          ))}
        </section>
      ) : null}
    </div>
  );
}
