"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2, Circle } from "lucide-react";

import {
  getServiceStatus,
  listDocuments,
  type ServiceStatus,
} from "@/lib/api";

interface OnboardingChecklistProps {
  backendHealthy: boolean;
  hasVideos: boolean;
}

interface StepState {
  label: string;
  done: boolean;
  hint: React.ReactNode;
}

export function OnboardingChecklist({
  backendHealthy,
  hasVideos,
}: OnboardingChecklistProps) {
  const [status, setStatus] = useState<Record<string, ServiceStatus>>({});
  const [hasIndexed, setHasIndexed] = useState(false);

  useEffect(() => {
    getServiceStatus().then(setStatus).catch(() => {});
    listDocuments()
      .then((docs) => setHasIndexed(docs.some((doc) => doc.is_indexed)))
      .catch(() => {});
  }, []);

  const modelsReady =
    ["configured", "ok"].includes(status.chat?.status ?? "") &&
    ["configured", "ok"].includes(status.embedding?.status ?? "");

  const steps: StepState[] = [
    {
      label: "Backend running",
      done: backendHealthy,
      hint: "Start it: cd backend && ./venv/bin/uvicorn main:app --reload",
    },
    {
      label: "Models configured",
      done: modelsReady,
      hint: (
        <Link className="underline" href="/settings">
          Configure chat & embedding in Settings
        </Link>
      ),
    },
    {
      label: "First video processed",
      done: hasVideos,
      hint: "Paste a Bilibili URL below and press Process",
    },
    {
      label: "First document indexed",
      done: hasIndexed,
      hint: (
        <Link className="underline" href="/knowledge">
          Index it in Knowledge Base, then ask in Chat
        </Link>
      ),
    },
  ];

  if (steps.every((step) => step.done)) {
    return null;
  }

  return (
    <section className="space-y-2 rounded-md border border-input p-4">
      <h2 className="text-sm font-semibold">Getting started</h2>
      <ul className="space-y-1">
        {steps.map((step) => (
          <li key={step.label} className="flex items-start gap-2 text-sm">
            {step.done ? (
              <CheckCircle2 className="mt-0.5 h-4 w-4 text-green-600" />
            ) : (
              <Circle className="mt-0.5 h-4 w-4 text-muted-foreground" />
            )}
            <span>
              {step.label}
              {!step.done ? (
                <span className="block text-xs text-muted-foreground">
                  {step.hint}
                </span>
              ) : null}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
