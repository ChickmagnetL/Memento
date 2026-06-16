"use client";

import { FormEvent, useEffect, useState } from "react";
import { Eye, EyeOff } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  getModelSettings,
  getServiceStatus,
  updateModelSettings,
  fetchApiKey,
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

export function SettingsForm() {
  const [settings, setSettings] = useState<ModelsSettings | null>(null);
  const [status, setStatus] = useState<Record<string, ServiceStatus>>({});
  const [message, setMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [visibleKeys, setVisibleKeys] = useState<Record<string, boolean>>({});
  const [plainKeys, setPlainKeys] = useState<Record<string, string | null>>({});

  useEffect(() => {
    getModelSettings().then(setSettings).catch(() => setMessage("Load failed"));
    getServiceStatus().then(setStatus).catch(() => {});
  }, []);

  function setField(name: ModelName, key: keyof ModelConfig, value: string) {
    setSettings((current) =>
      current
        ? { ...current, [name]: { ...current[name], [key]: value } }
        : current
    );
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
                </label>
              ))}
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
