"use client";

import { FormEvent, useEffect, useState } from "react";
import { Eye, EyeOff } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  deployAsr,
  getAsrDeployProgress,
  getAsrDeployStatus,
  getModelSettings,
  getServiceStatus,
  updateModelSettings,
  fetchApiKey,
  type AsrDeployProgress,
  type AsrDeployStatus,
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
                <span className="text-xs text-muted-foreground">
                  {status[name]?.status ?? "unknown"}
                </span>
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
                      本地默认使用 http://localhost:8001/v1；云端或局域网 ASR 也填写 OpenAI-compatible base URL。
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
                  {asrDeployStatus && !asrDeployStatus.venv_exists ? (
                    <div className="flex items-center justify-between gap-3 rounded-md border border-input p-3">
                      <span className="text-sm text-muted-foreground">
                        本地 ASR 未安装
                      </span>
                      <Button
                        type="button"
                        size="sm"
                        onClick={handleDeployAsr}
                        disabled={isDeployingAsr}
                      >
                        一键部署
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
    </div>
  );
}
