"use client";

import { Brain, Check, Pencil, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useLanguage } from "@/lib/i18n";

interface MemoryProposalBubbleProps {
  content: string;
  onAccept: (content: string) => void;
  onReject: () => void;
}

export function MemoryProposalBubble({
  content,
  onAccept,
  onReject,
}: MemoryProposalBubbleProps) {
  const { t } = useLanguage();
  // Resettable per-mount: parent remounts via key when a new proposal arrives.
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(content);

  if (!editing) {
    return (
      <div className="mr-auto flex w-full max-w-[85%] flex-col gap-3 rounded-md border border-primary/40 bg-muted px-3 py-2 text-sm">
        <div className="flex items-center gap-1.5 text-xs font-medium text-primary">
          <Brain className="h-3.5 w-3.5" />
          {t("Memory proposal")}
        </div>
        <div className="whitespace-pre-wrap">{content}</div>
        <div className="flex items-center justify-end gap-2">
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={onReject}
          >
            <X className="h-4 w-4" />
            {t("Reject")}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setEditing(true)}
          >
            <Pencil className="h-4 w-4" />
            {t("Edit")}
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={() => onAccept(content)}
          >
            <Check className="h-4 w-4" />
            {t("Accept")}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mr-auto flex w-full max-w-[85%] flex-col gap-3 rounded-md border border-primary/40 bg-muted px-3 py-2 text-sm">
      <div className="flex items-center gap-1.5 text-xs font-medium text-primary">
        <Brain className="h-3.5 w-3.5" />
        {t("Memory proposal")}
      </div>
      <textarea
        className="w-full min-h-[100px] rounded-md border border-input bg-background px-3 py-2 text-sm resize-y"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
      />
      <div className="flex items-center justify-end gap-2">
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => {
            setDraft(content);
            setEditing(false);
          }}
        >
          {t("Cancel")}
        </Button>
        <Button
          type="button"
          size="sm"
          onClick={() => onAccept(draft.trim() || content)}
          disabled={!draft.trim()}
        >
          <Check className="h-4 w-4" />
          {t("Confirm")}
        </Button>
      </div>
    </div>
  );
}
