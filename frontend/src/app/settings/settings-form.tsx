"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  getModelSettings,
  getServiceStatus,
  updateModelSettings,
  type ModelConfig,
  type ModelsSettings,
  type ServiceStatus,
} from "@/lib/api";

const MODEL_NAMES = ["chat", "embedding", "asr"] as const;
type ModelName = (typeof MODEL_NAMES)[number];

const FIELDS: { key: keyof ModelConfig; label: string }[] = [
  { key: "provider", label: "Provider" },
  { key: "endpoint", label: "Endpoint" },
  { key: "api_key", label: "API Key" },
  { key: "model", label: "Model" },
];

export function SettingsForm() {
  const [settings, setSettings] = useState<ModelsSettings | null>(null);
  const [status, setStatus] = useState<Record<string, ServiceStatus>>({});
  const [message, setMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);

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
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-6 px-6 py-10">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-sm text-muted-foreground">
          <Link className="underline" href="/">
            ← Videos
          </Link>
        </p>
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
                <label key={key} className="block text-sm">
                  <span className="mb-1 block text-muted-foreground">
                    {label}
                  </span>
                  <input
                    className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                    value={settings[name][key] ?? ""}
                    onChange={(event) =>
                      setField(name, key, event.target.value)
                    }
                  />
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
    </main>
  );
}
