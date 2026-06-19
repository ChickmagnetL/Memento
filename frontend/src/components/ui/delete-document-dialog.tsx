"use client";

import { Button } from "@/components/ui/button";

interface DeleteDocumentDialogProps {
  fileName: string;
  deleteSource: boolean;
  onDeleteSourceChange: (value: boolean) => void;
  onConfirm: () => void;
  onCancel: () => void;
}

export function DeleteDocumentDialog({
  fileName,
  deleteSource,
  onDeleteSourceChange,
  onConfirm,
  onCancel,
}: DeleteDocumentDialogProps) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Delete document"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="w-full max-w-md space-y-4 rounded-md border border-input bg-background p-6 shadow-lg">
        <div className="space-y-1">
          <h2 className="text-base font-semibold">Delete document</h2>
          <p className="break-all text-sm text-muted-foreground">
            Delete <span className="font-medium text-foreground">{fileName}</span> from the knowledge base?
            Indexed chunks will be removed. The source file is kept unless you choose to delete it below.
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={deleteSource}
            onChange={(e) => onDeleteSourceChange(e.target.checked)}
          />
          Also delete the source file
        </label>
        <div className="flex justify-end gap-2">
          <Button onClick={onCancel} type="button" variant="ghost">
            Cancel
          </Button>
          <Button onClick={onConfirm} type="button">
            Delete
          </Button>
        </div>
      </div>
    </div>
  );
}
