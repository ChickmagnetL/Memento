"use client";
/* eslint-disable react-hooks/refs */

import { useEffect, useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";

import {
  getEmbeddingReindexJob,
  getActiveEmbeddingReindexJob,
  createPreset,
  deletePreset,
  previewEmbeddingPresetSwitch,
  fetchAvailableModels,
  fetchPresetApiKey,
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
   * Render-prop called for the selected card when modelName === "asr".
   * ModelPanel injects the selected ASR preset's `protocol`/`endpoint` plus
   * the protocol setter; the parent owns the ASR-specific JSX.
   */
  asrExtras?: (ctx: {
    protocol: ModelConfig["protocol"];
    onProtocolChange: (value: string) => void;
    endpoint: string | null;
    disabled: boolean;
  }) => ReactNode;
}

const EMPTY_MODEL_CONFIG: ModelConfig = {
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
    endpoint: config.endpoint ?? null,
    api_key: config.api_key ?? null,
    model: config.model ?? null,
    protocol: (config.protocol as ModelConfig["protocol"]) ?? null,
  };
}

function toPresetConfig(config: ModelConfig): PresetConfig {
  return {
    endpoint: config.endpoint,
    api_key: config.api_key,
    model: config.model,
    protocol: config.protocol,
  };
}

function normalizeConfig(config: PresetConfig | ModelConfig) {
  return {
    endpoint: config.endpoint ?? null,
    api_key: config.api_key ?? null,
    model: config.model ?? null,
    protocol: config.protocol ?? null,
  };
}

