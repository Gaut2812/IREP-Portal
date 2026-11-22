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

  const card = "bg-white p-4 rounded-xl border border-[#E2E8F0] shadow-sm";

  return (
    <RoleGuard allowedRoles={["student", "trainer"]}>
      <AppShell pageTitle={t("dashboard.title")}>
        <div className="space-y-6 max-w-7xl mx-auto" data-testid="student-dashboard">
          {loading && (
            <div className="space-y-6 animate-pulse" aria-busy="true" aria-label={t("dashboard.loading")}>
              <div className="h-8 w-64 bg-white rounded-lg" />
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {[1, 2, 3, 4].map((i) => <div key={i} className="h-28 bg-white rounded-xl border border-[#E2E8F0]" />)}
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="h-64 bg-white rounded-xl border border-[#E2E8F0]" />
                <div className="h-64 bg-white rounded-xl border border-[#E2E8F0]" />
              </div>
            </div>
          )}

          {!loading && error && (
            <div className="bg-white rounded-2xl border border-[#FECACA] p-8 text-center space-y-3 max-w-md mx-auto">
              <AlertCircle className="w-8 h-8 text-[#D93636] mx-auto" />
              <h2 className="text-base font-bold text-[#0F1F3A]">{t("dashboard.error_title")}</h2>
              <p className="text-xs text-[#64748B]">{error}</p>
              <button onClick={load} className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg">
                <RefreshCw className="w-3.5 h-3.5" /> {t("dashboard.retry")}
              </button>
            </div>
          )}

          {!loading && !error && data && (
            <>
              {/* Greeting */}
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-xl font-bold text-[#0F1F3A]">{data.student.greeting}</h2>
                  <p className="text-xs text-[#64748B] mt-0.5">
                    {t("dashboard.semester")} {data.student.semester} · {data.student.track}{data.student.week_label ? ` · ${data.student.week_label}` : ""}
                  </p>
                </div>
                <Link href="/student/coding/prob_connected_components" className="flex items-center gap-1.5 px-3 py-1.5 bg-[#2B5CD0] hover:bg-[#1E46B0] text-white text-xs font-bold rounded-lg shadow-sm">
                  <span>{t("dashboard.resume_practice")}</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>

              {/* Row 1: four KPI cards (PDF 2) */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <button type="button" onClick={openWhy} data-testid="readiness-card" className={`${card} text-left space-y-2 hover:border-[#2B5CD0] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2B5CD0] cursor-pointer`}>
                  <div className="flex items-center justify-between text-xs text-[#64748B] font-medium">
                    <span>{t("dashboard.readiness_score")}</span>
                    {data.student.has_snapshot && <span className={bandChipClass(data.student.readiness_band)}>{bandLabel(data.student.readiness_band)}</span>}
                  </div>
                  {data.student.has_snapshot ? (
                    <>
                      <div className="flex items-baseline gap-2">
                        <span className="text-3xl font-black text-[#0F1F3A]">{data.student.readiness_score}<span className="text-base text-[#64748B]">/100</span></span>
                        <span className={`text-xs font-bold ${data.student.readiness_delta >= 0 ? "text-[#15803D]" : "text-[#D93636]"}`}>
                          {data.student.readiness_delta >= 0 ? "+" : ""}{data.student.readiness_delta} {t("dashboard.this_month")}
                        </span>
                      </div>
                      <div className="text-[11px] text-[#2B5CD0] flex items-center gap-1 font-semibold">
                        <Info className="w-3 h-3" /> {t("dashboard.why_score")}
                      </div>
                    </>
                  ) : (
                    <div className="text-xs text-[#64748B]">{t("dashboard.empty_desc")}</div>
                  )}
                </button>

                <div className={`${card} space-y-2`}>
                  <div className="text-xs text-[#64748B] font-medium">{t("dashboard.problems_solved")}</div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-black text-[#0F1F3A]">{data.student.problems_solved}</span>
                    {data.student.problems_delta > 0 && <span className="text-xs font-bold text-[#15803D]">▲ {data.student.problems_delta} {t("dashboard.this_month")}</span>}
                  </div>
                  <div className="text-[11px] text-[#64748B] flex items-center gap-1"><CheckCircle2 className="w-3 h-3 text-[#2B5CD0]" /> {data.student.batch}</div>
                </div>

                <div className={`${card} space-y-2`}>
                  <div className="flex items-center justify-between text-xs text-[#64748B] font-medium">
                    <span>{t("dashboard.attendance")}</span>
                    <span className={data.student.attendance_pct >= data.student.attendance_target ? "chip-green" : "chip-amber"}>
                      {data.student.attendance_pct >= data.student.attendance_target ? t("dashboard.on_track") : t("dashboard.below_target")}
                    </span>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-black text-[#0F1F3A]">{data.student.attendance_pct}%</span>
                    <span className="text-xs text-[#64748B]">{t("dashboard.target")} {data.student.attendance_target}%</span>
                  </div>
                  <div className="text-[11px] text-[#64748B] flex items-center gap-1">
                    <Calendar className="w-3 h-3 text-[#2BB3A0]" />
                    {fill(t("dashboard.sessions_attended"), { a: data.student.sessions_attended, b: data.student.sessions_total })}
                  </div>
                </div>

                <div className={`${card} space-y-2`}>
                  <div className="text-xs text-[#64748B] font-medium">{t("dashboard.practice_streak")}</div>
                  <div className="text-3xl font-black text-[#0F1F3A]">🔥 {data.student.streak_days} {t("dashboard.days")}</div>
                  <div className="text-[11px] text-[#64748B] flex items-center gap-1"><Flame className="w-3 h-3 text-[#F59E0B]" /> {t("dashboard.best")}: {data.student.streak_best} {t("dashboard.days")}</div>
                </div>
              </div>

              {/* Row 2: skills + this week */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-4">
                  <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
                    <h3 className="font-bold text-sm text-[#0F1F3A]">{t("dashboard.skill_progress")}</h3>
                    <span className="text-[11px] font-semibold text-[#64748B]">{t("dashboard.semester")} {data.student.semester}</span>
                  </div>
                  <div className="space-y-3.5" data-testid="skill-progress">
                    {data.skill_progress.map((item) => (
                      <div key={item.key} className="space-y-1">
                        <div className="flex justify-between text-xs font-semibold">
                          <span className="text-[#0F1F3A]">{item.skill}</span>
                          <span className="text-[#64748B]">{item.percentage}%</span>
                        </div>
                        <div className="w-full bg-[#F1F5F9] rounded-full h-2 overflow-hidden" role="progressbar" aria-valuenow={item.percentage} aria-valuemin={0} aria-valuemax={100} aria-label={item.skill}>
                          <div className="h-full rounded-full transition-all duration-500" style={{ width: `${item.percentage}%`, backgroundColor: COLOR_HEX[item.color] || COLOR_HEX.teal }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-4">
                  <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
                    <h3 className="font-bold text-sm text-[#0F1F3A]">{t("dashboard.this_week")}</h3>
                    <span className="text-[11px] font-semibold text-[#64748B]">{data.student.week_label}</span>
                  </div>
                  {data.this_week.length === 0 ? (
                    <p className="text-xs text-[#64748B] py-6 text-center">{t("dashboard.no_sessions")}</p>
                  ) : (
                    <div className="space-y-2.5" data-testid="this-week">
                      {data.this_week.map((row) => (
                        <Link key={row.id} href="/student/live" className="flex items-center justify-between p-2.5 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] hover:bg-[#F1F5F9] transition-all">
                          <div className="flex items-center gap-3 min-w-0">
                            <span className="w-10 text-center font-bold text-xs text-[#0F1F3A] bg-white py-1 rounded border border-[#E2E8F0] flex-shrink-0">{row.day}</span>
                            <span className="text-xs font-medium text-[#0F1F3A] truncate">{row.topic}</span>
                          </div>
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full flex-shrink-0 ${row.is_lab ? "bg-[#EDE9FE] text-[#6D28D9]" : "bg-[#EFF6FF] text-[#1D4ED8]"}`}>{row.duration}</span>
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Row 3: project, upcoming, badges */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-3 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between text-xs text-[#64748B] font-medium mb-1">
                      <span>{t("dashboard.current_project")}</span>
                      {data.current_project && <span className="chip-purple">{data.current_project.progress_pct}% {t("dashboard.complete")}</span>}
                    </div>
                    {data.current_project ? (
                      <>
                        <h4 className="font-bold text-sm text-[#0F1F3A]">{data.current_project.title}</h4>
                        <p className="text-xs text-[#64748B] mt-0.5">{data.current_project.subtitle}</p>
                        <div className="mt-4 space-y-1.5">
                          <div className="w-full bg-[#F1F5F9] rounded-full h-2"><div className="h-full bg-[#2BB3A0] rounded-full" style={{ width: `${data.current_project.progress_pct}%` }} /></div>
                          <div className="text-[11px] text-[#64748B] pt-1">
                            {fill(t("dashboard.tasks_open"), { n: data.current_project.open_tasks })}
                            {data.current_project.pending_prs > 0 && ` · ${fill(t("dashboard.prs_pending"), { n: data.current_project.pending_prs })}`}
                          </div>
                        </div>
                      </>
                    ) : (
                      <p className="text-xs text-[#64748B] py-4">{t("dashboard.no_project")}</p>
                    )}
                  </div>
                  <Link href="/student/projects/board" className="text-xs font-bold text-[#2B5CD0] hover:underline flex items-center gap-1 pt-2">
                    <span>{t("dashboard.open_board")}</span><ExternalLink className="w-3 h-3" />
                  </Link>
                </div>

                <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-3">
                  <div className="flex items-center justify-between text-xs text-[#64748B] font-medium border-b border-[#E2E8F0] pb-2">
                    <span>{t("dashboard.upcoming")}</span><Clock className="w-3.5 h-3.5 text-[#64748B]" />
                  </div>
                  {data.upcoming_events.length === 0 ? (
                    <p className="text-xs text-[#64748B] py-4 text-center">{t("dashboard.no_upcoming")}</p>
                  ) : (
                    <div className="space-y-2.5" data-testid="upcoming-events">
                      {data.upcoming_events.map((e) => (
                        <div key={e.id} className="flex items-center justify-between text-xs gap-2">
                          <span className="font-semibold text-[#0F1F3A] truncate">{e.title}</span>
                          <span className={`${kindChipClass(e.kind)} flex-shrink-0`}>{e.date}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-3">
                  <div className="flex items-center justify-between text-xs text-[#64748B] font-medium border-b border-[#E2E8F0] pb-2">
                    <span>{t("dashboard.badges_earned")}</span><Award className="w-3.5 h-3.5 text-[#2BB3A0]" />
                  </div>
                  {data.badges.length === 0 ? (
                    <p className="text-xs text-[#64748B] py-4 text-center">{t("dashboard.no_badges")}</p>
                  ) : (
                    <>
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-[#2BB3A0] to-[#2B5CD0] flex items-center justify-center text-white text-xl shadow-md">{data.badges[0].icon}</div>
                        <div>
                          <div className="text-[10px] text-[#64748B] uppercase font-bold">{t("dashboard.latest")}</div>
                          <div className="text-xs font-bold text-[#0F1F3A]">{data.badges[0].name}</div>
                          <div className="text-[11px] text-[#64748B]">{data.badges[0].description}</div>
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2 pt-1">
                        {data.badges.slice(1).map((b) => (
                          <span key={b.id} title={`${b.name} – ${b.description}`} className="w-7 h-7 rounded-lg bg-[#F1F5F9] border border-[#E2E8F0] flex items-center justify-center text-xs">{b.icon}</span>
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
            <div className="relative w-full max-w-md bg-white h-full shadow-2xl p-6 overflow-y-auto space-y-4" data-testid="why-score-drawer">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-base font-bold text-[#0F1F3A] flex items-center gap-2"><Sparkles className="w-4 h-4 text-[#2BB3A0]" /> {t("dashboard.why_title")}</h3>
                  <p className="text-xs text-[#64748B] mt-1">{t("dashboard.why_desc")}</p>
                </div>
                <button onClick={() => setWhyOpen(false)} className="p-1.5 rounded-lg hover:bg-[#F1F5F9]" aria-label={t("dashboard.close")}><X className="w-4 h-4 text-[#64748B]" /></button>
              </div>
              {whyLoading && <div className="h-40 bg-[#F1F5F9] rounded-xl animate-pulse" />}
              {!whyLoading && why && (
                <>
                  <div className="flex items-baseline gap-3">
                    <span className="text-4xl font-black text-[#0F1F3A]">{why.score}</span>
                    <span className={bandChipClass(why.band)}>{bandLabel(why.band)}</span>
                  </div>
                  <p className="text-[11px] text-[#64748B]">{fill(t("dashboard.bands"), { ready: why.thresholds.ready_min, nearly: why.thresholds.nearly_min })}{why.snapshot_date ? ` · ${fill(t("dashboard.snapshot_as_of"), { date: why.snapshot_date })}` : ""}</p>
                  <table className="w-full text-xs">
                    <thead><tr className="text-[#64748B] text-[11px] border-b border-[#E2E8F0]">
                      <th className="text-left pb-2 font-semibold">{t("dashboard.component")}</th>
                      <th className="text-right pb-2 font-semibold">{t("dashboard.value")}</th>
                      <th className="text-right pb-2 font-semibold">{t("dashboard.weight")}</th>
                      <th className="text-right pb-2 font-semibold">{t("dashboard.contribution")}</th>
                    </tr></thead>
                    <tbody className="divide-y divide-[#F1F5F9]">
                      {why.components.map((c) => (
                        <tr key={c.key}>
                          <td className="py-2 font-semibold text-[#0F1F3A]">{c.label}</td>
                          <td className="py-2 text-right text-[#64748B]">{c.value}</td>
                          <td className="py-2 text-right text-[#64748B]">{Math.round(c.weight * 100)}%</td>
                          <td className="py-2 text-right font-bold text-[#0F1F3A]">{c.contribution.toFixed(1)}</td>
                        </tr>
                      ))}
                      <tr className="border-t border-[#E2E8F0]">
                        <td className="py-2 font-bold text-[#0F1F3A]" colSpan={3}>{t("dashboard.total")}</td>
                        <td className="py-2 text-right font-black text-[#2BB3A0]">{why.score}</td>
                      </tr>
                    </tbody>
                  </table>
                  {why.history.length > 1 && (
                    <div>
                      <div className="text-xs font-bold text-[#0F1F3A] mb-2 flex items-center gap-1"><TrendingUp className="w-3.5 h-3.5 text-[#2B5CD0]" /> {t("dashboard.history")}</div>
                      <div className="flex items-end gap-1.5 h-20">
                        {why.history.map((h) => (
                          <div key={h.date} className="flex-1 flex flex-col items-center gap-1" title={`${h.date}: ${h.score}`}>
                            <div className="w-full bg-[#2B5CD0]/80 rounded-t" style={{ height: `${h.score}%` }} />
                            <span className="text-[9px] text-[#64748B]">{h.score}</span>
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
