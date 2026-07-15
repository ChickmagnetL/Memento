"use client";

import { useCallback, useEffect, useState } from "react";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  getLocalAsrStatus,
  installLocalAsrModel,
  selectLocalAsrModel,
  uninstallAllLocalAsr,
  uninstallLocalAsrModel,
  type AsrManagerStatus,
} from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

function formatBytes(value: number) {
  if (value === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(value) / Math.log(1024)));
  return `${(value / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

// Parse a registry size string like "0.9GB" / "71MB" into bytes.
function parseSize(size: string): number {
  const match = size.match(/([\d.]+)\s*(GB|MB|KB)/i);
  if (!match) return 0;
  const value = parseFloat(match[1]);
  const unit = match[2].toUpperCase();
  if (unit === "GB") return value * 1024 ** 3;
  if (unit === "MB") return value * 1024 ** 2;
  return value * 1024;
}

// Derive unique families in stable order from the model registry status.
const FAMILY_LABELS: Record<string, string> = {
  sensevoice: "SenseVoice (Chinese)",
  moonshine: "Moonshine Voice (English)",
};

export interface LocalAsrModalProps {
  open: boolean;
  onClose: () => void;
  onDeploy: () => void;
  isDeploying: boolean;
}

export function LocalAsrModal({
  open,
  onClose,
  onDeploy,
  isDeploying,
}: LocalAsrModalProps) {
  const { t } = useLanguage();
  const [localAsrStatus, setLocalAsrStatus] =
    useState<AsrManagerStatus | null>(null);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [pollIntervalId, setPollIntervalId] = useState<number | null>(null);

  const stopModalPolling = useCallback(() => {
    setPollIntervalId((prev) => {
      if (prev !== null) {
        window.clearInterval(prev);
      }
      return null;
    });
  }, []);

  const startModalPolling = useCallback(() => {
    stopModalPolling();
    const id = window.setInterval(async () => {
      try {
        const status = await getLocalAsrStatus();
        setLocalAsrStatus(status);
        if (status.progress.done) {
          stopModalPolling();
        }
      } catch {
        stopModalPolling();
      }
    }, 1500);
    setPollIntervalId(id);
  }, [stopModalPolling]);

  const handleInstallModel = useCallback(
    async (slug: string) => {
      try {
        await installLocalAsrModel(slug);
        startModalPolling();
      } catch {
        // error will show in next poll
      }
    },
    [startModalPolling],
  );

  const handleUninstallModel = useCallback(
    async (slug: string) => {
      try {
        await uninstallLocalAsrModel(slug);
        startModalPolling();
      } catch {
        // error will show in next poll
      }
    },
    [startModalPolling],
  );

  // Selecting a Size variant makes it the active local model when installed.
  const handleSizeChange = useCallback(
    async (slug: string) => {
      setSelectedSlug(slug);
      const model = localAsrStatus?.models[slug];
      if (model?.installed) {
        try {
          await selectLocalAsrModel(slug);
          const status = await getLocalAsrStatus();
          setLocalAsrStatus(status);
        } catch {
          // error will show in next poll
        }
      }
    },
    [localAsrStatus],
  );

  const handleUninstallAll = useCallback(async () => {
    try {
      await uninstallAllLocalAsr();
      startModalPolling();
    } catch {
      // error will show in next poll
    }
  }, [startModalPolling]);

  const handleClose = useCallback(() => {
    stopModalPolling();
    setLocalAsrStatus(null);
    setSelectedSlug(null);
    onClose();
  }, [onClose, stopModalPolling]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalId !== null) {
        window.clearInterval(pollIntervalId);
      }
    };
  }, [pollIntervalId]);

  // Load status + start polling when opened; stop polling on close/unmount.
  // State reset on close lives in handleClose (event handler), not here,
  // to avoid synchronous setState within the effect body.
  useEffect(() => {
    if (!open) {
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const status = await getLocalAsrStatus();
        if (cancelled) return;
        setLocalAsrStatus(status);
        setSelectedSlug(status.current ?? Object.keys(status.models)[0] ?? null);
        if (!status.progress.done) {
          startModalPolling();
        }
      } catch {
        if (cancelled) return;
        setLocalAsrStatus(null);
      }
    })();
    return () => {
      cancelled = true;
      stopModalPolling();
    };
  }, [open, startModalPolling, stopModalPolling]);

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg max-h-[80vh] overflow-y-auto rounded-lg border bg-background p-5 shadow-lg space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">{t("Local ASR Model Settings")}</h2>
          <button
            type="button"
            onClick={handleClose}
            className="text-muted-foreground hover:text-foreground"
            aria-label={t("Close")}
          >
            <X size={18} />
          </button>
        </div>

        {localAsrStatus ? (() => {
          const models = Object.values(localAsrStatus.models);
          const families = Array.from(
            new Set(models.map((m) => m.family)),
          );
          const currentModel = selectedSlug
            ? localAsrStatus.models[selectedSlug]
            : undefined;
          const currentFamily = currentModel?.family ?? families[0];
          const familyModels = models.filter(
            (m) => m.family === currentFamily,
          );
          const envReady = localAsrStatus.environment.venv_exists;
          const installedSize = models
            .filter((m) => m.installed)
            .reduce((sum, m) => sum + parseSize(m.size), 0);

          return (
            <>
              {/* Section 1: ASR Environment */}
              <section className="space-y-2">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {t("ASR Environment")}
                </h3>
                <div className="flex items-center justify-between gap-3 rounded-md border border-input bg-muted/30 p-3">
                  <div className="text-sm">
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-block h-2 w-2 rounded-full ${envReady ? "bg-green-500" : "bg-red-500"}`}
                      />
                      <span>
                        {envReady
                          ? t("Environment ready")
                          : t("Environment not installed")}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {envReady
                        ? t("Environment size: ~{size}", { size: formatBytes(installedSize) })
                        : t("Environment size: —")}
                    </p>
                  </div>
                  {envReady ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="destructive"
                      onClick={handleUninstallAll}
                    >
                      {t("Uninstall Environment")}
                    </Button>
                  ) : (
                    <Button
                      type="button"
                      size="sm"
                      onClick={onDeploy}
                      disabled={isDeploying}
                    >
                      {t("Install Environment")}
                    </Button>
                  )}
                </div>
              </section>

              {/* Section 2 & 3: Model family + size */}
              <section className="space-y-2">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {t("Model")}
                </h3>
                <div className="flex gap-3">
                  <label className="block flex-1 text-sm">
                    <span className="mb-1 block text-muted-foreground">
                      {t("Family")}
                    </span>
                    <select
                      className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                      value={currentFamily}
                      onChange={(event) => {
                        const next = models.find(
                          (m) => m.family === event.target.value,
                        );
                        if (next) {
                          handleSizeChange(next.slug);
                        }
                      }}
                    >
                      {families.map((family) => (
                        <option key={family} value={family}>
                          {t(FAMILY_LABELS[family] ?? family)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block flex-1 text-sm">
                    <span className="mb-1 block text-muted-foreground">
                      {t("Size")}
                    </span>
                    <select
                      className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                      value={selectedSlug ?? ""}
                      onChange={(event) =>
                        handleSizeChange(event.target.value)
                      }
                    >
                      {familyModels.map((m) => (
                        <option key={m.slug} value={m.slug}>
                          {m.label.replace(/^(SenseVoice|Moonshine Voice)\s*/, "")} — {m.size}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                {currentModel ? (
                  <div className="flex items-center justify-between rounded-md border border-input bg-muted/30 p-3">
                    <div className="flex items-center gap-2 text-sm">
                      <span
                        className={`inline-block h-2 w-2 rounded-full ${currentModel.installed ? "bg-green-500" : "bg-red-500"}`}
                      />
                      <span className="font-medium">{currentModel.label}</span>
                      <span className="text-xs text-muted-foreground">
                        {currentModel.size}
                      </span>
                    </div>
                    {currentModel.installed ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="destructive"
                        onClick={() =>
                          handleUninstallModel(currentModel.slug)
                        }
                      >
                        {t("Uninstall")}
                      </Button>
                    ) : (
                      <Button
                        type="button"
                        size="sm"
                        onClick={() =>
                          handleInstallModel(currentModel.slug)
                        }
                      >
                        {t("Install")}
                      </Button>
                    )}
                  </div>
                ) : null}
              </section>

              {/* Progress / error — only when a task is running */}
              {localAsrStatus.progress &&
              localAsrStatus.progress.stage !== "idle" ? (
                <div className="space-y-1 rounded-md border-l-2 border-blue-500 bg-blue-50 p-3 text-sm dark:bg-blue-950/30">
                  <p className="text-muted-foreground">
                    {localAsrStatus.progress.stage}
                    {localAsrStatus.progress.model_slug
                      ? ` (${localAsrStatus.progress.model_slug})`
                      : ""}
                    {localAsrStatus.progress.percent !== null
                      ? ` ${localAsrStatus.progress.percent}%`
                      : ""}
                  </p>
                  {localAsrStatus.progress.detail ? (
                    <p className="text-xs text-muted-foreground">
                      {localAsrStatus.progress.detail}
                    </p>
                  ) : null}
                  {localAsrStatus.progress.error ? (
                    <p className="text-xs text-red-500">
                      {localAsrStatus.progress.error}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </>
          );
        })() : (
          <p className="text-sm text-muted-foreground">{t("Loading…")}</p>
        )}
      </div>
    </div>
  );
}
