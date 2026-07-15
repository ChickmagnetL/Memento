"use client";

import { Button } from "@/components/ui/button";
import { useLanguage } from "@/lib/i18n";

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

function languageLabel(lan: string, locale: string): string {
  const languageCode = lan.startsWith("ai-") ? lan.slice(3) : lan;
  try {
    return new Intl.DisplayNames([locale], { type: "language" }).of(languageCode) ?? lan;
  } catch {
    return lan;
  }
}

function dialogTitleKey(reason: string): string {
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

function defaultMessageKey(reason: string): string {
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
  const { language, t } = useLanguage();
  const isNonChinese = reason === "non_chinese_subtitles";
  const needsLogin =
    (reason === "not_logged_in" || reason === "auth_expired") && !!onGoToLogin;
  const needsRetry =
    (reason === "subtitle_unstable" || reason === "upstream_error") &&
    !!onRetry;
  const bodyMessage = message?.trim() || t(defaultMessageKey(reason));
  const languageNames =
    availableLanguages?.length
      ? availableLanguages.map((lan) => languageLabel(lan, language)).join(", ")
      : "";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t("Subtitle options")}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="w-full max-w-md space-y-4 rounded-md border border-input bg-background p-6 shadow-lg">
        <div className="space-y-1">
          <h2 className="text-base font-semibold">{t(dialogTitleKey(reason))}</h2>
          <p className="break-all text-sm text-muted-foreground">
            {bodyMessage}{" "}
            {languageNames
              ? t("Available: {languages}.", { languages: languageNames })
              : ""}{" "}
            {t("Video: {title}", { title: videoTitle })}
          </p>
        </div>
        <div className="flex flex-col gap-2">
          {isNonChinese && onUseOfficial ? (
            <Button onClick={onUseOfficial} type="button">
              {t("Use official subtitles")}
            </Button>
          ) : null}
          {needsLogin ? (
            <Button onClick={onGoToLogin} type="button">
              {t("Go to Login")}
            </Button>
          ) : null}
          {needsRetry ? (
            <Button onClick={onRetry} type="button">
              {t("Retry")}
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
            {t("Use ASR transcription")}
          </Button>
          <Button onClick={onCancel} type="button" variant="ghost">
            {t("Cancel")}
          </Button>
        </div>
      </div>
    </div>
  );
}
