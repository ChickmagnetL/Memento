"use client";

import { Button } from "@/components/ui/button";
import { useLanguage } from "@/lib/i18n";

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
  const { t } = useLanguage();

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t("Delete document")}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="w-full max-w-md space-y-4 rounded-md border border-input bg-background p-6 shadow-lg">
        <div className="space-y-1">
          <h2 className="text-base font-semibold">{t("Delete document")}</h2>
          <p className="break-all text-sm text-muted-foreground">
            {t("Delete {fileName} from the knowledge base? Indexed chunks will be removed. The source file is kept unless you choose to delete it below.", {
              fileName,
            })}
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={deleteSource}
            onChange={(e) => onDeleteSourceChange(e.target.checked)}
          />
          {t("Also delete the source file")}
        </label>
        <div className="flex justify-end gap-2">
          <Button onClick={onCancel} type="button" variant="ghost">
            {t("Cancel")}
          </Button>
          <Button onClick={onConfirm} type="button">
            {t("Delete")}
          </Button>
        </div>
      </div>
    </div>
  );
}
