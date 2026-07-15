"use client";

import { useCallback, useEffect, useState } from "react";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  createPreset,
  getLocalModelStatus,
  installLocalModel,
  listPresets,
  previewEmbeddingPresetConfigSwitch,
  previewEmbeddingPresetSwitch,
  switchActivePreset,
  switchEmbeddingPreset,
  uninstallAllLocalModels,
  uninstallLocalModel,
  updatePreset,
  type EmbeddingSwitchPreview,
  type LocalModelManagerStatus,
  type LocalModelService,
  type PresetConfig,
} from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

const SERVICE_LABELS: Record<LocalModelService, string> = {
  asr: "ASR",
  embedding: "Embedding",
};

const FAMILY_LABELS: Record<string, string> = {
  sensevoice: "SenseVoice (Chinese)",
  moonshine: "Moonshine Voice (English)",
};

function isBusy(status: LocalModelManagerStatus | null) {
  const stage = status?.progress.stage ?? "idle";
  return !["idle", "done", "failed"].includes(stage);
}

const LOCAL_ENDPOINTS: Record<LocalModelService, string> = {
  asr: "http://localhost:8001/v1",
  embedding: "http://localhost:8003/v1",
};

function normalizedEndpoint(value: string | null | undefined) {
  return (value ?? "").trim().replace(/\/+$/, "");
}

const STATUS_CACHE_PREFIX = "memento.local-model-status.v1";

function readCachedStatus(service: LocalModelService) {
  if (typeof window === "undefined") return null;
  try {
    const value = window.localStorage.getItem(`${STATUS_CACHE_PREFIX}.${service}`);
    if (!value) return null;
    const parsed = JSON.parse(value) as LocalModelManagerStatus;
    return parsed?.models && parsed?.environment ? parsed : null;
  } catch {
    return null;
  }
}

function writeCachedStatus(
  service: LocalModelService,
  status: LocalModelManagerStatus,
) {
  try {
    window.localStorage.setItem(
      `${STATUS_CACHE_PREFIX}.${service}`,
      JSON.stringify(status),
    );
  } catch {
    // Status caching is an optimization; storage may be unavailable.
  }
}

