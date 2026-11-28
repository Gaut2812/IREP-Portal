"use client";

/** The inside of one trainer / parent / college thread message (C2.10 for threads):
 *  the text (or "This message was deleted"), "edited", sent / seen ticks, and for the sender Edit (within the
 *  window) and Delete for everyone (asks first, ConfirmDelete). The page keeps its own bubble styling. */
import React, { useState } from "react";
import { Check, CheckCheck, Pencil, Trash2 } from "lucide-react";
import { ConfirmDelete } from "@/components/ui";
import { ApiError, fetchApi } from "@/lib/api";
import { useLanguage } from "@/lib/LanguageContext";

export interface ThreadMsg {
  id: string; is_mine: boolean; text: string; original_text?: string; read?: boolean; time?: string; date?: string;
  deleted?: boolean; edited?: boolean; can_edit?: boolean; can_delete?: boolean;
}

export function ThreadMessageBody({ m, text, meta, onChanged }: {
  m: ThreadMsg;
  text?: string;                 // what to show (a page may toggle translated / original); defaults to m.text
  meta?: React.ReactNode;        // the page's own time or date
  onChanged: () => void | Promise<void>;
}) {
  const { t } = useLanguage();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState("");
  const muted = m.is_mine ? "text-white/70" : "text-subtle";

  if (m.deleted) {
    return (
      <div data-testid="dm-deleted">
        <p className={`italic ${muted}`}>{t("discussions.deleted")}</p>
        {meta && <div className={`text-caption text-right ${muted}`}>{meta}</div>}
      </div>
    );
  }

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!draft.trim()) return;
    setError("");
    try {
      await fetchApi(`/direct-messages/${m.id}`, { method: "PATCH", body: JSON.stringify({ text: draft.trim() }) });
      setEditing(false);
      await onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("thread_msg.edit_failed"));
    }
  };

  return (
    <div className="space-y-1">
      {editing ? (
        <form onSubmit={save} className="flex flex-col gap-1.5" data-testid="dm-edit-form">
          <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={2} maxLength={4000} aria-label={t("discussions.edit")} autoFocus
            data-testid="dm-edit-input" className="w-full px-2 py-1 rounded-tile text-xs text-ink bg-white border border-line" />
          <div className="flex justify-end gap-1.5">
            <button type="button" onClick={() => setEditing(false)} className="px-2 py-1 rounded-tile text-caption font-semibold bg-white/20">{t("discussions.cancel_edit")}</button>
            <button type="submit" data-testid="dm-edit-save" className="px-2 py-1 rounded-tile text-caption font-semibold bg-white text-brand">{t("discussions.edit")}</button>
          </div>
          {error && <p className="text-caption" role="alert">{error}</p>}
        </form>
      ) : (
        <p className="leading-relaxed whitespace-pre-wrap" data-testid="dm-text">{text ?? m.text}</p>
      )}
      <div className={`flex items-center justify-end gap-1.5 text-caption ${muted}`}>
        {m.edited && <span data-testid="dm-edited">{t("discussions.edited")}</span>}
        {meta}
        {m.is_mine && (m.read
          ? <CheckCheck className="w-3.5 h-3.5" aria-label={t("discussions.seen")} data-testid="dm-seen" />
          : <Check className="w-3.5 h-3.5" aria-label={t("discussions.sent")} data-testid="dm-sent" />)}
        {m.can_edit && !editing && (
          <button type="button" onClick={() => { setDraft(m.original_text || m.text); setEditing(true); }} aria-label={t("discussions.edit")} title={t("discussions.edit")}
            data-testid="dm-edit" className="p-0.5 rounded hover:bg-white/20"><Pencil className="w-3 h-3" /></button>
        )}
        {m.can_delete && !editing && (
          <button type="button" onClick={() => setAsking(true)} aria-label={t("discussions.delete")} title={t("discussions.delete")}
            data-testid="dm-delete" className="p-0.5 rounded hover:bg-white/20"><Trash2 className="w-3 h-3" /></button>
        )}
      </div>
      {asking && (
        <ConfirmDelete itemName={(m.text || "").slice(0, 60)} note={t("thread_msg.delete_note")} onClose={() => setAsking(false)}
          onConfirm={async () => { await fetchApi(`/direct-messages/${m.id}`, { method: "DELETE" }); await onChanged(); }} />
      )}
    </div>
  );
}
