"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { useAuth } from "@/lib/AuthContext";
import { fetchApi, WS_BASE } from "@/lib/api";
import {
  Mic, MicOff, Video, VideoOff, Hand, MessageSquare, BarChart2, Cpu, LogOut, ArrowDown, ThumbsUp,
  CheckCircle2, AlertCircle, RefreshCw, Radio, Square, Plus, Send, Clock,
} from "lucide-react";

interface LiveState {
  session_id: string; title: string; subtext: string; trainer: string; role: "student" | "trainer"; provider: string;
  meeting: { state: "not_started" | "live" | "ended"; started_at: string | null; ended_at: string | null; is_recording: boolean };
  timer: { elapsed_sec: number; duration_sec: number; label: string };
  schedule: { starts_at: string; ends_at: string; join_window_open: boolean };
  can_join: boolean;
  stage: { sharing_user: string | null; file: string | null; source: string | null; code: string | null; flow_title: string | null; flow_steps: { step: number; title: string; color: string }[] };
  participants: { user_id: string; name: string; initials: string; role: string; is_you: boolean }[];
  more_participants: number; participant_count: number;
  poll: { id: string; question: string; is_open: boolean; total_votes: number; my_vote: string | null; options: { key: string; text: string; color: string; votes: number; pct: number }[] } | null;
  qa: { id: string; author: string; text: string; upvotes: number; my_upvote: boolean; answered_at: string | null }[];
  attendance: { minutes_present: number; total_minutes: number; threshold_minutes: number; threshold_pct: number; marked_present: boolean; joined_at: string | null; is_in_room: boolean } | null;
  attendance_on_track: boolean | null;
}

const FLOW_STYLE: Record<string, string> = {
  blue: "bg-[#EFF6FF] border-[#BFDBFE] text-[#1D4ED8]", green: "bg-[#DCFCE7] border-[#BBF7D0] text-[#15803D]",
  amber: "bg-[#FEF3C7] border-[#FDE68A] text-[#B45309]", purple: "bg-[#EDE9FE] border-[#DDD6FE] text-[#6D28D9]",
};
const BAR: Record<string, string> = { red: "bg-red-500", teal: "bg-[#2BB3A0]", blue: "bg-blue-500", amber: "bg-amber-500", purple: "bg-purple-500" };
const PCT_TEXT: Record<string, string> = { red: "text-red-400", teal: "text-[#2BB3A0]", blue: "text-blue-400", amber: "text-amber-400", purple: "text-purple-400" };
const AVATAR = ["bg-[#2B5CD0]", "bg-[#2BB3A0]", "bg-[#7C5CE0]", "bg-[#F59E0B]", "bg-pink-600"];

function fill(template: string, vars: Record<string, string | number>) {
  return Object.entries(vars).reduce((acc, [k, v]) => acc.replace(`{${k}}`, String(v)), template);
}
const fmt = (sec: number) => `${String(Math.floor(sec / 3600)).padStart(2, "0")}:${String(Math.floor((sec % 3600) / 60)).padStart(2, "0")}:${String(sec % 60).padStart(2, "0")}`;

