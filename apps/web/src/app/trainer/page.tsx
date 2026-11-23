"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { fetchApi } from "@/lib/api";
import { LabApprovalsCard } from "@/components/LabApprovalsCard";
import {
  Code2, ExternalLink, Filter, AlertCircle, RefreshCw, CheckCircle2, X
} from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

interface CodingProblemSummary {
  id: string; slug?: string; title: string; difficulty: string; topic: string; week_info: string;
  total_submissions: number; accepted_submissions: number; solved_percentage: number;
}
interface SupportRow {
  flag_id: string; student_id: string; name: string; batch: string; score: number; issue: string; reason_key: string;
  severity: string; action: string; action_label: string; parent_notified: boolean; status: string;
}
interface DashboardData {
  trainer: { name: string; designation: string };
  kpis: {
    active_batches: { value: number; students: number; colleges: number };
    today_attendance: { value: number | null; delta_vs_last_week: number | null; sessions: number; day: string };
    pending_code_reviews: { value: number; older_than_2_days: number };
    at_risk_students: { value: number; parents_notified: number; open_flags: number };
  };
  batch_readiness: { batch_id: string; batch: string; score: number; color: string }[];
  today_schedule: { date: string; label: string; is_today: boolean; items: { id: string; time: string; batch: string; topic: string; status: string; status_label: string; can_enter: boolean; room: string }[] };
  students_needing_support: SupportRow[];
  thresholds: { score_below: number; attendance_below: number };
  quick_actions: { key: string; href: string; variant: string }[];
}

function fill(template: string, vars: Record<string, string | number>) {
  return Object.entries(vars).reduce((acc, [k, v]) => acc.replace(`{${k}}`, String(v)), template);
}

const actionChip: Record<string, string> = { parent_call: "chip-red", extra_saturday: "chip-amber", mentor: "chip-blue" };
const statusChip: Record<string, string> = { Done: "chip-green", Next: "chip-blue", Live: "chip-green", Later: "bg-slate-100 text-slate-600" };

