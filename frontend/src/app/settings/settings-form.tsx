"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Eye, EyeOff, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  deployAsr,
  getAsrDeployProgress,
  getAsrDeployStatus,
  getLocalAsrStatus,
  getModelSettings,
  getServiceStatus,
  installLocalAsrModel,
  selectLocalAsrModel,
  uninstallAllLocalAsr,
  uninstallLocalAsrModel,
  updateModelSettings,
  fetchApiKey,
  type AsrDeployProgress,
  type AsrDeployStatus,
  type AsrManagerStatus,
  type ModelConfig,
  type ModelsSettings,
  type ServiceStatus,
} from "@/lib/api";

const MODEL_NAMES = ["chat", "embedding", "asr"] as const;
type ModelName = (typeof MODEL_NAMES)[number];

// provider is intentionally omitted: it is not yet wired to any behavior
// (clients are built from endpoint/api_key/model). Editing it as free text
// could persist an invalid value and break get_settings(). Defer to 5B.
const FIELDS: { key: keyof ModelConfig; label: string }[] = [
  { key: "endpoint", label: "Endpoint" },
  { key: "api_key", label: "API Key" },
  { key: "model", label: "Model" },
];

function asrBaseUrl(endpoint: string | null) {
  const fallback = "http://localhost:8001/v1";
  const value = (endpoint || fallback).trim() || fallback;
  const base = value.replace(/\/+$/, "");
  try {
    const parsed = new URL(base);
    if (
      ["localhost", "127.0.0.1", "::1"].includes(parsed.hostname) &&
      !parsed.pathname.replace(/\/+$/, "")
    ) {
      return `${base}/v1`;
    }
  } catch {
    // Keep partially typed custom endpoints visible while the user edits.
  }
  return base;
}

function asrRequestUrl(endpoint: string | null, protocol: ModelConfig["protocol"]) {
  const route =
    (protocol ?? "transcriptions") === "chat_audio"
      ? "/chat/completions"
      : "/audio/transcriptions";
  return `${asrBaseUrl(endpoint)}${route}`;
}

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

