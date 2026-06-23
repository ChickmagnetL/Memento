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
  const [preview, setPreview] = useState<{
    documentId: string;
    chunks: ChunkPreview[];
  } | null>(null);
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

  const rawDocs = documents.filter((doc) => doc.status === "raw");
  const indexedDocs = documents.filter((doc) => doc.status === "indexed");

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

  async function handleDelete(documentId: string, deleteSourceFile: boolean) {
    await withBusy(documentId, async () => {
      await deleteDocument(documentId, deleteSourceFile);
      setPreview((current) =>
        current?.documentId === documentId ? null : current
      );
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
    } catch {
      setError("Failed to scan unimported documents.");
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
    } catch {
      setError("Failed to import unimported documents.");
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-8 py-8">
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
            <Button
              variant="outline"
              size="sm"
              onClick={toggleSelectAll}
            >
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
                    {item.platform ?? "?"} · {item.file_path}
                  </p>
                </div>
              </li>
            ))}
          </ul>
      ) : null}

      {/* 未整理 section */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">未整理</h2>
        {rawDocs.length === 0 ? (
          <EmptyState icon={Database} title="还没有文档" description="导入视频后自动出现在这里" />
        ) : (
          rawDocs.map((doc) => (
            <div
              key={doc.id}
              className="flex flex-col gap-2 rounded-md border border-border p-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0">
                <p className="truncate font-mono text-sm">{doc.file_path}</p>
                <p className="text-xs text-muted-foreground">Not indexed</p>
              </div>
              <div className="flex shrink-0 gap-2">
                <Button variant="outline" size="sm" className="w-[100px]" disabled={busyId === doc.id} onClick={() => handlePreview(doc.id)}>
                  <Eye className="mr-1 h-4 w-4" /> 预览
                </Button>
                <Button variant="outline" size="sm" className="w-[110px]" disabled={busyId === doc.id} onClick={() => handleClean(doc.id)}>
                  <Sparkles className="mr-1 h-4 w-4" /> 清理并入库
                </Button>
                <Button size="sm" className="w-[100px]" disabled={busyId === doc.id} onClick={() => handleIndex(doc.id)}>
                  <Database className="mr-1 h-4 w-4" /> 直接入库
                </Button>
                <Button variant="outline" size="sm" className="w-[90px]" disabled={busyId === doc.id} onClick={() => { setDeleteSource(false); setDeleteTarget({ documentId: doc.id, fileName: doc.file_path }); }}>
                  <Trash2 className="mr-1 h-4 w-4" /> 删除
                </Button>
              </div>
            </div>
          ))
        )}
      </section>

      {/* 已索引 section */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">已索引</h2>
        {indexedDocs.length === 0 ? (
          <EmptyState icon={Database} title="还没有已索引的文档" description="先去整理吧" />
        ) : (
          indexedDocs.map((doc) => (
            <div
              key={doc.id}
              className="flex flex-col gap-2 rounded-md border border-border p-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0">
                <p className="truncate font-mono text-sm">{doc.file_path}</p>
                <p className="text-xs text-muted-foreground">
                  Indexed ({doc.chunk_count} chunks, {doc.indexed_at})
                </p>
              </div>
              <div className="flex shrink-0 gap-2">
                <Button variant="outline" size="sm" className="w-[100px]" disabled={busyId === doc.id} onClick={() => handlePreview(doc.id)}>
                  <Eye className="mr-1 h-4 w-4" /> 预览
                </Button>
                <Button size="sm" className="w-[100px]" disabled={busyId === doc.id} onClick={() => handleIndex(doc.id)}>
                  <Database className="mr-1 h-4 w-4" /> 重新索引
                </Button>
                <Button variant="outline" size="sm" className="w-[90px]" disabled={busyId === doc.id} onClick={() => { setDeleteSource(false); setDeleteTarget({ documentId: doc.id, fileName: doc.file_path }); }}>
                  <Trash2 className="mr-1 h-4 w-4" /> 删除
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
