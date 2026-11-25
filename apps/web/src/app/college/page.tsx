"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { Badge, Button, Card, CardHeader, EmptyState, Select, StatTile, Table, THead, Th, Tr, Td, type Tone } from "@/components/ui";
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

// chart colours match the status fills in globals.css (recharts needs literal values)
const BAND_HEX: Record<string, string> = { green: "#1F9D6B", amber: "#E6A23C", red: "#E05252" };
const BAND_TONE: Record<string, Tone> = { green: "success", amber: "warning", red: "danger" };
const BLUES = ["#BFDBFE", "#93C5FD", "#60A5FA", "#3B82F6", "#2B5CD0", "#1E40AF"];
const AXIS = "#64748B";
const GRID = "#E2E8F0";

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

  // only the latest request may set state: a slower reply for the old language must not overwrite the new one
  const latest = useRef(0);
  const load = useCallback(async () => {
    const req = ++latest.current;
    setLoading(true);
    setError(null);
    try {
      const q = semester ? `&semester=${semester}` : "";
      const res = await fetchApi<Overview>(`/college/overview?lang=${language}${q}`);
      if (req === latest.current) setData(res);
    } catch (err: any) {
      if (req === latest.current) setError(err?.detail || err?.message || "error");
    } finally {
      if (req === latest.current) setLoading(false);
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

  const semesterLabel = semester ? `${t("college_dashboard.semester_filter")} ${semester}` : t("college_dashboard.all_semesters");
  const filter = (
    <div className="flex items-center gap-2">
      <label className="text-label font-medium text-muted" htmlFor="semester-filter">{t("college_dashboard.semester_filter")}</label>
      <Select id="semester-filter" value={semester} onChange={(e) => setSemester(e.target.value)} data-testid="semester-filter">
        <option value="">{t("college_dashboard.all_semesters")}</option>
        {(data?.filters.semesters || [2, 3, 4, 5, 6, 7]).map((s) => <option key={s} value={s}>{t("college_dashboard.semester_filter")} {s}</option>)}
      </Select>
    </div>
  );

  return (
    <RoleGuard allowedRoles={["college"]}>
      <AppShell pageTitle={t("college_dashboard.title")} pageActions={filter}>
        <div className="space-y-6 max-w-7xl" data-testid="college-dashboard">
          {loading && (
            <div className="space-y-6 animate-pulse" aria-busy="true" aria-label={t("college_dashboard.loading")}>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">{[1, 2, 3, 4].map((i) => <div key={i} className="h-32 bg-surface rounded-card border border-line" />)}</div>
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6"><div className="lg:col-span-5 h-72 bg-surface rounded-card border border-line" /><div className="lg:col-span-7 h-72 bg-surface rounded-card border border-line" /></div>
            </div>
          )}

          {!loading && error && (
            <Card className="text-center space-y-3 max-w-md mx-auto border-danger-line">
              <AlertCircle className="w-8 h-8 text-danger mx-auto" />
              <h2 className="text-heading font-semibold text-ink">{t("college_dashboard.error_title")}</h2>
              <p className="text-body text-muted">{error}</p>
              <Button onClick={load}><RefreshCw className="w-4 h-4" /> {t("college_dashboard.retry")}</Button>
            </Card>
          )}

          {!loading && !error && data && (
            <>
              {/* Row 1 KPIs (PDF 9) */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="college-kpis">
                <StatTile label={t("college_dashboard.students_enrolled")} value={data.kpis.students_enrolled.value}
                  hint={fill(t("college_dashboard.sem_branches"), { s: data.kpis.students_enrolled.semesters, b: data.kpis.students_enrolled.branches })} />
                <StatTile label={t("college_dashboard.avg_attendance")} value={`${data.kpis.avg_attendance.value}%`}
                  hint={<span className={data.kpis.avg_attendance.above_target ? "text-success" : "text-danger"}>
                    {fill(t(data.kpis.avg_attendance.above_target ? "college_dashboard.above_target" : "college_dashboard.below_target"), { t: data.kpis.avg_attendance.target })}
                  </span>} />
                <StatTile label={t("college_dashboard.certifications")} value={data.kpis.certifications.value}
                  hint={<span className="text-success">{fill(t("college_dashboard.this_semester"), { n: data.kpis.certifications.this_semester })}</span>} />
                <StatTile label={t("college_dashboard.internships")} value={data.kpis.internships.value}
                  hint={fill(t("college_dashboard.sem6_pct"), { p: data.kpis.internships.sem6_pct })} />
              </div>

              {/* Row 2 donut + branch table */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                <Card className="lg:col-span-5" data-testid="readiness-donut">
                  <CardHeader title={t("college_dashboard.placement_readiness")} subtitle={semesterLabel} />
                  <div className="relative h-52 w-full flex items-center justify-center">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={data.readiness_distribution} cx="50%" cy="50%" innerRadius={62} outerRadius={86} paddingAngle={2} stroke="none" dataKey="count" nameKey="label">
                          {data.readiness_distribution.map((entry) => <Cell key={entry.band} fill={BAND_HEX[entry.color]} />)}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="absolute text-center pointer-events-none">
                      <div className="text-kpi font-semibold text-ink tabular">{data.readiness_total}</div>
                      <div className="text-caption text-muted">{t("college_dashboard.students")}</div>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center justify-center gap-2 pt-4">
                    {data.readiness_distribution.map((b) => <Badge key={b.band} tone={BAND_TONE[b.color] ?? "neutral"}>{b.label} {b.percentage}%</Badge>)}
                  </div>
                </Card>

                <Card padded={false} className="lg:col-span-7">
                  <CardHeader className="px-5 pt-5" title={t("college_dashboard.branch_readiness")}
                    subtitle={`${data.branch_readiness.length} ${t("college_dashboard.branch")}`} />
                  <Table data-testid="branch-table">
                    <THead>
                      <tr>
                        <Th>{t("college_dashboard.branch")}</Th>
                        <Th align="right">{t("college_dashboard.students")}</Th>
                        <Th align="right">{t("college_dashboard.attendance")}</Th>
                        <Th align="right">{t("college_dashboard.avg_score")}</Th>
                        <Th align="right">{t("college_dashboard.trend")}</Th>
                      </tr>
                    </THead>
                    <tbody>
                      {data.branch_readiness.map((b) => (
                        <Tr key={b.branch_id} className="hover:bg-surface-2">
                          <Td className="font-medium">{b.branch}</Td>
                          <Td align="right">{b.students}</Td>
                          <Td align="right">{b.attendance}%</Td>
                          <Td align="right" className="font-medium">{b.avg_score}</Td>
                          <Td align="right" className={`font-medium ${b.trend >= 0 ? "text-success" : "text-danger"}`}>{b.trend >= 0 ? "▲" : "▼"} {Math.abs(b.trend)}</Td>
                        </Tr>
                      ))}
                    </tbody>
                  </Table>
                </Card>
              </div>

              {/* Row 3 certifications chart, events, reports */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <Card>
                  <CardHeader title={t("college_dashboard.cumulative_certs")}
                    subtitle={data.cumulative_certifications.length > 0
                      ? `${data.cumulative_certifications[0].month} – ${data.cumulative_certifications[data.cumulative_certifications.length - 1].month}` : undefined} />
                  {data.cumulative_certifications.length === 0 ? (
                    <EmptyState title={t("college_dashboard.no_certs")} />
                  ) : (
                    <div className="h-48 w-full" data-testid="cert-chart">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={data.cumulative_certifications} margin={{ top: 4, right: 4, bottom: 0, left: -16 }}>
                          <XAxis dataKey="month" tick={{ fontSize: 12, fill: AXIS }} axisLine={{ stroke: GRID }} tickLine={false} />
                          <YAxis tick={{ fontSize: 12, fill: AXIS }} axisLine={false} tickLine={false} />
                          <Tooltip cursor={{ fill: "#F8FAFC" }} />
                          <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={36}>
                            {data.cumulative_certifications.map((entry, i) => <Cell key={`${entry.year}-${entry.month}`} fill={BLUES[Math.min(i, BLUES.length - 1)]} />)}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </Card>

                <Card>
                  <CardHeader title={t("college_dashboard.upcoming_events")} actions={<Calendar className="w-4 h-4 text-subtle" />} />
                  {data.upcoming_events.length === 0 ? (
                    <EmptyState title={t("college_dashboard.no_events")} />
                  ) : (
                    <ul className="divide-y divide-line-soft -my-2" data-testid="college-events">
                      {data.upcoming_events.map((e) => (
                        <li key={e.id} className="flex items-center justify-between gap-3 py-2.5">
                          <span className="text-body text-ink truncate">{e.title}</span>
                          <Badge tone="violet" className="flex-shrink-0">{e.date}</Badge>
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>

                <Card className="flex flex-col">
                  <CardHeader title={t("college_dashboard.mou_reports")} actions={<FileText className="w-4 h-4 text-subtle" />} />
                  {data.mou_reports.length === 0 ? (
                    <EmptyState title={t("college_dashboard.no_reports")} />
                  ) : (
                    <ul className="space-y-2" data-testid="mou-reports">
                      {data.mou_reports.map((r) => (
                        <li key={r.id} className="flex items-center justify-between gap-3 p-3 rounded-tile bg-surface-2 border border-line">
                          <div className="min-w-0">
                            <div className="text-body font-medium text-ink truncate">{r.title}</div>
                            <div className="text-caption text-muted truncate">{fill(t("college_dashboard.generated_on"), { g: r.generated_at?.slice(0, 10) || "", d: r.data_as_of || "" })}</div>
                          </div>
                          <Button size="sm" variant="secondary" onClick={() => download(r)} className="flex-shrink-0" aria-label={`${t("college_dashboard.pdf")} ${r.title}`}>
                            <Download className="w-4 h-4" /><span>{t("college_dashboard.pdf")}</span>
                          </Button>
                        </li>
                      ))}
                    </ul>
                  )}
                  <Button variant="secondary" onClick={generate} disabled={generating} className="w-full mt-4 text-brand" data-testid="generate-report">
                    <Sparkles className="w-4 h-4" /> {generating ? t("college_dashboard.generating") : t("college_dashboard.generate")}
                  </Button>
                </Card>
              </div>
            </>
          )}
        </div>
        {toast && (
          <div role="status" className="fixed bottom-6 right-6 z-50 bg-ink text-white text-body font-medium px-4 py-3 rounded-card shadow-pop flex items-center gap-2" data-testid="toast">
            <CheckCircle2 className="w-4 h-4 text-teal" /> {toast}
          </div>
        )}
      </AppShell>
    </RoleGuard>
  );
}
