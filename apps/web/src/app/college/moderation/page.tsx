"use client";

/** Screen 34 moderation (S10): the college's own words. Block refuses the post; flag lets it through
 *  and sends it to the trainers' moderation queue (link L18). */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { Plus, Trash2 } from "lucide-react";

interface Term { id: string; term: string; action: "block" | "flag" }

export default function ModerationTermsPage() {
  const { t } = useLanguage();
  const [terms, setTerms] = useState<Term[]>([]);
  const [term, setTerm] = useState("");
  const [action, setAction] = useState<"block" | "flag">("flag");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { setTerms((await fetchApi<{ terms: Term[] }>("/college/moderation/terms")).terms); } catch (e) { setError(e instanceof ApiError ? String(e.detail) : t("mod.load_failed")); }
  }, [t]);
  useEffect(() => { load(); }, [load]);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (term.trim().length < 2) return setError(t("mod.err_term"));
    setError("");
    try {
      await fetchApi("/college/moderation/terms", { method: "POST", body: JSON.stringify({ term, action }) });
      setTerm("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("mod.load_failed"));
    }
  };

  const remove = async (id: string) => {
    await fetchApi(`/college/moderation/terms/${id}`, { method: "DELETE" }).catch(() => undefined);
    await load();
  };

  return (
    <RoleGuard allowedRoles={["college"]}>
      <AppShell pageTitle={t("mod.title")}>
        <div className="max-w-2xl space-y-6">
          <p className="text-xs text-ink-soft">{t("mod.help")}</p>
          <form onSubmit={add} noValidate className="bg-white rounded-card border border-line p-3 flex flex-wrap gap-2" data-testid="mod-form">
            <input value={term} onChange={(e) => setTerm(e.target.value)} placeholder={t("mod.term_ph")} aria-label={t("mod.term_ph")} maxLength={64}
              className="flex-1 min-w-[160px] px-2.5 py-1.5 bg-surface-2 border border-line rounded-tile text-xs" data-testid="mod-term" />
            <select value={action} onChange={(e) => setAction(e.target.value as "block" | "flag")} aria-label={t("mod.action")}
              className="px-2.5 py-1.5 border border-line-strong rounded-tile text-xs" data-testid="mod-action">
              <option value="flag">{t("mod.flag")}</option>
              <option value="block">{t("mod.block")}</option>
            </select>
            <button type="submit" className="px-3 py-1.5 bg-brand text-white text-xs font-semibold rounded-tile inline-flex items-center gap-1" data-testid="mod-add"><Plus className="w-3.5 h-3.5" />{t("mod.add")}</button>
          </form>
          {error && <p className="text-xs text-red-600" role="alert" data-testid="mod-error">{error}</p>}
          <ul className="bg-white rounded-card border border-line divide-y divide-line-soft" data-testid="mod-list">
            {terms.length === 0 && <li className="p-4 text-xs text-muted text-center">{t("mod.none")}</li>}
            {terms.map((x) => (
              <li key={x.id} className="px-3 py-2 flex items-center justify-between text-xs" data-testid="mod-row">
                <span className="font-mono font-semibold">{x.term}</span>
                <span className="flex items-center gap-3">
                  <span className={x.action === "block" ? "text-danger font-semibold" : "text-warning font-semibold"}>{t(`mod.${x.action}`)}</span>
                  <button type="button" onClick={() => remove(x.id)} aria-label={t("mod.remove")} className="text-muted hover:text-red-600"><Trash2 className="w-3.5 h-3.5" /></button>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
