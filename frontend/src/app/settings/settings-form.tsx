"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  getServiceStatus,
  type LocalModelService,
  type ModelConfig,
  type PresetModelName,
  type ServiceStatus,
} from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

import { LocalModelModal } from "./local-model-modal";
import { ModelPanel } from "./model-panel";

type SettingsTab = "general" | PresetModelName;

const TABS: { name: SettingsTab; label: string }[] = [
  { name: "general", label: "General" },
  { name: "chat", label: "Chat" },
  { name: "embedding", label: "Embedding" },
  { name: "asr", label: "ASR" },
];

const LOCAL_MODEL_SERVICES: LocalModelService[] = ["asr", "embedding"];

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
  disabled: boolean;
}

export function SettingsForm() {
  const { language, setLanguage, t } = useLanguage();
  const [activeTab, setActiveTab] = useState<SettingsTab>("general");
  const [status, setStatus] = useState<Record<string, ServiceStatus>>({});
  const [message, setMessage] = useState("");
  const [localModelService, setLocalModelService] =
    useState<LocalModelService | null>(null);
  const [panelRevision, setPanelRevision] = useState(0);

  const refreshStatus = useCallback(async () => {
    try {
      setStatus(await getServiceStatus());
    } catch (e) {
      setMessage(e instanceof Error ? e.message : t("Operation failed"));
    }
  }, [t]);

  useEffect(() => {
    // The refresh waits for the status request before updating state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshStatus();
  }, [refreshStatus]);

  const localModelsCard = (
    service: LocalModelService,
    disabled: boolean,
  ) => (
    <div className="flex items-center justify-between gap-3 rounded-md border border-input bg-muted/30 p-3">
      <div>
        <p className="text-sm text-muted-foreground">
          {service === "asr"
            ? t("Install and manage local ASR models")
            : t("Install and manage local Embedding models")}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          {t("CUDA, MPS, or CPU is selected automatically.")}
        </p>
      </div>
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={disabled}
        onClick={() => setLocalModelService(service)}
      >
        {service === "asr"
          ? t("Local ASR Models")
          : t("Local Embedding Models")}
      </Button>
    </div>
  );

  const renderAsrExtras = (ctx: AsrExtrasCtx) => (
    <label className="block text-sm">
      <span className="mb-1 block text-muted-foreground">{t("Protocol")}</span>
      <select
        className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
        value={ctx.protocol ?? "transcriptions"}
        onChange={(e) => ctx.onProtocolChange(e.target.value)}
        disabled={ctx.disabled}
      >
        <option value="transcriptions">transcriptions</option>
        <option value="chat_audio">chat_audio</option>
      </select>
      <p className="mt-1 text-xs text-muted-foreground">
        {t("Requests {url}", { url: asrRequestUrl(ctx.endpoint, ctx.protocol) })}
      </p>
    </label>
  );

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-6 py-10">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold">{t("Settings")}</h1>
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
            {t(tab.label)}
          </button>
        ))}
      </nav>

      {activeTab === "general" ? (
        <section className="flex items-center justify-between gap-4 rounded-md border border-input p-4">
          <div>
            <h2 className="text-sm font-medium">{t("Language")}</h2>
            <p className="text-xs text-muted-foreground">
              {t("Choose the language used by the application.")}
            </p>
          </div>
          <select
            aria-label={t("Language")}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
            value={language}
            onChange={(event) => setLanguage(event.target.value as "en" | "zh-CN")}
          >
            <option value="zh-CN">简体中文</option>
            <option value="en">English</option>
          </select>
        </section>
      ) : (
        <ModelPanel
          key={`${activeTab}-${panelRevision}`}
          modelName={activeTab}
          fields={FIELDS.map((field) => ({ ...field, label: t(field.label) }))}
          status={status[activeTab]}
          asrExtras={activeTab === "asr" ? renderAsrExtras : undefined}
          onStatusRefresh={refreshStatus}
        />
      )}

      {activeTab === "asr" || activeTab === "embedding"
        ? localModelsCard(activeTab, false)
        : null}

      {LOCAL_MODEL_SERVICES.map((service) => (
        <LocalModelModal
          key={service}
          service={service}
          open={localModelService === service}
          onClose={() => setLocalModelService(null)}
          onConfigured={() => {
            setPanelRevision((current) => current + 1);
            void refreshStatus();
          }}
        />
      ))}
    </div>
  );
}
