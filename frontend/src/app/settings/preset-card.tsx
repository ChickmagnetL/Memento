"use client";

import { useEffect, useState, type ReactNode } from "react";
import { Eye, EyeOff, MoreHorizontal } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ModelConfig, PresetResponse, ServiceStatus } from "@/lib/api";

export interface PresetCardProps {
  preset: PresetResponse;
  isActive: boolean;
  isSelected: boolean;
  selectionDisabled?: boolean;
  status?: ServiceStatus;
  fields: { key: keyof ModelConfig; label: string }[];
  values: ModelConfig;
  onFieldChange: (key: keyof ModelConfig, value: string) => void;
  fieldsDisabled: boolean;
  actionLabel: "Save" | "Activate";
  actionDisabled: boolean;
  onAction: () => void;
  onSelect: () => void;
  onRename: () => void;
  onDelete: () => void;
  canDelete: boolean;
  menuDisabled: boolean;
  // api_key mask
  apiKeyVisible: boolean;
  apiKeyPlain: string | null;
  canRevealApiKey: boolean;
  onToggleApiKey: () => void;
  children?: ReactNode;
  // rename-related props — kept on the card so the rename UI is self-contained
  isRenaming: boolean;
  renameValue: string;
  onRenameChange: (value: string) => void;
  onRenameSubmit: () => void;
  onRenameCancel: () => void;
}

function statusDotColor(status: string): string {
  if (/^(ok|healthy|running|online|up|ready)$/i.test(status)) {
    return "bg-success";
  }
  if (/^(error|unhealthy|down|fail|failed|offline|unreachable)$/i.test(status)) {
    return "bg-destructive";
  }
  return "bg-muted-foreground";
}

