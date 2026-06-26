"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  deployAsr,
  getAsrDeployProgress,
  getAsrDeployStatus,
  getServiceStatus,
  type AsrDeployProgress,
  type AsrDeployStatus,
  type ModelConfig,
  type PresetModelName,
  type ServiceStatus,
} from "@/lib/api";

import { LocalAsrModal } from "./local-asr-modal";
import { ModelPanel } from "./model-panel";

const TABS: { name: PresetModelName; label: string }[] = [
  { name: "chat", label: "Chat" },
  { name: "embedding", label: "Embedding" },
  { name: "asr", label: "ASR" },
];

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

// SettingsForm owns the ASR-specific JSX but the protocol select's value/onChange
// belong to the ASR preset's config, which lives in ModelPanel's settings state.
// ModelPanel injects protocol/endpoint via this render-prop ctx.
interface AsrExtrasCtx {
  protocol: ModelConfig["protocol"];
  onProtocolChange: (value: string) => void;
  endpoint: string | null;
}

export function SettingsForm() {
  const [activeTab, setActiveTab] = useState<PresetModelName>("chat");
  const [status, setStatus] = useState<Record<string, ServiceStatus>>({});
  const [message, setMessage] = useState("");
  const [asrDeployStatus, setAsrDeployStatus] =
    useState<AsrDeployStatus | null>(null);
  const [asrDeployProgress, setAsrDeployProgress] =
    useState<AsrDeployProgress | null>(null);
  const [isDeployingAsr, setIsDeployingAsr] = useState(false);
  const [showLocalAsrModal, setShowLocalAsrModal] = useState(false);

  useEffect(() => {
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

  const renderAsrExtras = (ctx: AsrExtrasCtx) => (
    <div className="space-y-3">
      <label className="block text-sm">
        <span className="mb-1 block text-muted-foreground">Protocol</span>
        <select
          className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
          value={ctx.protocol ?? "transcriptions"}
          onChange={(e) => ctx.onProtocolChange(e.target.value)}
        >
          <option value="transcriptions">transcriptions</option>
          <option value="chat_audio">chat_audio</option>
        </select>
        <p className="mt-1 text-xs text-muted-foreground">
          Requests {asrRequestUrl(ctx.endpoint, ctx.protocol)}
        </p>
      </label>
      {asrDeployStatus && asrDeployStatus.venv_exists ? (
        <div className="flex items-center justify-between gap-3 rounded-md border border-input bg-muted/30 p-3">
          <span className="text-sm text-muted-foreground">Local ASR installed</span>
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
        <div className="flex items-center justify-between gap-3 rounded-md border border-input bg-muted/30 p-3">
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
          {asrDeployProgress.error ? `: ${asrDeployProgress.error}` : ""}
        </p>
      ) : null}
    </div>
  );

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-6 py-10">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold">Settings</h1>
      </header>

      {message ? <p className="text-sm">{message}</p> : null}

      <nav className="flex gap-2 border-b border-border">
        {TABS.map((tab) => (
          <button
            key={tab.name}
            type="button"
            onClick={() => setActiveTab(tab.name)}
            className={
              activeTab === tab.name
                ? "rounded-t-md bg-primary/10 px-4 py-2 text-sm font-medium text-primary"
                : "cursor-pointer px-4 py-2 text-sm text-muted-foreground hover:text-foreground"
            }
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <ModelPanel
        key={activeTab}
        modelName={activeTab}
        fields={FIELDS}
        status={status[activeTab]}
        asrExtras={activeTab === "asr" ? renderAsrExtras : undefined}
      />

      <LocalAsrModal
        open={showLocalAsrModal}
        onClose={() => setShowLocalAsrModal(false)}
        onDeploy={handleDeployAsr}
        isDeploying={isDeployingAsr}
      />
    </div>
  );
}
