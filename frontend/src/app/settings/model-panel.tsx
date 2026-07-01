"use client";

import { useEffect, useState, type ReactNode } from "react";

import {
  createPreset,
  deletePreset,
  fetchApiKey,
  getActivePreset,
  listPresets,
  renamePreset,
  switchActivePreset,
  updatePreset,
  type ModelConfig,
  type PresetConfig,
  type PresetModelName,
  type PresetResponse,
  type ServiceStatus,
} from "@/lib/api";

import { PresetCard } from "./preset-card";

export interface ModelPanelProps {
  modelName: PresetModelName;
  status?: ServiceStatus;
  fields: { key: keyof ModelConfig; label: string }[];
  /**
   * Render-prop called only for the active card when modelName === "asr".
   * ModelPanel injects the ASR preset's `protocol`/`endpoint` (which live in
   * its own settings state, not the parent's) + the protocol setter; the
   * parent owns the ASR-specific JSX (protocol select + asrRequestUrl + Local
   * ASR management). A static ReactNode can't reach the protocol field.
   */
  asrExtras?: (ctx: {
    protocol: ModelConfig["protocol"];
    onProtocolChange: (value: string) => void;
    endpoint: string | null;
  }) => ReactNode;
}

const EMPTY_MODEL_CONFIG: ModelConfig = {
  provider: null,
  endpoint: null,
  api_key: null,
  model: null,
  protocol: null,
};

// Adapt a preset's stored config into the shape ModelConfig requires.
// PresetConfig has all-optional fields and `protocol?: string | null`;
// ModelConfig has required fields and `protocol: "transcriptions" | "chat_audio" | null`.
// Defaults the optionals to null and narrows protocol so the scalar
// `useState<ModelConfig>` (and PresetCard's `values` prop) satisfies tsc.
function toModelConfig(config: PresetConfig): ModelConfig {
  return {
    provider: config.provider ?? null,
    endpoint: config.endpoint ?? null,
    api_key: config.api_key ?? null,
    model: config.model ?? null,
    protocol: (config.protocol as ModelConfig["protocol"]) ?? null,
  };
}

export function ModelPanel({
  modelName,
  status,
  fields,
  asrExtras,
}: ModelPanelProps) {
  const [presets, setPresets] = useState<PresetResponse[]>([]);
  const [activePresetId, setActivePresetId] = useState<string | null>(null);
  const [settings, setSettings] = useState<ModelConfig>(EMPTY_MODEL_CONFIG);
  const [renamingPreset, setRenamingPreset] = useState<{
    presetId: string;
  } | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [apiKeyVisible, setApiKeyVisible] = useState(false);
  const [apiKeyPlain, setApiKeyPlain] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState("");

  // Load this model's preset list + active preset on mount / model change.
  useEffect(() => {
    async function load() {
      try {
        const presetList = await listPresets(modelName);
        setPresets(presetList);
        const active = await getActivePreset(modelName);
        setActivePresetId(active.preset_id);
        if (active.preset?.config) {
          setSettings(toModelConfig(active.preset.config));
        }
      } catch (e) {
        setMessage(e instanceof Error ? e.message : "Operation failed");
      }
    }
    load();
  }, [modelName]);

  function setField(key: keyof ModelConfig, value: string) {
    setSettings((current) => ({ ...current, [key]: value }));
  }

  async function toggleApiKeyVisibility() {
    if (apiKeyVisible) {
      setApiKeyVisible(false);
      return;
    }
    try {
      const plain = await fetchApiKey(modelName);
      setApiKeyPlain(plain);
      setApiKeyVisible(true);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Operation failed");
    }
  }

  async function handleSwitchPreset(presetId: string) {
    try {
      await switchActivePreset(modelName, presetId);
      setActivePresetId(presetId);
      const preset = presets.find((p) => p.id === presetId);
      if (preset) {
        setSettings(toModelConfig(preset.config));
      }
      setMessage("");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Operation failed");
    }
  }

  async function handleCreatePreset() {
    try {
      const newPreset = await createPreset(modelName, settings);
      const presetList = await listPresets(modelName);
      setPresets(presetList);
      await handleSwitchPreset(newPreset.id);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Operation failed");
    }
  }

  async function handleRenamePreset(presetId: string, newName: string) {
    try {
      await renamePreset(modelName, presetId, newName);
      const presetList = await listPresets(modelName);
      setPresets(presetList);
      setRenamingPreset(null);
      setRenameValue("");
      setMessage("");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Operation failed");
    }
  }

  async function handleDeletePreset(presetId: string) {
    if (presets.length <= 1) {
      setMessage("Cannot delete the last preset.");
      return;
    }
    try {
      await deletePreset(modelName, presetId);
      const updatedList = await listPresets(modelName);
      setPresets(updatedList);
      const active = await getActivePreset(modelName);
      setActivePresetId(active.preset_id);
      if (active.preset?.config) {
        setSettings(toModelConfig(active.preset.config));
      }
      setMessage("");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Operation failed");
    }
  }

  // Save writes the ACTIVE preset. Status refresh is the parent's concern —
  // `status` arrives as a prop with no callback path on this interface.
  async function handleSave() {
    if (!activePresetId) {
      return;
    }
    setMessage("");
    setIsSaving(true);
    try {
      await updatePreset(modelName, activePresetId, settings);
      setMessage("Saved.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="space-y-3">
      {message ? (
        <p className="text-sm text-muted-foreground">{message}</p>
      ) : null}

      {presets.map((preset) => {
        const isActive = preset.id === activePresetId;
        return (
          <PresetCard
            key={preset.id}
            preset={preset}
            isActive={isActive}
            status={modelName === "asr" ? undefined : status}
            fields={fields}
            values={isActive ? settings : toModelConfig(preset.config)}
            onFieldChange={setField}
            onSave={handleSave}
            isSaving={isSaving}
            onSwitchActivate={() => handleSwitchPreset(preset.id)}
            onRename={() => {
              setRenamingPreset({ presetId: preset.id });
              setRenameValue(preset.name);
            }}
            onDelete={() => handleDeletePreset(preset.id)}
            canDelete={presets.length > 1}
            apiKeyVisible={apiKeyVisible}
            apiKeyPlain={apiKeyPlain}
            onToggleApiKey={toggleApiKeyVisibility}
            isRenaming={renamingPreset?.presetId === preset.id}
            renameValue={renameValue}
            onRenameChange={setRenameValue}
            onRenameSubmit={() => handleRenamePreset(preset.id, renameValue)}
            onRenameCancel={() => {
              setRenamingPreset(null);
              setRenameValue("");
            }}
          >
            {isActive && asrExtras
              ? asrExtras({
                  protocol: settings.protocol,
                  onProtocolChange: (v) => setField("protocol", v),
                  endpoint: settings.endpoint,
                })
              : undefined}
          </PresetCard>
        );
      })}

      <div
        onClick={handleCreatePreset}
        className="cursor-pointer rounded-xl border border-dashed border-border p-4 text-center text-sm text-muted-foreground transition-colors hover:border-primary/50"
      >
        + New preset
      </div>
    </div>
  );
}
