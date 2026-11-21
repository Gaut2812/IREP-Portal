"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { fetchApi } from "@/lib/api";
import {
  Terminal, Container, Cloud, Cpu, ShieldAlert, Code, Play, StopCircle, ExternalLink, Lock, AlertCircle, RefreshCw, CheckCircle2, X, Clock, Database,
} from "lucide-react";

interface Chip { label: string; type: string }
interface LabCard {
  id: string; name: string; category: string; description: string; icon: string; chips: Chip[]; footer: string;
  requires_approval: boolean; session_minutes: number; action: "launch" | "open" | "request" | "pending" | "locked";
  locked: { reason: string; message: string } | null;
}
interface ActiveSession { id: string; lab_id: string; lab_name: string; icon: string; status: string; workspace_file: string | null; running_minutes: number; minutes_left: number; idle_limit_min: number; open_url: string }
interface LabsData {
  labs: LabCard[]; active_sessions: ActiveSession[];
  usage: { lab_minutes_used: number; lab_minutes_quota: number; cloud_credits_left_pct: number };
  queue: { waiting: number; label: string };
}

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = { terminal: Terminal, container: Container, cloud: Cloud, cpu: Cpu, shield: ShieldAlert, code: Code, database: Database };
const CHIP: Record<string, string> = { green: "chip-green", amber: "chip-amber", purple: "chip-purple", red: "chip-red", blue: "chip-blue" };
const FILTERS: { key: string; label: string }[] = [
  { key: "All labs", label: "labs.filter_all" }, { key: "Software Engineering", label: "labs.filter_se" }, { key: "AI & Data Science", label: "labs.filter_ai" },
  { key: "Cybersecurity", label: "labs.filter_cyber" }, { key: "Cloud & DevOps", label: "labs.filter_cloud" },
];

function fill(template: string, vars: Record<string, string | number>) {
  return Object.entries(vars).reduce((acc, [k, v]) => acc.replace(`{${k}}`, String(v)), template);
}

