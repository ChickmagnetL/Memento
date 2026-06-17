"use client";

import { Button } from "@/components/ui/button";

interface SubtitleDecisionDialogProps {
  videoTitle: string;
  onCancel: () => void;
  onUseAsr: () => void;
  onConfigureCookie: () => void;
}

export function SubtitleDecisionDialog({
  videoTitle,
  onCancel,
  onUseAsr,
  onConfigureCookie,
}: SubtitleDecisionDialogProps) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Subtitle options"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="w-full max-w-md space-y-4 rounded-md border border-input bg-background p-6 shadow-lg">
        <div className="space-y-1">
          <h2 className="text-base font-semibold">No subtitles available</h2>
          <p className="break-all text-sm text-muted-foreground">
            We couldn&apos;t fetch subtitles for{" "}
            <span className="font-medium text-foreground">{videoTitle}</span>.
            This usually means the Bilibili video has no CC subtitles, or no
            login cookie is configured.
          </p>
        </div>
        <div className="flex flex-col gap-2">
          <Button
            onClick={onConfigureCookie}
            type="button"
            variant="outline"
          >
            Configure Cookie in Settings
          </Button>
          <Button onClick={onUseAsr} type="button">
            Use ASR transcription
          </Button>
          <Button onClick={onCancel} type="button" variant="ghost">
            Cancel
          </Button>
        </div>
      </div>
    </div>
  );
}