export function SettingsForm() {
  const [settings, setSettings] = useState<ModelsSettings | null>(null);
  const [status, setStatus] = useState<Record<string, ServiceStatus>>({});
  const [message, setMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [visibleKeys, setVisibleKeys] = useState<Record<string, boolean>>({});
  const [plainKeys, setPlainKeys] = useState<Record<string, string | null>>({});
  const [asrDeployStatus, setAsrDeployStatus] =
    useState<AsrDeployStatus | null>(null);
  const [asrDeployProgress, setAsrDeployProgress] =
    useState<AsrDeployProgress | null>(null);
  const [isDeployingAsr, setIsDeployingAsr] = useState(false);

  // ── Local ASR model shelf modal ──────────────────────────────────────────
  const [showLocalAsrModal, setShowLocalAsrModal] = useState(false);
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

  const openLocalAsrModal = useCallback(async () => {
    try {
      const status = await getLocalAsrStatus();
      setLocalAsrStatus(status);
      setSelectedSlug(status.current ?? Object.keys(status.models)[0] ?? null);
      setShowLocalAsrModal(true);
      if (!status.progress.done) {
        startModalPolling();
      }
    } catch {
      setLocalAsrStatus(null);
      setShowLocalAsrModal(true);
    }
  }, [startModalPolling]);

  const closeLocalAsrModal = useCallback(() => {
    stopModalPolling();
    setShowLocalAsrModal(false);
    setLocalAsrStatus(null);
    setSelectedSlug(null);
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

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalId !== null) {
        window.clearInterval(pollIntervalId);
      }
    };
  }, [pollIntervalId]);

  useEffect(() => {
    getModelSettings().then(setSettings).catch(() => setMessage("Load failed"));
    getServiceStatus().then(setStatus).catch(() => {});
    getAsrDeployStatus().then(setAsrDeployStatus).catch(() => {});
  }, []);

  useEffect(() => {
    if (!isDeployingAsr) {
      return;
    }
    const interval = window.setInterval(async () => {
      try {
        const progress = await getAsrDeployProgress();
        setAsrDeployProgress(progress);
        if (progress.done) {
          window.clearInterval(interval);
          setIsDeployingAsr(false);
          setAsrDeployStatus(await getAsrDeployStatus());
        }
      } catch {
        window.clearInterval(interval);
        setIsDeployingAsr(false);
        setMessage("ASR deploy status failed.");
      }
    }, 1000);
    return () => window.clearInterval(interval);
  }, [isDeployingAsr]);

  function setField(name: ModelName, key: keyof ModelConfig, value: string) {
    setSettings((current) =>
      current
        ? { ...current, [name]: { ...current[name], [key]: value } }
        : current
    );
  }

  async function handleDeployAsr() {
    setMessage("");
    setIsDeployingAsr(true);
    try {
      const progress = await deployAsr();
      setAsrDeployProgress(progress);
    } catch {
      setIsDeployingAsr(false);
      setMessage("ASR deploy failed.");
    }
  }

  async function toggleApiKeyVisibility(name: string) {
    const currentlyVisible = visibleKeys[name];
    if (currentlyVisible) {
      setVisibleKeys((prev) => ({ ...prev, [name]: false }));
      return;
    }
    try {
      const plain = await fetchApiKey(name);
      setPlainKeys((prev) => ({ ...prev, [name]: plain }));
      setVisibleKeys((prev) => ({ ...prev, [name]: true }));
    } catch {
      setMessage("Failed to fetch api_key.");
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!settings) {
      return;
    }
    setMessage("");
    setIsSaving(true);
    try {
      const saved = await updateModelSettings(settings);
      setSettings(saved);
      setStatus(await getServiceStatus());
      setMessage("Saved.");
    } catch {
      setMessage("Save failed.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-6 py-10">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold">Settings</h1>
      </header>

      {message ? <p className="text-sm">{message}</p> : null}

      {settings ? (
        <form className="flex flex-col gap-6" onSubmit={handleSubmit}>
          {MODEL_NAMES.map((name) => (
            <section
              key={name}
              className="space-y-3 rounded-md border border-input p-4"
            >
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold capitalize">{name}</h2>
                {name !== "asr" ? (
                  <span className="text-xs text-muted-foreground">
                    {status[name]?.status ?? "unknown"}
                  </span>
                ) : null}
              </div>
              {FIELDS.map(({ key, label }) => (
                <label key={key} className="relative block text-sm">
                  <span className="mb-1 block text-muted-foreground">
                    {label}
                  </span>
                  <div className="relative">
                    <input
                      className="h-9 w-full rounded-md border border-input bg-background px-3 pr-9 text-sm"
                      value={key === "api_key" && visibleKeys[name] ? (plainKeys[name] ?? settings[name][key] ?? "") : (settings[name][key] ?? "")}
                      onChange={(event) => {
                        setField(name, key, event.target.value);
                      }}
                    />
                    {key === "api_key" && settings[name].api_key ? (
                      <button
                        type="button"
                        onClick={() => toggleApiKeyVisibility(name)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                        aria-label={visibleKeys[name] ? "Hide API key" : "Show API key"}
                      >
                        {visibleKeys[name] ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    ) : null}
                  </div>
                  {name === "asr" && label === "Endpoint" ? (
                    <p className="mt-1 text-xs text-muted-foreground">
                      Local default uses http://localhost:8001/v1; for cloud or LAN ASR, fill in an OpenAI-compatible base URL.
                    </p>
                  ) : null}
                </label>
              ))}
              {name === "asr" ? (
                <div className="space-y-3">
                  <label className="block text-sm">
                    <span className="mb-1 block text-muted-foreground">
                      Protocol
                    </span>
                    <select
                      className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                      value={settings.asr.protocol ?? "transcriptions"}
                      onChange={(event) =>
                        setField(
                          "asr",
                          "protocol",
                          event.target.value
                        )
                      }
                    >
                      <option value="transcriptions">transcriptions</option>
                      <option value="chat_audio">chat_audio</option>
                    </select>
                    <p className="mt-1 text-xs text-muted-foreground">
                      当前协议将请求 {asrRequestUrl(settings.asr.endpoint, settings.asr.protocol)}
                    </p>
                  </label>
                  {asrDeployStatus && asrDeployStatus.venv_exists ? (
                    <div className="flex items-center justify-between gap-3 rounded-md border border-input p-3">
                      <span className="text-sm text-muted-foreground">
                        Local ASR installed
                      </span>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={openLocalAsrModal}
                      >
                        Local ASR Model Settings
                      </Button>
                    </div>
                  ) : null}
                  {asrDeployStatus && !asrDeployStatus.venv_exists ? (
                    <div className="flex items-center justify-between gap-3 rounded-md border border-input p-3">
                      <span className="text-sm text-muted-foreground">
                        Local ASR not installed
                      </span>
                      <Button
                        type="button"
                        size="sm"
                        onClick={handleDeployAsr}
                        disabled={isDeployingAsr}
                      >
                        Deploy
                      </Button>
                    </div>
                  ) : null}
                  {asrDeployProgress ? (
                    <p className="text-xs text-muted-foreground">
                      {asrDeployProgress.detail}
                      {asrDeployProgress.percent !== null
                        ? ` ${asrDeployProgress.percent}%`
                        : ""}
                      {asrDeployProgress.error
                        ? `: ${asrDeployProgress.error}`
                        : ""}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </section>
          ))}
          <Button type="submit" disabled={isSaving}>
            Save
          </Button>
        </form>
      ) : (
        <p className="text-sm text-muted-foreground">Loading…</p>
      )}
      {showLocalAsrModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-lg max-h-[80vh] overflow-y-auto rounded-lg border bg-background p-5 shadow-lg space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Local ASR Model Settings</h2>
              <button
                type="button"
                onClick={closeLocalAsrModal}
                className="text-muted-foreground hover:text-foreground"
                aria-label="Close"
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
                      ASR Environment
                    </h3>
                    <div className="flex items-center justify-between gap-3 rounded-md border border-input bg-muted/30 p-3">
                      <div className="text-sm">
                        <div className="flex items-center gap-2">
                          <span
                            className={`inline-block h-2 w-2 rounded-full ${envReady ? "bg-green-500" : "bg-red-500"}`}
                          />
                          <span>
                            {envReady
                              ? "Environment ready"
                              : "Environment not installed"}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {envReady
                            ? `Environment size: ~${formatBytes(installedSize)}`
                            : "Environment size: —"}
                        </p>
                      </div>
                      {envReady ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="destructive"
                          onClick={handleUninstallAll}
                        >
                          Uninstall Environment
                        </Button>
                      ) : (
                        <Button
                          type="button"
                          size="sm"
                          onClick={handleDeployAsr}
                          disabled={isDeployingAsr}
                        >
                          Install Environment
                        </Button>
                      )}
                    </div>
                  </section>

                  {/* Section 2 & 3: Model family + size */}
                  <section className="space-y-2">
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Model
                    </h3>
                    <div className="flex gap-3">
                      <label className="block flex-1 text-sm">
                        <span className="mb-1 block text-muted-foreground">
                          Family
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
                              {FAMILY_LABELS[family] ?? family}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="block flex-1 text-sm">
                        <span className="mb-1 block text-muted-foreground">
                          Size
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
                            Uninstall
                          </Button>
                        ) : (
                          <Button
                            type="button"
                            size="sm"
                            onClick={() =>
                              handleInstallModel(currentModel.slug)
                            }
                          >
                            Install
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
              <p className="text-sm text-muted-foreground">Loading…</p>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
