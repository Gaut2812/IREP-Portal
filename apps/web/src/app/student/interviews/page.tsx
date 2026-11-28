"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { fetchApi, API_BASE } from "@/lib/api";
import { Play, Calendar, MessageSquareQuote, AlertCircle, RefreshCw, CheckCircle2, Clock } from "lucide-react";
import { SlotCalendar, type CalSlot } from "@/components/interviews/SlotCalendar";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, LabelList } from "recharts";

interface Latest {
  id: string; round_number: number; title: string; date: string; duration_min: number; interviewer: string; overall: number; max: number;
  chips: { label: string; type: string }[]; rubric: { key: string; label: string; score: number; max: number }[];
  feedback: string | null; has_recording: boolean; comments: { id: string; at_seconds: number; label: string; text: string; author: string }[];
}
type Slot = CalSlot;
interface Booking extends Slot { slot_id: string; can_cancel: boolean }
interface Data {
  latest_interview: Latest | null;
  trend: { round: number; label: string; score: number }[];
  target: number;
  available_slots: Slot[];
  my_bookings: Booking[];
}

const TYPE_CHIP: Record<string, string> = { technical: "chip-blue", hr: "chip-green", ai_coding: "chip-purple" };

function fill(template: string, vars: Record<string, string | number>) {
  return Object.entries(vars).reduce((acc, [k, v]) => acc.replace(`{${k}}`, String(v)), template);
}