export default function LiveClassroomPage() {
  const params = useParams<{ sessionId: string }>();
  const sessionId = params.sessionId;
  const router = useRouter();
  const { t } = useLanguage();
  const { token } = useAuth();
  const [st, setSt] = useState<LiveState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [joined, setJoined] = useState(false);
  const [joinUrl, setJoinUrl] = useState<string | null>(null);
  const [joinProvider, setJoinProvider] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [mic, setMic] = useState(false);
  const [cam, setCam] = useState(false);
  const [hand, setHand] = useState(false);
  const [question, setQuestion] = useState("");
  const [pollOpen, setPollOpen] = useState(false);
  const [pollQ, setPollQ] = useState("");
  const [pollOpts, setPollOpts] = useState("");
  const [tick, setTick] = useState(0);
  const autoJoinTried = useRef(false);

  const load = useCallback(async () => {
    try {
      const res = await fetchApi<LiveState>(`/live/${sessionId}`);
      setSt(res);
      setTick(0);
      setError(null);
      if (res.attendance?.is_in_room || (res.role === "trainer" && res.meeting.state === "live")) {
        // already in the room (e.g. after a reload)
        setJoined((j) => j || !!res.attendance?.is_in_room);
      }
    } catch (err: any) {
      setError(err?.detail || err?.message || "error");
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => { load(); }, [load]);

  // Realtime: WebSocket pings trigger a refetch; poll every 5 s as a fallback
  useEffect(() => {
    const id = setInterval(load, 5000);
    let ws: WebSocket | null = null;
    if (token && !token.startsWith("mock")) {
      try {
        ws = new WebSocket(`${WS_BASE}/ws/live/${sessionId}?token=${encodeURIComponent(token)}`);
        ws.onmessage = () => load();
      } catch { /* fallback polling only */ }
    }
    const ping = setInterval(() => { try { ws?.readyState === 1 && ws.send("ping"); } catch { /* ignore */ } }, 25000);
    return () => { clearInterval(id); clearInterval(ping); try { ws?.close(); } catch { /* ignore */ } };
  }, [load, sessionId, token]);

  // local timer between refreshes
  useEffect(() => {
    const id = setInterval(() => setTick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(id);
  }, [toast]);

  const join = useCallback(async () => {
    setBusy(true);
    try {
      const res = await fetchApi<{ join_url: string | null; provider?: string }>(`/sessions/${sessionId}/join`, { method: "POST" });
      setJoined(true);
      setJoinUrl(res.join_url);
      setJoinProvider(res.provider ?? null);
      // Teams cannot be embedded (Master Plan): open the Teams app / web client
      if (res.provider === "teams" && res.join_url) window.open(res.join_url, "_blank", "noopener");
      await load();
    } catch (err: any) {
      setToast(err?.detail || t("live_class.action_failed"));
    } finally {
      setBusy(false);
    }
  }, [sessionId, load, t]);

  // students drop straight into a live room when they arrive from "Join"
  useEffect(() => {
    if (!st || autoJoinTried.current || joined) return;
    if (st.role === "student" && st.meeting.state === "live" && st.can_join) {
      autoJoinTried.current = true;
      join();
    }
  }, [st, joined, join]);

  const leave = async () => {
    try { await fetchApi(`/sessions/${sessionId}/leave`, { method: "POST" }); } catch { /* ignore */ }
    router.push(st?.role === "trainer" ? "/trainer" : "/student/live");
  };

  const endClass = async () => {
    setBusy(true);
    try {
      const res = await fetchApi<{ attendance: { present: number; absent: number } }>(`/sessions/${sessionId}/end`, { method: "POST" });
      setToast(fill(t("live_class.present_on_end"), { p: res.attendance.present, a: res.attendance.absent }));
      await load();
    } catch (err: any) {
      setToast(err?.detail || t("live_class.action_failed"));
    } finally {
      setBusy(false);
    }
  };

  const vote = async (key: string) => {
    try {
      await fetchApi(`/live/${sessionId}/poll/vote`, { method: "POST", body: JSON.stringify({ option: key }) });
      await load();
    } catch (err: any) {
      setToast(err?.detail || t("live_class.action_failed"));
    }
  };

  const ask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    try {
      await fetchApi(`/live/${sessionId}/qa`, { method: "POST", body: JSON.stringify({ text: question }) });
      setQuestion("");
      await load();
    } catch (err: any) {
      setToast(err?.detail || t("live_class.action_failed"));
    }
  };

  const upvote = async (qid: string) => {
    try { await fetchApi(`/live/${sessionId}/qa/${qid}/upvote`, { method: "POST" }); await load(); } catch { setToast(t("live_class.action_failed")); }
  };
  const answered = async (qid: string) => {
    try { await fetchApi(`/live/${sessionId}/qa/${qid}/answered`, { method: "POST" }); await load(); } catch { setToast(t("live_class.action_failed")); }
  };
  const launchPoll = async () => {
    const options = pollOpts.split("\n").map((o) => o.trim()).filter(Boolean);
    if (!pollQ.trim() || options.length < 2) return;
    try {
      await fetchApi(`/live/${sessionId}/polls`, { method: "POST", body: JSON.stringify({ question: pollQ, options }) });
      setPollOpen(false); setPollQ(""); setPollOpts("");
      await load();
    } catch (err: any) {
      setToast(err?.detail || t("live_class.action_failed"));
    }
  };

  const shell = (children: React.ReactNode) => (
    <RoleGuard allowedRoles={["student", "trainer"]}>
      <div className="h-screen w-screen bg-[#1B2236] text-white flex flex-col font-sans overflow-hidden" data-testid="live-classroom">{children}</div>
    </RoleGuard>
  );

  if (loading) return shell(<div className="flex-1 flex items-center justify-center text-sm text-[#94A3B8]" aria-busy="true">{t("live_class.loading")}</div>);
  if (error || !st) return shell(
    <div className="flex-1 flex items-center justify-center p-6">
      <div className="bg-[#141A29] border border-[#2D3748] rounded-2xl p-8 text-center space-y-3 max-w-md">
        <AlertCircle className="w-8 h-8 text-red-400 mx-auto" />
        <h2 className="text-base font-bold">{t("live_class.error_title")}</h2>
        <p className="text-xs text-[#94A3B8]">{error}</p>
        <button onClick={load} className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg"><RefreshCw className="w-3.5 h-3.5" /> {t("live_class.retry")}</button>
      </div>
    </div>
  );

  const live = st.meeting.state === "live";
  const elapsed = live ? Math.min(st.timer.duration_sec * 2, st.timer.elapsed_sec + tick) : st.timer.elapsed_sec;
  const isTrainer = st.role === "trainer";
  const a = st.attendance;
  const startsAt = new Date(st.schedule.starts_at).toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" });

  // Lobby / ended screens
  if (st.meeting.state === "ended" || (!joined && !(isTrainer && live))) {
    return shell(
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="bg-[#141A29] border border-[#2D3748] rounded-2xl p-8 text-center space-y-4 max-w-md w-full" data-testid="live-lobby">
          <div className="flex items-center justify-center gap-2"><span className="w-7 h-7 rounded-md bg-[#2BB3A0] flex items-center justify-center font-bold text-xs">IR</span><span className="font-extrabold">{t("live_class.brand")}</span></div>
          <h1 className="text-lg font-black">{st.title}</h1>
          <p className="text-xs text-[#94A3B8]">{st.subtext}</p>
          {st.meeting.state === "ended" ? (
            <>
              <div className="text-sm font-bold text-[#2BB3A0]">{t("live_class.ended_title")}</div>
              <p className="text-xs text-[#CBD5E1]">{t("live_class.ended_desc")}</p>
              <Link href={isTrainer ? "/trainer" : "/student/live"} className="inline-block px-4 py-2 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg">{t("live_class.back_to_sessions")}</Link>
            </>
          ) : (
            <>
              <div className="text-sm font-bold">{t("live_class.lobby_title")}</div>
              <p className="text-xs text-[#CBD5E1]">{live ? "" : isTrainer ? "" : st.can_join ? "" : `${t("live_class.lobby_not_started")} ${fill(t("live_class.lobby_opens"), { t: startsAt })}`}</p>
              {isTrainer ? (
                <button onClick={join} disabled={busy} className="w-full py-3 bg-[#2BB3A0] hover:bg-[#249B8A] text-white font-bold text-sm rounded-xl disabled:opacity-50 flex items-center justify-center gap-2" data-testid="start-class">
                  <Radio className="w-4 h-4" /> {t("live_class.start_class")}
                </button>
              ) : (
                <button onClick={join} disabled={busy || !st.can_join} className="w-full py-3 bg-[#2BB3A0] hover:bg-[#249B8A] text-white font-bold text-sm rounded-xl disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2" data-testid="join-now">
                  <Radio className="w-4 h-4" /> {t("live_class.join_now")}
                </button>
              )}
              <Link href={isTrainer ? "/trainer" : "/student/live"} className="block text-xs text-[#94A3B8] hover:text-white">{t("live_class.back_to_sessions")}</Link>
            </>
          )}
        </div>
        {toast && <div role="status" className="fixed bottom-6 right-6 bg-[#0F172A] border border-[#334155] text-xs font-semibold px-4 py-3 rounded-xl" data-testid="toast">{toast}</div>}
      </div>
    );
  }

  return shell(
    <>
      {/* Top bar (PDF 13) */}
      <header className="h-12 bg-[#141A29] border-b border-[#2D3748] px-4 flex items-center justify-between flex-shrink-0 gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <span className="w-6 h-6 rounded-md bg-[#2BB3A0] flex items-center justify-center font-bold text-xs flex-shrink-0">IR</span>
          <span className="font-extrabold text-sm tracking-wide flex-shrink-0">{t("live_class.brand")}</span>
          <span className="font-bold text-xs text-[#E2E8F0] truncate">{st.title}</span>
          <span className="text-[11px] text-[#94A3B8] hidden md:inline truncate">{st.subtext}</span>
        </div>
        <div className="flex items-center gap-3 text-xs flex-shrink-0">
          {st.meeting.is_recording && (
            <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-red-950/80 border border-red-800 text-red-400 font-bold text-[10px]">
              <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" /> {t("live_class.rec")}
            </span>
          )}
          <span className="font-mono text-[#CBD5E1]" data-testid="live-timer">{fmt(elapsed)} / {fmt(st.timer.duration_sec)}</span>
          {!isTrainer && st.attendance_on_track !== null && (
            <span className={`${a?.marked_present || st.attendance_on_track ? "chip-green" : "chip-amber"} text-[10px] font-bold`} data-testid="attendance-pill">
              {a?.marked_present ? t("live_class.marked_present") : st.attendance_on_track ? t("live_class.attendance_on_track") : t("live_class.attendance_at_risk")}
            </span>
          )}
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        {/* Stage */}
        <div className="flex-1 flex flex-col p-4 gap-3 overflow-hidden min-w-0">
          <div className="flex-1 bg-[#141A29] rounded-2xl border border-[#2D3748] p-4 flex flex-col overflow-hidden">
            {joinUrl && joinProvider === "teams" ? (
              <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center" data-testid="teams-join">
                <p className="text-sm text-[#E2E8F0] font-semibold">{t("live_class.teams_opened")}</p>
                <a href={joinUrl} target="_blank" rel="noopener noreferrer" className="px-4 py-2.5 bg-[#5B5FC7] text-white text-xs font-bold rounded-xl" data-testid="teams-join-link">
                  {t("live_class.join_in_teams")}
                </a>
                <p className="text-[11px] text-[#94A3B8] max-w-sm">{t("live_class.teams_attendance_note")}</p>
              </div>
            ) : joinUrl ? (
              <iframe src={joinUrl} title={st.title} className="flex-1 w-full rounded-xl bg-black" allow="camera; microphone; display-capture; fullscreen" />
            ) : (
              <>
                <div className="flex items-center justify-between pb-3 border-b border-[#2D3748] gap-2">
                  <div className="flex items-center gap-2 text-xs min-w-0">
                    <span className="w-2.5 h-2.5 rounded-full bg-[#2BB3A0] flex-shrink-0" />
                    <span className="font-bold text-[#E2E8F0] truncate" data-testid="stage-sharing">
                      {st.stage.sharing_user ? <>{fill(t("live_class.sharing"), { n: st.stage.sharing_user })} · <code className="font-mono text-[#2BB3A0]">{st.stage.file}</code></> : t("live_class.waiting_share")}
                    </span>
                  </div>
                  {st.stage.source && <span className="text-[10px] text-[#94A3B8] bg-[#1E293B] px-2 py-0.5 rounded flex-shrink-0">{st.stage.source}</span>}
                </div>
                <div className="flex-1 grid grid-cols-1 md:grid-cols-12 gap-4 py-3 overflow-hidden">
                  <pre className="md:col-span-8 bg-[#0F172A] rounded-xl p-3.5 font-mono text-xs overflow-auto border border-[#1E293B] text-[#E2E8F0] leading-relaxed whitespace-pre-wrap" data-testid="stage-code">{st.stage.code}</pre>
                  {st.stage.flow_steps.length > 0 && (
                    <div className="md:col-span-4 bg-white rounded-xl p-4 text-[#0F1F3A] flex flex-col shadow-lg" data-testid="stage-flow">
                      <div className="text-xs font-bold border-b border-[#E2E8F0] pb-2 text-center">{st.stage.flow_title}</div>
                      <div className="space-y-2 py-2">
                        {st.stage.flow_steps.map((f, i) => (
                          <React.Fragment key={f.step}>
                            <div className={`p-2 rounded-lg border text-center text-xs font-bold ${FLOW_STYLE[f.color] || FLOW_STYLE.blue}`}>{f.step}. {f.title}</div>
                            {i < st.stage.flow_steps.length - 1 && <div className="flex justify-center text-[#94A3B8]"><ArrowDown className="w-3.5 h-3.5" /></div>}
                          </React.Fragment>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
            {/* Participant tiles */}
            <div className="flex items-center gap-2 pt-2 border-t border-[#2D3748] overflow-x-auto" data-testid="participants">
              {st.participants.map((p, i) => (
                <div key={p.user_id} className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#1E293B] border border-[#334155] text-xs flex-shrink-0">
                  <span className={`w-5 h-5 rounded-full ${AVATAR[i % AVATAR.length]} text-white font-bold text-[10px] flex items-center justify-center`}>{p.initials}</span>
                  <span className="text-[11px] text-[#E2E8F0] whitespace-nowrap">{p.name}{p.role === "trainer" ? ` (${t("live_class.trainer")})` : p.is_you ? ` (${t("live_class.you")})` : ""}</span>
                </div>
              ))}
              {st.more_participants > 0 && <span className="text-[11px] text-[#94A3B8] px-2 flex-shrink-0">{fill(t("live_class.more"), { n: st.more_participants })}</span>}
            </div>
          </div>

          {/* Control bar */}
          <div className="h-12 bg-[#141A29] rounded-xl border border-[#2D3748] px-4 flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-2">
              <button onClick={() => setMic(!mic)} aria-label={mic ? t("live_class.mute") : t("live_class.unmute")} aria-pressed={mic} className={`p-2 rounded-lg ${mic ? "bg-[#2BB3A0]" : "bg-[#1E293B] text-[#94A3B8] hover:text-white"}`}>{mic ? <Mic className="w-4 h-4" /> : <MicOff className="w-4 h-4" />}</button>
              <button onClick={() => setCam(!cam)} aria-label={t("live_class.camera")} aria-pressed={cam} className={`p-2 rounded-lg ${cam ? "bg-[#2BB3A0]" : "bg-[#1E293B] text-[#94A3B8] hover:text-white"}`}>{cam ? <Video className="w-4 h-4" /> : <VideoOff className="w-4 h-4" />}</button>
              <button onClick={() => setHand(!hand)} aria-label={t("live_class.raise_hand")} aria-pressed={hand} className={`p-2 rounded-lg ${hand ? "bg-[#F59E0B]" : "bg-[#1E293B] text-[#94A3B8] hover:text-white"}`}><Hand className="w-4 h-4" /></button>
              <a href="#qa" aria-label={t("live_class.chat")} className="p-2 rounded-lg bg-[#1E293B] text-[#94A3B8] hover:text-white"><MessageSquare className="w-4 h-4" /></a>
              {isTrainer ? (
                <button onClick={() => setPollOpen(true)} aria-label={t("live_class.new_poll")} className="p-2 rounded-lg bg-[#1E293B] text-[#94A3B8] hover:text-white" data-testid="new-poll"><BarChart2 className="w-4 h-4" /></button>
              ) : (
                <a href="#poll" aria-label={t("live_class.poll")} className="p-2 rounded-lg bg-[#1E293B] text-[#94A3B8] hover:text-white"><BarChart2 className="w-4 h-4" /></a>
              )}
              <Link href="/student/labs" aria-label={t("live_class.lab")} className="p-2 rounded-lg bg-[#1E293B] text-[#2BB3A0] hover:text-white"><Cpu className="w-4 h-4" /></Link>
            </div>
            <div className="flex items-center gap-2">
              {isTrainer && (
                <button onClick={endClass} disabled={busy} className="flex items-center gap-1.5 px-3 py-1.5 border border-red-500 text-red-400 hover:bg-red-950 text-xs font-bold rounded-lg disabled:opacity-50" data-testid="end-class">
                  <Square className="w-3.5 h-3.5" /> {t("live_class.end_class")}
                </button>
              )}
              <button onClick={leave} className="flex items-center gap-1.5 px-4 py-1.5 bg-[#D93636] hover:bg-[#B91C1C] text-white text-xs font-bold rounded-lg" data-testid="leave">
                <LogOut className="w-3.5 h-3.5" /> {t("live_class.leave")}
              </button>
            </div>
          </div>
        </div>

        {/* Right column */}
        <aside className="w-80 bg-[#141A29] border-l border-[#2D3748] p-4 flex-col gap-4 overflow-y-auto hidden lg:flex">
          <section id="poll" className="bg-[#1E293B] border border-[#334155] rounded-xl p-3.5 space-y-2.5" data-testid="live-poll">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-[#E2E8F0]">{t("live_class.live_poll")}</span>
              {st.poll && <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#2B5CD0] text-white font-bold">{fill(t("live_class.votes"), { n: st.poll.total_votes })}</span>}
            </div>
            {!st.poll ? <p className="text-[11px] text-[#94A3B8]">{t("live_class.no_poll")}</p> : (
              <>
                <p className="text-[11px] text-[#CBD5E1] leading-tight font-medium">{st.poll.question}</p>
                <div className="space-y-2 pt-1">
                  {st.poll.options.map((o) => {
                    const canVote = st.poll!.is_open && !st.poll!.my_vote;
                    return (
                      <button key={o.key} type="button" disabled={!canVote} onClick={() => vote(o.key)} className={`w-full text-left space-y-1 rounded-md ${canVote ? "hover:bg-[#0F172A] cursor-pointer p-1 -m-1" : "cursor-default"}`} data-testid={`poll-option-${o.key}`}>
                        <div className={`flex justify-between text-[11px] ${st.poll!.my_vote === o.key ? "text-white font-bold" : "text-[#94A3B8]"}`}>
                          <span>{o.text}{st.poll!.my_vote === o.key ? ` · ${t("live_class.you_voted")}` : ""}</span>
                          <span className={`font-bold ${PCT_TEXT[o.color] || "text-blue-400"}`}>{o.pct}%</span>
                        </div>
                        <div className="w-full bg-[#0F172A] h-1.5 rounded-full overflow-hidden"><div className={`${BAR[o.color] || "bg-blue-500"} h-full`} style={{ width: `${o.pct}%` }} /></div>
                      </button>
                    );
                  })}
                </div>
              </>
            )}
          </section>

          <section id="qa" className="bg-[#1E293B] border border-[#334155] rounded-xl p-3.5 space-y-2.5 flex-1" data-testid="live-qa">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-[#E2E8F0]">{t("live_class.qa")}</span>
              <span className="text-[10px] text-[#94A3B8]">{t("live_class.qa_label")}</span>
            </div>
            {st.qa.length === 0 && <p className="text-[11px] text-[#94A3B8]">{t("live_class.no_questions")}</p>}
            {st.qa.map((q) => (
              <div key={q.id} className="p-2.5 rounded-lg bg-[#0F172A] border border-[#334155] space-y-1.5 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-[#2BB3A0]">{q.author}</span>
                  <button onClick={() => upvote(q.id)} aria-pressed={q.my_upvote} aria-label={`${t("live_class.upvote")} ${q.text}`} className={`flex items-center gap-1 text-[10px] font-bold ${q.my_upvote ? "text-white" : "text-[#38BDF8]"} hover:text-white`}>
                    <ThumbsUp className="w-3 h-3" /><span>{q.upvotes}</span>
                  </button>
                </div>
                <p className="text-[11px] text-[#E2E8F0]">{q.text}</p>
                {q.answered_at ? (
                  <div className="text-[10px] text-[#2BB3A0] font-semibold flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> {fill(t("live_class.answered_live"), { t: q.answered_at })}</div>
                ) : isTrainer && (
                  <button onClick={() => answered(q.id)} className="text-[10px] text-[#94A3B8] hover:text-white underline">{t("live_class.mark_answered")}</button>
                )}
              </div>
            ))}
            <form onSubmit={ask} className="flex gap-1.5 pt-1">
              <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder={t("live_class.ask")} aria-label={t("live_class.ask")} className="flex-1 px-2.5 py-1.5 bg-[#0F172A] border border-[#334155] rounded-lg text-xs text-white placeholder-[#64748B] focus:outline-none focus:border-[#2B5CD0]" data-testid="qa-input" />
              <button type="submit" aria-label={t("live_class.send")} className="px-2.5 bg-[#2B5CD0] rounded-lg"><Send className="w-3.5 h-3.5" /></button>
            </form>
          </section>

          {!isTrainer && (
            <section className="bg-[#0F172A] border border-[#334155] rounded-xl p-3.5 space-y-2 text-xs" data-testid="auto-attendance">
              <div className="flex items-center justify-between font-bold text-[#E2E8F0]">
                <span className="flex items-center gap-1.5"><Clock className="w-3.5 h-3.5 text-[#2BB3A0]" /> {t("live_class.auto_attendance")}</span>
                {a && <span className="text-[#2BB3A0]">{a.minutes_present} / {a.total_minutes} min</span>}
              </div>
              {a ? (
                <>
                  <div className="w-full bg-[#1E293B] h-2 rounded-full overflow-hidden" role="progressbar" aria-valuenow={a.minutes_present} aria-valuemin={0} aria-valuemax={a.total_minutes}>
                    <div className="bg-[#2BB3A0] h-full rounded-full" style={{ width: `${Math.min(100, (a.minutes_present / a.total_minutes) * 100)}%` }} />
                  </div>
                  <p className="text-[11px] text-[#94A3B8] leading-tight">
                    {a.joined_at ? fill(t("live_class.attendance_detail"), { j: new Date(a.joined_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }), m: a.minutes_present, t: a.total_minutes }) : t("live_class.not_joined")}{" "}
                    {fill(t("live_class.attendance_rule"), { th: a.threshold_minutes, p: a.threshold_pct })}
                  </p>
                </>
              ) : <p className="text-[11px] text-[#94A3B8]">{t("live_class.not_joined")}</p>}
            </section>
          )}
        </aside>
      </div>

      {pollOpen && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50" role="dialog" aria-modal="true" aria-label={t("live_class.new_poll")}>
          <div className="bg-[#141A29] border border-[#334155] rounded-2xl max-w-md w-full p-5 space-y-3">
            <h3 className="text-sm font-bold flex items-center gap-2"><Plus className="w-4 h-4" /> {t("live_class.new_poll")}</h3>
            <label className="block text-xs font-semibold">{t("live_class.poll_question")}
              <input value={pollQ} onChange={(e) => setPollQ(e.target.value)} className="mt-1 w-full px-3 py-2 bg-[#0F172A] border border-[#334155] rounded-lg text-xs focus:outline-none focus:border-[#2B5CD0]" data-testid="poll-question" />
            </label>
            <label className="block text-xs font-semibold">{t("live_class.poll_options")}
              <textarea rows={3} value={pollOpts} onChange={(e) => setPollOpts(e.target.value)} className="mt-1 w-full px-3 py-2 bg-[#0F172A] border border-[#334155] rounded-lg text-xs focus:outline-none focus:border-[#2B5CD0]" data-testid="poll-options" />
            </label>
            <div className="flex gap-2">
              <button onClick={() => setPollOpen(false)} className="flex-1 py-2 bg-[#1E293B] text-xs font-bold rounded-lg">✕</button>
              <button onClick={launchPoll} className="flex-1 py-2 bg-[#2BB3A0] text-xs font-bold rounded-lg" data-testid="launch-poll">{t("live_class.launch_poll")}</button>
            </div>
          </div>
        </div>
      )}

      {toast && <div role="status" className="fixed bottom-20 right-6 z-50 bg-[#0F172A] border border-[#334155] text-xs font-semibold px-4 py-3 rounded-xl shadow-2xl" data-testid="toast">{toast}</div>}
    </>
  );
}
