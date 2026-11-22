"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { fetchApi, API_BASE } from "@/lib/api";
import { Radio, Play, CheckCircle2, ShieldCheck, AlertCircle, RefreshCw, Bell, X, Mic, Lock } from "lucide-react";

interface WeekRow {
  id: string; day: string; time: string; date: string; title: string; type: string; status: string; action: string;
  join_enabled: boolean; recording_id: string | null; reminder_set: boolean;
}
interface LiveData {
  hero_session: {
    id: string; title: string; trainer: string; date_label: string; time_label: string; lab: string | null;
    starts_in_min: number; is_live: boolean; join_enabled: boolean; room: string; reminder_set: boolean;
  } | null;
  week_label: string;
  week_sessions: WeekRow[];
  attendance_summary: {
    overall_pct: number; sessions_attended: number; sessions_total: number; weekday_pct: number | null; saturday_pct: number | null;
    recordings_watched_for_missed: number; missed_with_recording: number;
  };
  recording_library: { id: string; title: string; duration: string; recorded_on: string | null; chapters: number; has_transcript: boolean; has_summary: boolean; watched: boolean }[];
}
interface Player { recording_id: string; title: string; url: string; expires_at: string; chapters: { at_sec: number; title: string }[] }

const STATUS_CHIP: Record<string, string> = {
  Attended: "chip-green", Completed: "chip-green", Missed: "chip-red", Upcoming: "chip-amber", Live: "chip-green", Scheduled: "bg-slate-100 text-slate-600",
};

function fill(template: string, vars: Record<string, string | number>) {
  return Object.entries(vars).reduce((acc, [k, v]) => acc.replace(`{${k}}`, String(v)), template);
}

