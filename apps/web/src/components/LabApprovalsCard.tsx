"use client";

import React, { useCallback, useEffect, useState } from "react";
import { FlaskConical, Check, X } from "lucide-react";
import { fetchApi } from "@/lib/api";
import { useLanguage } from "@/lib/LanguageContext";

interface Approval { id: string; lab_name: string; student_name: string; batch: string; aup_accepted: boolean; requested_at: string | null }

/** Trainer side of Screen 29: approve or deny restricted lab access (e.g. Cyber Range). */
export const LabApprovalsCard: React.FC = () => {
  const { t } = useLanguage();
  const [items, setItems] = useState<Approval[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [denying, setDenying] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);

  const load = useCallback(async () => {
    try {
      setItems((await fetchApi<{ approvals: Approval[] }>("/trainer/approvals/labs?status=pending")).approvals);
    } catch { /* card stays empty */ } finally { setLoaded(true); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const decide = async (a: Approval, decision: "approve" | "deny") => {
    if (decision === "deny" && reason.trim().length < 3) { setMessage({ text: t("lab_approvals.reason_required"), ok: false }); return; }
    setBusy(a.id); setMessage(null);
    try {
      await fetchApi(`/trainer/approvals/labs/${a.id}`, { method: "POST", body: JSON.stringify({ decision, reason: decision === "deny" ? reason.trim() : null }) });
      setItems((prev) => prev.filter((x) => x.id !== a.id));
      setMessage({ text: decision === "approve" ? t("lab_approvals.approved").replace("{name}", a.student_name) : t("lab_approvals.denied").replace("{name}", a.student_name), ok: true });
      setDenying(null); setReason("");
    } catch (err: any) {
      setMessage({ text: err?.detail || "Error", ok: false });
    } finally { setBusy(null); }
  };

  if (!loaded) return null;
  return (
    <div id="lab-approvals" className="bg-white rounded-card border border-line p-4 shadow-card space-y-3 scroll-mt-4" data-testid="lab-approvals">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ink flex items-center gap-2"><FlaskConical className="w-4 h-4 text-violet" />{t("lab_approvals.title")}</h3>
        {items.length > 0 && <span className="min-w-[20px] h-5 px-1.5 rounded-full bg-danger text-white text-caption font-semibold flex items-center justify-center">{items.length}</span>}
      </div>
      {message && <p role="status" className={`text-xs ${message.ok ? "text-success" : "text-danger"}`}>{message.text}</p>}
      {items.length === 0 ? <p className="text-xs text-muted">{t("lab_approvals.empty")}</p> : (
        <div className="space-y-2">
          {items.map((a) => (
            <div key={a.id} className="p-3 bg-surface-2 border border-line rounded-tile text-xs space-y-2" data-testid={`approval-${a.id}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <span className="font-semibold text-ink">{a.student_name}</span> <span className="text-muted">· {a.batch}</span>
                  <div className="text-ink-soft">{t("lab_approvals.wants")} <strong>{a.lab_name}</strong>{a.aup_accepted && <span className="ml-1.5 chip-green text-caption">{t("lab_approvals.aup")}</span>}</div>
                </div>
                <div className="flex gap-1.5">
                  <button onClick={() => decide(a, "approve")} disabled={busy === a.id} data-testid="approve" className="px-3 py-1.5 bg-success hover:bg-success text-white font-semibold rounded-tile flex items-center gap-1 disabled:opacity-50"><Check className="w-3.5 h-3.5" />{t("lab_approvals.approve")}</button>
                  <button onClick={() => { setDenying(denying === a.id ? null : a.id); setReason(""); }} className="px-3 py-1.5 bg-white border border-line text-danger font-semibold rounded-tile flex items-center gap-1"><X className="w-3.5 h-3.5" />{t("lab_approvals.deny")}</button>
                </div>
              </div>
              {denying === a.id && (
                <div className="flex gap-1.5">
                  <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t("lab_approvals.reason")} aria-label={t("lab_approvals.reason")} className="flex-1 min-w-0 px-2 py-1.5 border border-line rounded-tile bg-white focus:outline-none focus:border-brand" />
                  <button onClick={() => decide(a, "deny")} disabled={busy === a.id} className="px-3 py-1.5 bg-danger text-white font-semibold rounded-tile disabled:opacity-50">{t("lab_approvals.confirm_deny")}</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
