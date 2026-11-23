"use client";

/** Screen 14 · At-risk students (trainer): flags from the nightly readiness run (L34); a parent call reaches 18 and 15 (L31). */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { AlertTriangle, CheckCircle2, Phone } from "lucide-react";

interface Flag {
  id: string; student_id: string; name: string; score: number | null; band: string | null; attendance_pct: number | null; batch: string | null;
  issue: string; severity: string; status: string; suggested_action: string; action_label: string; parent_notified: boolean; flagged_on: string | null; ai_calls_7d?: number;
}
interface History { actions: { type: string; note: string | null; by: string | null; at: string | null }[] }

const OUTCOME: Record<string, string> = { sent: "at_risk.call_sent", held: "at_risk.call_held", already: "at_risk.call_already", no_parent: "at_risk.call_no_parent" };

export default function AtRiskPage() {
  const { t, language } = useLanguage();
  const [status, setStatus] = useState<"open" | "resolved">("open");
  const [data, setData] = useState<{ flags: Flag[]; summary: { open: number; high: number; parents_alerted: number } } | null>(null);
  const [selected, setSelected] = useState<Flag | null>(null);
  const [history, setHistory] = useState<History | null>(null);
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await fetchApi(`/trainer/at-risk?status=${status}&lang=${language}`));
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("at_risk.load_failed"));
    }
  }, [status, language, t]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!selected) return setHistory(null);
    fetchApi<History>(`/trainer/flags/${selected.id}?lang=${language}`).then(setHistory).catch(() => setHistory(null));
  }, [selected, language]);

  const act = async (type: "parent_call" | "extra_saturday" | "mentor" | "note" | "resolve") => {
    if (!selected) return;
    if ((type === "resolve" || type === "note") && !note.trim()) return setError(t("at_risk.err_note"));
    setBusy(true);
    setError("");
    setMsg("");
    try {
      if (type === "resolve") {
        await fetchApi(`/trainer/flags/${selected.id}/resolve`, { method: "POST", body: JSON.stringify({ note }) });
        setMsg(t("at_risk.resolved"));
        setSelected(null);
      } else {
        const r = await fetchApi<{ parent_call: string | null }>(`/trainer/flags/${selected.id}/actions`, { method: "POST", body: JSON.stringify({ action_type: type, note: note || null }) });
        setMsg(r.parent_call ? t(OUTCOME[r.parent_call]) : t("at_risk.action_saved"));
        setHistory(await fetchApi<History>(`/trainer/flags/${selected.id}?lang=${language}`));
      }
      setNote("");
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("at_risk.save_failed"));
    } finally {
      setBusy(false);
    }
  };

  const sev: Record<string, string> = { high: "bg-[#FEE2E2] text-[#991B1B]", medium: "bg-[#FEF3C7] text-[#92400E]", low: "bg-[#F1F5F9] text-[#475569]" };

  return (
    <RoleGuard allowedRoles={["trainer"]}>
      <AppShell pageTitle={t("at_risk.title")}>
        <div className="p-4 md:p-6 space-y-4 max-w-6xl">
          {data && (
            <div className="grid grid-cols-3 gap-3" data-testid="risk-summary">
              {([["open", data.summary.open], ["high", data.summary.high], ["parents_alerted", data.summary.parents_alerted]] as const).map(([k, v]) => (
                <div key={k} className="bg-white rounded-xl border border-[#E2E8F0] p-3">
                  <div className="text-2xl font-black text-[#0F1F3A]">{v}</div>
                  <div className="text-[11px] text-[#64748B]">{t(`at_risk.sum_${k}`)}</div>
                </div>
              ))}
            </div>
          )}
          <div className="flex gap-2" role="tablist">
            {(["open", "resolved"] as const).map((s) => (
              <button key={s} type="button" role="tab" aria-selected={status === s} onClick={() => { setStatus(s); setSelected(null); }} data-testid={`risk-tab-${s}`}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold ${status === s ? "bg-[#2B5CD0] text-white" : "border border-[#CBD5E1]"}`}>{t(`at_risk.tab_${s}`)}</button>
            ))}
          </div>
          {msg && <p className="text-xs text-[#166534] font-bold" role="status" data-testid="risk-msg">{msg}</p>}
          {error && <p className="text-xs text-red-600" role="alert" data-testid="risk-error">{error}</p>}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
            <ul className="lg:col-span-3 bg-white rounded-xl border border-[#E2E8F0] divide-y divide-[#F1F5F9]" data-testid="risk-list">
              {data?.flags.length === 0 && <li className="p-6 text-center text-xs text-[#64748B]">{t("at_risk.none")}</li>}
              {data?.flags.map((f) => (
                <li key={f.id}>
                  <button type="button" onClick={() => setSelected(f)} aria-pressed={selected?.id === f.id} data-testid="risk-row"
                    className={`w-full text-left px-3 py-2.5 flex items-center gap-3 ${selected?.id === f.id ? "bg-[#EFF6FF]" : "hover:bg-[#F8FAFC]"}`}>
                    <AlertTriangle className={`w-4 h-4 shrink-0 ${f.severity === "high" ? "text-[#DC2626]" : "text-[#D97706]"}`} />
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-bold text-[#0F1F3A] truncate">{f.name}</div>
                      <div className="text-[11px] text-[#64748B]">{f.issue} · {t("at_risk.score")} {f.score ?? "—"} · {t("at_risk.attendance")} {f.attendance_pct ?? "—"}%{f.batch ? ` · ${f.batch}` : ""}{` · ${t("at_risk.ai_calls")} ${f.ai_calls_7d ?? 0}`}</div>
                    </div>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${sev[f.severity] || sev.low}`}>{t(`at_risk.sev_${f.severity}`)}</span>
                    {f.parent_notified && <Phone className="w-3.5 h-3.5 text-[#2BB3A0]" aria-label={t("at_risk.parent_alerted")} />}
                  </button>
                </li>
              ))}
            </ul>
            {selected && (
              <section className="lg:col-span-2 bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-3 h-fit" data-testid="risk-detail">
                <div>
                  <h2 className="text-sm font-black text-[#0F1F3A]">{selected.name}</h2>
                  <p className="text-xs text-[#475569]">{selected.issue} · {t("at_risk.suggested")}: <b>{selected.action_label}</b></p>
                  {selected.parent_notified && <p className="text-[11px] text-[#2BB3A0] font-semibold mt-1">{t("at_risk.parent_alerted")}</p>}
                </div>
                {selected.status !== "resolved" && (
                  <>
                    <div className="grid grid-cols-2 gap-2">
                      <button type="button" disabled={busy} onClick={() => act("parent_call")} data-testid="act-parent-call" className="px-2 py-2 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg inline-flex items-center justify-center gap-1 disabled:opacity-50">
                        <Phone className="w-3.5 h-3.5" />{t("at_risk.parent_call")}
                      </button>
                      <button type="button" disabled={busy} onClick={() => act("extra_saturday")} className="px-2 py-2 border border-[#CBD5E1] text-xs font-bold rounded-lg disabled:opacity-50">{t("at_risk.extra_saturday")}</button>
                      <button type="button" disabled={busy} onClick={() => act("mentor")} className="px-2 py-2 border border-[#CBD5E1] text-xs font-bold rounded-lg disabled:opacity-50">{t("at_risk.mentor")}</button>
                      <button type="button" disabled={busy} onClick={() => act("note")} className="px-2 py-2 border border-[#CBD5E1] text-xs font-bold rounded-lg disabled:opacity-50">{t("at_risk.add_note")}</button>
                    </div>
                    <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("at_risk.note_ph")} data-testid="risk-note"
                      className="w-full px-2.5 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg text-xs" />
                    <button type="button" disabled={busy} onClick={() => act("resolve")} data-testid="act-resolve" className="w-full px-2 py-2 bg-[#166534] text-white text-xs font-bold rounded-lg inline-flex items-center justify-center gap-1 disabled:opacity-50">
                      <CheckCircle2 className="w-3.5 h-3.5" />{t("at_risk.resolve")}
                    </button>
                  </>
                )}
                <div>
                  <h3 className="text-[11px] font-black text-[#64748B] uppercase tracking-wide">{t("at_risk.history")}</h3>
                  <ol className="mt-1 space-y-1" data-testid="risk-history">
                    {(history?.actions || []).length === 0 && <li className="text-[11px] text-[#94A3B8]">{t("at_risk.no_history")}</li>}
                    {history?.actions.map((a, i) => (
                      <li key={i} className="text-[11px] text-[#334155]">
                        <b>{t(`at_risk.act_${a.type}`)}</b>{a.by ? ` · ${a.by}` : ""}{a.at ? ` · ${a.at.slice(0, 10)}` : ""}{a.note ? `: ${a.note}` : ""}
                      </li>
                    ))}
                  </ol>
                </div>
              </section>
            )}
          </div>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
