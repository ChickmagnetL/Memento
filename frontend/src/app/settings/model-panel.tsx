"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";

import {
  getEmbeddingReindexJob,
  getActiveEmbeddingReindexJob,
  createPreset,
  deletePreset,
  previewEmbeddingPresetSwitch,
  fetchApiKey,
  getActivePreset,
  listPresets,
  previewEmbeddingPresetConfigSwitch,
  renamePreset,
  switchEmbeddingPreset,
  switchActivePreset,
  updatePreset,
  type EmbeddingReindexJob,
  type EmbeddingSwitchPreview,
  type EmbeddingSwitchResult,
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

async function loadPanelState(modelName: PresetModelName) {
  const presetList = await listPresets(modelName);
  const active = await getActivePreset(modelName);
  return { presetList, active };
}

function formatJobValue(value: string) {
  return value.replace(/_/g, " ");
}

export function ModelPanel({
  modelName,
  status,
  fields,
  asrExtras,
}: ModelPanelProps) {
  const messageSourceRef = useRef<"poll" | "other" | null>(null);
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
  const [pendingSwitchPreview, setPendingSwitchPreview] =
    useState<EmbeddingSwitchPreview | null>(null);
  const [pendingEmbeddingSave, setPendingEmbeddingSave] = useState<{
    presetId: string;
    config: PresetConfig;
  } | null>(null);
  const [reindexJob, setReindexJob] = useState<EmbeddingReindexJob | null>(null);
  const [isSwitching, setIsSwitching] = useState(false);
  const [message, setMessage] = useState("");
  const hasActiveEmbeddingReindexJob =
    modelName === "embedding" &&
    (reindexJob?.status === "pending" || reindexJob?.status === "running");

  function setInlineMessage(
    nextMessage: string,
    source: "poll" | "other" = "other"
  ) {
    messageSourceRef.current = nextMessage ? source : null;
    setMessage(nextMessage);
  }

  // Load this model's preset list + active preset on mount / model change.
  useEffect(() => {
    async function load() {
      try {
        const { presetList, active } = await loadPanelState(modelName);
        setPresets(presetList);
        if (modelName === "embedding") {
          const activeJob = await getActiveEmbeddingReindexJob();
          setReindexJob(activeJob);
          if (
            activeJob &&
            (activeJob.status === "pending" || activeJob.status === "running")
          ) {
            setActivePresetId(activeJob.preset_id);
            const activeJobPreset = presetList.find(
              (preset) => preset.id === activeJob.preset_id
            );
            if (activeJobPreset) {
              setSettings(toModelConfig(activeJobPreset.config));
            }
            return;
          }
        } else {
          setReindexJob(null);
        }
        setActivePresetId(active.preset_id);
        if (active.preset?.config) {
          setSettings(toModelConfig(active.preset.config));
        }
      } catch (e) {
        setInlineMessage(e instanceof Error ? e.message : "Operation failed");
      }
    }
    load();
  }, [modelName]);

  useEffect(() => {
    if (modelName !== "embedding" || !reindexJob) {
      return;
    }

    if (hasActiveEmbeddingReindexJob) {
      let cancelled = false;
      let timeoutId: number | null = null;

      const poll = async () => {
        try {
          const job = await getEmbeddingReindexJob(reindexJob.id);
          if (!cancelled) {
            if (messageSourceRef.current === "poll") {
              setInlineMessage("");
            }
            setReindexJob(job);
          }
        } catch (e) {
          if (cancelled) {
            return;
          }
          setInlineMessage(
            e instanceof Error ? e.message : "Operation failed",
            "poll"
          );
          timeoutId = window.setTimeout(() => {
            void poll();
          }, 1000);
        }
      };

      timeoutId = window.setTimeout(() => {
        void poll();
      }, 1000);

      return () => {
        cancelled = true;
        if (timeoutId !== null) {
          window.clearTimeout(timeoutId);
        }
      };
    }

    async function refreshAfterJob() {
      try {
        const { presetList, active } = await loadPanelState(modelName);
        if (messageSourceRef.current === "poll") {
          setInlineMessage("");
        }
        setPresets(presetList);
        setActivePresetId(active.preset_id);
        if (active.preset?.config) {
          setSettings(toModelConfig(active.preset.config));
        }
      } catch (e) {
        setInlineMessage(e instanceof Error ? e.message : "Operation failed");
      }
    }

    void refreshAfterJob();
  }, [hasActiveEmbeddingReindexJob, modelName, reindexJob]);

  function setField(key: keyof ModelConfig, value: string) {
    if (pendingEmbeddingSave) {
      setPendingSwitchPreview(null);
      setPendingEmbeddingSave(null);
    }
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
      setInlineMessage(e instanceof Error ? e.message : "Operation failed");
    }
  }

  function activatePresetFromList(
    presetId: string,
    presetList: PresetResponse[] = presets
  ) {
    setActivePresetId(presetId);
    const preset = presetList.find((item) => item.id === presetId);
    if (preset) {
      setSettings(toModelConfig(preset.config));
    }
  }

  function replacePresetInList(updatedPreset: PresetResponse) {
    const presetList = presets.map((preset) =>
      preset.id === updatedPreset.id ? updatedPreset : preset
    );
    setPresets(presetList);
    return presetList;
  }

  function showEmbeddingSwitchPreview(
    preview: EmbeddingSwitchPreview,
    pendingSave: { presetId: string; config: PresetConfig } | null = null
  ) {
    setReindexJob(null);
    setPendingEmbeddingSave(pendingSave);
    setPendingSwitchPreview(preview);
  }

  function handleEmbeddingSwitchResult(
    result: EmbeddingSwitchResult,
    presetList: PresetResponse[] = presets
  ) {
    setInlineMessage("");
    setPendingSwitchPreview(null);
    setPendingEmbeddingSave(null);
    activatePresetFromList(result.preset_id, presetList);
    if (result.job_id) {
      setReindexJob({
        id: result.job_id,
        preset_id: result.preset_id,
        status: result.status,
        stage: result.stage,
        total_documents: result.total_documents ?? 0,
        processed_documents: result.processed_documents ?? 0,
        failed_documents: result.failed_documents ?? [],
        error: result.error ?? null,
        started_at: result.started_at ?? new Date().toISOString(),
        finished_at: result.finished_at ?? null,
      });
      return;
    }
    setReindexJob(null);
  }

  async function handleSwitchPreset(
    presetId: string,
    presetList: PresetResponse[] = presets
  ) {
    if (isSwitching || isSaving || hasActiveEmbeddingReindexJob) {
      return;
    }
    setPendingSwitchPreview(null);
    setPendingEmbeddingSave(null);
    setReindexJob(null);
    setInlineMessage(
      modelName === "embedding"
        ? "Switching embedding preset..."
        : "Switching preset..."
    );
    try {
      setIsSwitching(true);
      if (modelName === "embedding") {
        const preview = await previewEmbeddingPresetSwitch(presetId);
        if (!preview.same_dimension) {
          setInlineMessage("");
          showEmbeddingSwitchPreview(preview);
          return;
        }
        const result = await switchEmbeddingPreset(presetId, false);
        handleEmbeddingSwitchResult(result, presetList);
        return;
      }

      await switchActivePreset(modelName, presetId);
      activatePresetFromList(presetId, presetList);
      setInlineMessage("");
    } catch (e) {
      setInlineMessage(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setIsSwitching(false);
    }
  }

  async function handleConfirmEmbeddingSwitch() {
    if (!pendingSwitchPreview || isSwitching || isSaving) {
      return;
    }
    setInlineMessage("");
    try {
      setIsSwitching(true);
      const nextPresetId = pendingSwitchPreview.preset_id;
      if (pendingEmbeddingSave) {
        setIsSaving(true);
        const updatedPreset = await updatePreset(
          "embedding",
          pendingEmbeddingSave.presetId,
          pendingEmbeddingSave.config
        );
        const presetList = replacePresetInList(updatedPreset);
        const result = await switchEmbeddingPreset(nextPresetId, true);
        handleEmbeddingSwitchResult(result, presetList);
        return;
      }
      const result = await switchEmbeddingPreset(
        nextPresetId,
        true
      );
      handleEmbeddingSwitchResult(result);
    } catch (e) {
      setInlineMessage(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setIsSwitching(false);
      setIsSaving(false);
    }
  }

  function handleCancelEmbeddingSwitch() {
    if (isSwitching) {
      return;
    }
    setPendingSwitchPreview(null);
    setPendingEmbeddingSave(null);
  }

  async function handleCreatePreset() {
    try {
      const newPreset = await createPreset(modelName, settings);
      const presetList = await listPresets(modelName);
      setPresets(presetList);
      await handleSwitchPreset(newPreset.id, presetList);
    } catch (e) {
      setInlineMessage(e instanceof Error ? e.message : "Operation failed");
    }
  }

  async function handleRenamePreset(presetId: string, newName: string) {
    try {
      await renamePreset(modelName, presetId, newName);
      const presetList = await listPresets(modelName);
      setPresets(presetList);
      setRenamingPreset(null);
      setRenameValue("");
      setInlineMessage("");
    } catch (e) {
      setInlineMessage(e instanceof Error ? e.message : "Operation failed");
    }
  }

  async function handleDeletePreset(presetId: string) {
    if (modelName === "embedding" && hasActiveEmbeddingReindexJob) {
      setInlineMessage(
        "Cannot delete embedding presets while an embedding reindex job is running."
      );
      return;
    }
    if (presets.length <= 1) {
      setInlineMessage("Cannot delete the last preset.");
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
      setInlineMessage("");
    } catch (e) {
      setInlineMessage(e instanceof Error ? e.message : "Operation failed");
    }
  }

  // Save writes the ACTIVE preset. Status refresh is the parent's concern —
  // `status` arrives as a prop with no callback path on this interface.
  async function handleSave() {
    if (!activePresetId) {
      return;
    }
    if (modelName === "embedding" && hasActiveEmbeddingReindexJob) {
      setInlineMessage(
        "Cannot save embedding presets while an embedding reindex job is running."
      );
      return;
    }
    setPendingSwitchPreview(null);
    setPendingEmbeddingSave(null);
    setReindexJob(null);
    setInlineMessage(
      modelName === "embedding"
        ? "Saving and checking embedding preset..."
        : ""
    );
    setIsSaving(true);
    try {
      if (modelName === "embedding") {
        const saveConfig = { ...settings };
        const preview = await previewEmbeddingPresetConfigSwitch(
          activePresetId,
          saveConfig
        );
        if (!preview.same_dimension) {
          setInlineMessage("");
          showEmbeddingSwitchPreview(preview, {
            presetId: activePresetId,
            config: saveConfig,
          });
          return;
        }
        const updatedPreset = await updatePreset(
          modelName,
          activePresetId,
          saveConfig
        );
        replacePresetInList(updatedPreset);
        setInlineMessage("Saved.");
        return;
      }
      const updatedPreset = await updatePreset(modelName, activePresetId, settings);
      replacePresetInList(updatedPreset);
      setInlineMessage("Saved.");
    } catch (e) {
      setInlineMessage(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setIsSaving(false);
    }
  }

  const previewPreset = pendingSwitchPreview
    ? presets.find((preset) => preset.id === pendingSwitchPreview.preset_id)
    : null;
  const reindexPreset = reindexJob
    ? presets.find((preset) => preset.id === reindexJob.preset_id)
    : null;

  return (
    <div className="space-y-3">
      {message ? (
        <p className="text-sm text-muted-foreground">{message}</p>
      ) : null}

      {modelName === "embedding" && reindexJob && !pendingSwitchPreview ? (
        <div className="space-y-2 rounded-md border border-input bg-muted/30 p-3">
          <p className="text-sm text-foreground">
            Embedding reindex status: {formatJobValue(reindexJob.status)}
          </p>
          <p className="text-xs text-muted-foreground">
            Preset: {reindexPreset?.name ?? reindexJob.preset_id}
          </p>
          <p className="text-xs text-muted-foreground">
            Stage: {formatJobValue(reindexJob.stage)}
          </p>
          <p className="text-xs text-muted-foreground">
            Progress: {reindexJob.processed_documents} /{" "}
            {reindexJob.total_documents} documents
          </p>
          {reindexJob.error ? (
            <p className="text-xs text-destructive">{reindexJob.error}</p>
          ) : null}
          {reindexJob.failed_documents.length > 0 ? (
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Failed documents:</p>
              {reindexJob.failed_documents.map((document) => (
                <p
                  key={document.document_id}
                  className="text-xs text-muted-foreground"
                >
                  {document.title ?? document.document_id}: {document.error}
                </p>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      {modelName === "embedding" &&
      pendingSwitchPreview &&
      !pendingSwitchPreview.same_dimension ? (
        <div className="space-y-2 rounded-md border border-input bg-muted/30 p-3">
          <p className="text-sm text-foreground">
            {pendingEmbeddingSave ? "Saving" : "Switching to"}{" "}
            {previewPreset?.name ?? pendingSwitchPreview.preset_id} will rebuild
            the embedding index.
          </p>
          <p className="text-xs text-muted-foreground">
            Dimension {pendingSwitchPreview.current_dimension} to{" "}
            {pendingSwitchPreview.new_dimension}.{" "}
            {pendingSwitchPreview.indexed_document_count} indexed documents will be
            reprocessed.
          </p>
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={handleCancelEmbeddingSwitch}
              disabled={isSwitching}
            >
              Cancel
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={handleConfirmEmbeddingSwitch}
              disabled={isSwitching}
            >
              {pendingEmbeddingSave ? "Confirm save" : "Confirm switch"}
            </Button>
          </div>
        </div>
      ) : null}

      {presets.map((preset) => {
        const isActive = preset.id === activePresetId;
        return (
          <PresetCard
            key={preset.id}
            preset={preset}
            isActive={isActive}
            switchDisabled={
              !isActive && (hasActiveEmbeddingReindexJob || isSwitching || isSaving)
            }
            status={modelName === "asr" ? undefined : status}
            fields={fields}
            values={isActive ? settings : toModelConfig(preset.config)}
            onFieldChange={setField}
            onSave={handleSave}
            isSaving={
              isSaving || (modelName === "embedding" && hasActiveEmbeddingReindexJob)
            }
            onSwitchActivate={() => handleSwitchPreset(preset.id)}
            onRename={() => {
              setRenamingPreset({ presetId: preset.id });
              setRenameValue(preset.name);
            }}
            onDelete={() => handleDeletePreset(preset.id)}
            canDelete={
              presets.length > 1 &&
              !(modelName === "embedding" && hasActiveEmbeddingReindexJob)
            }
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
