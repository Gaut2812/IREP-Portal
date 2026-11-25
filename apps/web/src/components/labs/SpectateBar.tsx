"use client";

/** Labs track S13: the trainer's read-only lab view for this class. Students get a link; the
 *  trainer posts or removes it (an https link on the lab hub). */
import React, { useState } from "react";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { Eye } from "lucide-react";

export function SpectateBar({ sessionId, spectate, isTrainer, onChange }: {
  sessionId: string; spectate: { url: string; label: string | null } | null; isTrainer: boolean; onChange: () => void;
}) {
  const { t } = useLanguage();
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");

  const post = async () => {
    setError("");
    try {
      await fetchApi(`/trainer/sessions/${sessionId}/spectate`, { method: "PUT", body: JSON.stringify({ url, label: t("live_class.spectate_default_label") }) });
      setUrl("");
      onChange();
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : t("live_class.spectate_failed"));
    }
  };
  const remove = async () => {
    await fetchApi(`/trainer/sessions/${sessionId}/spectate`, { method: "DELETE" }).catch(() => undefined);
    onChange();
  };

  if (!isTrainer && !spectate) return null;
  return (
    <div className="px-4 py-2 bg-[#141A29] border-b border-[#2D3748] flex flex-wrap items-center gap-2 text-xs" data-testid="spectate-bar">
      <Eye className="w-4 h-4 text-teal" />
      {spectate ? (
        <>
          <a href={spectate.url} target="_blank" rel="noopener noreferrer" className="font-semibold text-teal underline" data-testid="spectate-link">
            {spectate.label || t("live_class.spectate_default_label")}
          </a>
          <span className="text-subtle">{t("live_class.spectate_readonly")}</span>
          {isTrainer && <button type="button" onClick={remove} className="ml-auto text-danger-fill font-semibold" data-testid="spectate-remove">{t("live_class.spectate_remove")}</button>}
        </>
      ) : (
        <>
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder={t("live_class.spectate_ph")} aria-label={t("live_class.spectate_ph")}
            className="flex-1 min-w-[200px] bg-[#0F172A] border border-ink-soft rounded-tile px-2 py-1 text-line" data-testid="spectate-url" />
          <button type="button" onClick={post} disabled={url.trim().length < 10} className="px-3 py-1 bg-teal text-white font-semibold rounded-tile disabled:opacity-40" data-testid="spectate-post">
            {t("live_class.spectate_post")}
          </button>
          {error && <span className="text-danger-fill w-full" role="alert" data-testid="spectate-error">{error}</span>}
        </>
      )}
    </div>
  );
}
