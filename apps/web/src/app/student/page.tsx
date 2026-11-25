"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { fetchApi } from "@/lib/api";
import {
  TrendingUp, Award, Flame, CheckCircle2, Calendar, ArrowRight, Clock,
  ExternalLink, AlertCircle, RefreshCw, Info, X, Sparkles
} from "lucide-react";

interface SkillRow { key: string; skill: string; percentage: number; color: string }
interface WeekRow { id: string; day: string; topic: string; duration: string; type: string; status: string; is_lab: boolean }
interface EventRow { id: string; title: string; kind: string; date: string; starts_at: string }
interface BadgeRow { id: string; name: string; description: string; icon: string; earned_on?: string | null }
interface DashboardData {
  student: {
    id: string; name: string; greeting: string; semester: number; branch: string; batch: string; track: string;
    week_label: string; readiness_score: number; readiness_band: string; readiness_delta: number; has_snapshot: boolean;
    snapshot_date?: string | null; problems_solved: number; problems_delta: number; attendance_pct: number;
    attendance_target: number; sessions_attended: number; sessions_total: number; streak_days: number; streak_best: number;
  };
  skill_progress: SkillRow[];
  this_week: WeekRow[];
  current_project: { id: string; title: string; subtitle: string; progress_pct: number; open_tasks: number; pending_prs: number } | null;
  upcoming_events: EventRow[];
  badges: BadgeRow[];
  config: { ready_min: number; nearly_min: number };
}
interface WhyScore {
  score: number; band: string; snapshot_date?: string | null;
  thresholds: { ready_min: number; nearly_min: number };
  components: { key: string; label: string; value: number; weight: number; contribution: number }[];
  history: { date: string; score: number }[];
}

const COLOR_HEX: Record<string, string> = { teal: "#2BB3A0", blue: "#2B5CD0", purple: "#7C5CE0", orange: "#F59E0B", green: "#15803D" };

function fill(template: string, vars: Record<string, string | number>) {
  return Object.entries(vars).reduce((acc, [k, v]) => acc.replace(`{${k}}`, String(v)), template);
}

function bandChipClass(band: string) {
  if (band === "Placement Ready") return "chip-green";
  if (band === "Nearly Ready") return "chip-amber";
  return "chip-red";
}

function kindChipClass(kind: string) {
  if (kind === "test") return "chip-amber";
  if (kind === "interview") return "chip-blue";
  if (kind === "exam") return "chip-purple";
  return "chip-green";
}

