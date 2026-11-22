"use client";

import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { fetchApi, fetchBlob } from "@/lib/api";
import { Download, Calendar, FileText, AlertCircle, RefreshCw, CheckCircle2, Sparkles } from "lucide-react";
import { PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from "recharts";

interface Overview {
  college: { name: string; title: string };
  filters: { semester: number | null; semesters: number[] };
  kpis: {
    students_enrolled: { value: number; semesters: string; branches: number };
    avg_attendance: { value: number; target: number; above_target: boolean };
    certifications: { value: number; this_semester: number };
    internships: { value: number; sem6_pct: number; sem6_total: number };
  };
  readiness_distribution: { band: string; label: string; count: number; percentage: number; color: string }[];
  readiness_total: number;
  branch_readiness: { branch_id: string; branch: string; students: number; attendance: number; avg_score: number; trend: number }[];
  cumulative_certifications: { month: string; year: number; count: number; new: number }[];
  upcoming_events: { id: string; title: string; kind: string; date: string }[];
  mou_reports: { id: string; title: string; type: string; period: string; generated_at: string | null; data_as_of: string | null; size_kb: number; download_url: string }[];
}

const BAND_HEX: Record<string, string> = { green: "#2BB3A0", amber: "#F59E0B", red: "#D93636" };
const CHIP: Record<string, string> = { green: "chip-green", amber: "chip-amber", red: "chip-red" };
const BLUES = ["#BFDBFE", "#93C5FD", "#60A5FA", "#3B82F6", "#2B5CD0", "#1E40AF"];

function fill(template: string, vars: Record<string, string | number>) {
  return Object.entries(vars).reduce((acc, [k, v]) => acc.replace(`{${k}}`, String(v)), template);
}

export default function CollegeDashboardPage() {
  const { t, language } = useLanguage();
  const [data, setData] = useState<Overview | null>(null);
  const [semester, setSemester] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const q = semester ? `&semester=${semester}` : "";
      setData(await fetchApi<Overview>(`/college/overview?lang=${language}${q}`));
    } catch (err: any) {
      setError(err?.detail || err?.message || "error");
    } finally {
      setLoading(false);
    }
  }, [language, semester]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(id);
  }, [toast]);

  const download = async (r: Overview["mou_reports"][number]) => {
    try {
      const blob = await fetchBlob(`/college/reports/${r.id}/download`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${r.id}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      setToast(t("college_dashboard.download_failed"));
    }
  };

  const generate = async () => {
    setGenerating(true);
    try {
      await fetchApi("/college/reports/generate", { method: "POST", body: JSON.stringify({ report_type: "progress" }) });
      setToast(t("college_dashboard.generated"));
      load();
    } catch (err: any) {
      setToast(err?.detail || t("college_dashboard.error_title"));
    } finally {
      setGenerating(false);
    }
  };

  const card = "bg-white p-4 rounded-xl border border-[#E2E8F0] shadow-sm space-y-2";
  const panel = "bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-3";

  return (
    <RoleGuard allowedRoles={["college"]}>
      <AppShell pageTitle={t("college_dashboard.title")}>
        <div className="space-y-6 max-w-7xl mx-auto" data-testid="college-dashboard">
          <div className="flex items-center justify-end gap-2">
            <label className="text-xs font-semibold text-[#64748B]" htmlFor="semester-filter">{t("college_dashboard.semester_filter")}</label>
            <select id="semester-filter" value={semester} onChange={(e) => setSemester(e.target.value)} className="bg-white border border-[#CBD5E1] text-xs font-semibold text-[#0F1F3A] rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-[#2B5CD0]" data-testid="semester-filter">
              <option value="">{t("college_dashboard.all_semesters")}</option>
              {(data?.filters.semesters || [2, 3, 4, 5, 6, 7]).map((s) => <option key={s} value={s}>{t("college_dashboard.semester_filter")} {s}</option>)}
            </select>
          </div>

          {loading && (
            <div className="space-y-6 animate-pulse" aria-busy="true" aria-label={t("college_dashboard.loading")}>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">{[1, 2, 3, 4].map((i) => <div key={i} className="h-24 bg-white rounded-xl border border-[#E2E8F0]" />)}</div>
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6"><div className="lg:col-span-5 h-64 bg-white rounded-xl border border-[#E2E8F0]" /><div className="lg:col-span-7 h-64 bg-white rounded-xl border border-[#E2E8F0]" /></div>
            </div>
          )}

          {!loading && error && (
            <div className="bg-white rounded-2xl border border-[#FECACA] p-8 text-center space-y-3 max-w-md mx-auto">
              <AlertCircle className="w-8 h-8 text-[#D93636] mx-auto" />
              <h2 className="text-base font-bold text-[#0F1F3A]">{t("college_dashboard.error_title")}</h2>
              <p className="text-xs text-[#64748B]">{error}</p>
              <button onClick={load} className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg"><RefreshCw className="w-3.5 h-3.5" /> {t("college_dashboard.retry")}</button>
            </div>
          )}

          {!loading && !error && data && (
            <>
              {/* Row 1 KPIs (PDF 9) */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="college-kpis">
                <div className={card}>
                  <div className="text-xs text-[#64748B] font-medium">{t("college_dashboard.students_enrolled")}</div>
                  <div className="text-3xl font-black text-[#0F1F3A]">{data.kpis.students_enrolled.value}</div>
                  <div className="text-[11px] text-[#64748B]">{fill(t("college_dashboard.sem_branches"), { s: data.kpis.students_enrolled.semesters, b: data.kpis.students_enrolled.branches })}</div>
                </div>
                <div className={card}>
                  <div className="text-xs text-[#64748B] font-medium">{t("college_dashboard.avg_attendance")}</div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-black text-[#0F1F3A]">{data.kpis.avg_attendance.value}%</span>
                    <span className={`text-xs font-bold ${data.kpis.avg_attendance.above_target ? "text-[#15803D]" : "text-[#D93636]"}`}>
                      {fill(t(data.kpis.avg_attendance.above_target ? "college_dashboard.above_target" : "college_dashboard.below_target"), { t: data.kpis.avg_attendance.target })}
                    </span>
                  </div>
                </div>
                <div className={card}>
                  <div className="text-xs text-[#64748B] font-medium">{t("college_dashboard.certifications")}</div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-black text-[#0F1F3A]">{data.kpis.certifications.value}</span>
                    <span className="text-xs font-bold text-[#15803D]">{fill(t("college_dashboard.this_semester"), { n: data.kpis.certifications.this_semester })}</span>
                  </div>
                </div>
                <div className={card}>
                  <div className="text-xs text-[#64748B] font-medium">{t("college_dashboard.internships")}</div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-black text-[#0F1F3A]">{data.kpis.internships.value}</span>
                    <span className="text-xs font-bold text-[#15803D]">{fill(t("college_dashboard.sem6_pct"), { p: data.kpis.internships.sem6_pct })}</span>
                  </div>
                </div>
              </div>

              {/* Row 2 donut + branch table */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                <div className={`lg:col-span-5 ${panel}`} data-testid="readiness-donut">
                  <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
                    <h3 className="font-bold text-xs text-[#0F1F3A]">{t("college_dashboard.placement_readiness")}</h3>
                    <span className="text-[11px] text-[#64748B]">{semester ? `${t("college_dashboard.semester_filter")} ${semester}` : t("college_dashboard.all_semesters")}</span>
                  </div>
                  <div className="relative h-48 w-full flex items-center justify-center">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={data.readiness_distribution} cx="50%" cy="50%" innerRadius={55} outerRadius={80} paddingAngle={3} dataKey="count" nameKey="label">
                          {data.readiness_distribution.map((entry) => <Cell key={entry.band} fill={BAND_HEX[entry.color]} />)}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="absolute text-center pointer-events-none">
                      <div className="text-xl font-black text-[#0F1F3A]">{data.readiness_total}</div>
                      <div className="text-[10px] text-[#64748B]">{t("college_dashboard.students")}</div>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center justify-center gap-3 text-xs pt-1">
                    {data.readiness_distribution.map((b) => <span key={b.band} className={`${CHIP[b.color]} font-bold`}>{b.label} {b.percentage}%</span>)}
                  </div>
                </div>

                <div className={`lg:col-span-7 ${panel}`}>
                  <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
                    <h3 className="font-bold text-xs text-[#0F1F3A]">{t("college_dashboard.branch_readiness")}</h3>
                    <span className="text-[11px] text-[#64748B]">{data.branch_readiness.length} {t("college_dashboard.branch")}</span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs text-left" data-testid="branch-table">
                      <thead><tr className="border-b border-[#E2E8F0] text-[#64748B] text-[11px]">
                        <th className="pb-2 font-semibold">{t("college_dashboard.branch")}</th><th className="pb-2 font-semibold">{t("college_dashboard.students")}</th>
                        <th className="pb-2 font-semibold">{t("college_dashboard.attendance")}</th><th className="pb-2 font-semibold">{t("college_dashboard.avg_score")}</th>
                        <th className="pb-2 font-semibold text-right">{t("college_dashboard.trend")}</th>
                      </tr></thead>
                      <tbody className="divide-y divide-[#E2E8F0]">
                        {data.branch_readiness.map((b) => (
                          <tr key={b.branch_id} className="hover:bg-[#F8FAFC]">
                            <td className="py-2.5 font-bold text-[#0F1F3A]">{b.branch}</td>
                            <td className="py-2.5 text-[#64748B]">{b.students}</td>
                            <td className="py-2.5 text-[#64748B]">{b.attendance}%</td>
                            <td className="py-2.5 font-bold text-[#0F1F3A]">{b.avg_score}</td>
                            <td className={`py-2.5 text-right font-bold ${b.trend >= 0 ? "text-[#15803D]" : "text-[#D93636]"}`}>{b.trend >= 0 ? "▲" : "▼"} {Math.abs(b.trend)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              {/* Row 3 certifications chart, events, reports */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className={panel}>
                  <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
                    <h3 className="font-bold text-xs text-[#0F1F3A]">{t("college_dashboard.cumulative_certs")}</h3>
                    {data.cumulative_certifications.length > 0 && <span className="text-[11px] text-[#2BB3A0] font-semibold">{data.cumulative_certifications[0].month} – {data.cumulative_certifications[data.cumulative_certifications.length - 1].month}</span>}
                  </div>
                  {data.cumulative_certifications.length === 0 ? (
                    <p className="text-xs text-[#64748B] py-6 text-center">{t("college_dashboard.no_certs")}</p>
                  ) : (
                    <div className="h-44 w-full pt-2" data-testid="cert-chart">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={data.cumulative_certifications}>
                          <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                          <YAxis tick={{ fontSize: 11 }} />
                          <Tooltip />
                          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                            {data.cumulative_certifications.map((entry, i) => <Cell key={`${entry.year}-${entry.month}`} fill={BLUES[Math.min(i, BLUES.length - 1)]} />)}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>

                <div className={panel}>
                  <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
                    <h3 className="font-bold text-xs text-[#0F1F3A]">{t("college_dashboard.upcoming_events")}</h3><Calendar className="w-3.5 h-3.5 text-[#64748B]" />
                  </div>
                  {data.upcoming_events.length === 0 ? (
                    <p className="text-xs text-[#64748B] py-6 text-center">{t("college_dashboard.no_events")}</p>
                  ) : (
                    <div className="space-y-2.5" data-testid="college-events">
                      {data.upcoming_events.map((e) => (
                        <div key={e.id} className="flex items-center justify-between text-xs gap-2">
                          <span className="font-semibold text-[#0F1F3A] truncate">{e.title}</span>
                          <span className="chip-purple text-[10px] flex-shrink-0">{e.date}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className={panel}>
                  <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
                    <h3 className="font-bold text-xs text-[#0F1F3A]">{t("college_dashboard.mou_reports")}</h3><FileText className="w-3.5 h-3.5 text-[#64748B]" />
                  </div>
                  {data.mou_reports.length === 0 ? (
                    <p className="text-xs text-[#64748B] py-4 text-center">{t("college_dashboard.no_reports")}</p>
                  ) : (
                    <div className="space-y-2" data-testid="mou-reports">
                      {data.mou_reports.map((r) => (
                        <div key={r.id} className="flex items-center justify-between p-2 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] text-xs gap-2">
                          <div className="min-w-0">
                            <div className="font-medium text-[#0F1F3A] truncate">{r.title}</div>
                            <div className="text-[10px] text-[#64748B] truncate">{fill(t("college_dashboard.generated_on"), { g: r.generated_at?.slice(0, 10) || "", d: r.data_as_of || "" })}</div>
                          </div>
                          <button type="button" onClick={() => download(r)} className="flex items-center gap-1 px-2.5 py-1 bg-[#2BB3A0] hover:bg-[#249B8A] text-white font-bold text-[10px] rounded flex-shrink-0 cursor-pointer" aria-label={`${t("college_dashboard.pdf")} ${r.title}`}>
                            <Download className="w-3 h-3" /><span>{t("college_dashboard.pdf")}</span>
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  <button type="button" onClick={generate} disabled={generating} className="w-full mt-1 py-2 border border-[#2B5CD0] text-[#2B5CD0] hover:bg-[#EFF6FF] font-bold text-xs rounded-lg flex items-center justify-center gap-1.5 disabled:opacity-50" data-testid="generate-report">
                    <Sparkles className="w-3.5 h-3.5" /> {generating ? t("college_dashboard.generating") : t("college_dashboard.generate")}
                  </button>
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
      </AppShell>
    </RoleGuard>
  );
}
