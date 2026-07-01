"use client";

import { useState } from "react";
import { Database, Eye, FolderSearch, Sparkles, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { DeleteDocumentDialog } from "@/components/ui/delete-document-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorBanner } from "@/components/ui/error-banner";
import {
  cleanDocument,
  deleteDocument,
  importUnimportedDocuments,
  indexDocument,
  listDocuments,
  listUnimportedDocuments,
  previewChunks,
  type ChunkPreview,
  type DocumentRecord,
  type UnimportedDocument,
} from "@/lib/api";

interface DocumentManagerProps {
  initialDocuments: DocumentRecord[];
}

export function DocumentManager({ initialDocuments }: DocumentManagerProps) {
  const [documents, setDocuments] =
    useState<DocumentRecord[]>(initialDocuments);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [expandedPreviewId, setExpandedPreviewId] = useState<string | null>(null);
  const [previewChunksData, setPreviewChunksData] = useState<ChunkPreview[]>([]);
  const [deleteSource, setDeleteSource] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{
    documentId: string;
    fileName: string;
  } | null>(null);
  const [unimported, setUnimported] = useState<UnimportedDocument[]>([]);
  const [selectedUnimported, setSelectedUnimported] = useState<Set<string>>(
    new Set()
  );
  const [scanning, setScanning] = useState(false);
  const [activeTab, setActiveTab] = useState<"raw" | "indexed">("raw");

  const rawDocs = documents.filter((doc) => doc.status === "raw");
  const indexedDocs = documents.filter((doc) => doc.status === "indexed");
  const activeDocs = activeTab === "raw" ? rawDocs : indexedDocs;

  async function refresh() {
    setDocuments(await listDocuments());
  }

  async function withBusy(documentId: string, action: () => Promise<void>) {
    setError("");
    setBusyId(documentId);
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
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
    if (expandedPreviewId === documentId) {
      setExpandedPreviewId(null);
      setPreviewChunksData([]);
      return;
    }
    await withBusy(documentId, async () => {
      const chunks = await previewChunks(documentId);
      setExpandedPreviewId(documentId);
      setPreviewChunksData(chunks);
    });
  }

  async function handleDelete(documentId: string, deleteSourceFile: boolean) {
    await withBusy(documentId, async () => {
      await deleteDocument(documentId, deleteSourceFile);
      if (expandedPreviewId === documentId) {
        setExpandedPreviewId(null);
        setPreviewChunksData([]);
      }
      await refresh();
    });
    setDeleteTarget(null);
    setDeleteSource(false);
  }

  async function handleClean(documentId: string) {
    await withBusy(documentId, async () => {
      await cleanDocument(documentId);
      await refresh();
    });
  }

  async function handleScanUnimported() {
    setError("");
    setScanning(true);
    try {
      const items = await listUnimportedDocuments();
      setUnimported(items);
      setSelectedUnimported(new Set());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setScanning(false);
    }
  }

  function toggleUnimported(filePath: string) {
    setSelectedUnimported((current) => {
      const next = new Set(current);
      if (next.has(filePath)) {
        next.delete(filePath);
      } else {
        next.add(filePath);
      }
      return next;
    });
  }

  const allUnimportedSelected =
    unimported.length > 0 && selectedUnimported.size === unimported.length;

  function toggleSelectAll() {
    setSelectedUnimported((current) => {
      if (unimported.length > 0 && current.size === unimported.length) {
        return new Set();
      }
      return new Set(unimported.map((item) => item.file_path));
    });
  }

  async function handleImportUnimported() {
    setError("");
    const paths = Array.from(selectedUnimported);
    if (paths.length === 0) {
      return;
    }
    try {
      await importUnimportedDocuments(paths);
      setUnimported([]);
      setSelectedUnimported(new Set());
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    }
  }

  function renderDocCard(doc: DocumentRecord) {
    const isExpanded = expandedPreviewId === doc.id;
    const isRaw = doc.status === "raw";
    return (
      <div key={doc.id}>
        <div className="flex flex-col gap-3 rounded-md border border-border p-4">
          <div className="min-w-0">
            <p className="text-sm font-medium leading-snug">
              {doc.title ?? "Untitled"}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {doc.author && doc.author !== "Unknown"
                ? `${doc.author} · `
                : ""}
              {isRaw
                ? "Not indexed"
                : `Indexed (${doc.chunk_count} chunks, ${doc.indexed_at})`}
            </p>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={busyId === doc.id}
              onClick={() => handlePreview(doc.id)}
            >
              <Eye className="mr-1 h-4 w-4" /> Preview
            </Button>
            {isRaw ? (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={busyId === doc.id}
                  onClick={() => handleClean(doc.id)}
                >
                  <Sparkles className="mr-1 h-4 w-4" /> Clean
                </Button>
                <Button
                  size="sm"
                  disabled={busyId === doc.id}
                  onClick={() => handleIndex(doc.id)}
                >
                  <Database className="mr-1 h-4 w-4" /> Index
                </Button>
              </>
            ) : null}
            <Button
              variant="outline"
              size="sm"
              disabled={busyId === doc.id}
              onClick={() => {
                setDeleteSource(false);
                setDeleteTarget({
                  documentId: doc.id,
                  fileName: doc.file_path,
                });
              }}
            >
              <Trash2 className="mr-1 h-4 w-4" /> Delete
            </Button>
          </div>
        </div>
        {isExpanded && previewChunksData.length > 0 ? (
          <div className="mt-2 space-y-2 rounded-md border border-border bg-muted/30 p-3">
            <p className="text-xs font-semibold text-muted-foreground">
              Chunk preview ({previewChunksData.length})
            </p>
            {previewChunksData.map((chunk) => (
              <div
                key={chunk.chunk_index}
                className="rounded-md bg-muted p-2 text-sm"
              >
                <p className="mb-1 text-xs text-muted-foreground">
                  #{chunk.chunk_index} · {chunk.title_path}
                  {chunk.start_timestamp
                    ? ` · [${chunk.start_timestamp}]`
                    : ""}
                </p>
                <pre className="whitespace-pre-wrap font-sans">
                  {chunk.text}
                </pre>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-8 py-8">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-semibold">Knowledge Base</h1>
        <Button
          variant="outline"
          size="sm"
          disabled={scanning}
          onClick={handleScanUnimported}
        >
          <FolderSearch className="mr-1 h-4 w-4" />
          {scanning ? "Scanning..." : "Scan unimported"}
        </Button>
        {unimported.length > 0 ? (
          <>
            <Button
              size="sm"
              disabled={selectedUnimported.size === 0}
              onClick={handleImportUnimported}
            >
              Import to knowledge base ({selectedUnimported.size})
            </Button>
            <Button variant="outline" size="sm" onClick={toggleSelectAll}>
              {allUnimportedSelected ? "Deselect all" : "Select all"}
            </Button>
          </>
        ) : null}
      </header>

      {error ? <ErrorBanner message={error} /> : null}

      {unimported.length > 0 ? (
        <ul className="space-y-2">
          {unimported.map((item) => (
            <li
              key={item.file_path}
              className={`flex cursor-pointer items-center gap-2 rounded-md border p-3 text-sm transition-colors hover:bg-muted/50 ${
                selectedUnimported.has(item.file_path)
                  ? "border-primary bg-primary/10"
                  : "border-border"
              }`}
              onClick={() => toggleUnimported(item.file_path)}
            >
              <input
                type="checkbox"
                checked={selectedUnimported.has(item.file_path)}
                readOnly
              />
              <div className="min-w-0">
                <p className="truncate font-medium">
                  {item.title ?? "(untitled)"}
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  {[item.author, item.platform].filter(Boolean).join(" · ") || "?"} · {item.file_path}
                </p>
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="inline-flex rounded-lg bg-muted p-1">
        <button
          type="button"
          className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
            activeTab === "raw"
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
          onClick={() => setActiveTab("raw")}
        >
          Not Indexed
          {rawDocs.length > 0 ? (
            <span className="ml-1.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-muted-foreground/15 px-1.5 text-xs text-muted-foreground">
              {rawDocs.length}
            </span>
          ) : null}
        </button>
        <button
          type="button"
          className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
            activeTab === "indexed"
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
          onClick={() => setActiveTab("indexed")}
        >
          Indexed
          {indexedDocs.length > 0 ? (
            <span className="ml-1.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-muted-foreground/15 px-1.5 text-xs text-muted-foreground">
              {indexedDocs.length}
            </span>
          ) : null}
        </button>
      </div>

      <section className="space-y-2">
        {activeDocs.length === 0 ? (
          <EmptyState
            icon={Database}
            title={
              activeTab === "raw"
                ? "No documents yet"
                : "No indexed documents"
            }
            description={
              activeTab === "raw"
                ? "Import a video to get started"
                : "Index a document first"
            }
          />
        ) : (
          activeDocs.map((doc) => renderDocCard(doc))
        )}
      </section>

      {deleteTarget ? (
        <DeleteDocumentDialog
          fileName={deleteTarget.fileName}
          deleteSource={deleteSource}
          onDeleteSourceChange={setDeleteSource}
          onConfirm={() => handleDelete(deleteTarget.documentId, deleteSource)}
          onCancel={() => {
            setDeleteTarget(null);
            setDeleteSource(false);
          }}
        />
      ) : null}
    </div>
  );
}