export default function MockInterviewsPage() {
  const { t, language } = useLanguage();
  const [data, setData] = useState<Data | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [toast, setToast] = useState<{ text: string; ok: boolean } | null>(null);
  const [bookError, setBookError] = useState<string | null>(null);   // stays in the card, not only a passing toast
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [seekTo, setSeekTo] = useState<number | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setData(await fetchApi<Data>(`/student/interviews?lang=${language}`));
    } catch (err: any) {
      setError(err?.detail || err?.message || "error");
    } finally {
      setLoading(false);
    }
  }, [language]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(id);
  }, [toast]);

  const book = async (slot: Slot) => {
    setBusy(slot.id);
    setBookError(null);
    try {
      await fetchApi(`/student/interview-slots/${slot.id}/book`, { method: "POST" });
      setToast({ text: t("interviews.booked_toast"), ok: true });
      await load();
    } catch (err: any) {
      setToast({ text: err?.detail || t("interviews.action_failed"), ok: false });
      setBookError(err?.detail || t("interviews.action_failed"));
      await load();
    } finally {
      setBusy(null);
    }
  };

  const cancel = async (b: Booking) => {
    setBusy(b.id);
    try {
      await fetchApi(`/student/bookings/${b.id}`, { method: "DELETE" });
      setToast({ text: t("interviews.cancelled"), ok: true });
      await load();
    } catch (err: any) {
      setToast({ text: err?.detail || t("interviews.action_failed"), ok: false });
    } finally {
      setBusy(null);
    }
  };

  const ensureVideo = async () => {
    if (videoUrl || !data?.latest_interview) return;
    try {
      const res = await fetchApi<{ url: string }>(`/student/interviews/${data.latest_interview.id}/recording`);
      setVideoUrl(`${API_BASE.replace(/\/api\/v1$/, "")}${res.url}`);
    } catch (err: any) {
      setToast({ text: err?.detail || t("interviews.action_failed"), ok: false });
    }
  };

  const jump = async (sec: number) => {
    await ensureVideo();
    setSeekTo(sec);
    if (videoRef.current) {
      try { videoRef.current.currentTime = sec; } catch { /* metadata not loaded yet */ }
    }
  };

  const li = data?.latest_interview;
  const chartData = data ? [...data.trend.map((p) => ({ name: `#${p.round} · ${p.score.toFixed(1)}`, score: p.score })), { name: fill(t("interviews.target"), { t: data.target }), target: data.target }] : [];

  return (
    <RoleGuard allowedRoles={["student"]}>
      <AppShell pageTitle={t("interviews.title")}>
        <div className="max-w-7xl mx-auto" data-testid="mock-interviews">
          {loading && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 animate-pulse" aria-busy="true" aria-label={t("interviews.loading")}>
              <div className="lg:col-span-7 h-96 bg-white rounded-card border border-line" />
              <div className="lg:col-span-5 space-y-5"><div className="h-48 bg-white rounded-card border border-line" /><div className="h-40 bg-white rounded-card border border-line" /></div>
            </div>
          )}

          {!loading && error && (
            <div className="bg-white rounded-card border border-danger-line p-8 text-center space-y-3 max-w-md mx-auto">
              <AlertCircle className="w-8 h-8 text-danger mx-auto" />
              <h2 className="text-base font-semibold text-ink">{t("interviews.error_title")}</h2>
              <p className="text-xs text-muted">{error}</p>
              <button onClick={load} className="inline-flex items-center gap-1.5 px-4 py-2 bg-brand text-white text-xs font-semibold rounded-tile"><RefreshCw className="w-3.5 h-3.5" /> {t("interviews.retry")}</button>
            </div>
          )}

          {!loading && !error && data && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Left: latest scored interview (PDF 7) */}
              <div className="lg:col-span-7 bg-white rounded-card border border-line shadow-card p-6 space-y-5" data-testid="latest-interview">
                {!li ? (
                  <p className="text-xs text-muted py-10 text-center">{t("interviews.no_interview")}</p>
                ) : (
                  <>
                    <div className="border-b border-line pb-4 space-y-2">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <h2 className="text-base font-semibold text-ink">{li.title}</h2>
                        <span className="text-xs text-muted font-medium">{fill(t("interviews.meta"), { d: li.date, m: li.duration_min, i: li.interviewer })}</span>
                      </div>
                      <div className="flex flex-wrap items-center gap-3 pt-1">
                        <div>
                          <div className="text-caption text-muted">{t("interviews.overall")}</div>
                          <div className="text-3xl font-semibold text-ink" data-testid="overall">{li.overall.toFixed(1)}<span className="text-base text-muted">/{li.max}</span></div>
                        </div>
                        {li.chips.map((c) => <span key={c.label} className={`${c.type === "green" ? "chip-green" : "chip-amber"} font-semibold`}>{c.label}</span>)}
                      </div>
                    </div>
                    <div className="space-y-3.5" data-testid="rubric">
                      {li.rubric.map((r) => (
                        <div key={r.key} className="space-y-1">
                          <div className="flex justify-between text-xs font-medium">
                            <span className="text-ink">{r.label}</span>
                            <span className="font-semibold text-teal">{r.score}/{r.max}</span>
                          </div>
                          <div className="grid grid-cols-5 gap-1.5 h-2" role="img" aria-label={`${r.label} ${r.score} of ${r.max}`}>
                            {Array.from({ length: r.max }, (_, i) => <div key={i} className={`rounded-full ${i < r.score ? "bg-teal" : "bg-line-soft"}`} />)}
                          </div>
                        </div>
                      ))}
                    </div>
                    {li.feedback && (
                      <div className="pt-3 border-t border-line space-y-2">
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-ink"><MessageSquareQuote className="w-4 h-4 text-brand" /> {t("interviews.trainer_feedback")}</div>
                        <p className="text-xs text-ink-soft leading-relaxed bg-surface-2 p-3.5 rounded-card border border-line">{li.feedback}</p>
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* Right column */}
              <div className="lg:col-span-5 space-y-5">
                <div className="bg-white rounded-card border border-line p-4 shadow-card space-y-2" data-testid="trend">
                  <div className="text-xs font-semibold text-ink border-b border-line pb-2">{t("interviews.progress")}</div>
                  {data.trend.length === 0 ? <p className="text-xs text-muted py-6 text-center">{t("interviews.no_interview")}</p> : (
                    <div className="h-44 w-full pt-2">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData} margin={{ top: 18, right: 16, left: -18, bottom: 0 }}>
                          <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                          <YAxis domain={[0, 5]} tick={{ fontSize: 10 }} />
                          <Tooltip />
                          <ReferenceLine y={data.target} stroke="#F59E0B" strokeDasharray="4 4" />
                          <Line type="monotone" dataKey="score" stroke="#2BB3A0" strokeWidth={3} dot={{ r: 5, fill: "#2BB3A0" }} connectNulls={false} isAnimationActive={false}>
                            <LabelList dataKey="score" position="top" fontSize={10} formatter={(v: any) => (typeof v === "number" ? v.toFixed(1) : "")} />
                          </Line>
                          <Line type="monotone" dataKey="target" stroke="#F59E0B" strokeDasharray="4 4" dot={{ r: 4, fill: "#fff", stroke: "#F59E0B" }} isAnimationActive={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>

                <div className="bg-white rounded-card border border-line p-4 shadow-card space-y-3" data-testid="book-slots">
                  <div className="flex items-center justify-between text-xs font-semibold text-ink border-b border-line pb-2"><span>{t("interviews.book_next")}</span><Calendar className="w-3.5 h-3.5 text-muted" /></div>
                  {data.my_bookings.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-caption font-semibold text-muted">{t("interviews.my_bookings")}</div>
                      {data.my_bookings.map((b) => (
                        <div key={b.id} className="flex items-center justify-between p-2.5 rounded-tile border border-success-line bg-success-faint" data-testid={`booking-${b.slot_id}`}>
                          <div className="text-xs"><div className="font-semibold text-ink">{b.date} · {b.time}</div><span className={`${TYPE_CHIP[b.round_type] || "chip-blue"} text-caption`}>{b.type_label}</span></div>
                          <div className="flex items-center gap-2">
                            <span className="chip-green text-caption"><CheckCircle2 className="w-3 h-3" /> {t("interviews.booked")}</span>
                            {b.can_cancel && <button onClick={() => cancel(b)} disabled={busy === b.id} className="text-caption text-muted hover:text-danger underline" data-testid={`cancel-${b.slot_id}`}>{t("interviews.cancel")}</button>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  {bookError && <p className="p-2.5 rounded-tile bg-danger-faint border border-danger-line text-xs text-danger" role="alert" data-testid="book-error">{bookError}</p>}
                  <SlotCalendar slots={data.available_slots} busyId={busy} onBook={book} t={t} locale={language === "ta" ? "ta-IN" : "en-IN"} />
                </div>

                <div className="bg-white rounded-card border border-line p-4 shadow-card space-y-3" data-testid="recording">
                  <div className="text-xs font-semibold text-ink">{t("interviews.recording")}</div>
                  {videoUrl ? (
                    <video ref={videoRef} controls src={videoUrl} className="w-full rounded-tile bg-[#1B2236] aspect-video" data-seek={seekTo ?? undefined}
                      onLoadedMetadata={() => { if (seekTo !== null && videoRef.current) videoRef.current.currentTime = seekTo; }} />
                  ) : (
                    <button type="button" onClick={ensureVideo} disabled={!li?.has_recording} className="w-full h-28 bg-[#1B2236] rounded-tile flex items-center justify-center group disabled:opacity-50" aria-label={t("interviews.play")} data-testid="play-recording">
                      <span className="w-12 h-12 rounded-full bg-teal group-hover:scale-110 flex items-center justify-center shadow-pop transition-transform"><Play className="w-5 h-5 text-white ml-0.5" /></span>
                    </button>
                  )}
                  <p className="text-caption text-muted text-center">{t("interviews.recording_caption")}</p>
                  {li && li.comments.length > 0 && (
                    <div className="space-y-1.5" data-testid="comments">
                      <div className="text-caption font-semibold text-muted">{t("interviews.comments")}</div>
                      {li.comments.map((c) => (
                        <button key={c.id} type="button" onClick={() => jump(c.at_seconds)} className={`w-full text-left flex gap-2 p-2 rounded-tile border text-xs hover:bg-brand-soft ${seekTo === c.at_seconds ? "border-brand bg-brand-soft" : "border-line"}`} aria-label={fill(t("interviews.jump"), { t: c.label })} data-testid={`comment-${c.at_seconds}`}>
                          <span className="font-mono font-semibold text-brand flex items-center gap-1 flex-shrink-0"><Clock className="w-3 h-3" />{c.label}</span>
                          <span className="text-ink-soft">{c.text}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
        {toast && (
          <div role="status" className={`fixed bottom-6 right-6 z-50 text-white text-xs font-semibold px-4 py-3 rounded-card shadow-pop flex items-center gap-2 max-w-sm ${toast.ok ? "bg-ink" : "bg-danger"}`} data-testid="toast">
            {toast.ok ? <CheckCircle2 className="w-4 h-4 text-teal flex-shrink-0" /> : <AlertCircle className="w-4 h-4 flex-shrink-0" />} {toast.text}
          </div>
        )}
      </AppShell>
    </RoleGuard>
  );
}