export function LocalModelModal({
  service,
  open,
  onClose,
  onConfigured,
}: {
  service: LocalModelService;
  open: boolean;
  onClose: () => void;
  onConfigured: () => void;
}) {
  const { t } = useLanguage();
  const [status, setStatus] = useState<LocalModelManagerStatus | null>(() =>
    readCachedStatus(service),
  );
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [configurationMessage, setConfigurationMessage] = useState("");
  const [isConfiguring, setIsConfiguring] = useState(false);
  const [pendingEmbeddingSwitch, setPendingEmbeddingSwitch] = useState<{
    preview: EmbeddingSwitchPreview;
    presetId: string;
    config: PresetConfig;
    updateBeforeSwitch: boolean;
  } | null>(null);

  const applyStatus = useCallback((next: LocalModelManagerStatus) => {
    setStatus(next);
    writeCachedStatus(service, next);
    setSelectedSlug((current) =>
      current && next.models[current]
        ? current
        : (Object.keys(next.models)[0] ?? null),
    );
  }, [service]);

  const refresh = useCallback(async () => {
    const next = await getLocalModelStatus(service);
    applyStatus(next);
    return next;
  }, [applyStatus, service]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const next = await getLocalModelStatus(service, {
          probeRuntimeDevice: false,
        });
        if (cancelled) return;
        applyStatus(next);
        void refresh().catch((error) => {
          if (!cancelled) {
            setMessage(error instanceof Error ? error.message : t("Operation failed"));
          }
        });
      } catch (error) {
        if (!cancelled) {
          setMessage(error instanceof Error ? error.message : t("Operation failed"));
        }
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, [applyStatus, refresh, service, t]);

  useEffect(() => {
    if (!open || !status) return;
    const timeoutId = window.setTimeout(() => {
      void refresh().catch((error) => {
        setMessage(error instanceof Error ? error.message : t("Operation failed"));
      });
    }, 0);
    return () => window.clearTimeout(timeoutId);
    // Refresh when a retained dialog is reopened.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (!open || !isBusy(status)) return;
    const interval = window.setInterval(() => {
      void refresh().catch((error) => {
        setMessage(error instanceof Error ? error.message : t("Operation failed"));
      });
    }, 1500);
    return () => window.clearInterval(interval);
  }, [open, refresh, status, t]);

  async function run(action: () => Promise<unknown>) {
    setMessage("");
    try {
      await action();
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("Operation failed"));
    }
  }

  function localPresetConfig(modelId: string): PresetConfig {
    return {
      endpoint: LOCAL_ENDPOINTS[service],
      api_key: "local",
      model: modelId,
      ...(service === "asr" ? { protocol: "transcriptions" } : {}),
    };
  }

  async function configureAndActivate(modelId: string) {
    setMessage("");
    setConfigurationMessage("");
    setPendingEmbeddingSwitch(null);
    setIsConfiguring(true);
    try {
      const config = localPresetConfig(modelId);
      const presets = await listPresets(service);
      const existing = presets.find(
        (preset) =>
          normalizedEndpoint(preset.config.endpoint) ===
          normalizedEndpoint(LOCAL_ENDPOINTS[service]),
      );
      const preset = existing
        ? existing
        : await createPreset(
            service,
            config,
            service === "asr" ? "Local ASR" : "Local Embedding",
          );

      if (service === "embedding") {
        const preview = existing
          ? await previewEmbeddingPresetConfigSwitch(preset.id, config)
          : await previewEmbeddingPresetSwitch(preset.id);
        if (!preview.same_dimension) {
          setPendingEmbeddingSwitch({
            preview,
            presetId: preset.id,
            config,
            updateBeforeSwitch: Boolean(existing),
          });
          return;
        }
        if (existing) {
          await updatePreset(service, preset.id, config);
        }
        await switchEmbeddingPreset(preset.id, false);
      } else {
        if (existing) {
          await updatePreset(service, preset.id, config);
        }
        await switchActivePreset(service, preset.id);
      }

      setConfigurationMessage(t("{service} preset configured and activated.", {
        service: SERVICE_LABELS[service],
      }));
      onConfigured();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("Operation failed"));
    } finally {
      setIsConfiguring(false);
    }
  }

  async function confirmEmbeddingSwitch() {
    if (!pendingEmbeddingSwitch) return;
    setMessage("");
    setIsConfiguring(true);
    try {
      if (pendingEmbeddingSwitch.updateBeforeSwitch) {
        await updatePreset(
          "embedding",
          pendingEmbeddingSwitch.presetId,
          pendingEmbeddingSwitch.config,
        );
      }
      await switchEmbeddingPreset(pendingEmbeddingSwitch.presetId, true);
      setPendingEmbeddingSwitch(null);
      setConfigurationMessage(t("Embedding preset configured. Index rebuild has started and it will become active when the rebuild completes."));
      onConfigured();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("Operation failed"));
    } finally {
      setIsConfiguring(false);
    }
  }

  if (!open) return null;

  const models = status ? Object.values(status.models) : [];
  const selectedModel = selectedSlug ? status?.models[selectedSlug] : undefined;
  const families = Array.from(
    new Set(models.map((model) => model.family).filter(Boolean)),
  ) as string[];
  const currentFamily = selectedModel?.family ?? families[0];
  const visibleModels =
    service === "asr" && currentFamily
      ? models.filter((model) => model.family === currentFamily)
      : models;
  const busy = isBusy(status) || isConfiguring;
  const environment = status?.environment;
  const displayedDevice =
    environment?.runtime_device ?? environment?.target_device ?? "cpu";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="max-h-[80vh] w-full max-w-lg space-y-5 overflow-y-auto rounded-lg border bg-background p-5 shadow-lg">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">
            {service === "asr"
              ? t("Local ASR Models")
              : t("Local Embedding Models")}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
            aria-label={t("Close")}
          >
            <X size={18} />
          </button>
        </div>

        {status ? (
          <>
            <section className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t("Environment")}
              </h3>
              <div className="flex items-center justify-between gap-3 rounded-md border border-input bg-muted/30 p-3">
                <div className="text-sm">
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-block h-2 w-2 rounded-full ${environment?.venv_exists ? "bg-green-500" : "bg-red-500"}`}
                    />
                    <span>
                      {environment?.venv_exists
                        ? t("Environment ready")
                        : t("Environment not installed")}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {environment?.runtime_device
                      ? t("Active device: {device}", { device: displayedDevice.toUpperCase() })
                      : t("Planned device: {device}", { device: displayedDevice.toUpperCase() })}
                  </p>
                  {!environment?.venv_exists ? (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {t("First model install also creates the environment.")}
                    </p>
                  ) : null}
                </div>
                {environment?.venv_exists ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="destructive"
                    disabled={busy}
                    onClick={() => {
                      if (window.confirm(t("Remove the local {service} environment and all its models?", {
                        service: SERVICE_LABELS[service],
                      }))) {
                        void run(() => uninstallAllLocalModels(service));
                      }
                    }}
                  >
                    {t("Uninstall Environment")}
                  </Button>
                ) : null}
              </div>
            </section>

            <section className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t("Select model")}
              </h3>
              <div className="flex gap-3">
                {service === "asr" ? (
                  <label className="block flex-1 text-sm">
                    <span className="mb-1 block text-muted-foreground">{t("Family")}</span>
                    <select
                      className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                      value={currentFamily ?? ""}
                      disabled={busy}
                      onChange={(event) => {
                        const next = models.find(
                          (model) => model.family === event.target.value,
                        );
                        if (next) {
                          setSelectedSlug(next.slug);
                          setPendingEmbeddingSwitch(null);
                          setConfigurationMessage("");
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
                ) : null}
                <label className="block flex-1 text-sm">
                  <span className="mb-1 block text-muted-foreground">{t("Model")}</span>
                  <select
                    className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                    value={selectedSlug ?? ""}
                    disabled={busy}
                    onChange={(event) => {
                      setSelectedSlug(event.target.value);
                      setPendingEmbeddingSwitch(null);
                      setConfigurationMessage("");
                    }}
                  >
                    {visibleModels.map((model) => (
                      <option key={model.slug} value={model.slug}>
                        {model.label}{model.size ? ` — ${model.size}` : ""}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              {selectedModel ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-3 rounded-md border border-input bg-muted/30 p-3">
                    <div className="text-sm">
                      <div className="flex items-center gap-2">
                        <span
                          className={`inline-block h-2 w-2 rounded-full ${selectedModel.installed ? "bg-green-500" : "bg-red-500"}`}
                        />
                        <span className="font-medium">{selectedModel.label}</span>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {selectedModel.model_id}
                      </p>
                    </div>
                    {selectedModel.installed ? (
                      <div className="flex gap-2">
                        <Button
                          type="button"
                          size="sm"
                          disabled={busy}
                          onClick={() =>
                            void configureAndActivate(selectedModel.model_id)
                          }
                        >
                          {isConfiguring ? t("Configuring…") : t("Configure & Activate")}
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="destructive"
                          disabled={busy}
                          onClick={() => {
                            if (window.confirm(t("Uninstall {model}?", {
                              model: selectedModel.label,
                            }))) {
                              void run(() => uninstallLocalModel(service, selectedModel.slug));
                            }
                          }}
                        >
                          {t("Uninstall")}
                        </Button>
                      </div>
                    ) : (
                      <Button
                        type="button"
                        size="sm"
                        disabled={busy}
                        onClick={() =>
                          void run(() => installLocalModel(service, selectedSlug!))
                        }
                      >
                        {t("Install")}
                      </Button>
                    )}
                  </div>
                  {pendingEmbeddingSwitch ? (
                    <div className="space-y-2 rounded-md border border-input bg-muted/30 p-3">
                      <p className="text-sm">
                        {t("Activating this model requires rebuilding the embedding index.")}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {t("Dimension {current} to {next}. {count} indexed documents will be reprocessed.", {
                          current: pendingEmbeddingSwitch.preview.current_dimension,
                          next: pendingEmbeddingSwitch.preview.new_dimension,
                          count: pendingEmbeddingSwitch.preview.indexed_document_count,
                        })}
                      </p>
                      <div className="flex justify-end gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={isConfiguring}
                          onClick={() => setPendingEmbeddingSwitch(null)}
                        >
                          {t("Cancel")}
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          disabled={isConfiguring}
                          onClick={() => void confirmEmbeddingSwitch()}
                        >
                          {t("Confirm & Rebuild")}
                        </Button>
                      </div>
                    </div>
                  ) : null}
                  {configurationMessage ? (
                    <p className="text-xs text-green-600 dark:text-green-400">
                      {configurationMessage}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </section>

            {status.progress.stage !== "idle" ? (
              <div className="space-y-1 rounded-md border-l-2 border-blue-500 bg-blue-50 p-3 text-sm dark:bg-blue-950/30">
                <p className="text-muted-foreground">
                  {status.progress.stage}
                  {status.progress.percent !== null
                    ? ` ${status.progress.percent}%`
                    : ""}
                </p>
                {status.progress.detail ? (
                  <p className="text-xs text-muted-foreground">
                    {status.progress.detail}
                  </p>
                ) : null}
                {status.progress.error ? (
                  <p className="text-xs text-red-500">{status.progress.error}</p>
                ) : null}
              </div>
            ) : null}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">{t("Loading…")}</p>
        )}

        {message ? <p className="text-sm text-red-500">{message}</p> : null}
      </div>
    </div>
  );
}