export default function VirtualLabsPage() {
  const { t } = useLanguage();
  const [data, setData] = useState<LabsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("All labs");
  const [busy, setBusy] = useState<string | null>(null);
  const [toast, setToast] = useState<{ text: string; ok: boolean } | null>(null);
  const [aupLab, setAupLab] = useState<LabCard | null>(null);
  const [aupAccepted, setAupAccepted] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setData(await fetchApi<LabsData>("/student/labs"));
    } catch (err: any) {
      setError(err?.detail || err?.message || "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const id = setInterval(load, 60000);   // running minutes / culled sessions
    return () => clearInterval(id);
  }, [load]);
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(id);
  }, [toast]);

  const errText = (err: any) => (typeof err?.detail === "string" && err.detail.startsWith("{") ? (() => { try { return JSON.parse(err.detail).message; } catch { return err.detail; } })() : err?.detail) || t("labs.action_failed");

  const launch = async (lab: LabCard) => {
    setBusy(lab.id);
    try {
      await fetchApi(`/student/labs/${lab.id}/launch`, { method: "POST" });
      setToast({ text: fill(t("labs.launched"), { n: lab.name }), ok: true });
      await load();
    } catch (err: any) {
      setToast({ text: errText(err), ok: false });
    } finally {
      setBusy(null);
    }
  };

  const stop = async (s: ActiveSession) => {
    setBusy(s.id);
    try {
      const res = await fetchApi<{ minutes: number }>(`/student/lab-sessions/${s.id}/stop`, { method: "POST" });
      setToast({ text: fill(t("labs.stopped"), { m: res.minutes }), ok: true });
      await load();
    } catch (err: any) {
      setToast({ text: errText(err), ok: false });
    } finally {
      setBusy(null);
    }
  };

  const requestAccess = async () => {
    if (!aupLab || !aupAccepted) return;
    setBusy(aupLab.id);
    try {
      await fetchApi(`/student/labs/${aupLab.id}/request-access`, { method: "POST", body: JSON.stringify({ accept_aup: true }) });
      setToast({ text: t("labs.request_sent"), ok: true });
      setAupLab(null);
      setAupAccepted(false);
      await load();
    } catch (err: any) {
      setToast({ text: errText(err), ok: false });
    } finally {
      setBusy(null);
    }
  };

  const labs = data ? (filter === "All labs" ? data.labs : data.labs.filter((l) => l.category === filter)) : [];

  return (
    <RoleGuard allowedRoles={["student"]}>
      <AppShell pageTitle={t("labs.title")}>
        <div className="space-y-6 max-w-7xl mx-auto" data-testid="virtual-labs">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-2" role="tablist">
              {FILTERS.map((f) => (
                <button key={f.key} role="tab" aria-selected={filter === f.key} onClick={() => setFilter(f.key)}
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${filter === f.key ? "bg-[#2B5CD0] text-white shadow-sm" : "bg-white text-[#64748B] border border-[#E2E8F0] hover:bg-[#F8FAFC]"}`}>
                  {t(f.label)}
                </button>
              ))}
            </div>
            {data && (
              <div className="flex items-center gap-3 text-[11px] text-[#64748B]" data-testid="usage-meter">
                <span className="font-semibold text-[#0F1F3A]">{t("labs.usage_title")}:</span>
                <span>{fill(t("labs.lab_minutes"), { u: data.usage.lab_minutes_used, q: data.usage.lab_minutes_quota })}</span>
                <span className="hidden sm:inline">· {fill(t("labs.cloud_credits"), { p: data.usage.cloud_credits_left_pct })}</span>
              </div>
            )}
          </div>

          {loading && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 animate-pulse" aria-busy="true" aria-label={t("labs.loading")}>
              {[1, 2, 3, 4, 5, 6].map((i) => <div key={i} className="h-48 bg-white rounded-xl border border-[#E2E8F0]" />)}
            </div>
          )}

          {!loading && error && (
            <div className="bg-white rounded-2xl border border-[#FECACA] p-8 text-center space-y-3 max-w-md mx-auto">
              <AlertCircle className="w-8 h-8 text-[#D93636] mx-auto" />
              <h2 className="text-base font-bold text-[#0F1F3A]">{t("labs.error_title")}</h2>
              <p className="text-xs text-[#64748B]">{error}</p>
              <button onClick={load} className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg"><RefreshCw className="w-3.5 h-3.5" /> {t("labs.retry")}</button>
            </div>
          )}

          {!loading && !error && data && (
            <>
              {labs.length === 0 ? (
                <p className="text-xs text-[#64748B] text-center py-10">{t("labs.empty_filter")}</p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                  {labs.map((lab) => {
                    const Icon = ICONS[lab.icon] || Terminal;
                    return (
                      <div key={lab.id} className="bg-white rounded-xl border border-[#E2E8F0] p-5 shadow-sm flex flex-col justify-between gap-4 hover:shadow-md transition-all" data-testid={`lab-${lab.id}`}>
                        <div className="space-y-3">
                          <div className="flex items-center gap-3">
                            <div className="p-2.5 rounded-xl bg-[#EFF6FF] text-[#2B5CD0]"><Icon className="w-5 h-5" /></div>
                            <h3 className="font-bold text-sm text-[#0F1F3A]">{lab.name}</h3>
                          </div>
                          <p className="text-xs text-[#64748B] leading-relaxed">{lab.description}</p>
                          <div className="flex gap-2 flex-wrap">{lab.chips.map((c) => <span key={c.label} className={CHIP[c.type] || "chip-blue"}>{c.label}</span>)}</div>
                          {lab.locked && lab.action === "locked" && (
                            <p className="text-[11px] text-[#B45309] bg-[#FEF3C7] rounded-lg px-2 py-1.5 flex items-start gap-1.5" data-testid={`lock-${lab.id}`}><Lock className="w-3 h-3 mt-0.5 flex-shrink-0" />{lab.locked.message}</p>
                          )}
                        </div>
                        <div className="flex items-center justify-between border-t border-[#E2E8F0] pt-3 gap-2">
                          <span className="text-[11px] text-[#64748B] font-medium">{lab.footer}</span>
                          {lab.action === "launch" && (
                            <button onClick={() => launch(lab)} disabled={busy === lab.id} className="px-4 py-1.5 bg-[#2BB3A0] hover:bg-[#249B8A] text-white text-xs font-bold rounded-lg shadow-sm flex items-center gap-1 disabled:opacity-50" data-testid={`launch-${lab.id}`}>
                              <Play className="w-3 h-3" /><span>{busy === lab.id ? t("labs.launching") : t("labs.launch")}</span>
                            </button>
                          )}
                          {lab.action === "open" && (
                            <Link href={data.active_sessions.find((s) => s.lab_id === lab.id)?.open_url || "#"} className="px-4 py-1.5 border border-[#2B5CD0] text-[#2B5CD0] hover:bg-[#EFF6FF] text-xs font-bold rounded-lg flex items-center gap-1">
                              <ExternalLink className="w-3 h-3" /><span>{t("labs.open")}</span>
                            </Link>
                          )}
                          {lab.action === "request" && (
                            <button onClick={() => { setAupLab(lab); setAupAccepted(false); }} className="px-3.5 py-1.5 border border-[#2B5CD0] text-[#2B5CD0] hover:bg-[#EFF6FF] text-xs font-bold rounded-lg flex items-center gap-1" data-testid={`launch-${lab.id}`}>
                              <Lock className="w-3 h-3" /><span>{t("labs.launch")}</span>
                            </button>
                          )}
                          {lab.action === "pending" && (
                            <span className="px-3 py-1.5 bg-[#FEF3C7] text-[#B45309] text-xs font-bold rounded-lg flex items-center gap-1" data-testid={`pending-${lab.id}`}><Clock className="w-3 h-3" />{t("labs.requested")}</span>
                          )}
                          {lab.action === "locked" && (
                            <button disabled className="px-3.5 py-1.5 bg-[#F1F5F9] text-[#94A3B8] text-xs font-bold rounded-lg flex items-center gap-1 cursor-not-allowed"><Lock className="w-3 h-3" />{t("labs.locked")}</button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Active session (PDF 5) */}
              <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm space-y-3" data-testid="active-session">
                <h3 className="font-bold text-xs text-[#0F1F3A]">{t("labs.active_session")}</h3>
                {data.active_sessions.length === 0 ? (
                  <p className="text-xs text-[#64748B]">{t("labs.no_active")}</p>
                ) : data.active_sessions.map((s) => {
                  const Icon = ICONS[s.icon] || Terminal;
                  return (
                    <div key={s.id} className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <span className="relative flex h-3 w-3"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#2BB3A0] opacity-75" /><span className="relative inline-flex rounded-full h-3 w-3 bg-[#2BB3A0]" /></span>
                        <Icon className="w-4 h-4 text-[#2B5CD0]" />
                        <div>
                          <div className="font-bold text-xs text-[#0F1F3A]">{s.lab_name}{s.workspace_file && <> · <code className="font-mono text-[#2B5CD0]">{s.workspace_file}</code></>} · {fill(t("labs.running_for"), { n: s.running_minutes })}</div>
                          <div className="text-[11px] text-[#64748B]">{fill(t("labs.minutes_left"), { n: s.minutes_left, i: s.idle_limit_min })}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Link href={s.open_url} className="flex items-center gap-1 px-3 py-1.5 border border-[#2B5CD0] text-[#2B5CD0] text-xs font-bold rounded-lg hover:bg-[#EFF6FF]" data-testid="open-session">
                          <span>{t("labs.open")}</span><ExternalLink className="w-3 h-3" />
                        </Link>
                        <button onClick={() => stop(s)} disabled={busy === s.id} className="flex items-center gap-1 px-3 py-1.5 bg-[#D93636] hover:bg-[#B91C1C] text-white text-xs font-bold rounded-lg shadow disabled:opacity-50" data-testid="stop-session">
                          <StopCircle className="w-3.5 h-3.5" /><span>{t("labs.stop")}</span>
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>

        {aupLab && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" role="dialog" aria-modal="true" aria-label={t("labs.aup_title")} data-testid="aup-dialog">
            <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl border border-[#E2E8F0]">
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-base font-bold text-[#0F1F3A] flex items-center gap-2"><ShieldAlert className="w-5 h-5 text-[#D93636]" /> {t("labs.aup_title")}</h3>
                <button onClick={() => setAupLab(null)} className="p-1.5 rounded-lg hover:bg-[#F1F5F9]" aria-label={t("labs.cancel")}><X className="w-4 h-4 text-[#64748B]" /></button>
              </div>
              <p className="text-xs text-[#334155] leading-relaxed bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-3">{t("labs.aup_body")}</p>
              <label className="flex items-start gap-2 text-xs font-semibold text-[#0F1F3A] cursor-pointer">
                <input type="checkbox" checked={aupAccepted} onChange={(e) => setAupAccepted(e.target.checked)} className="mt-0.5" data-testid="aup-accept" />
                <span>{t("labs.aup_accept")}</span>
              </label>
              <div className="flex gap-2">
                <button onClick={() => setAupLab(null)} className="flex-1 py-2 bg-[#F1F5F9] text-[#0F1F3A] font-bold text-xs rounded-xl">{t("labs.cancel")}</button>
                <button onClick={requestAccess} disabled={!aupAccepted || busy === aupLab.id} className="flex-1 py-2 bg-[#2B5CD0] text-white font-bold text-xs rounded-xl disabled:opacity-50" data-testid="aup-submit">{t("labs.aup_submit")}</button>
              </div>
            </div>
          </div>
        )}

        {toast && (
          <div role="status" className={`fixed bottom-6 right-6 z-50 text-white text-xs font-semibold px-4 py-3 rounded-xl shadow-2xl flex items-center gap-2 max-w-sm ${toast.ok ? "bg-[#0F1F3A]" : "bg-[#B91C1C]"}`} data-testid="toast">
            {toast.ok ? <CheckCircle2 className="w-4 h-4 text-[#2BB3A0] flex-shrink-0" /> : <AlertCircle className="w-4 h-4 flex-shrink-0" />} {toast.text}
          </div>
        )}
      </AppShell>
    </RoleGuard>
  );
}
