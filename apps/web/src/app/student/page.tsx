"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { Badge, Button, Card, CardHeader, EmptyState, ProgressBar, StatTile, buttonClass, type Tone } from "@/components/ui";
import { useLanguage } from "@/lib/LanguageContext";
import { TileDetails, type DetailKind } from "@/components/dashboard/TileDetails";
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

/** Where an upcoming item opens. Kinds without a student screen (guest talk, demo day) stay plain text. */
const EVENT_HREF: Record<string, string> = { test: "/student/tests", exam: "/student/tests", interview: "/student/interviews", drive: "/student/interviews" };

const BAND_TONE: Record<string, Tone> = { "Placement Ready": "success", "Nearly Ready": "warning", "Needs Support": "danger" };

/** Skill bars: brand blue, green when strong, amber when it needs work (same rule as readiness components). */
const skillTone = (pct: number): Tone => (pct < 60 ? "warning" : pct >= 80 ? "success" : "brand");

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

/** Readiness snapshots as bars. Each column has a fixed height so the bar's % height resolves (it collapsed to 0 before). */
function ScoreHistory({ history, readyMin, title }: { history: { date: string; score: number }[]; readyMin: number; title: string }) {
  const short = (d: string) => {
    const dt = new Date(d);
    return Number.isNaN(dt.getTime()) ? d : dt.toLocaleDateString(undefined, { day: "numeric", month: "short" });
  };
  return (
    <div data-testid="score-history">
      <div className="text-xs font-semibold text-ink mb-2 flex items-center gap-1"><TrendingUp className="w-3.5 h-3.5 text-brand" /> {title}</div>
      <div className="relative">
        <div className="absolute inset-x-0 border-t border-dashed border-success-line" style={{ bottom: `${readyMin}%` }} aria-hidden="true" />
        <div className="flex items-end gap-1.5 h-28">
          {history.map((h) => (
            <div key={h.date} className="flex-1 h-full flex flex-col justify-end items-center min-w-0" title={`${h.date}: ${h.score}`}>
              <span className="text-caption text-ink-soft tabular mb-0.5">{h.score}</span>
              <div className={`w-full max-w-10 rounded-t ${h.score >= readyMin ? "bg-success-fill" : "bg-brand"}`}
                style={{ height: `${Math.max(2, Math.min(100, h.score))}%` }} data-testid="score-bar" />
            </div>
          ))}
        </div>
      </div>
      <div className="flex gap-1.5 mt-1">
        {history.map((h) => <span key={h.date} className="flex-1 text-center text-caption text-muted truncate">{short(h.date)}</span>)}
      </div>
    </div>
  );
}