export function PresetCard({
  preset,
  isActive,
  isSelected,
  selectionDisabled = false,
  status,
  fields,
  values,
  onFieldChange,
  fieldsDisabled,
  actionLabel,
  actionDisabled,
  onAction,
  onSelect,
  onRename,
  onDelete,
  canDelete,
  menuDisabled,
  apiKeyVisible,
  apiKeyPlain,
  canRevealApiKey,
  onToggleApiKey,
  children,
  isRenaming,
  renameValue,
  onRenameChange,
  onRenameSubmit,
  onRenameCancel,
}: PresetCardProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const isMenuOpen = menuOpen && !menuDisabled;

  // Close the ⋯ menu on click-outside. stopPropagation on the trigger keeps
  // the opening click from immediately closing it.
  useEffect(() => {
    if (!menuOpen) {
      return;
    }
    if (menuDisabled) {
      const timeoutId = window.setTimeout(() => setMenuOpen(false), 0);
      return () => window.clearTimeout(timeoutId);
    }
    function handleClickOutside() {
      setMenuOpen(false);
    }
    window.addEventListener("click", handleClickOutside);
    return () => window.removeEventListener("click", handleClickOutside);
  }, [menuDisabled, menuOpen]);

  function handleCardClick() {
    if (isSelected || isRenaming || isMenuOpen || selectionDisabled) {
      return;
    }
    onSelect();
  }

  return (
    <div
      onClick={handleCardClick}
      className={cn(
        "rounded-xl border bg-card p-4 text-card-foreground shadow transition-colors",
        isActive
          ? "border-primary ring-1 ring-primary/30"
          : isSelected
            ? "border-primary/60"
            : "border-border",
        !isSelected &&
          !isRenaming &&
          !selectionDisabled &&
          "cursor-pointer hover:border-primary/50",
        !isSelected && selectionDisabled && "cursor-not-allowed opacity-60",
      )}
    >
      {/* Top row: preset name + active marker + status + ⋯ menu */}
      <div className="flex items-center justify-between gap-3">
        {isRenaming ? (
          <div
            onClick={(event) => event.stopPropagation()}
            className="flex flex-1 items-center gap-2 rounded-md border border-input bg-muted/30 p-2"
          >
            <input
              type="text"
              className="h-8 flex-1 rounded-md border border-input bg-background px-2 text-sm"
              value={renameValue}
              onChange={(event) => onRenameChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  onRenameSubmit();
                } else if (event.key === "Escape") {
                  event.preventDefault();
                  onRenameCancel();
                }
              }}
              autoFocus
            />
            <Button type="button" size="sm" onClick={onRenameSubmit}>
              OK
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={onRenameCancel}
            >
              Cancel
            </Button>
          </div>
        ) : (
          <div className="flex min-w-0 items-center gap-2">
            <span
              className={cn(
                "truncate text-sm font-medium",
                isActive ? "text-primary" : "text-foreground",
              )}
            >
              {preset.name}
            </span>
            {isActive ? (
              <span className="shrink-0 text-xs text-primary">● Active</span>
            ) : (
              <span className="shrink-0 text-xs text-muted-foreground">○</span>
            )}
            {status ? (
              <span className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
                <span
                  className={cn(
                    "h-2 w-2 rounded-full",
                    statusDotColor(status.status),
                  )}
                />
                {status.status}
              </span>
            ) : null}
          </div>
        )}

        {/* ⋯ menu — hidden while renaming */}
        {!isRenaming ? (
          <div className="relative shrink-0">
            <button
              type="button"
              aria-label="Preset actions"
              disabled={menuDisabled}
              onClick={(event) => {
                event.stopPropagation();
                if (menuDisabled) {
                  return;
                }
                setMenuOpen((open) => !open);
              }}
              className="rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
            >
              <MoreHorizontal size={18} />
            </button>
            {isMenuOpen ? (
              <div
                onClick={(event) => event.stopPropagation()}
                className="absolute right-0 top-full z-30 mt-1 w-32 rounded-md border border-border bg-popover p-1 text-sm shadow-md"
              >
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    setMenuOpen(false);
                    onRename();
                  }}
                  className="block w-full rounded-sm px-2 py-1.5 text-left text-foreground hover:bg-accent"
                >
                  Rename
                </button>
                <button
                  type="button"
                  disabled={!canDelete}
                  onClick={(event) => {
                    event.stopPropagation();
                    setMenuOpen(false);
                    onDelete();
                  }}
                  className="block w-full rounded-sm px-2 py-1.5 text-left text-destructive hover:bg-accent disabled:pointer-events-none disabled:opacity-50"
                >
                  Delete
                </button>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      {/* Summary row: endpoint / model */}
      <div className="mt-2 grid gap-1 text-xs text-muted-foreground sm:grid-cols-2">
        <div className="min-w-0">
          <span className="block uppercase tracking-wide text-muted-foreground/70">
            Endpoint
          </span>
          <span className="block truncate">{values.endpoint || "Not set"}</span>
        </div>
        <div className="min-w-0">
          <span className="block uppercase tracking-wide text-muted-foreground/70">
            Model
          </span>
          <span className="block truncate">{values.model || "Not set"}</span>
        </div>
      </div>

      {/* Expanded fields — selected preset only */}
      {isSelected ? (
        <div className="mt-4 space-y-3">
          {fields.map(({ key, label }) => {
            const isApiKey = key === "api_key";
            const fieldValue =
              isApiKey && apiKeyVisible
                ? (apiKeyPlain ?? values.api_key ?? "")
                : (values[key] ?? "");
            return (
              <label key={key} className="relative block text-sm">
                <span className="mb-1 block text-muted-foreground">{label}</span>
                <div className="relative">
                  <input
                    type={isApiKey && !apiKeyVisible ? "password" : "text"}
                    className="h-9 w-full rounded-md border border-input bg-background px-3 pr-9 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                    value={fieldValue}
                    onChange={(event) => onFieldChange(key, event.target.value)}
                    disabled={fieldsDisabled}
                  />
                  {isApiKey && values.api_key && canRevealApiKey ? (
                    <button
                      type="button"
                      onClick={onToggleApiKey}
                      disabled={fieldsDisabled}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60"
                      aria-label={
                        apiKeyVisible ? "Hide API key" : "Show API key"
                      }
                    >
                      {apiKeyVisible ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  ) : null}
                </div>
              </label>
            );
          })}

          {children}

          <div className="flex justify-end">
            <Button
              type="button"
              size="sm"
              onClick={(event) => {
                event.stopPropagation();
                onAction();
              }}
              disabled={actionDisabled}
            >
              {actionLabel}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
