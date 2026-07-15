"use client";

import { Button } from "@/components/ui/button";
import { useLanguage } from "@/lib/i18n";

interface DeleteSessionDialogProps {
  open: boolean;
  sessionTitle: string;
  deleting?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export function DeleteSessionDialog({
  open,
  sessionTitle,
  deleting = false,
  onCancel,
  onConfirm,
}: DeleteSessionDialogProps) {
  const { t } = useLanguage();

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t("Delete conversation")}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="w-full max-w-md space-y-4 rounded-md border border-input bg-background p-6 shadow-lg">
        <div className="space-y-1">
          <h2 className="text-base font-semibold">{t("Delete conversation?")}</h2>
          <p className="break-all text-sm text-muted-foreground">
            {t("This conversation and all its messages will be permanently deleted.")}
          </p>
          <p className="break-all text-sm text-muted-foreground">
            <span className="font-medium text-foreground">{sessionTitle}</span>
          </p>
        </div>
        <div className="flex justify-end gap-2">
          <Button onClick={onCancel} type="button" variant="ghost" disabled={deleting}>
            {t("Cancel")}
          </Button>
          <Button onClick={onConfirm} type="button" disabled={deleting}>
            {deleting ? t("Deleting...") : t("Delete")}
          </Button>
        </div>
      </div>
    </div>
  );
}
