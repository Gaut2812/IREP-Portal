"use client";

/** The one delete confirmation used on every screen: names the item, says it cannot be undone, Cancel has the
 *  focus, Esc closes. Shown only after the Delete button is pressed. With `typeToConfirm`, the user must type
 *  the name first (colleges, MoUs). The parent does the request in `onConfirm`; a thrown ApiError shows here. */
import React, { useEffect, useRef, useState } from "react";
import { Trash2, AlertTriangle } from "lucide-react";
import { ApiError } from "@/lib/api";
import { useLanguage } from "@/lib/LanguageContext";
import { buttonClass } from "./Controls";
import { cn } from "@/lib/cn";

export function ConfirmDelete({ itemName, note, typeToConfirm, onConfirm, onClose }: {
  itemName: string;
  note?: string;
  typeToConfirm?: string;
  onConfirm: () => Promise<void>;
  onClose: () => void;
}) {
  const { t } = useLanguage();
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    cancelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !busy) onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  const blocked = !!typeToConfirm && typed.trim() !== typeToConfirm;
  const confirm = async () => {
    if (blocked || busy) return;
    setBusy(true);
    setError("");
    try {
      await onConfirm();
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("delete.failed"));
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4" role="alertdialog" aria-modal="true"
      aria-labelledby="confirm-delete-title" aria-describedby="confirm-delete-body" data-testid="confirm-delete">
      <button type="button" className="absolute inset-0 bg-ink/50" aria-label={t("delete.cancel")} onClick={() => !busy && onClose()} tabIndex={-1} />
      <div className="relative w-full max-w-md bg-surface rounded-card border border-line shadow-pop p-5 space-y-4">
        <div className="flex items-start gap-3">
          <span className="w-10 h-10 rounded-full bg-danger-soft text-danger flex items-center justify-center flex-shrink-0"><AlertTriangle className="w-5 h-5" /></span>
          <div className="min-w-0 space-y-1">
            <h2 id="confirm-delete-title" className="text-heading font-semibold text-ink">{t("delete.title")}</h2>
            <p id="confirm-delete-body" className="text-body text-ink-soft">
              <span className="font-semibold text-ink break-words" data-testid="confirm-delete-name">“{itemName}”</span> {t("delete.permanent")}
            </p>
            {note && <p className="text-label text-muted">{note}</p>}
          </div>
        </div>
        {typeToConfirm && (
          <label className="block text-label text-ink-soft">
            {t("delete.type_to_confirm")} <span className="font-semibold text-ink">{typeToConfirm}</span>
            <input value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" data-testid="confirm-delete-input"
              className="mt-1 w-full h-9 px-3 bg-surface border border-line rounded-tile text-body text-ink focus:outline-none focus:border-danger" />
          </label>
        )}
        {error && <p className="text-label text-danger" role="alert" data-testid="confirm-delete-error">{error}</p>}
        <div className="flex justify-end gap-2">
          <button ref={cancelRef} type="button" onClick={onClose} disabled={busy} className={buttonClass("secondary", "md")} data-testid="confirm-delete-cancel">
            {t("delete.cancel")}
          </button>
          <button type="button" onClick={confirm} disabled={blocked || busy} className={cn(buttonClass("danger", "md"), "disabled:opacity-50")} data-testid="confirm-delete-ok">
            <Trash2 className="w-4 h-4" /> {busy ? t("delete.deleting") : t("delete.confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}

/** Small trash button that opens the confirmation. */
export function DeleteButton({ onClick, label, className, testId = "delete-button" }: {
  onClick: () => void; label?: string; className?: string; testId?: string;
}) {
  const { t } = useLanguage();
  return (
    <button type="button" onClick={onClick} data-testid={testId} aria-label={label || t("delete.button")} title={label || t("delete.button")}
      className={cn("inline-flex items-center gap-1 h-8 px-2.5 rounded-tile border border-danger-line text-danger text-label font-medium hover:bg-danger-soft", className)}>
      <Trash2 className="w-4 h-4" /><span>{label || t("delete.button")}</span>
    </button>
  );
}