export default function StudentDashboardPage() {
  const { t, language } = useLanguage();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [whyOpen, setWhyOpen] = useState(false);
  const [why, setWhy] = useState<WhyScore | null>(null);
  const [whyLoading, setWhyLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchApi<DashboardData>(`/student/dashboard?lang=${language}`);
      setData(res);
    } catch (err: any) {
      setError(err?.detail || err?.message || "error");
    } finally {
      setLoading(false);
    }
  }, [language]);

  useEffect(() => { load(); }, [load]);

  const openWhy = async () => {
    setWhyOpen(true);
    if (why) return;
    setWhyLoading(true);
    try {
      setWhy(await fetchApi<WhyScore>(`/student/dashboard/why-score?lang=${language}`));
    } catch {
      setWhy(null);
    } finally {
      setWhyLoading(false);
    }
  };

  const bandLabel = (band: string) => {
    if (band === "Placement Ready") return t("dashboard.band_placement_ready");
    if (band === "Nearly Ready") return t("dashboard.band_nearly_ready");
    return t("dashboard.band_needs_support");
  };

  const card = "bg-white p-4 rounded-card border border-line shadow-card";

  return (
    <RoleGuard allowedRoles={["student", "trainer"]}>
      <AppShell pageTitle={t("dashboard.title")}>
        <div className="space-y-6 max-w-7xl mx-auto" data-testid="student-dashboard">
          {loading && (
            <div className="space-y-6 animate-pulse" aria-busy="true" aria-label={t("dashboard.loading")}>
              <div className="h-8 w-64 bg-white rounded-tile" />
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {[1, 2, 3, 4].map((i) => <div key={i} className="h-28 bg-white rounded-card border border-line" />)}
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="h-64 bg-white rounded-card border border-line" />
                <div className="h-64 bg-white rounded-card border border-line" />
              </div>
            </div>
          )}

          {!loading && error && (
            <div className="bg-white rounded-card border border-danger-line p-8 text-center space-y-3 max-w-md mx-auto">
              <AlertCircle className="w-8 h-8 text-danger mx-auto" />
              <h2 className="text-base font-semibold text-ink">{t("dashboard.error_title")}</h2>
              <p className="text-xs text-muted">{error}</p>
              <button onClick={load} className="inline-flex items-center gap-1.5 px-4 py-2 bg-brand text-white text-xs font-semibold rounded-tile">
                <RefreshCw className="w-3.5 h-3.5" /> {t("dashboard.retry")}
              </button>
            </div>
          )}

          {!loading && !error && data && (
            <>
              {/* Greeting */}
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-xl font-semibold text-ink">{data.student.greeting}</h2>
                  <p className="text-xs text-muted mt-0.5">
                    {t("dashboard.semester")} {data.student.semester} · {data.student.track}{data.student.week_label ? ` · ${data.student.week_label}` : ""}
                  </p>
                </div>
                <Link href="/student/coding/prob_connected_components" className="flex items-center gap-1.5 px-3 py-1.5 bg-brand hover:bg-brand-hover text-white text-xs font-semibold rounded-tile shadow-card">
                  <span>{t("dashboard.resume_practice")}</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>

              {/* Row 1: four KPI cards (PDF 2) */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <button type="button" onClick={openWhy} data-testid="readiness-card" className={`${card} text-left space-y-2 hover:border-brand focus:outline-none focus-visible:ring-2 focus-visible:ring-brand cursor-pointer`}>
                  <div className="flex items-center justify-between text-xs text-muted font-medium">
                    <span>{t("dashboard.readiness_score")}</span>
                    {data.student.has_snapshot && <span className={bandChipClass(data.student.readiness_band)}>{bandLabel(data.student.readiness_band)}</span>}
                  </div>
                  {data.student.has_snapshot ? (
                    <>
                      <div className="flex items-baseline gap-2">
                        <span className="text-3xl font-semibold text-ink">{data.student.readiness_score}<span className="text-base text-muted">/100</span></span>
                        <span className={`text-xs font-semibold ${data.student.readiness_delta >= 0 ? "text-success" : "text-danger"}`}>
                          {data.student.readiness_delta >= 0 ? "+" : ""}{data.student.readiness_delta} {t("dashboard.this_month")}
                        </span>
                      </div>
                      <div className="text-caption text-brand flex items-center gap-1 font-semibold">
                        <Info className="w-3 h-3" /> {t("dashboard.why_score")}
                      </div>
                    </>
                  ) : (
                    <div className="text-xs text-muted">{t("dashboard.empty_desc")}</div>
                  )}
                </button>

                <div className={`${card} space-y-2`}>
                  <div className="text-xs text-muted font-medium">{t("dashboard.problems_solved")}</div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-semibold text-ink">{data.student.problems_solved}</span>
                    {data.student.problems_delta > 0 && <span className="text-xs font-semibold text-success">▲ {data.student.problems_delta} {t("dashboard.this_month")}</span>}
                  </div>
                  <div className="text-caption text-muted flex items-center gap-1"><CheckCircle2 className="w-3 h-3 text-brand" /> {data.student.batch}</div>
                </div>

                <div className={`${card} space-y-2`}>
                  <div className="flex items-center justify-between text-xs text-muted font-medium">
                    <span>{t("dashboard.attendance")}</span>
                    <span className={data.student.attendance_pct >= data.student.attendance_target ? "chip-green" : "chip-amber"}>
                      {data.student.attendance_pct >= data.student.attendance_target ? t("dashboard.on_track") : t("dashboard.below_target")}
                    </span>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-semibold text-ink">{data.student.attendance_pct}%</span>
                    <span className="text-xs text-muted">{t("dashboard.target")} {data.student.attendance_target}%</span>
                  </div>
                  <div className="text-caption text-muted flex items-center gap-1">
                    <Calendar className="w-3 h-3 text-teal" />
                    {fill(t("dashboard.sessions_attended"), { a: data.student.sessions_attended, b: data.student.sessions_total })}
                  </div>
                </div>

                <div className={`${card} space-y-2`}>
                  <div className="text-xs text-muted font-medium">{t("dashboard.practice_streak")}</div>
                  <div className="text-3xl font-semibold text-ink">🔥 {data.student.streak_days} {t("dashboard.days")}</div>
                  <div className="text-caption text-muted flex items-center gap-1"><Flame className="w-3 h-3 text-warning-fill" /> {t("dashboard.best")}: {data.student.streak_best} {t("dashboard.days")}</div>
                </div>
              </div>

              {/* Row 2: skills + this week */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-white p-5 rounded-card border border-line shadow-card space-y-4">
                  <div className="flex items-center justify-between border-b border-line pb-3">
                    <h3 className="font-semibold text-sm text-ink">{t("dashboard.skill_progress")}</h3>
                    <span className="text-caption font-semibold text-muted">{t("dashboard.semester")} {data.student.semester}</span>
                  </div>
                  <div className="space-y-3.5" data-testid="skill-progress">
                    {data.skill_progress.map((item) => (
                      <div key={item.key} className="space-y-1">
                        <div className="flex justify-between text-xs font-semibold">
                          <span className="text-ink">{item.skill}</span>
                          <span className="text-muted">{item.percentage}%</span>
                        </div>
                        <div className="w-full bg-line-soft rounded-full h-2 overflow-hidden" role="progressbar" aria-valuenow={item.percentage} aria-valuemin={0} aria-valuemax={100} aria-label={item.skill}>
                          <div className="h-full rounded-full transition-all duration-500" style={{ width: `${item.percentage}%`, backgroundColor: COLOR_HEX[item.color] || COLOR_HEX.teal }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-white p-5 rounded-card border border-line shadow-card space-y-4">
                  <div className="flex items-center justify-between border-b border-line pb-3">
                    <h3 className="font-semibold text-sm text-ink">{t("dashboard.this_week")}</h3>
                    <span className="text-caption font-semibold text-muted">{data.student.week_label}</span>
                  </div>
                  {data.this_week.length === 0 ? (
                    <p className="text-xs text-muted py-6 text-center">{t("dashboard.no_sessions")}</p>
                  ) : (
                    <div className="space-y-2.5" data-testid="this-week">
                      {data.this_week.map((row) => (
                        <Link key={row.id} href="/student/live" className="flex items-center justify-between p-2.5 rounded-tile bg-surface-2 border border-line hover:bg-line-soft transition-all">
                          <div className="flex items-center gap-3 min-w-0">
                            <span className="w-10 text-center font-semibold text-xs text-ink bg-white py-1 rounded border border-line flex-shrink-0">{row.day}</span>
                            <span className="text-xs font-medium text-ink truncate">{row.topic}</span>
                          </div>
                          <span className={`text-caption font-semibold px-2 py-0.5 rounded-full flex-shrink-0 ${row.is_lab ? "bg-violet-soft text-violet" : "bg-brand-soft text-info"}`}>{row.duration}</span>
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Row 3: project, upcoming, badges */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-white p-5 rounded-card border border-line shadow-card space-y-3 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between text-xs text-muted font-medium mb-1">
                      <span>{t("dashboard.current_project")}</span>
                      {data.current_project && <span className="chip-purple">{data.current_project.progress_pct}% {t("dashboard.complete")}</span>}
                    </div>
                    {data.current_project ? (
                      <>
                        <h4 className="font-semibold text-sm text-ink">{data.current_project.title}</h4>
                        <p className="text-xs text-muted mt-0.5">{data.current_project.subtitle}</p>
                        <div className="mt-4 space-y-1.5">
                          <div className="w-full bg-line-soft rounded-full h-2"><div className="h-full bg-teal rounded-full" style={{ width: `${data.current_project.progress_pct}%` }} /></div>
                          <div className="text-caption text-muted pt-1">
                            {fill(t("dashboard.tasks_open"), { n: data.current_project.open_tasks })}
                            {data.current_project.pending_prs > 0 && ` · ${fill(t("dashboard.prs_pending"), { n: data.current_project.pending_prs })}`}
                          </div>
                        </div>
                      </>
                    ) : (
                      <p className="text-xs text-muted py-4">{t("dashboard.no_project")}</p>
                    )}
                  </div>
                  <Link href="/student/projects/board" className="text-xs font-semibold text-brand hover:underline flex items-center gap-1 pt-2">
                    <span>{t("dashboard.open_board")}</span><ExternalLink className="w-3 h-3" />
                  </Link>
                </div>

                <div className="bg-white p-5 rounded-card border border-line shadow-card space-y-3">
                  <div className="flex items-center justify-between text-xs text-muted font-medium border-b border-line pb-2">
                    <span>{t("dashboard.upcoming")}</span><Clock className="w-3.5 h-3.5 text-muted" />
                  </div>
                  {data.upcoming_events.length === 0 ? (
                    <p className="text-xs text-muted py-4 text-center">{t("dashboard.no_upcoming")}</p>
                  ) : (
                    <div className="space-y-2.5" data-testid="upcoming-events">
                      {data.upcoming_events.map((e) => (
                        <div key={e.id} className="flex items-center justify-between text-xs gap-2">
                          <span className="font-semibold text-ink truncate">{e.title}</span>
                          <span className={`${kindChipClass(e.kind)} flex-shrink-0`}>{e.date}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="bg-white p-5 rounded-card border border-line shadow-card space-y-3">
                  <div className="flex items-center justify-between text-xs text-muted font-medium border-b border-line pb-2">
                    <span>{t("dashboard.badges_earned")}</span><Award className="w-3.5 h-3.5 text-teal" />
                  </div>
                  {data.badges.length === 0 ? (
                    <p className="text-xs text-muted py-4 text-center">{t("dashboard.no_badges")}</p>
                  ) : (
                    <>
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 rounded-card bg-gradient-to-tr from-teal to-brand flex items-center justify-center text-white text-xl shadow-pop">{data.badges[0].icon}</div>
                        <div>
                          <div className="text-caption text-muted font-semibold">{t("dashboard.latest")}</div>
                          <div className="text-xs font-semibold text-ink">{data.badges[0].name}</div>
                          <div className="text-caption text-muted">{data.badges[0].description}</div>
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2 pt-1">
                        {data.badges.slice(1).map((b) => (
                          <span key={b.id} title={`${b.name} – ${b.description}`} className="w-7 h-7 rounded-tile bg-line-soft border border-line flex items-center justify-center text-xs">{b.icon}</span>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Why this score drawer */}
        {whyOpen && (
          <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label={t("dashboard.why_title")}>
            <button type="button" className="absolute inset-0 bg-black/40" onClick={() => setWhyOpen(false)} aria-label={t("dashboard.close")} />
            <div className="relative w-full max-w-md bg-white h-full shadow-pop p-6 overflow-y-auto space-y-4" data-testid="why-score-drawer">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-base font-semibold text-ink flex items-center gap-2"><Sparkles className="w-4 h-4 text-teal" /> {t("dashboard.why_title")}</h3>
                  <p className="text-xs text-muted mt-1">{t("dashboard.why_desc")}</p>
                </div>
                <button onClick={() => setWhyOpen(false)} className="p-1.5 rounded-tile hover:bg-line-soft" aria-label={t("dashboard.close")}><X className="w-4 h-4 text-muted" /></button>
              </div>
              {whyLoading && <div className="h-40 bg-line-soft rounded-card animate-pulse" />}
              {!whyLoading && why && (
                <>
                  <div className="flex items-baseline gap-3">
                    <span className="text-4xl font-semibold text-ink">{why.score}</span>
                    <span className={bandChipClass(why.band)}>{bandLabel(why.band)}</span>
                  </div>
                  <p className="text-caption text-muted">{fill(t("dashboard.bands"), { ready: why.thresholds.ready_min, nearly: why.thresholds.nearly_min })}{why.snapshot_date ? ` · ${fill(t("dashboard.snapshot_as_of"), { date: why.snapshot_date })}` : ""}</p>
                  <table className="w-full text-xs">
                    <thead><tr className="text-muted text-caption border-b border-line">
                      <th className="text-left pb-2 font-semibold">{t("dashboard.component")}</th>
                      <th className="text-right pb-2 font-semibold">{t("dashboard.value")}</th>
                      <th className="text-right pb-2 font-semibold">{t("dashboard.weight")}</th>
                      <th className="text-right pb-2 font-semibold">{t("dashboard.contribution")}</th>
                    </tr></thead>
                    <tbody className="divide-y divide-line-soft">
                      {why.components.map((c) => (
                        <tr key={c.key}>
                          <td className="py-2 font-semibold text-ink">{c.label}</td>
                          <td className="py-2 text-right text-muted">{c.value}</td>
                          <td className="py-2 text-right text-muted">{Math.round(c.weight * 100)}%</td>
                          <td className="py-2 text-right font-semibold text-ink">{c.contribution.toFixed(1)}</td>
                        </tr>
                      ))}
                      <tr className="border-t border-line">
                        <td className="py-2 font-semibold text-ink" colSpan={3}>{t("dashboard.total")}</td>
                        <td className="py-2 text-right font-semibold text-teal">{why.score}</td>
                      </tr>
                    </tbody>
                  </table>
                  {why.history.length > 1 && (
                    <div>
                      <div className="text-xs font-semibold text-ink mb-2 flex items-center gap-1"><TrendingUp className="w-3.5 h-3.5 text-brand" /> {t("dashboard.history")}</div>
                      <div className="flex items-end gap-1.5 h-20">
                        {why.history.map((h) => (
                          <div key={h.date} className="flex-1 flex flex-col items-center gap-1" title={`${h.date}: ${h.score}`}>
                            <div className="w-full bg-brand/80 rounded-t" style={{ height: `${h.score}%` }} />
                            <span className="text-caption text-muted">{h.score}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        )}
      </AppShell>
    </RoleGuard>
  );
}