export default function StudentDashboardPage() {
  const { t, language } = useLanguage();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [whyOpen, setWhyOpen] = useState(false);
  const [why, setWhy] = useState<WhyScore | null>(null);
  const [whyLoading, setWhyLoading] = useState(false);
  const [detail, setDetail] = useState<DetailKind | null>(null);

  // only the latest request may set state: a slower reply for the old language must not overwrite the new one
  const latest = useRef(0);
  const load = useCallback(async () => {
    const req = ++latest.current;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchApi<DashboardData>(`/student/dashboard?lang=${language}`);
      if (req === latest.current) setData(res);
    } catch (err: any) {
      if (req === latest.current) setError(err?.detail || err?.message || "error");
    } finally {
      if (req === latest.current) setLoading(false);
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

  const tile = "bg-surface p-5 rounded-card border border-line shadow-card min-w-0";

  return (
    <RoleGuard allowedRoles={["student", "trainer"]}>
      <AppShell pageTitle={t("dashboard.title")}>
        <div className="space-y-6 max-w-7xl" data-testid="student-dashboard">
          {loading && (
            <div className="space-y-6 animate-pulse" aria-busy="true" aria-label={t("dashboard.loading")}>
              <div className="h-8 w-64 bg-surface rounded-tile" />
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {[1, 2, 3, 4].map((i) => <div key={i} className="h-32 bg-surface rounded-card border border-line" />)}
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="h-64 bg-surface rounded-card border border-line" />
                <div className="h-64 bg-surface rounded-card border border-line" />
              </div>
            </div>
          )}

          {!loading && error && (
            <Card className="text-center space-y-3 max-w-md mx-auto border-danger-line">
              <AlertCircle className="w-8 h-8 text-danger mx-auto" />
              <h2 className="text-heading font-semibold text-ink">{t("dashboard.error_title")}</h2>
              <p className="text-body text-muted">{error}</p>
              <Button onClick={load}><RefreshCw className="w-4 h-4" /> {t("dashboard.retry")}</Button>
            </Card>
          )}

          {!loading && !error && data && (
            <>
              {/* Greeting */}
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="text-heading font-semibold text-ink">{data.student.greeting}</h2>
                  <p className="text-label text-muted mt-0.5">
                    {t("dashboard.semester")} {data.student.semester} · {data.student.track}{data.student.week_label ? ` · ${data.student.week_label}` : ""}
                  </p>
                </div>
                <Link href="/student/coding" className={buttonClass("primary", "md")}>
                  <span>{t("dashboard.resume_practice")}</span>
                  <ArrowRight className="w-4 h-4" />
                </Link>
              </div>

              {/* Row 1: four KPI cards (PDF 2) */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <button type="button" onClick={openWhy} data-testid="readiness-card"
                  className={`${tile} text-left hover:border-brand transition-colors cursor-pointer`}>
                  <div className="flex items-center justify-between gap-2 text-label font-medium text-muted">
                    <span>{t("dashboard.readiness_score")}</span>
                    {data.student.has_snapshot && <Badge tone={BAND_TONE[data.student.readiness_band] ?? "neutral"}>{bandLabel(data.student.readiness_band)}</Badge>}
                  </div>
                  {data.student.has_snapshot ? (
                    <>
                      <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-kpi font-semibold text-ink tabular">{data.student.readiness_score}<span className="text-heading text-muted font-normal">/100</span></span>
                        <span className={`text-label font-medium ${data.student.readiness_delta >= 0 ? "text-success" : "text-danger"}`}>
                          {data.student.readiness_delta >= 0 ? "+" : ""}{data.student.readiness_delta} {t("dashboard.this_month")}
                        </span>
                      </div>
                      <div className="mt-1.5 text-label text-brand flex items-center gap-1 font-medium">
                        <Info className="w-4 h-4" /> {t("dashboard.why_score")}
                      </div>
                    </>
                  ) : (
                    <div className="mt-2 text-label text-muted">{t("dashboard.empty_desc")}</div>
                  )}
                </button>

                <button type="button" onClick={() => setDetail("problems")} className="text-left rounded-card hover:ring-1 hover:ring-brand" data-testid="tile-problems">
                <StatTile label={t("dashboard.problems_solved")}
                  value={<span className="flex items-baseline gap-2">
                    {data.student.problems_solved}
                    {data.student.problems_delta > 0 && <span className="text-label font-medium text-success">▲ {data.student.problems_delta} {t("dashboard.this_month")}</span>}
                  </span>}
                  hint={<span className="flex items-center gap-1"><CheckCircle2 className="w-4 h-4 text-brand" /> {t("dashboard.by_topic")}</span>} />
                </button>

                <div className={tile}>
                  <div className="flex items-center justify-between gap-2 text-label font-medium text-muted">
                    <span>{t("dashboard.attendance")}</span>
                    <Badge tone={data.student.attendance_pct >= data.student.attendance_target ? "success" : "warning"}>
                      {data.student.attendance_pct >= data.student.attendance_target ? t("dashboard.on_track") : t("dashboard.below_target")}
                    </Badge>
                  </div>
                  <div className="mt-2 flex items-baseline gap-2">
                    <span className="text-kpi font-semibold text-ink tabular">{data.student.attendance_pct}%</span>
                    <span className="text-label text-muted">{t("dashboard.target")} {data.student.attendance_target}%</span>
                  </div>
                  <div className="mt-1.5 text-label text-muted flex items-center gap-1">
                    <Calendar className="w-4 h-4 text-teal" />
                    {fill(t("dashboard.sessions_attended"), { a: data.student.sessions_attended, b: data.student.sessions_total })}
                  </div>
                </div>

                <button type="button" onClick={() => setDetail("streak")} className="text-left rounded-card hover:ring-1 hover:ring-brand" data-testid="tile-streak">
                <StatTile label={t("dashboard.practice_streak")}
                  value={`🔥 ${data.student.streak_days} ${t("dashboard.days")}`}
                  hint={<span className="flex items-center gap-1"><Flame className="w-4 h-4 text-warning-fill" /> {t("dashboard.best")}: {data.student.streak_best} {t("dashboard.days")}</span>} />
                </button>
              </div>

              {/* Row 2: skills + this week */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card>
                  <CardHeader title={t("dashboard.skill_progress")} subtitle={`${t("dashboard.semester")} ${data.student.semester}`}
                    actions={<button type="button" onClick={() => setDetail("skills")} className="text-label font-medium text-brand hover:underline" data-testid="open-skill-how">{t("dashboard.how_skills_grow")}</button>} />
                  <div className="space-y-4" data-testid="skill-progress">
                    {data.skill_progress.map((item) => (
                      <div key={item.key}>
                        <div className="flex justify-between gap-3 text-body mb-1.5">
                          <span className="text-ink">{item.skill}</span>
                          <span className="text-ink font-medium tabular">{item.percentage}%</span>
                        </div>
                        <ProgressBar value={item.percentage} tone={skillTone(item.percentage)} label={item.skill} />
                      </div>
                    ))}
                  </div>
                </Card>

                <Card>
                  <CardHeader title={t("dashboard.this_week")} subtitle={data.student.week_label} />
                  {data.this_week.length === 0 ? (
                    <EmptyState title={t("dashboard.no_sessions")} />
                  ) : (
                    <ul className="divide-y divide-line-soft -my-2" data-testid="this-week">
                      {data.this_week.map((row) => (
                        <li key={row.id}>
                          <Link href="/student/live" className="flex items-center justify-between gap-3 py-2.5 group">
                            <div className="flex items-center gap-3 min-w-0">
                              <span className="w-11 text-center text-label font-medium text-ink-soft bg-surface-2 py-1 rounded-tile border border-line flex-shrink-0">{row.day}</span>
                              <span className="text-body text-ink truncate group-hover:text-brand">{row.topic}</span>
                            </div>
                            <Badge tone={row.is_lab ? "violet" : "brand"} className="flex-shrink-0">{row.duration}</Badge>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>
              </div>

              {/* Row 3: project, upcoming, badges */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <Card className="flex flex-col">
                  <CardHeader title={t("dashboard.current_project")}
                    actions={data.current_project ? <Badge tone="violet">{data.current_project.progress_pct}% {t("dashboard.complete")}</Badge> : undefined} />
                  <div className="flex-1">
                    {data.current_project ? (
                      <>
                        <div className="text-body font-medium text-ink">{data.current_project.title}</div>
                        <p className="text-label text-muted mt-0.5">{data.current_project.subtitle}</p>
                        <ProgressBar value={data.current_project.progress_pct} tone="brand" className="mt-4" />
                        <div className="text-label text-muted mt-2">
                          {fill(t("dashboard.tasks_open"), { n: data.current_project.open_tasks })}
                          {data.current_project.pending_prs > 0 && ` · ${fill(t("dashboard.prs_pending"), { n: data.current_project.pending_prs })}`}
                        </div>
                      </>
                    ) : (
                      <EmptyState title={t("dashboard.no_project")} />
                    )}
                  </div>
                  <Link href="/student/projects/board" className="mt-4 text-body font-medium text-brand hover:underline underline-offset-2 inline-flex items-center gap-1">
                    <span>{t("dashboard.open_board")}</span><ExternalLink className="w-4 h-4" />
                  </Link>
                </Card>

                <Card>
                  <CardHeader title={t("dashboard.upcoming")} actions={<Clock className="w-4 h-4 text-subtle" />} />
                  {data.upcoming_events.length === 0 ? (
                    <EmptyState title={t("dashboard.no_upcoming")} />
                  ) : (
                    <ul className="divide-y divide-line-soft -my-2" data-testid="upcoming-events">
                      {data.upcoming_events.map((e) => {
                        const href = EVENT_HREF[e.kind];
                        const inner = (<>
                          <span className={`text-body text-ink truncate ${href ? "group-hover:text-brand" : ""}`}>{e.title}</span>
                          <span className={`${kindChipClass(e.kind)} flex-shrink-0`}>{e.date}</span>
                        </>);
                        return (
                          <li key={e.id}>
                            {href
                              ? <Link href={href} className="flex items-center justify-between gap-3 py-2.5 group">{inner}</Link>
                              : <div className="flex items-center justify-between gap-3 py-2.5">{inner}</div>}
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </Card>

                <Card>
                  <CardHeader title={t("dashboard.badges_earned")}
                    actions={<button type="button" onClick={() => setDetail("badges")} className="text-label font-medium text-brand hover:underline inline-flex items-center gap-1" data-testid="open-all-badges"><Award className="w-4 h-4 text-teal" />{t("dashboard.all_badges")}</button>} />
                  {data.badges.length === 0 ? (
                    <EmptyState title={t("dashboard.no_badges")} />
                  ) : (
                    <>
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 rounded-card bg-gradient-to-tr from-teal to-brand flex items-center justify-center text-white text-xl flex-shrink-0">{data.badges[0].icon}</div>
                        <div className="min-w-0">
                          <div className="text-caption text-muted">{t("dashboard.latest")}</div>
                          <div className="text-body font-medium text-ink">{data.badges[0].name}</div>
                          <div className="text-label text-muted">{data.badges[0].description}</div>
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2 pt-4">
                        {data.badges.slice(1).map((b) => (
                          <span key={b.id} title={`${b.name} – ${b.description}`} className="w-8 h-8 rounded-tile bg-surface-2 border border-line flex items-center justify-center text-body">{b.icon}</span>
                        ))}
                      </div>
                    </>
                  )}
                </Card>
              </div>
            </>
          )}
        </div>

        {detail && <TileDetails kind={detail} onClose={() => setDetail(null)} t={t} lang={language} />}

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
                  {why.history.length > 0 && <ScoreHistory history={why.history} readyMin={why.thresholds.ready_min} title={t("dashboard.history")} />}
                </>
              )}
            </div>
          </div>
        )}
      </AppShell>
    </RoleGuard>
  );
}