export default function TrainerDashboardPage() {
  const { t, language } = useLanguage();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [acting, setActing] = useState<string | null>(null);
  const [resolving, setResolving] = useState<SupportRow | null>(null);
  const [resolveNote, setResolveNote] = useState("");

  const [codingProblems, setCodingProblems] = useState<CodingProblemSummary[]>([]);
  const [loadingProblems, setLoadingProblems] = useState(true);
  const [selectedWeek, setSelectedWeek] = useState("All");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchApi<DashboardData>(`/trainer/dashboard?lang=${language}`));
    } catch (err: any) {
      setError(err?.detail || err?.message || "error");
    } finally {
      setLoading(false);
    }
  }, [language]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetchApi<{ problems: CodingProblemSummary[] } | CodingProblemSummary[]>("/trainer/coding-problems");
        setCodingProblems(Array.isArray(res) ? res : res.problems || []);
      } catch {
        setCodingProblems([]);
      } finally {
        setLoadingProblems(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(id);
  }, [toast]);

  const runAction = async (row: SupportRow) => {
    setActing(row.flag_id);
    try {
      const res = await fetchApi<{ parent_notified: boolean; notified_now: boolean; status: string }>(`/trainer/flags/${row.flag_id}/actions`, {
        method: "POST", body: JSON.stringify({ action_type: row.action }),
      });
      setToast(fill(t("trainer_dashboard.action_recorded"), { a: row.action_label, n: row.name }) + (res.notified_now ? ` · ${t("trainer_dashboard.parent_alerted")}` : ""));
      setData((prev) => prev ? {
        ...prev,
        students_needing_support: prev.students_needing_support.map((r) => r.flag_id === row.flag_id ? { ...r, parent_notified: res.parent_notified, status: res.status } : r),
      } : prev);
    } catch (err: any) {
      setToast(err?.detail || t("trainer_dashboard.error_title"));
    } finally {
      setActing(null);
    }
  };

  const submitResolve = async () => {
    if (!resolving || !resolveNote.trim()) return;
    try {
      await fetchApi(`/trainer/flags/${resolving.flag_id}/resolve`, { method: "POST", body: JSON.stringify({ note: resolveNote }) });
      setToast(t("trainer_dashboard.resolved"));
      setResolving(null);
      setResolveNote("");
      load();
    } catch (err: any) {
      setToast(err?.detail || t("trainer_dashboard.error_title"));
    }
  };

  const filteredProblems = selectedWeek === "All" ? codingProblems : codingProblems.filter((p) => p.week_info?.includes(`Week ${selectedWeek}`));
  const card = "bg-white p-4 rounded-xl border border-[#E2E8F0] shadow-sm space-y-2";
  const quickLabel = (key: string) => t(`trainer_dashboard.${key}`);

  return (
    <RoleGuard allowedRoles={["trainer"]}>
      <AppShell pageTitle={t("trainer_dashboard.title")}>
        <div className="space-y-6 max-w-7xl mx-auto pb-10" data-testid="trainer-dashboard">
          {loading && (
            <div className="space-y-6 animate-pulse" aria-busy="true" aria-label={t("trainer_dashboard.loading")}>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">{[1, 2, 3, 4].map((i) => <div key={i} className="h-24 bg-white rounded-xl border border-[#E2E8F0]" />)}</div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6"><div className="h-64 bg-white rounded-xl border border-[#E2E8F0]" /><div className="h-64 bg-white rounded-xl border border-[#E2E8F0]" /></div>
            </div>
          )}

          {!loading && error && (
            <div className="bg-white rounded-2xl border border-[#FECACA] p-8 text-center space-y-3 max-w-md mx-auto">
              <AlertCircle className="w-8 h-8 text-[#D93636] mx-auto" />
              <h2 className="text-base font-bold text-[#0F1F3A]">{t("trainer_dashboard.error_title")}</h2>
              <p className="text-xs text-[#64748B]">{error}</p>
              <button onClick={load} className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg"><RefreshCw className="w-3.5 h-3.5" /> {t("trainer_dashboard.retry")}</button>
            </div>
          )}

          {!loading && !error && data && (
            <>
              <LabApprovalsCard />

              {/* Row 1 KPI cards (PDF 8) */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="trainer-kpis">
                <div className={card}>
                  <div className="text-xs text-[#64748B] font-medium">{t("trainer_dashboard.active_batches")}</div>
                  <div className="text-3xl font-black text-[#0F1F3A]">{data.kpis.active_batches.value}</div>
                  <div className="text-[11px] text-[#64748B]">{fill(t(data.kpis.active_batches.colleges === 1 ? "trainer_dashboard.students_colleges" : "trainer_dashboard.students_colleges_plural"), { s: data.kpis.active_batches.students, c: data.kpis.active_batches.colleges })}</div>
                </div>
                <div className={card}>
                  <div className="text-xs text-[#64748B] font-medium">{t("trainer_dashboard.today_attendance")}</div>
                  {data.kpis.today_attendance.value === null ? (
                    <div className="text-sm text-[#64748B] py-2">{t("trainer_dashboard.no_attendance")}</div>
                  ) : (
                    <div className="flex items-baseline gap-2">
                      <span className="text-3xl font-black text-[#0F1F3A]">{data.kpis.today_attendance.value}%</span>
                      {data.kpis.today_attendance.delta_vs_last_week !== null && (
                        <span className={`text-xs font-bold ${data.kpis.today_attendance.delta_vs_last_week >= 0 ? "text-[#15803D]" : "text-[#D93636]"}`}>
                          {data.kpis.today_attendance.delta_vs_last_week >= 0 ? "▲" : "▼"} {Math.abs(data.kpis.today_attendance.delta_vs_last_week)}% {t("trainer_dashboard.vs_last_week")}
                        </span>
                      )}
                    </div>
                  )}
                  <div className="text-[11px] text-[#64748B]">{fill(t("trainer_dashboard.sessions_today"), { n: data.kpis.today_attendance.sessions })} · {data.kpis.today_attendance.day}</div>
                </div>
                <div className={card}>
                  <div className="text-xs text-[#64748B] font-medium">{t("trainer_dashboard.pending_reviews")}</div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-black text-[#0F1F3A]">{data.kpis.pending_code_reviews.value}</span>
                    {data.kpis.pending_code_reviews.older_than_2_days > 0 ? (
                      <span className="text-xs font-bold text-[#D93636]">{fill(t("trainer_dashboard.older_than"), { n: data.kpis.pending_code_reviews.older_than_2_days })}</span>
                    ) : (
                      <span className="text-xs font-bold text-[#15803D]">{t("trainer_dashboard.queue_clear")}</span>
                    )}
                  </div>
                  <Link href="/trainer/reviews" className="text-[11px] text-[#2B5CD0] font-semibold hover:underline">{t("trainer_dashboard.review_prs")} →</Link>
                </div>
                <div className={card}>
                  <div className="text-xs text-[#64748B] font-medium">{t("trainer_dashboard.at_risk")}</div>
                  <div className="text-3xl font-black text-[#D93636]">{data.kpis.at_risk_students.value}</div>
                  <div className="text-[11px] text-[#64748B]">{fill(t("trainer_dashboard.parents_notified"), { n: data.kpis.at_risk_students.parents_notified })}</div>
                </div>
              </div>

              {/* Row 2 chart + schedule */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-3">
                  <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
                    <h3 className="font-bold text-xs text-[#0F1F3A]">{t("trainer_dashboard.batch_readiness")}</h3>
                    <span className="text-[11px] text-[#64748B]">{t("trainer_dashboard.average_semester")}</span>
                  </div>
                  <div className="h-56 w-full pt-2" data-testid="batch-readiness-chart">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={data.batch_readiness}>
                        <XAxis dataKey="batch" tick={{ fontSize: 11 }} />
                        <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                        <Tooltip />
                        <Bar dataKey="score" radius={[6, 6, 0, 0]} label={{ position: "top", fontSize: 11, fill: "#0F1F3A" }}>
                          {data.batch_readiness.map((entry) => <Cell key={entry.batch_id} fill={entry.score >= 75 ? "#2BB3A0" : "#2B5CD0"} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="flex items-center justify-center gap-4 text-[11px] text-[#64748B] pt-1">
                    <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#2BB3A0]" /> {t("trainer_dashboard.legend_ready")}</span>
                    <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#2B5CD0]" /> {t("trainer_dashboard.legend_below")}</span>
                  </div>
                </div>

                <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-3">
                  <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
                    <h3 className="font-bold text-xs text-[#0F1F3A]">{data.today_schedule.is_today ? t("trainer_dashboard.today_schedule") : t("trainer_dashboard.next_day_schedule")}</h3>
                    <span className="text-[11px] text-[#64748B] font-semibold">{data.today_schedule.label}</span>
                  </div>
                  {data.today_schedule.items.length === 0 ? (
                    <p className="text-xs text-[#64748B] py-6 text-center">{t("trainer_dashboard.no_schedule")}</p>
                  ) : (
                    <div className="space-y-2.5" data-testid="today-schedule">
                      {data.today_schedule.items.map((item) => (
                        <div key={item.id} className="flex items-center justify-between p-3 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] gap-2">
                          <div className="flex items-center gap-3 min-w-0">
                            <span className="w-16 text-xs font-bold text-[#0F1F3A] flex-shrink-0">{item.time}</span>
                            <div className="min-w-0">
                              <div className="text-xs font-bold text-[#0F1F3A] truncate">{item.topic}</div>
                              <div className="text-[10px] text-[#64748B]">{item.batch}</div>
                            </div>
                          </div>
                          {item.can_enter ? (
                            <Link href={item.room} className="px-3 py-1 bg-[#2B5CD0] hover:bg-[#1E46B0] text-white text-xs font-bold rounded-lg shadow-sm flex-shrink-0">{t("trainer_dashboard.enter_room")}</Link>
                          ) : (
                            <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full flex-shrink-0 ${statusChip[item.status] || "bg-slate-100 text-slate-600"}`}>{item.status_label}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Row 3 weekly DSA widget (Screen 24 integration) */}
              <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-4" data-testid="trainer-dsa-widget">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-[#E2E8F0] pb-3">
                  <div className="flex items-center gap-2">
                    <Code2 className="w-5 h-5 text-[#2B5CD0]" />
                    <h3 className="font-bold text-sm text-[#0F1F3A]">{t("trainer_dashboard.dsa_widget")}</h3>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-[#64748B] font-medium flex items-center gap-1"><Filter className="w-3.5 h-3.5" /> Week:</span>
                    <select value={selectedWeek} onChange={(e) => setSelectedWeek(e.target.value)} className="bg-[#F8FAFC] border border-[#CBD5E1] text-xs font-semibold text-[#0F1F3A] rounded-lg px-2.5 py-1 focus:outline-none cursor-pointer" aria-label="Week">
                      <option value="All">All Weeks (1-8)</option>
                      {[1, 2, 3, 4, 5, 6, 7, 8].map((w) => <option key={w} value={String(w)}>Week {w}</option>)}
                    </select>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead><tr className="border-b border-[#E2E8F0] text-[#64748B] text-[11px]">
                      <th className="pb-2.5 font-semibold">Problem</th><th className="pb-2.5 font-semibold">Schedule</th><th className="pb-2.5 font-semibold">Topic</th>
                      <th className="pb-2.5 font-semibold">Difficulty</th><th className="pb-2.5 font-semibold text-center">Submissions</th><th className="pb-2.5 font-semibold text-center">Solved %</th><th className="pb-2.5 font-semibold text-right"></th>
                    </tr></thead>
                    <tbody className="divide-y divide-[#E2E8F0]">
                      {loadingProblems ? (
                        <tr><td colSpan={7} className="py-6 text-center text-xs text-[#64748B]">…</td></tr>
                      ) : filteredProblems.length === 0 ? (
                        <tr><td colSpan={7} className="py-6 text-center text-xs text-[#64748B]">No problems for this week.</td></tr>
                      ) : filteredProblems.map((prob) => (
                        <tr key={prob.id} className="hover:bg-[#F8FAFC]">
                          <td className="py-2.5 font-bold text-[#0F1F3A]">{prob.title}</td>
                          <td className="py-2.5 text-[#64748B]">{prob.week_info}</td>
                          <td className="py-2.5"><span className="chip-blue text-[10px]">{prob.topic}</span></td>
                          <td className="py-2.5"><span className={prob.difficulty === "Easy" ? "chip-green text-[10px]" : prob.difficulty === "Medium" ? "chip-amber text-[10px]" : "chip-red text-[10px]"}>{prob.difficulty}</span></td>
                          <td className="py-2.5 text-center font-mono text-[#0F1F3A]">{prob.total_submissions}</td>
                          <td className="py-2.5 text-center font-bold text-[#15803D] text-[11px]">{prob.solved_percentage}%</td>
                          <td className="py-2.5 text-right"><Link href={`/student/coding/${prob.id}`} className="inline-flex items-center gap-1 px-2.5 py-1 bg-[#2B5CD0] hover:bg-[#1E46B0] text-white font-bold text-[11px] rounded-lg"><span>Open</span><ExternalLink className="w-2.5 h-2.5" /></Link></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Row 4 support table + quick actions */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-3">
                  <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
                    <h3 className="font-bold text-xs text-[#0F1F3A]">{t("trainer_dashboard.needing_support")}</h3>
                    <span className="text-[11px] text-[#D93636] font-semibold">{fill(t("trainer_dashboard.score_below"), { n: data.thresholds.score_below })}</span>
                  </div>
                  {data.students_needing_support.length === 0 ? (
                    <p className="text-xs text-[#64748B] py-6 text-center">{t("trainer_dashboard.no_support")}</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs text-left" data-testid="support-table">
                        <thead><tr className="border-b border-[#E2E8F0] text-[#64748B] text-[11px]">
                          <th className="pb-2 font-semibold">{t("trainer_dashboard.student")}</th><th className="pb-2 font-semibold">{t("trainer_dashboard.batch")}</th>
                          <th className="pb-2 font-semibold">{t("trainer_dashboard.score")}</th><th className="pb-2 font-semibold">{t("trainer_dashboard.issue")}</th>
                          <th className="pb-2 font-semibold text-right">{t("trainer_dashboard.action")}</th>
                        </tr></thead>
                        <tbody className="divide-y divide-[#E2E8F0]">
                          {data.students_needing_support.map((st) => (
                            <tr key={st.flag_id} className="hover:bg-[#F8FAFC]">
                              <td className="py-2.5 font-bold text-[#0F1F3A]">{st.name}{st.parent_notified && <span className="ml-1.5 text-[9px] text-[#15803D] font-semibold" title={t("trainer_dashboard.notified")}>✓</span>}</td>
                              <td className="py-2.5 text-[#64748B]">{st.batch}</td>
                              <td className="py-2.5"><span className="px-2 py-0.5 rounded-md bg-red-100 text-red-700 font-bold text-[11px]">{st.score}</span></td>
                              <td className="py-2.5 text-[#64748B]">{st.issue}</td>
                              <td className="py-2.5 text-right whitespace-nowrap">
                                <button type="button" disabled={acting === st.flag_id} onClick={() => runAction(st)} className={`${actionChip[st.action] || "chip-blue"} cursor-pointer disabled:opacity-50`} data-testid="support-action">{st.action_label}</button>
                                <button type="button" onClick={() => { setResolving(st); setResolveNote(""); }} className="ml-1.5 text-[10px] text-[#64748B] hover:text-[#0F1F3A] underline" aria-label={`${t("trainer_dashboard.resolve")} ${st.name}`}>{t("trainer_dashboard.resolve")}</button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

                <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-3">
                  <h3 className="font-bold text-xs text-[#0F1F3A] border-b border-[#E2E8F0] pb-2">{t("trainer_dashboard.quick_actions")}</h3>
                  <div className="grid grid-cols-2 gap-2.5 pt-1" data-testid="quick-actions">
                    {data.quick_actions.map((qa) => (
                      <Link key={qa.key} href={qa.href} className={`py-2.5 px-3 text-center font-bold text-xs rounded-xl transition-all ${qa.variant === "blue" ? "bg-[#2B5CD0] hover:bg-[#1E46B0] text-white shadow" : qa.variant === "teal" ? "bg-[#2BB3A0] hover:bg-[#249B8A] text-white shadow" : "border border-[#CBD5E1] hover:bg-[#F8FAFC] text-[#0F1F3A]"}`}>
                        {quickLabel(qa.key)}
                      </Link>
                    ))}
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        {toast && (
          <div role="status" className="fixed bottom-6 right-6 z-50 bg-[#0F1F3A] text-white text-xs font-semibold px-4 py-3 rounded-xl shadow-2xl flex items-center gap-2" data-testid="toast">
            <CheckCircle2 className="w-4 h-4 text-[#2BB3A0]" /> {toast}
          </div>
        )}

        {resolving && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" role="dialog" aria-modal="true">
            <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl border border-[#E2E8F0]">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-bold text-[#0F1F3A]">{t("trainer_dashboard.resolve")} · {resolving.name}</h3>
                <button onClick={() => setResolving(null)} className="p-1.5 rounded-lg hover:bg-[#F1F5F9]" aria-label={t("trainer_dashboard.cancel")}><X className="w-4 h-4 text-[#64748B]" /></button>
              </div>
              <label className="block text-xs font-bold text-[#0F1F3A]">{t("trainer_dashboard.resolve_note")}
                <textarea value={resolveNote} onChange={(e) => setResolveNote(e.target.value)} rows={3} className="mt-1 w-full px-3 py-2 border border-[#E2E8F0] rounded-lg bg-[#F8FAFC] text-xs font-normal focus:outline-none focus:border-[#2B5CD0]" data-testid="resolve-note" />
              </label>
              <div className="flex gap-2">
                <button onClick={() => setResolving(null)} className="flex-1 py-2 bg-[#F1F5F9] text-[#0F1F3A] font-bold text-xs rounded-xl">{t("trainer_dashboard.cancel")}</button>
                <button onClick={submitResolve} disabled={!resolveNote.trim()} className="flex-1 py-2 bg-[#2BB3A0] text-white font-bold text-xs rounded-xl disabled:opacity-50">{t("trainer_dashboard.resolve_confirm")}</button>
              </div>
            </div>
          </div>
        )}
      </AppShell>
    </RoleGuard>
  );
}
