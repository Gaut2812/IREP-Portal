"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { Badge, Button, Card, CardHeader, EmptyState, Field, Select, StatTile, Table, THead, Th, Tr, Td, buttonClass, inputClass, type Tone } from "@/components/ui";
import { useLanguage } from "@/lib/LanguageContext";
import { fetchApi } from "@/lib/api";
import { LabApprovalsCard } from "@/components/LabApprovalsCard";
import {
  Code2, ExternalLink, Filter, AlertCircle, RefreshCw, CheckCircle2, X, ArrowRight
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

const ACTION_TONE: Record<string, Tone | "info"> = { parent_call: "danger", extra_saturday: "warning", mentor: "info" };
const STATUS_TONE: Record<string, Tone | "info"> = { Done: "success", Next: "info", Live: "success", Later: "neutral" };
const DIFFICULTY_TONE: Record<string, Tone> = { Easy: "success", Medium: "warning", Hard: "danger" };
// chart colours match globals.css tokens (recharts needs literal values)
const READY = "#1F9D6B";
const BELOW = "#2B5CD0";
const INK = "#0F1F3A";
const AXIS = "#64748B";
const GRID = "#E2E8F0";

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

  // only the latest request may set state: a slower reply for the old language must not overwrite the new one
  const latest = useRef(0);
  const load = useCallback(async () => {
    const req = ++latest.current;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchApi<DashboardData>(`/trainer/dashboard?lang=${language}`);
      if (req === latest.current) setData(res);
    } catch (err: any) {
      if (req === latest.current) setError(err?.detail || err?.message || "error");
    } finally {
      if (req === latest.current) setLoading(false);
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
  const quickLabel = (key: string) => t(`trainer_dashboard.${key}`);
  const quickClass = (variant: string) =>
    variant === "blue" ? buttonClass("primary", "md", "w-full")
      : variant === "teal" ? buttonClass("primary", "md", "w-full bg-teal border-teal hover:bg-teal-hover")
        : buttonClass("secondary", "md", "w-full");

  return (
    <RoleGuard allowedRoles={["trainer"]}>
      <AppShell pageTitle={t("trainer_dashboard.title")}>
        <div className="space-y-6 max-w-7xl pb-10" data-testid="trainer-dashboard">
          {loading && (
            <div className="space-y-6 animate-pulse" aria-busy="true" aria-label={t("trainer_dashboard.loading")}>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">{[1, 2, 3, 4].map((i) => <div key={i} className="h-32 bg-surface rounded-card border border-line" />)}</div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6"><div className="h-72 bg-surface rounded-card border border-line" /><div className="h-72 bg-surface rounded-card border border-line" /></div>
            </div>
          )}

          {!loading && error && (
            <Card className="text-center space-y-3 max-w-md mx-auto border-danger-line">
              <AlertCircle className="w-8 h-8 text-danger mx-auto" />
              <h2 className="text-heading font-semibold text-ink">{t("trainer_dashboard.error_title")}</h2>
              <p className="text-body text-muted">{error}</p>
              <Button onClick={load}><RefreshCw className="w-4 h-4" /> {t("trainer_dashboard.retry")}</Button>
            </Card>
          )}

          {!loading && !error && data && (
            <>
              <LabApprovalsCard />

              {/* Row 1 KPI cards (PDF 8) */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="trainer-kpis">
                <StatTile label={t("trainer_dashboard.active_batches")} value={data.kpis.active_batches.value}
                  hint={fill(t(data.kpis.active_batches.colleges === 1 ? "trainer_dashboard.students_colleges" : "trainer_dashboard.students_colleges_plural"), { s: data.kpis.active_batches.students, c: data.kpis.active_batches.colleges })} />
                <StatTile label={t("trainer_dashboard.today_attendance")}
                  value={data.kpis.today_attendance.value === null ? undefined : (
                    <span className="flex items-baseline gap-2">
                      {data.kpis.today_attendance.value}%
                      {data.kpis.today_attendance.delta_vs_last_week !== null && (
                        <span className={`text-label font-medium ${data.kpis.today_attendance.delta_vs_last_week >= 0 ? "text-success" : "text-danger"}`}>
                          {data.kpis.today_attendance.delta_vs_last_week >= 0 ? "▲" : "▼"} {Math.abs(data.kpis.today_attendance.delta_vs_last_week)}% {t("trainer_dashboard.vs_last_week")}
                        </span>
                      )}
                    </span>
                  )}
                  hint={<>
                    {data.kpis.today_attendance.value === null && <span className="block text-body text-muted mt-2 mb-1">{t("trainer_dashboard.no_attendance")}</span>}
                    {fill(t("trainer_dashboard.sessions_today"), { n: data.kpis.today_attendance.sessions })} · {data.kpis.today_attendance.day}
                  </>} />
                <StatTile label={t("trainer_dashboard.pending_reviews")}
                  value={<span className="flex items-baseline gap-2">
                    {data.kpis.pending_code_reviews.value}
                    {data.kpis.pending_code_reviews.older_than_2_days > 0 ? (
                      <span className="text-label font-medium text-danger">{fill(t("trainer_dashboard.older_than"), { n: data.kpis.pending_code_reviews.older_than_2_days })}</span>
                    ) : (
                      <span className="text-label font-medium text-success">{t("trainer_dashboard.queue_clear")}</span>
                    )}
                  </span>}
                  hint={<Link href="/trainer/reviews" className="text-brand font-medium hover:underline underline-offset-2 inline-flex items-center gap-1">{t("trainer_dashboard.review_prs")}<ArrowRight className="w-4 h-4" aria-hidden /></Link>} />
                <StatTile label={t("trainer_dashboard.at_risk")} value={data.kpis.at_risk_students.value} tone="danger"
                  hint={fill(t("trainer_dashboard.parents_notified"), { n: data.kpis.at_risk_students.parents_notified })} />
              </div>

              {/* Row 2 chart + schedule */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card>
                  <CardHeader title={t("trainer_dashboard.batch_readiness")} subtitle={t("trainer_dashboard.average_semester")} />
                  <div className="h-56 w-full" data-testid="batch-readiness-chart">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={data.batch_readiness} margin={{ top: 20, right: 4, bottom: 0, left: -16 }}>
                        <XAxis dataKey="batch" tick={{ fontSize: 12, fill: AXIS }} axisLine={{ stroke: GRID }} tickLine={false} />
                        <YAxis domain={[0, 100]} tick={{ fontSize: 12, fill: AXIS }} axisLine={false} tickLine={false} />
                        <Tooltip cursor={{ fill: "#F8FAFC" }} />
                        <Bar dataKey="score" radius={[4, 4, 0, 0]} maxBarSize={48} label={{ position: "top", fontSize: 12, fill: INK }}>
                          {data.batch_readiness.map((entry) => <Cell key={entry.batch_id} fill={entry.score >= 75 ? READY : BELOW} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="flex items-center justify-center gap-4 text-caption text-muted pt-3">
                    <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-success-fill" /> {t("trainer_dashboard.legend_ready")}</span>
                    <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-brand" /> {t("trainer_dashboard.legend_below")}</span>
                  </div>
                </Card>

                <Card>
                  <CardHeader title={data.today_schedule.is_today ? t("trainer_dashboard.today_schedule") : t("trainer_dashboard.next_day_schedule")}
                    subtitle={data.today_schedule.label} />
                  {data.today_schedule.items.length === 0 ? (
                    <EmptyState title={t("trainer_dashboard.no_schedule")} />
                  ) : (
                    <ul className="divide-y divide-line-soft -my-2" data-testid="today-schedule">
                      {data.today_schedule.items.map((item) => (
                        <li key={item.id} className="flex items-center justify-between gap-3 py-3">
                          <div className="flex items-center gap-4 min-w-0">
                            <span className="w-16 text-label font-medium text-ink-soft tabular flex-shrink-0">{item.time}</span>
                            <div className="min-w-0">
                              <div className="text-body font-medium text-ink truncate">{item.topic}</div>
                              <div className="text-label text-muted">{item.batch}</div>
                            </div>
                          </div>
                          {item.can_enter ? (
                            <Link href={item.room} className={buttonClass("primary", "sm", "flex-shrink-0")}>{t("trainer_dashboard.enter_room")}</Link>
                          ) : (
                            <Badge tone={STATUS_TONE[item.status] ?? "neutral"} className="flex-shrink-0">{item.status_label}</Badge>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>
              </div>

              {/* Row 3 weekly DSA widget (Screen 24 integration) */}
              <Card padded={false} data-testid="trainer-dsa-widget">
                <CardHeader className="px-5 pt-5"
                  title={<span className="inline-flex items-center gap-2"><Code2 className="w-5 h-5 text-brand" />{t("trainer_dashboard.dsa_widget")}</span>}
                  actions={<>
                    <span className="text-label text-muted inline-flex items-center gap-1"><Filter className="w-4 h-4" /> {t("trainer_dashboard.dsa_week")}</span>
                    <Select value={selectedWeek} onChange={(e) => setSelectedWeek(e.target.value)} aria-label={t("trainer_dashboard.dsa_week")}>
                      <option value="All">{t("trainer_dashboard.dsa_all_weeks")}</option>
                      {[1, 2, 3, 4, 5, 6, 7, 8].map((w) => <option key={w} value={String(w)}>{fill(t("trainer_dashboard.dsa_week_n"), { n: w })}</option>)}
                    </Select>
                  </>} />
                <Table>
                  <THead>
                    <tr>
                      <Th>{t("trainer_dashboard.dsa_problem")}</Th><Th>{t("trainer_dashboard.dsa_schedule")}</Th>
                      <Th>{t("trainer_dashboard.dsa_topic")}</Th><Th>{t("trainer_dashboard.dsa_difficulty")}</Th>
                      <Th align="right">{t("trainer_dashboard.dsa_submissions")}</Th><Th align="right">{t("trainer_dashboard.dsa_solved")}</Th>
                      <Th align="right"><span className="sr-only">{t("trainer_dashboard.dsa_open")}</span></Th>
                    </tr>
                  </THead>
                  <tbody>
                    {loadingProblems ? (
                      <Tr><Td colSpan={7} className="text-center text-muted">…</Td></Tr>
                    ) : filteredProblems.length === 0 ? (
                      <Tr><Td colSpan={7}><EmptyState title={t("trainer_dashboard.dsa_none")} className="py-4" /></Td></Tr>
                    ) : filteredProblems.map((prob) => (
                      <Tr key={prob.id} className="hover:bg-surface-2">
                        <Td className="font-medium">{prob.title}</Td>
                        <Td className="text-muted">{prob.week_info}</Td>
                        <Td><Badge tone="info">{prob.topic}</Badge></Td>
                        <Td><Badge tone={DIFFICULTY_TONE[prob.difficulty] ?? "neutral"}>
                          {DIFFICULTY_TONE[prob.difficulty] ? t(`trainer_dashboard.dsa_${prob.difficulty.toLowerCase()}`) : prob.difficulty}
                        </Badge></Td>
                        <Td align="right">{prob.total_submissions}</Td>
                        <Td align="right" className="font-medium text-success">{prob.solved_percentage}%</Td>
                        <Td align="right">
                          <Link href={`/trainer/assessments?problem=${prob.id}`} className={buttonClass("secondary", "sm")}><span>{t("trainer_dashboard.dsa_open")}</span><ExternalLink className="w-3.5 h-3.5" /></Link>
                        </Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              </Card>

              {/* Row 4 support table + quick actions */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <Card padded={false} className="lg:col-span-2">
                  <CardHeader className="px-5 pt-5" title={t("trainer_dashboard.needing_support")}
                    subtitle={<span className="text-danger">{fill(t("trainer_dashboard.score_below"), { n: data.thresholds.score_below })}</span>} />
                  {data.students_needing_support.length === 0 ? (
                    <EmptyState title={t("trainer_dashboard.no_support")} />
                  ) : (
                    <Table data-testid="support-table">
                      <THead>
                        <tr>
                          <Th>{t("trainer_dashboard.student")}</Th><Th>{t("trainer_dashboard.batch")}</Th>
                          <Th align="right">{t("trainer_dashboard.score")}</Th><Th>{t("trainer_dashboard.issue")}</Th>
                          <Th align="right">{t("trainer_dashboard.action")}</Th>
                        </tr>
                      </THead>
                      <tbody>
                        {data.students_needing_support.map((st) => (
                          <Tr key={st.flag_id} className="hover:bg-surface-2">
                            <Td className="font-medium">{st.name}{st.parent_notified && <span className="ml-1.5 text-success" title={t("trainer_dashboard.notified")}>✓</span>}</Td>
                            <Td className="text-muted">{st.batch}</Td>
                            <Td align="right"><Badge tone="danger">{st.score}</Badge></Td>
                            <Td className="text-muted">{st.issue}</Td>
                            <Td align="right" className="whitespace-nowrap">
                              <button type="button" disabled={acting === st.flag_id} onClick={() => runAction(st)} data-testid="support-action"
                                className="cursor-pointer disabled:opacity-50 rounded-full focus-visible:ring-2 focus-visible:ring-brand">
                                <Badge tone={ACTION_TONE[st.action] ?? "info"}>{st.action_label}</Badge>
                              </button>
                              <button type="button" onClick={() => { setResolving(st); setResolveNote(""); }} className="ml-2 text-label text-muted hover:text-ink underline underline-offset-2" aria-label={`${t("trainer_dashboard.resolve")} ${st.name}`}>{t("trainer_dashboard.resolve")}</button>
                            </Td>
                          </Tr>
                        ))}
                      </tbody>
                    </Table>
                  )}
                </Card>

                <Card>
                  <CardHeader title={t("trainer_dashboard.quick_actions")} />
                  <div className="grid grid-cols-2 gap-2.5" data-testid="quick-actions">
                    {data.quick_actions.map((qa) => (
                      <Link key={qa.key} href={qa.href} className={quickClass(qa.variant)}>{quickLabel(qa.key)}</Link>
                    ))}
                  </div>
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

        {resolving && (
          <div className="fixed inset-0 bg-ink/50 flex items-center justify-center p-4 z-50" role="dialog" aria-modal="true">
            <div className="bg-surface rounded-card max-w-md w-full p-6 space-y-4 shadow-pop border border-line">
              <div className="flex items-center justify-between">
                <h3 className="text-heading font-semibold text-ink">{t("trainer_dashboard.resolve")} · {resolving.name}</h3>
                <button onClick={() => setResolving(null)} className="p-1.5 rounded-tile hover:bg-line-soft" aria-label={t("trainer_dashboard.cancel")}><X className="w-4 h-4 text-muted" /></button>
              </div>
              <Field label={t("trainer_dashboard.resolve_note")}>
                <textarea value={resolveNote} onChange={(e) => setResolveNote(e.target.value)} rows={3} className={`${inputClass} h-auto py-2`} data-testid="resolve-note" />
              </Field>
              <div className="flex gap-2">
                <Button variant="secondary" className="flex-1" onClick={() => setResolving(null)}>{t("trainer_dashboard.cancel")}</Button>
                <Button className="flex-1" onClick={submitResolve} disabled={!resolveNote.trim()}>{t("trainer_dashboard.resolve_confirm")}</Button>
              </div>
            </div>
          </div>
        )}
      </AppShell>
    </RoleGuard>
  );
}
