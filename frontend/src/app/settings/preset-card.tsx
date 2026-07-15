"use client";

import { useEffect, useState, type ReactNode } from "react";
import { ChevronDown, Eye, EyeOff, MoreHorizontal } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useLanguage } from "@/lib/i18n";
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
  modelOptions?: string[];
  modelListMessage?: string;
  isFetchingModels?: boolean;
  onFetchModels?: () => void;
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
  modelOptions = [],
  modelListMessage = "",
  isFetchingModels = false,
  onFetchModels,
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
  const { t } = useLanguage();
  const [menuOpen, setMenuOpen] = useState(false);
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);
  const isMenuOpen = menuOpen && !menuDisabled;
  const isModelDropdownOpen =
    modelDropdownOpen && !fieldsDisabled && modelOptions.length > 0;

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

  useEffect(() => {
    if (!modelDropdownOpen) {
      return;
    }
    if (fieldsDisabled || modelOptions.length === 0) {
      const timeoutId = window.setTimeout(
        () => setModelDropdownOpen(false),
        0
      );
      return () => window.clearTimeout(timeoutId);
    }
    function handleClickOutside() {
      setModelDropdownOpen(false);
    }
    window.addEventListener("click", handleClickOutside);
    return () => window.removeEventListener("click", handleClickOutside);
  }, [fieldsDisabled, modelDropdownOpen, modelOptions.length]);

  function handleCardClick() {
    if (
      isSelected ||
      isRenaming ||
      isMenuOpen ||
      isModelDropdownOpen ||
      selectionDisabled
    ) {
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
              {t("Cancel")}
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
              <span className="shrink-0 text-xs text-primary">● {t("Active")}</span>
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
              aria-label={t("Preset actions")}
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
                  {t("Rename")}
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
                  {t("Delete")}
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
            {t("Endpoint")}
          </span>
          <span className="block truncate">{values.endpoint || t("Not set")}</span>
        </div>
        <div className="min-w-0">
          <span className="block uppercase tracking-wide text-muted-foreground/70">
            {t("Model")}
          </span>
          <span className="block truncate">{values.model || t("Not set")}</span>
        </div>
      </div>

      {/* Expanded fields — selected preset only */}
      {isSelected ? (
        <div className="mt-4 space-y-3">
          {fields.map(({ key, label }) => {
            const isApiKey = key === "api_key";
            const isModel = key === "model";
            const inputPadding = isApiKey ? "pr-9" : "";
            const fieldValue =
              isApiKey && apiKeyVisible
                ? (apiKeyPlain ?? values.api_key ?? "")
                : (values[key] ?? "");
            if (isModel) {
              const hasModelOptions = modelOptions.length > 0;
              const selectOptions =
                fieldValue && !modelOptions.includes(fieldValue)
                  ? [fieldValue, ...modelOptions]
                  : modelOptions;
              return (
                <div key={key} className="relative block text-sm">
                  <span className="mb-1 block text-muted-foreground">
                    {label}
                  </span>
                  <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                    {hasModelOptions ? (
                      <div
                        className="relative"
                        onClick={(event) => event.stopPropagation()}
                      >
                        <input
                          type="text"
                          aria-label={label}
                          className="h-9 w-full rounded-md border border-input bg-background px-3 pr-9 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                          value={fieldValue}
                          onChange={(event) =>
                            onFieldChange(key, event.target.value)
                          }
                          disabled={fieldsDisabled}
                        />
                        <button
                          type="button"
                          aria-label={t("Show model options")}
                          aria-haspopup="listbox"
                          aria-expanded={isModelDropdownOpen}
                          disabled={fieldsDisabled}
                          onClick={(event) => {
                            event.stopPropagation();
                            if (fieldsDisabled) {
                              return;
                            }
                            setModelDropdownOpen((open) => !open);
                          }}
                          onKeyDown={(event) => {
                            if (event.key === "Escape") {
                              event.preventDefault();
                              event.stopPropagation();
                              setModelDropdownOpen(false);
                            }
                          }}
                          className="absolute right-1 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          <ChevronDown
                            size={16}
                            className={cn(
                              "transition-transform",
                              isModelDropdownOpen && "rotate-180"
                            )}
                            aria-hidden="true"
                          />
                        </button>
                        {isModelDropdownOpen ? (
                          <div
                            role="listbox"
                            onClick={(event) => event.stopPropagation()}
                            className="absolute left-0 top-full z-30 mt-1 max-h-56 w-full overflow-auto rounded-md border border-border bg-popover p-1 text-sm shadow-md"
                          >
                            {selectOptions.map((option) => (
                              <button
                                key={option}
                                type="button"
                                role="option"
                                aria-selected={option === fieldValue}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  onFieldChange(key, option);
                                  setModelDropdownOpen(false);
                                }}
                                onKeyDown={(event) => {
                                  if (event.key === "Escape") {
                                    event.preventDefault();
                                    event.stopPropagation();
                                    setModelDropdownOpen(false);
                                  }
                                }}
                                className={cn(
                                  "block w-full rounded-sm px-2 py-1.5 text-left text-foreground hover:bg-accent",
                                  option === fieldValue && "bg-accent"
                                )}
                              >
                                {option}
                              </button>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    ) : (
                      <input
                        type="text"
                        aria-label={label}
                        className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                        value={fieldValue}
                        onChange={(event) =>
                          onFieldChange(key, event.target.value)
                        }
                        disabled={fieldsDisabled}
                      />
                    )}
                    {onFetchModels ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={(event) => {
                          event.stopPropagation();
                          onFetchModels();
                        }}
                        disabled={fieldsDisabled || isFetchingModels}
                        className="h-9 w-full px-3 text-xs sm:w-auto"
                      >
                        {isFetchingModels
                          ? t("Getting Models...")
                          : t("Get Model List")}
                      </Button>
                    ) : null}
                  </div>
                  {modelListMessage ? (
                    <span className="mt-1 block text-xs text-muted-foreground">
                      {modelListMessage}
                    </span>
                  ) : null}
                </div>
              );
            }
            return (
              <label key={key} className="relative block text-sm">
                <span className="mb-1 block text-muted-foreground">{label}</span>
                <div className="relative">
                  <input
                    type={isApiKey && !apiKeyVisible ? "password" : "text"}
                    className={cn(
                      "h-9 w-full rounded-md border border-input bg-background px-3 text-sm disabled:cursor-not-allowed disabled:opacity-60",
                      inputPadding
                    )}
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
                        apiKeyVisible ? t("Hide API key") : t("Show API key")
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
              {t(actionLabel)}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