export default function LiveSessionsPage() {
  const { t, language } = useLanguage();
  const [data, setData] = useState<LiveData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [device, setDevice] = useState<"idle" | "checking" | "ok" | "fail">("idle");
  const [player, setPlayer] = useState<Player | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchApi<LiveData>(`/student/live?lang=${language}`));
    } catch (err: any) {
      setError(err?.detail || err?.message || "error");
    } finally {
      setLoading(false);
    }
  }, [language]);

  useEffect(() => { load(); }, [load]);
  // keep the join button state honest: refresh every minute
  useEffect(() => {
    const id = setInterval(() => { fetchApi<LiveData>(`/student/live?lang=${language}`).then(setData).catch(() => undefined); }, 60000);
    return () => clearInterval(id);
  }, [language]);
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(id);
  }, [toast]);

  const remind = async (sessionId: string) => {
    setBusy(sessionId);
    try {
      await fetchApi(`/student/sessions/${sessionId}/remind`, { method: "POST" });
      setData((prev) => prev ? {
        ...prev,
        week_sessions: prev.week_sessions.map((r) => r.id === sessionId ? { ...r, reminder_set: true } : r),
        hero_session: prev.hero_session && prev.hero_session.id === sessionId ? { ...prev.hero_session, reminder_set: true } : prev.hero_session,
      } : prev);
      setToast(t("live_sessions.reminder_saved"));
    } catch (err: any) {
      setToast(err?.detail || t("live_sessions.action_failed"));
    } finally {
      setBusy(null);
    }
  };

  const openRecording = async (recordingId: string) => {
    setBusy(recordingId);
    try {
      const res = await fetchApi<Player>(`/student/recordings/${recordingId}/url`);
      setPlayer(res);
      setData((prev) => prev ? { ...prev, recording_library: prev.recording_library.map((r) => r.id === recordingId ? { ...r, watched: true } : r) } : prev);
    } catch (err: any) {
      setToast(err?.detail || t("live_sessions.action_failed"));
    } finally {
      setBusy(null);
    }
  };

  const checkDevices = async () => {
    setDevice("checking");
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("unsupported");
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true });
      stream.getTracks().forEach((tr) => tr.stop());
      setDevice("ok");
    } catch {
      setDevice("fail");
    }
  };

  const mediaBase = API_BASE.replace(/\/api\/v1$/, "");
  const s = data?.attendance_summary;

  return (
    <RoleGuard allowedRoles={["student"]}>
      <AppShell pageTitle={t("live_sessions.title")}>
        <div className="space-y-6 max-w-7xl mx-auto" data-testid="live-sessions">
          {loading && (
            <div className="space-y-6 animate-pulse" aria-busy="true" aria-label={t("live_sessions.loading")}>
              <div className="h-32 bg-white rounded-2xl border border-[#E2E8F0]" />
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6"><div className="lg:col-span-7 h-72 bg-white rounded-xl border border-[#E2E8F0]" /><div className="lg:col-span-5 h-72 bg-white rounded-xl border border-[#E2E8F0]" /></div>
            </div>
          )}

          {!loading && error && (
            <div className="bg-white rounded-2xl border border-[#FECACA] p-8 text-center space-y-3 max-w-md mx-auto">
              <AlertCircle className="w-8 h-8 text-[#D93636] mx-auto" />
              <h2 className="text-base font-bold text-[#0F1F3A]">{t("live_sessions.error_title")}</h2>
              <p className="text-xs text-[#64748B]">{error}</p>
              <button onClick={load} className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg"><RefreshCw className="w-3.5 h-3.5" /> {t("live_sessions.retry")}</button>
            </div>
          )}

          {!loading && !error && data && (
            <>
              {/* Hero card (PDF 14) */}
              {data.hero_session && (
                <div className="bg-gradient-to-r from-[#14284B] via-[#1E3A6E] to-[#2B5CD0] rounded-2xl p-6 text-white shadow-lg flex flex-wrap items-center justify-between gap-6" data-testid="hero-session">
                  <div className="space-y-2 max-w-xl">
                    <span className={`inline-block px-2.5 py-0.5 rounded-full text-white font-extrabold text-[10px] ${data.hero_session.is_live ? "bg-red-500 animate-pulse" : data.hero_session.starts_in_min <= 60 ? "bg-red-500" : "bg-white/20"}`}>
                      {data.hero_session.is_live ? t("live_sessions.live_now")
                        : data.hero_session.starts_in_min <= 60 ? fill(t("live_sessions.starting_in"), { n: data.hero_session.starts_in_min })
                        : fill(t("live_sessions.starts_on"), { d: data.hero_session.date_label })}
                    </span>
                    <h2 className="text-xl lg:text-2xl font-black tracking-tight">{data.hero_session.title}</h2>
                    <p className="text-xs text-[#CBD5E1]">
                      {data.hero_session.date_label} · {data.hero_session.time_label} · {data.hero_session.trainer}
                      {data.hero_session.lab && <span className="text-[#2BB3A0] font-semibold"> · {fill(t("live_sessions.lab_preloaded"), { l: data.hero_session.lab })}</span>}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    {data.hero_session.join_enabled ? (
                      <Link href={data.hero_session.room} className="px-6 py-3 bg-[#2BB3A0] hover:bg-[#249B8A] text-white font-bold text-xs rounded-xl shadow-md flex items-center gap-2" data-testid="join-session">
                        <Radio className="w-4 h-4" /><span>{t("live_sessions.join_session")}</span>
                      </Link>
                    ) : (
                      <div className="flex flex-col items-end gap-1.5">
                        <button type="button" disabled className="px-6 py-3 bg-white/15 text-white/70 font-bold text-xs rounded-xl flex items-center gap-2 cursor-not-allowed" data-testid="join-session-disabled">
                          <Lock className="w-4 h-4" />{t("live_sessions.join_session")}
                        </button>
                        <span className="text-[11px] text-[#CBD5E1]">{t("live_sessions.join_opens")}</span>
                      </div>
                    )}
                    <button type="button" onClick={checkDevices} className="flex items-center gap-1.5 text-[11px] text-[#A7F3D0] hover:underline" data-testid="device-check">
                      {device === "ok" ? <CheckCircle2 className="w-3.5 h-3.5 text-[#2BB3A0]" /> : <Mic className="w-3.5 h-3.5" />}
                      <span>{device === "ok" ? t("live_sessions.device_ok") : device === "fail" ? t("live_sessions.device_fail") : device === "checking" ? t("live_sessions.checking") : t("live_sessions.device_check")}</span>
                    </button>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Week table */}
                <div className="lg:col-span-7 bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5 space-y-4">
                  <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
                    <div>
                      <h3 className="font-bold text-xs text-[#0F1F3A]">{t("live_sessions.this_week")}</h3>
                      <p className="text-[11px] text-[#64748B]">{data.week_label}{data.week_label ? " · " : ""}{t("live_sessions.week_hint")}</p>
                    </div>
                  </div>
                  {data.week_sessions.length === 0 ? (
                    <p className="text-xs text-[#64748B] py-6 text-center">{t("live_sessions.no_sessions")}</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs text-left" data-testid="week-table">
                        <thead><tr className="border-b border-[#E2E8F0] text-[#64748B] text-[11px]">
                          <th className="pb-2 font-semibold">{t("live_sessions.when")}</th><th className="pb-2 font-semibold">{t("live_sessions.session")}</th>
                          <th className="pb-2 font-semibold">{t("live_sessions.type")}</th><th className="pb-2 font-semibold">{t("live_sessions.status")}</th>
                          <th className="pb-2 font-semibold text-right">{t("live_sessions.action")}</th>
                        </tr></thead>
                        <tbody className="divide-y divide-[#E2E8F0]">
                          {data.week_sessions.map((r) => (
                            <tr key={r.id} className="hover:bg-[#F8FAFC]" data-testid={`row-${r.id}`}>
                              <td className="py-3 whitespace-nowrap"><div className="font-bold text-[#0F1F3A]">{r.day}</div><div className="text-[10px] text-[#64748B]">{r.time}</div></td>
                              <td className="py-3 font-bold text-[#0F1F3A]">{r.title}</td>
                              <td className="py-3"><span className={r.type === "Live" ? "chip-blue text-[10px]" : "chip-purple text-[10px]"}>{r.type}</span></td>
                              <td className="py-3"><span className={`${STATUS_CHIP[r.status] || "chip-blue"} text-[10px]`}>{t(`live_sessions.status_${r.status}`)}</span></td>
                              <td className="py-3 text-right whitespace-nowrap">
                                {r.action === "join" && <Link href={`/live/${r.id}`} className="px-3 py-1 bg-[#2BB3A0] hover:bg-[#249B8A] text-white font-bold text-[11px] rounded-lg">{t("live_sessions.join")}</Link>}
                                {r.action === "watch_now" && r.recording_id && <button type="button" disabled={busy === r.recording_id} onClick={() => openRecording(r.recording_id!)} className="px-2.5 py-1 border border-red-300 text-red-600 hover:bg-red-50 font-bold text-[11px] rounded-lg">{t("live_sessions.watch_now")}</button>}
                                {r.action === "recording" && r.recording_id && <button type="button" disabled={busy === r.recording_id} onClick={() => openRecording(r.recording_id!)} className="px-2.5 py-1 border border-[#2B5CD0] text-[#2B5CD0] hover:bg-[#EFF6FF] font-bold text-[11px] rounded-lg">{t("live_sessions.recording")}</button>}
                                {r.action === "remind_me" && (r.reminder_set ? (
                                  <span className="text-[11px] font-semibold text-[#15803D] inline-flex items-center gap-1"><Bell className="w-3 h-3" /> {t("live_sessions.reminder_set")}</span>
                                ) : (
                                  <button type="button" disabled={busy === r.id} onClick={() => remind(r.id)} className="px-2.5 py-1 border border-[#2B5CD0] text-[#2B5CD0] hover:bg-[#EFF6FF] font-bold text-[11px] rounded-lg disabled:opacity-50" data-testid={`remind-${r.id}`}>{t("live_sessions.remind_me")}</button>
                                ))}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

                {/* Right column */}
                <div className="lg:col-span-5 space-y-5">
                  {s && (
                    <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm space-y-3" data-testid="attendance-summary">
                      <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
                        <h4 className="text-xs font-bold text-[#0F1F3A]">{t("live_sessions.my_attendance")}</h4>
                        <span className="text-sm font-black text-[#15803D]">{s.overall_pct}%</span>
                      </div>
                      <div className="text-xs text-[#64748B] font-semibold">{fill(t("live_sessions.sessions_of"), { a: s.sessions_attended, b: s.sessions_total })}</div>
                      <div className="space-y-2 text-xs pt-1">
                        <div className="flex justify-between"><span className="text-[#64748B]">{t("live_sessions.weekday")}</span><strong className="text-[#0F1F3A]">{s.weekday_pct ?? "—"}%</strong></div>
                        <div className="flex justify-between"><span className="text-[#64748B]">{t("live_sessions.saturday")}</span><strong className="text-[#0F1F3A]">{s.saturday_pct ?? "—"}%</strong></div>
                        <div className="flex justify-between"><span className="text-[#64748B]">{t("live_sessions.recordings_watched")}</span><strong className="text-[#2BB3A0]">{fill(t("live_sessions.of"), { a: s.recordings_watched_for_missed, b: s.missed_with_recording })}</strong></div>
                      </div>
                    </div>
                  )}

                  <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm space-y-3">
                    <h4 className="text-xs font-bold text-[#0F1F3A] border-b border-[#E2E8F0] pb-2">{t("live_sessions.library")}</h4>
                    {data.recording_library.length === 0 ? (
                      <p className="text-xs text-[#64748B] py-3 text-center">{t("live_sessions.no_recordings")}</p>
                    ) : (
                      <div className="space-y-2" data-testid="recording-library">
                        {data.recording_library.map((rec) => (
                          <div key={rec.id} className="flex items-center justify-between p-2.5 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] gap-2">
                            <div className="flex items-center gap-2.5 min-w-0">
                              <div className="w-7 h-7 rounded-lg bg-[#EFF6FF] text-[#2B5CD0] flex items-center justify-center flex-shrink-0"><Play className="w-3.5 h-3.5 ml-0.5" /></div>
                              <div className="min-w-0">
                                <div className="text-xs font-bold text-[#0F1F3A] truncate">{rec.title}</div>
                                <div className="text-[10px] text-[#64748B]">{rec.duration}{rec.watched ? ` · ${t("live_sessions.watched")}` : ""}</div>
                              </div>
                            </div>
                            <button type="button" disabled={busy === rec.id} onClick={() => openRecording(rec.id)} className="text-[11px] font-bold text-[#2B5CD0] hover:underline flex-shrink-0" aria-label={`${t("live_sessions.watch")} ${rec.title}`}>{t("live_sessions.watch")}</button>
                          </div>
                        ))}
                      </div>
                    )}
                    <p className="text-[10px] text-[#64748B] italic leading-tight text-center">{t("live_sessions.library_caption")}</p>
                  </div>

                  <div className="bg-[#EFF6FF] border border-[#BFDBFE] p-3.5 rounded-xl space-y-1.5 text-xs text-[#1E3A8A]">
                    <div className="font-bold flex items-center gap-1.5"><ShieldCheck className="w-4 h-4 text-[#2B5CD0]" /> {t("live_sessions.how_title")}</div>
                    <p className="text-[11px] leading-relaxed text-[#1D4ED8]">{t("live_sessions.how_body")}</p>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        {player && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50" role="dialog" aria-modal="true" aria-label={player.title} data-testid="recording-player">
            <div className="bg-[#1B2236] rounded-2xl max-w-2xl w-full p-5 space-y-3 text-white shadow-2xl">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold">{t("live_sessions.player_title")} · {player.title}</h3>
                <button onClick={() => setPlayer(null)} className="p-1.5 rounded-lg hover:bg-white/10" aria-label={t("live_sessions.close")}><X className="w-4 h-4" /></button>
              </div>
              <video controls className="w-full rounded-lg bg-black aspect-video" src={`${mediaBase}${player.url}`} />
              <div className="text-[10px] text-[#94A3B8]">{fill(t("live_sessions.link_expires"), { t: new Date(player.expires_at).toLocaleTimeString() })}</div>
              {player.chapters.length > 0 && (
                <div>
                  <div className="text-xs font-bold mb-1.5">{t("live_sessions.chapters")}</div>
                  <div className="flex flex-wrap gap-2">
                    {player.chapters.map((c) => (
                      <span key={c.at_sec} className="text-[11px] px-2 py-1 rounded bg-white/10">{Math.floor(c.at_sec / 60)}:{String(c.at_sec % 60).padStart(2, "0")} · {c.title}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {toast && (
          <div role="status" className="fixed bottom-6 right-6 z-50 bg-[#0F1F3A] text-white text-xs font-semibold px-4 py-3 rounded-xl shadow-2xl flex items-center gap-2" data-testid="toast">
            <CheckCircle2 className="w-4 h-4 text-[#2BB3A0]" /> {toast}
          </div>
        )}
      </AppShell>
    </RoleGuard>
  );
}
