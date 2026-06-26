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
  fetchApiKey,
  listPresets,
  createPreset,
  renamePreset,
  deletePreset,
  getActivePreset,
  switchActivePreset,
  updatePreset,
  type AsrDeployProgress,
  type AsrDeployStatus,
  type ModelConfig,
  type ModelsSettings,
  type ServiceStatus,
  type PresetResponse,
  type PresetModelName,
} from "@/lib/api";

import { LocalAsrModal } from "./local-asr-modal";

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

  // ── Presets state ────────────────────────────────────────────────────────
  const [presets, setPresets] = useState<Record<string, PresetResponse[]>>({});
  const [activePresetIds, setActivePresetIds] = useState<Record<string, string | null>>({});
  const [renamingPreset, setRenamingPreset] = useState<{ modelName: string; presetId: string } | null>(null);
  const [renameValue, setRenameValue] = useState("");

  // ── Local ASR model shelf modal ──────────────────────────────────────────
  const [showLocalAsrModal, setShowLocalAsrModal] = useState(false);

  // Close preset menu when clicking outside
  useEffect(() => {
    function handleClickOutside() {
      setRenamingPreset(null);
    }
    if (renamingPreset) {
      window.addEventListener("click", handleClickOutside);
      return () => window.removeEventListener("click", handleClickOutside);
    }
  }, [renamingPreset]);

  useEffect(() => {
    getModelSettings().then(setSettings).catch(() => setMessage("Load failed"));
    getServiceStatus().then(setStatus).catch(() => {});
    getAsrDeployStatus().then(setAsrDeployStatus).catch(() => {});

    // Load presets and active preset for each model
    MODEL_NAMES.forEach(async (name) => {
      try {
        const presetList = await listPresets(name as PresetModelName);
        setPresets((prev) => ({ ...prev, [name]: presetList }));

        const active = await getActivePreset(name as PresetModelName);
        setActivePresetIds((prev) => ({ ...prev, [name]: active.preset_id }));

        // If there's an active preset, load its config into settings
        if (active.preset && active.preset.config) {
          setSettings((current) =>
            current
              ? { ...current, [name]: active.preset!.config }
              : current
          );
        }
      } catch {
        // Ignore preset load failures
      }
    });
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
      // Save to the active preset
      for (const name of MODEL_NAMES) {
        const activeId = activePresetIds[name];
        if (activeId) {
          const config = settings[name];
          await updatePreset(name as PresetModelName, activeId, config);
        }
      }
      setStatus(await getServiceStatus());
      setMessage("Saved.");
    } catch {
      setMessage("Save failed.");
    } finally {
      setIsSaving(false);
    }
  }

  // ── Preset operations ────────────────────────────────────────────────────

  async function handleSwitchPreset(name: ModelName, presetId: string) {
    try {
      await switchActivePreset(name as PresetModelName, presetId);
      setActivePresetIds((prev) => ({ ...prev, [name]: presetId }));

      // Load the preset config into settings
      const preset = presets[name]?.find((p) => p.id === presetId);
      if (preset) {
        // Reset all fields to preset config (don't merge with old values)
        setSettings((current) =>
          current
            ? { ...current, [name]: preset.config }
            : current
        );
      }
      setMessage("");
    } catch {
      setMessage("Switch preset failed.");
    }
  }

  async function handleCreatePreset(name: ModelName) {
    try {
      const currentConfig = settings?.[name] || {};
      const newPreset = await createPreset(name as PresetModelName, currentConfig);

      // Refresh preset list
      const presetList = await listPresets(name as PresetModelName);
      setPresets((prev) => ({ ...prev, [name]: presetList }));

      // Switch to the new preset
      await handleSwitchPreset(name, newPreset.id);
    } catch {
      setMessage("Create preset failed.");
    }
  }

  async function handleRenamePreset(name: ModelName, presetId: string, newName: string) {
    try {
      await renamePreset(name as PresetModelName, presetId, newName);

      // Refresh preset list
      const presetList = await listPresets(name as PresetModelName);
      setPresets((prev) => ({ ...prev, [name]: presetList }));

      setRenamingPreset(null);
      setRenameValue("");
      setMessage("");
    } catch {
      setMessage("Rename preset failed.");
    }
  }

  async function handleDeletePreset(name: ModelName, presetId: string) {
    const presetList = presets[name] || [];
    if (presetList.length <= 1) {
      setMessage("Cannot delete the last preset.");
      return;
    }

    try {
      await deletePreset(name as PresetModelName, presetId);

      // Refresh preset list and active preset
      const updatedList = await listPresets(name as PresetModelName);
      setPresets((prev) => ({ ...prev, [name]: updatedList }));

      const active = await getActivePreset(name as PresetModelName);
      setActivePresetIds((prev) => ({ ...prev, [name]: active.preset_id }));

      // Load the new active preset config
      if (active.preset) {
        setSettings((current) =>
          current
            ? { ...current, [name]: active.preset!.config }
            : current
        );
      }

      setMessage("");
    } catch {
      setMessage("Delete preset failed.");
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
          {MODEL_NAMES.map((name) => {
            const modelPresets = presets[name] || [];
            const activeId = activePresetIds[name];
            const activePreset = modelPresets.find((p) => p.id === activeId);

            return (
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

                {/* Preset management header */}
                <div className="flex items-center justify-between border-b border-input pb-3">
                  <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Presets
                  </span>
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => handleCreatePreset(name)}
                      className="h-7 text-xs"
                    >
                      + New
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        if (activePreset) {
                          setRenamingPreset({ modelName: name, presetId: activePreset.id });
                          setRenameValue(activePreset.name);
                        }
                      }}
                      className="h-7 text-xs"
                    >
                      Rename
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        if (activeId) {
                          handleDeletePreset(name, activeId);
                        }
                      }}
                      disabled={modelPresets.length <= 1}
                      className="h-7 text-xs text-red-600 hover:text-red-700 disabled:opacity-50"
                    >
                      Delete
                    </Button>
                  </div>
                </div>

                {/* Rename dialog */}
                {renamingPreset?.modelName === name && renamingPreset?.presetId === activeId ? (
                  <div className="flex items-center gap-2 rounded-md border border-input bg-muted/30 p-3">
                    <input
                      type="text"
                      className="h-8 flex-1 rounded-md border border-input bg-background px-2 text-sm"
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && renamingPreset) {
                          handleRenamePreset(name, renamingPreset.presetId, renameValue);
                        } else if (e.key === "Escape") {
                          setRenamingPreset(null);
                          setRenameValue("");
                        }
                      }}
                      autoFocus
                    />
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => {
                        if (renamingPreset) {
                          handleRenamePreset(name, renamingPreset.presetId, renameValue);
                        }
                      }}
                    >
                      OK
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setRenamingPreset(null);
                        setRenameValue("");
                      }}
                    >
                      Cancel
                    </Button>
                  </div>
                ) : null}

                {/* Preset tabs */}
                <div className="flex flex-wrap gap-2">
                  {modelPresets.map((preset) => (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => handleSwitchPreset(name, preset.id)}
                      className={`rounded-md border-2 px-4 py-2 text-sm font-medium transition-colors ${
                        preset.id === activeId
                          ? "border-primary bg-primary/10 text-primary"
                          : "border-input bg-background text-foreground hover:border-primary"
                      }`}
                    >
                      {preset.name}
                    </button>
                  ))}
                </div>

                {/* Config fields */}
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
                        onClick={() => setShowLocalAsrModal(true)}
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
          );
          })}
          <Button type="submit" disabled={isSaving}>
            Save
          </Button>
        </form>
      ) : (
        <p className="text-sm text-muted-foreground">Loading…</p>
      )}
      <LocalAsrModal
        open={showLocalAsrModal}
        onClose={() => setShowLocalAsrModal(false)}
        onDeploy={handleDeployAsr}
        isDeploying={isDeployingAsr}
      />
    </div>
  );
}