function configsEqual(
  left: PresetConfig | ModelConfig,
  right: PresetConfig | ModelConfig
) {
  const a = normalizeConfig(left);
  const b = normalizeConfig(right);
  return (
    a.endpoint === b.endpoint &&
    a.api_key === b.api_key &&
    a.model === b.model &&
    a.protocol === b.protocol
  );
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
  const [selectedPresetId, setSelectedPresetId] = useState<string | null>(null);
  const apiKeyRequestSeqRef = useRef(0);
  const modelListRequestSeqRef = useRef(0);
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
  const [pendingEmbeddingAction, setPendingEmbeddingAction] = useState<{
    presetId: string;
    config?: PresetConfig;
    label: "save" | "activate";
  } | null>(null);
  const [reindexJob, setReindexJob] = useState<EmbeddingReindexJob | null>(null);
  const [isSwitching, setIsSwitching] = useState(false);
  const [message, setMessage] = useState("");
  const [modelOptions, setModelOptions] = useState<string[]>([]);
  const [modelListMessage, setModelListMessage] = useState("");
  const [isFetchingModels, setIsFetchingModels] = useState(false);
  const hasActiveEmbeddingReindexJob =
    modelName === "embedding" &&
    (reindexJob?.status === "pending" || reindexJob?.status === "running");
  const controlsDisabled =
    isSaving ||
    isSwitching ||
    (modelName === "embedding" && hasActiveEmbeddingReindexJob);

  function setInlineMessage(
    nextMessage: string,
    source: "poll" | "other" = "other"
  ) {
    messageSourceRef.current = nextMessage ? source : null;
    setMessage(nextMessage);
  }

  function clearModelOptions() {
    modelListRequestSeqRef.current += 1;
    setModelOptions([]);
    setModelListMessage("");
    setIsFetchingModels(false);
  }

  function invalidateApiKeyRevealRequest() {
    apiKeyRequestSeqRef.current += 1;
  }

  function invalidateApiKeyReveal() {
    invalidateApiKeyRevealRequest();
    setApiKeyVisible(false);
    setApiKeyPlain(null);
  }

  function selectPresetFromList(
    presetId: string | null,
    presetList: PresetResponse[] = presets
  ) {
    if (!presetId) {
      setSelectedPresetId(null);
      setSettings(EMPTY_MODEL_CONFIG);
      clearModelOptions();
      invalidateApiKeyReveal();
      return;
    }
    const preset = presetList.find((item) => item.id === presetId);
    if (!preset) {
      return;
    }
    setSelectedPresetId(presetId);
    setSettings(toModelConfig(preset.config));
    clearModelOptions();
    setPendingSwitchPreview(null);
    setPendingEmbeddingAction(null);
    invalidateApiKeyReveal();
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
            selectPresetFromList(activeJob.preset_id, presetList);
            return;
          }
        } else {
          setReindexJob(null);
        }
        setActivePresetId(active.preset_id);
        selectPresetFromList(active.preset_id, presetList);
      } catch (e) {
        setInlineMessage(e instanceof Error ? e.message : "Operation failed");
      }
    }
    load();
    // selectPresetFromList receives the freshly loaded presetList here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
        selectPresetFromList(active.preset_id, presetList);
      } catch (e) {
        setInlineMessage(e instanceof Error ? e.message : "Operation failed");
      }
    }

    void refreshAfterJob();
    // selectPresetFromList receives the freshly loaded presetList here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasActiveEmbeddingReindexJob, modelName, reindexJob]);

  function setField(key: keyof ModelConfig, value: string) {
    if (pendingEmbeddingAction) {
      setPendingSwitchPreview(null);
      setPendingEmbeddingAction(null);
    }
    if (key === "api_key") {
      invalidateApiKeyRevealRequest();
      if (apiKeyVisible) {
        setApiKeyPlain(value);
      }
    }
    if (key === "endpoint" || key === "api_key" || key === "protocol") {
      clearModelOptions();
    }
    setSettings((current) => ({ ...current, [key]: value }));
  }

  async function toggleApiKeyVisibility() {
    if (!selectedPresetId || !selectedPreset) {
      return;
    }
    if (apiKeyVisible) {
      invalidateApiKeyReveal();
      return;
    }
    if (settings.api_key !== selectedPreset.config.api_key) {
      invalidateApiKeyRevealRequest();
      setApiKeyPlain(settings.api_key ?? "");
      setApiKeyVisible(true);
      return;
    }
    const requestSeq = apiKeyRequestSeqRef.current + 1;
    apiKeyRequestSeqRef.current = requestSeq;
    try {
      const plain = await fetchPresetApiKey(modelName, selectedPresetId);
      if (apiKeyRequestSeqRef.current !== requestSeq) {
        return;
      }
      setApiKeyPlain(plain);
      setApiKeyVisible(true);
    } catch (e) {
      setInlineMessage(e instanceof Error ? e.message : "Operation failed");
    }
  }

  async function handleFetchModels() {
    if (!selectedPresetId || controlsDisabled || isFetchingModels) {
      return;
    }
    const requestSeq = modelListRequestSeqRef.current + 1;
    modelListRequestSeqRef.current = requestSeq;
    setIsFetchingModels(true);
    setModelListMessage("");
    try {
      const result = await fetchAvailableModels(
        modelName,
        selectedPresetId,
        toPresetConfig(settings)
      );
      if (modelListRequestSeqRef.current !== requestSeq) {
        return;
      }
      setModelOptions(result.models);
      setModelListMessage(
        result.models.length > 0
          ? `${result.models.length} model${result.models.length === 1 ? "" : "s"} available.`
          : "No models returned."
      );
    } catch (e) {
      if (modelListRequestSeqRef.current !== requestSeq) {
        return;
      }
      setModelOptions([]);
      setModelListMessage(e instanceof Error ? e.message : "Operation failed");
    } finally {
      if (modelListRequestSeqRef.current === requestSeq) {
        setIsFetchingModels(false);
      }
    }
  }

  function markPresetActiveFromList(
    presetId: string,
    presetList: PresetResponse[] = presets
  ) {
    setActivePresetId(presetId);
    selectPresetFromList(presetId, presetList);
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
    pendingAction: {
      presetId: string;
      config?: PresetConfig;
      label: "save" | "activate";
    } | null = null
  ) {
    setReindexJob(null);
    setPendingEmbeddingAction(pendingAction);
    setPendingSwitchPreview(preview);
  }

  function handleEmbeddingSwitchResult(
    result: EmbeddingSwitchResult,
    presetList: PresetResponse[] = presets
  ) {
    setInlineMessage("");
    setPendingSwitchPreview(null);
    setPendingEmbeddingAction(null);
    markPresetActiveFromList(result.preset_id, presetList);
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

  async function saveSelectedPresetConfig(
    presetId: string,
    config: PresetConfig
  ) {
    const updatedPreset = await updatePreset(modelName, presetId, config);
    const presetList = replacePresetInList(updatedPreset);
    selectPresetFromList(updatedPreset.id, presetList);
    return presetList;
  }

  async function activateRegularPreset(
    presetId: string,
    presetList: PresetResponse[] = presets
  ) {
    await switchActivePreset(modelName, presetId);
    markPresetActiveFromList(presetId, presetList);
    setInlineMessage("");
  }

  async function handleConfirmEmbeddingSwitch() {
    if (!pendingSwitchPreview || isSwitching || isSaving) {
      return;
    }
    setInlineMessage("");
    try {
      setIsSwitching(true);
      const nextPresetId = pendingSwitchPreview.preset_id;
      let presetList = presets;
      if (pendingEmbeddingAction?.config) {
        setIsSaving(true);
        presetList = await saveSelectedPresetConfig(
          pendingEmbeddingAction.presetId,
          pendingEmbeddingAction.config
        );
      }
      const result = await switchEmbeddingPreset(nextPresetId, true);
      handleEmbeddingSwitchResult(result, presetList);
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
    setPendingEmbeddingAction(null);
  }

  function handleSelectPreset(presetId: string) {
    if (controlsDisabled) {
      return;
    }
    selectPresetFromList(presetId);
  }

  async function handleActivateSelectedPreset() {
    if (!selectedPresetId || selectedIsActive || controlsDisabled) {
      return;
    }
    const selectedConfig = toPresetConfig(settings);
    setPendingSwitchPreview(null);
    setPendingEmbeddingAction(null);
    setReindexJob(null);
    setInlineMessage(
      modelName === "embedding"
        ? "Switching embedding preset..."
        : "Switching preset..."
    );
    setIsSwitching(true);
    try {
      let presetList = presets;
      if (modelName === "embedding") {
        if (selectedIsDirty) {
          const preview = await previewEmbeddingPresetConfigSwitch(
            selectedPresetId,
            selectedConfig
          );
          if (!preview.same_dimension) {
            setInlineMessage("");
            showEmbeddingSwitchPreview(preview, {
              presetId: selectedPresetId,
              config: selectedConfig,
              label: "activate",
            });
            return;
          }
          presetList = await saveSelectedPresetConfig(
            selectedPresetId,
            selectedConfig
          );
        } else {
          const preview = await previewEmbeddingPresetSwitch(selectedPresetId);
          if (!preview.same_dimension) {
            setInlineMessage("");
            showEmbeddingSwitchPreview(preview, {
              presetId: selectedPresetId,
              label: "activate",
            });
            return;
          }
        }
        const result = await switchEmbeddingPreset(selectedPresetId, false);
        handleEmbeddingSwitchResult(result, presetList);
        return;
      }

      if (selectedIsDirty) {
        presetList = await saveSelectedPresetConfig(
          selectedPresetId,
          selectedConfig
        );
      }
      await activateRegularPreset(selectedPresetId, presetList);
    } catch (e) {
      setInlineMessage(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setIsSwitching(false);
    }
  }

  async function handleCreatePreset() {
    if (controlsDisabled) {
      return;
    }
    try {
      const newPreset = await createPreset(
        modelName,
        toPresetConfig(EMPTY_MODEL_CONFIG)
      );
      const presetList = await listPresets(modelName);
      setPresets(presetList);
      selectPresetFromList(newPreset.id, presetList);
      setInlineMessage("");
    } catch (e) {
      setInlineMessage(e instanceof Error ? e.message : "Operation failed");
    }
  }

  async function handleRenamePreset(presetId: string, newName: string) {
    if (controlsDisabled) {
      return;
    }
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
    if (controlsDisabled) {
      return;
    }
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
      const selectedStillExists = selectedPresetId
        ? updatedList.some((preset) => preset.id === selectedPresetId)
        : false;
      if (
        presetId === selectedPresetId ||
        presetId === activePresetId ||
        !selectedStillExists
      ) {
        selectPresetFromList(active.preset_id, updatedList);
      }
      setInlineMessage("");
    } catch (e) {
      setInlineMessage(e instanceof Error ? e.message : "Operation failed");
    }
  }

  // Save writes the selected ACTIVE preset. Status refresh is the parent's concern —
  // `status` arrives as a prop with no callback path on this interface.
  async function handleSave() {
    if (!selectedPresetId || !selectedIsActive || !selectedIsDirty) {
      return;
    }
    if (modelName === "embedding" && hasActiveEmbeddingReindexJob) {
      setInlineMessage(
        "Cannot save embedding presets while an embedding reindex job is running."
      );
      return;
    }
    setPendingSwitchPreview(null);
    setPendingEmbeddingAction(null);
    setReindexJob(null);
    setInlineMessage(
      modelName === "embedding"
        ? "Saving and checking embedding preset..."
        : ""
    );
    setIsSaving(true);
    try {
      const saveConfig = toPresetConfig(settings);
      if (modelName === "embedding") {
        const preview = await previewEmbeddingPresetConfigSwitch(
          selectedPresetId,
          saveConfig
        );
        if (!preview.same_dimension) {
          setInlineMessage("");
          showEmbeddingSwitchPreview(preview, {
            presetId: selectedPresetId,
            config: saveConfig,
            label: "save",
          });
          return;
        }
        await saveSelectedPresetConfig(selectedPresetId, saveConfig);
        setInlineMessage("Saved.");
        return;
      }
      await saveSelectedPresetConfig(selectedPresetId, saveConfig);
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
  const selectedPreset = selectedPresetId
    ? presets.find((preset) => preset.id === selectedPresetId)
    : null;
  const selectedIsActive = Boolean(
    selectedPresetId && selectedPresetId === activePresetId
  );
  const selectedIsDirty = selectedPreset
    ? !configsEqual(settings, selectedPreset.config)
    : false;
  const pendingEmbeddingActionLabel = pendingEmbeddingAction?.label ?? "activate";
  const pendingEmbeddingActionVerb =
    pendingEmbeddingActionLabel === "save" ? "Saving" : "Activating";
  const pendingEmbeddingConfirmLabel =
    pendingEmbeddingActionLabel === "save" ? "Confirm save" : "Confirm activate";

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
            {pendingEmbeddingActionVerb}{" "}
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
              {pendingEmbeddingConfirmLabel}
            </Button>
          </div>
        </div>
      ) : null}

      {presets.map((preset) => {
        const isActive = preset.id === activePresetId;
        const isSelected = preset.id === selectedPresetId;
        return (
          <PresetCard
            key={preset.id}
            preset={preset}
            isActive={isActive}
            isSelected={isSelected}
            selectionDisabled={controlsDisabled}
            status={modelName === "asr" ? undefined : status}
            fields={fields}
            values={isSelected ? settings : toModelConfig(preset.config)}
            onFieldChange={setField}
            modelOptions={isSelected ? modelOptions : []}
            modelListMessage={isSelected ? modelListMessage : ""}
            isFetchingModels={isSelected && isFetchingModels}
            onFetchModels={isSelected ? handleFetchModels : undefined}
            fieldsDisabled={controlsDisabled}
            actionLabel={isActive ? "Save" : "Activate"}
            actionDisabled={
              isActive
                ? !selectedIsDirty ||
                  controlsDisabled
                : controlsDisabled
            }
            onAction={() => {
              if (isActive) {
                void handleSave();
              } else {
                void handleActivateSelectedPreset();
              }
            }}
            onSelect={() => handleSelectPreset(preset.id)}
            onRename={() => {
              setRenamingPreset({ presetId: preset.id });
              setRenameValue(preset.name);
            }}
            onDelete={() => handleDeletePreset(preset.id)}
            canDelete={
              presets.length > 1 &&
              !controlsDisabled
            }
            menuDisabled={controlsDisabled}
            apiKeyVisible={isSelected && apiKeyVisible}
            apiKeyPlain={isSelected ? apiKeyPlain : null}
            canRevealApiKey={isSelected}
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
            {isSelected && asrExtras
              ? asrExtras({
                protocol: settings.protocol,
                onProtocolChange: (v) => setField("protocol", v),
                endpoint: settings.endpoint,
                disabled: controlsDisabled,
              })
              : undefined}
          </PresetCard>
        );
      })}

      <div
        onClick={controlsDisabled ? undefined : handleCreatePreset}
        className={`rounded-xl border border-dashed border-border p-4 text-center text-sm text-muted-foreground transition-colors ${
          controlsDisabled
            ? "cursor-not-allowed opacity-60"
            : "cursor-pointer hover:border-primary/50"
        }`}
      >
        + New preset
      </div>
    </div>
  );
}
