"use client";

import { Button } from "@/components/ui/button";

interface SubtitleDecisionDialogProps {
  videoTitle: string;
  reason: string;
  message?: string;
  availableLanguages?: string[];
  onCancel: () => void;
  onUseAsr: () => void;
  onUseOfficial?: () => void;
  onRetry?: () => void;
  onGoToLogin?: () => void;
}

function languageLabel(lan: string): string {
  switch (lan) {
    case "ai-en":
      return "English";
    case "ai-ja":
      return "Japanese";
    case "ai-zh":
      return "Chinese";
    default:
      return lan;
  }
}

function dialogTitle(reason: string): string {
  switch (reason) {
    case "not_logged_in":
      return "Sign in required";
    case "auth_expired":
      return "Login expired";
    case "subtitle_unstable":
      return "Subtitles temporarily unavailable";
    case "upstream_error":
      return "Couldn't fetch subtitles";
    case "non_chinese_subtitles":
      return "No Chinese subtitles";
    default:
      return "No subtitles available";
  }
}

function defaultMessage(reason: string): string {
  switch (reason) {
    case "not_logged_in":
      return "Sign in is required to fetch subtitles for this video.";
    case "auth_expired":
      return "Your login session has expired. Sign in again to fetch subtitles.";
    case "subtitle_unstable":
      return "Subtitles are temporarily unavailable. Please try again.";
    case "upstream_error":
      return "We couldn't fetch subtitles due to an upstream error.";
    case "non_chinese_subtitles":
      return "This video has official subtitles, but none are in Chinese.";
    default:
      return "No CC subtitles are available for this video.";
  }
}

export function SubtitleDecisionDialog({
  videoTitle,
  reason,
  message,
  availableLanguages,
  onCancel,
  onUseAsr,
  onUseOfficial,
  onRetry,
  onGoToLogin,
}: SubtitleDecisionDialogProps) {
  const isNonChinese = reason === "non_chinese_subtitles";
  const needsLogin =
    (reason === "not_logged_in" || reason === "auth_expired") && !!onGoToLogin;
  const needsRetry =
    (reason === "subtitle_unstable" || reason === "upstream_error") &&
    !!onRetry;
  const bodyMessage = message?.trim() || defaultMessage(reason);
  const languageNames =
    availableLanguages?.length
      ? availableLanguages.map(languageLabel).join(", ")
      : "";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Subtitle options"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="w-full max-w-md space-y-4 rounded-md border border-input bg-background p-6 shadow-lg">
        <div className="space-y-1">
          <h2 className="text-base font-semibold">{dialogTitle(reason)}</h2>
          <p className="break-all text-sm text-muted-foreground">
            {bodyMessage}
            {languageNames ? ` Available: ${languageNames}.` : ""} Video:{" "}
            <span className="font-medium text-foreground">{videoTitle}</span>
          </p>
        </div>
        <div className="flex flex-col gap-2">
          {isNonChinese && onUseOfficial ? (
            <Button onClick={onUseOfficial} type="button">
              Use official subtitles
            </Button>
          ) : null}
          {needsLogin ? (
            <Button onClick={onGoToLogin} type="button">
              Go to Login
            </Button>
          ) : null}
          {needsRetry ? (
            <Button onClick={onRetry} type="button">
              Retry
            </Button>
          ) : null}
          <Button
            onClick={onUseAsr}
            type="button"
            variant={
              needsLogin || needsRetry || (isNonChinese && !!onUseOfficial)
                ? "outline"
                : "default"
            }
          >
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
