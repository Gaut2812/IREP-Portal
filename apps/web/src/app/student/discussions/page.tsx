"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { useAuth } from "@/lib/AuthContext";
import { fetchApi, WS_BASE } from "@/lib/api";
import {
  Users, Lock, Pin, Send, ThumbsUp, CheckCircle2, ShieldCheck, Code2, AlertCircle, RefreshCw, Flag, Bot, Laptop, BarChart3, Briefcase, Mic, GraduationCap, X,
} from "lucide-react";

interface Group { id: string; name: string; kind: string; icon: string; is_locked: boolean; unread: number; preview: string; my_role: string }
interface Message {
  id: string; sender_name: string; sender_role: string; sender_initials: string; is_mine: boolean; message_text: string; code_snippet: string | null;
  is_removed: boolean; is_marked_as_answer: boolean; reactions: number; my_reaction: boolean; reported_by_me: boolean; time: string;
}
interface Thread {
  group: { id: string; name: string; kind: string; icon: string; is_locked: boolean; pinned_note: string | null; moderators: string[] };
  me: { role: string; can_post: boolean; muted_until: string | null };
  messages: Message[];
}
interface Info { students: number; moderators: number; online: number; doubts_answered: number; avg_trainer_reply_min: number | null; top_helpers: { name: string; answers: number; medal: string }[] }

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  graduation: GraduationCap, bot: Bot, laptop: Laptop, chart: BarChart3, briefcase: Briefcase, mic: Mic, users: Users,
};
const MEDAL: Record<string, string> = { gold: "🥇", silver: "🥈", bronze: "🥉" };
const AVATAR = ["bg-violet", "bg-brand", "bg-warning-fill", "bg-teal", "bg-pink-600"];

function fill(template: string, vars: Record<string, string | number>) {
  return Object.entries(vars).reduce((acc, [k, v]) => acc.replace(`{${k}}`, String(v)), template);
}

export default function DiscussionGroupsPage() {
  const { t } = useLanguage();
  const { token } = useAuth();
  const [groups, setGroups] = useState<Group[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [thread, setThread] = useState<Thread | null>(null);
  const [info, setInfo] = useState<Info | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [code, setCode] = useState("");
  const [showCode, setShowCode] = useState(false);
  const [sending, setSending] = useState(false);
  const [toast, setToast] = useState<{ text: string; ok: boolean } | null>(null);
  const [reportFor, setReportFor] = useState<Message | null>(null);
  const [reason, setReason] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const loadGroups = useCallback(async () => {
    try {
      const res = await fetchApi<{ groups: Group[] }>("/student/discussions/groups");
      setGroups(res.groups);
      setSelected((cur) => cur || res.groups.find((g) => g.kind === "track_doubts")?.id || res.groups[0]?.id || null);
      setError(null);
    } catch (err: any) {
      setError(err?.detail || err?.message || "error");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadThread = useCallback(async (gid: string) => {
    try {
      const [th, inf] = await Promise.all([fetchApi<Thread>(`/groups/${gid}/messages`), fetchApi<Info>(`/groups/${gid}/info`)]);
      setThread(th);
      setInfo(inf);
      setGroups((prev) => prev.map((g) => (g.id === gid ? { ...g, unread: 0 } : g)));
    } catch (err: any) {
      setToast({ text: err?.detail || t("discussions.error_title"), ok: false });
    }
  }, [t]);

  useEffect(() => { loadGroups(); }, [loadGroups]);
  useEffect(() => { if (selected) loadThread(selected); }, [selected, loadThread]);
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [thread?.messages.length]);

  // live: WebSocket push for the open group, polling as a fallback
  useEffect(() => {
    if (!selected) return;
    const id = setInterval(() => { loadThread(selected); loadGroups(); }, 10000);
    let ws: WebSocket | null = null;
    if (token && !token.startsWith("mock")) {
      try {
        ws = new WebSocket(`${WS_BASE}/ws/groups/${selected}?token=${encodeURIComponent(token)}`);
        ws.onmessage = () => loadThread(selected);
      } catch { /* polling only */ }
    }
    return () => { clearInterval(id); try { ws?.close(); } catch { /* ignore */ } };
  }, [selected, token, loadThread, loadGroups]);

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(id);
  }, [toast]);

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected || (!text.trim() && !code.trim())) return;
    setSending(true);
    try {
      await fetchApi(`/groups/${selected}/messages`, { method: "POST", body: JSON.stringify({ message_text: text.trim() || "(code snippet)", code_snippet: code.trim() || null }) });
      setText(""); setCode(""); setShowCode(false);
      await loadThread(selected);
    } catch (err: any) {
      setToast({ text: err?.detail || t("discussions.send_failed"), ok: false });
    } finally {
      setSending(false);
    }
  };

  const react = async (m: Message) => {
    try {
      const res = await fetchApi<{ my_reaction: boolean; reactions: number }>(`/messages/${m.id}/react`, { method: "POST" });
      setThread((prev) => prev ? { ...prev, messages: prev.messages.map((x) => x.id === m.id ? { ...x, my_reaction: res.my_reaction, reactions: res.reactions } : x) } : prev);
    } catch { /* ignore */ }
  };

  const markAnswer = async (m: Message) => {
    try {
      await fetchApi(`/messages/${m.id}/mark-answer`, { method: "POST" });
      if (selected) loadThread(selected);
    } catch (err: any) {
      setToast({ text: err?.detail || t("discussions.send_failed"), ok: false });
    }
  };

  const submitReport = async () => {
    if (!reportFor || reason.trim().length < 3) return;
    try {
      await fetchApi(`/messages/${reportFor.id}/report`, { method: "POST", body: JSON.stringify({ reason: reason.trim() }) });
      setThread((prev) => prev ? { ...prev, messages: prev.messages.map((x) => x.id === reportFor.id ? { ...x, reported_by_me: true } : x) } : prev);
      setToast({ text: t("discussions.report_sent"), ok: true });
      setReportFor(null); setReason("");
    } catch (err: any) {
      setToast({ text: err?.detail || t("discussions.send_failed"), ok: false });
    }
  };

  const isModerator = thread?.me.role === "moderator";

  return (
    <RoleGuard allowedRoles={["student", "trainer"]}>
      <AppShell pageTitle={t("discussions.title")}>
        <div className="space-y-6 max-w-7xl mx-auto lg:h-[calc(100vh-120px)] flex flex-col" data-testid="discussions">
          <div className="bg-warning-soft border border-warning-line p-3 rounded-card flex items-center gap-2.5 text-xs text-warning flex-shrink-0">
            <ShieldCheck className="w-4 h-4 text-warning flex-shrink-0" />
            <span><strong>{t("discussions.banner_title")}</strong> {t("discussions.banner")}</span>
          </div>

          {loading && <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-5 animate-pulse" aria-busy="true" aria-label={t("discussions.loading")}><div className="lg:col-span-3 h-80 bg-white rounded-card" /><div className="lg:col-span-6 h-80 bg-white rounded-card" /><div className="lg:col-span-3 h-80 bg-white rounded-card" /></div>}

          {!loading && error && (
            <div className="bg-white rounded-card border border-danger-line p-8 text-center space-y-3 max-w-md mx-auto">
              <AlertCircle className="w-8 h-8 text-danger mx-auto" />
              <h2 className="text-base font-semibold text-ink">{t("discussions.error_title")}</h2>
              <p className="text-xs text-muted">{error}</p>
              <button onClick={loadGroups} className="inline-flex items-center gap-1.5 px-4 py-2 bg-brand text-white text-xs font-semibold rounded-tile"><RefreshCw className="w-3.5 h-3.5" /> {t("discussions.retry")}</button>
            </div>
          )}

          {!loading && !error && groups.length === 0 && <p className="text-xs text-muted text-center py-10">{t("discussions.no_groups")}</p>}

          {!loading && !error && groups.length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 flex-1 min-h-0">
              {/* Groups */}
              <div className="lg:col-span-3 bg-white rounded-card border border-line shadow-card p-3 flex flex-col justify-between overflow-hidden" data-testid="group-list">
                <div className="min-h-0 overflow-y-auto">
                  <div className="text-caption font-semibold text-muted px-2 py-1.5 border-b border-line">{t("discussions.my_groups")}</div>
                  <div className="mt-2 space-y-1">
                    {groups.map((g) => {
                      const Icon = ICONS[g.icon] || Users;
                      const active = selected === g.id;
                      return (
                        <button key={g.id} onClick={() => setSelected(g.id)} data-testid={`group-${g.id}`} aria-current={active}
                          className={`w-full flex items-center gap-2.5 px-2.5 py-2.5 rounded-card text-left text-xs transition-all ${active ? "bg-brand-soft border border-brand-line" : "hover:bg-surface-2 border border-transparent"}`}>
                          <span className="w-8 h-8 rounded-tile bg-line-soft flex items-center justify-center flex-shrink-0"><Icon className="w-4 h-4 text-brand" /></span>
                          <div className="min-w-0 flex-1">
                            <div className={`truncate flex items-center gap-1 ${active ? "font-semibold text-info" : "font-semibold text-ink"}`}>{g.name}{g.is_locked && <Lock className="w-3 h-3 text-warning flex-shrink-0" aria-label="announcement-only" />}</div>
                            <div className="text-caption text-muted truncate">{g.preview}</div>
                          </div>
                          {g.unread > 0 && <span className="min-w-[20px] h-5 px-1 rounded-full bg-brand text-white text-caption font-semibold flex items-center justify-center flex-shrink-0" data-testid={`unread-${g.id}`}>{g.unread}</span>}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div className="text-caption text-muted p-2 mt-2 bg-surface-2 rounded-tile border border-line leading-tight flex gap-1.5"><Lock className="w-3 h-3 flex-shrink-0 text-warning" />{t("discussions.locked_note")}</div>
              </div>

              {/* Conversation */}
              <div className="lg:col-span-6 bg-white rounded-card border border-line shadow-card flex flex-col overflow-hidden min-h-[480px]" data-testid="conversation">
                {thread && (
                  <>
                    <div className="p-4 border-b border-line flex items-center justify-between gap-2 flex-shrink-0">
                      <div className="min-w-0">
                        <h3 className="text-sm font-semibold text-ink truncate">{thread.group.name}</h3>
                        <p className="text-caption text-muted truncate">{fill(t("discussions.members_mods"), { n: (info?.students || 0) + (info?.moderators || 0), m: thread.group.moderators.join(" & ") })}</p>
                      </div>
                      {info && <span className="chip-green text-caption flex-shrink-0">● {fill(t("discussions.online"), { n: info.online })}</span>}
                    </div>
                    {thread.group.pinned_note && (
                      <div className="bg-warning-faint border-b border-warning-soft px-4 py-2 flex items-center gap-2 text-caption text-warning flex-shrink-0">
                        <Pin className="w-3.5 h-3.5 text-warning flex-shrink-0" /><span><strong>{t("discussions.pinned")}</strong> {thread.group.pinned_note}</span>
                      </div>
                    )}
                    <div className="flex-1 overflow-y-auto p-4 space-y-4" data-testid="messages">
                      {thread.messages.length === 0 && <p className="text-xs text-muted text-center py-10">{t("discussions.no_messages")}</p>}
                      {thread.messages.map((m, i) => (
                        <div key={m.id} className={`space-y-1.5 ${m.is_marked_as_answer ? "bg-success-faint border border-success-line p-3 rounded-card" : ""}`} data-testid={`msg-${m.id}`}>
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2 min-w-0">
                              <span className={`w-6 h-6 rounded-full ${m.sender_role === "Trainer" ? "bg-teal" : AVATAR[i % AVATAR.length]} text-white font-semibold text-caption flex items-center justify-center flex-shrink-0`}>{m.sender_initials}</span>
                              <span className="text-xs font-semibold text-ink truncate">{m.sender_name}</span>
                              {m.sender_role === "Trainer" && <span className="px-1.5 py-0.5 rounded bg-success-soft text-success text-caption font-semibold">{t("discussions.trainer")}</span>}
                              <span className="text-caption text-muted">{m.time}</span>
                            </div>
                            {m.is_marked_as_answer && <span className="chip-green text-caption font-semibold flex-shrink-0"><CheckCircle2 className="w-3 h-3" /> {t("discussions.marked_answer")}</span>}
                          </div>
                          <div className="pl-8 space-y-2">
                            <p className={`text-xs leading-relaxed ${m.is_removed ? "italic text-subtle" : "text-ink-soft"}`}>{m.is_removed ? t("discussions.removed") : m.message_text}</p>
                            {m.code_snippet && <pre className="bg-[#1B2236] text-line p-2.5 rounded-tile text-xs font-mono overflow-x-auto whitespace-pre-wrap">{m.code_snippet}</pre>}
                            {!m.is_removed && (
                              <div className="flex items-center gap-2">
                                <button onClick={() => react(m)} aria-pressed={m.my_reaction} data-testid={`react-${m.id}`}
                                  className={`flex items-center gap-1 px-2 py-0.5 rounded-tile text-caption font-semibold border ${m.my_reaction ? "bg-success-soft border-success-line text-success" : "bg-white border-line text-muted hover:bg-surface-2"}`}>
                                  👍 <span>{m.reactions}</span>
                                </button>
                                {isModerator && !m.is_marked_as_answer && <button onClick={() => markAnswer(m)} className="text-caption text-success hover:underline" data-testid={`answer-${m.id}`}>{t("discussions.mark_answer")}</button>}
                                {!m.is_mine && (m.reported_by_me
                                  ? <span className="text-caption text-subtle">{t("discussions.reported")}</span>
                                  : <button onClick={() => { setReportFor(m); setReason(""); }} className="text-caption text-subtle hover:text-danger flex items-center gap-0.5" aria-label={`${t("discussions.report")} ${m.sender_name}`} data-testid={`report-${m.id}`}><Flag className="w-3 h-3" /> {t("discussions.report")}</button>)}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                      <div ref={endRef} />
                    </div>
                    {thread.me.can_post ? (
                      <form onSubmit={send} className="p-3 border-t border-line space-y-2 flex-shrink-0">
                        {showCode && <textarea value={code} onChange={(e) => setCode(e.target.value)} rows={3} placeholder={t("discussions.code_placeholder")} className="w-full font-mono text-xs bg-[#1B2236] text-line rounded-tile p-2 focus:outline-none" data-testid="code-input" />}
                        <div className="flex items-center gap-2">
                          <input value={text} onChange={(e) => setText(e.target.value)} placeholder={t("discussions.ask")} aria-label={t("discussions.ask")} data-testid="message-input"
                            className="flex-1 px-3.5 py-2 bg-surface-2 border border-line rounded-card text-xs text-ink focus:outline-none focus:border-brand focus:bg-white" />
                          <button type="button" onClick={() => setShowCode(!showCode)} aria-pressed={showCode} className="p-2 text-muted hover:text-ink flex items-center gap-1 text-caption" data-testid="toggle-code"><Code2 className="w-4 h-4" /> {t("discussions.code")}</button>
                          <button type="submit" disabled={sending} className="px-4 py-2 bg-brand hover:bg-brand-hover text-white font-semibold text-xs rounded-card flex items-center gap-1.5 disabled:opacity-50" data-testid="send"><span>{t("discussions.send")}</span><Send className="w-3.5 h-3.5" /></button>
                        </div>
                      </form>
                    ) : (
                      <div className="p-3 border-t border-line text-caption text-warning bg-warning-faint flex items-center gap-2 flex-shrink-0" data-testid="locked-input">
                        <Lock className="w-3.5 h-3.5" /> {thread.me.muted_until ? t("discussions.muted_input") : t("discussions.locked_input")}
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* Info */}
              <div className="lg:col-span-3 space-y-4 overflow-y-auto">
                {info && (
                  <>
                    <div className="bg-white rounded-card border border-line p-4 shadow-card space-y-2 text-xs text-ink" data-testid="group-info">
                      <h4 className="font-semibold border-b border-line pb-2">{t("discussions.group_info")}</h4>
                      <div>👥 {fill(t("discussions.students"), { n: info.students })}</div>
                      <div>🧑‍🏫 {fill(t("discussions.moderators"), { n: info.moderators })}</div>
                      <div>✅ {fill(t("discussions.answered"), { n: info.doubts_answered })}</div>
                      {info.avg_trainer_reply_min !== null && <div>⏱ {fill(t("discussions.avg_reply"), { n: info.avg_trainer_reply_min })}</div>}
                    </div>
                    <div className="bg-white rounded-card border border-line p-4 shadow-card space-y-2" data-testid="top-helpers">
                      <div className="flex items-center justify-between border-b border-line pb-2"><h4 className="text-xs font-semibold text-ink">{t("discussions.top_helpers")}</h4><span className="text-caption text-muted">{t("discussions.this_month")}</span></div>
                      {info.top_helpers.map((h) => <div key={h.name} className="text-xs text-ink">{MEDAL[h.medal]} {h.name} · {fill(t("discussions.answers"), { n: h.answers })}</div>)}
                    </div>
                  </>
                )}
                <div className="bg-white rounded-card border border-line p-4 shadow-card space-y-1.5 text-caption text-muted">
                  <h4 className="text-xs font-semibold text-ink">{t("discussions.safety")}</h4>
                  <p>{t("discussions.safety_body")}</p>
                </div>
              </div>
            </div>
          )}
        </div>

        {reportFor && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" role="dialog" aria-modal="true" aria-label={t("discussions.report")} data-testid="report-dialog">
            <div className="bg-white rounded-card max-w-md w-full p-6 space-y-3 shadow-pop border border-line">
              <div className="flex items-center justify-between"><h3 className="text-sm font-semibold text-ink">{t("discussions.report_reason")}</h3><button onClick={() => setReportFor(null)} aria-label={t("discussions.cancel")} className="p-1 rounded hover:bg-line-soft"><X className="w-4 h-4 text-muted" /></button></div>
              <p className="text-xs text-muted bg-surface-2 rounded-tile p-2 border border-line">{reportFor.message_text}</p>
              <input value={reason} onChange={(e) => setReason(e.target.value)} className="w-full px-3 py-2 border border-line rounded-tile text-xs focus:outline-none focus:border-brand" data-testid="report-reason" />
              <div className="flex gap-2">
                <button onClick={() => setReportFor(null)} className="flex-1 py-2 bg-line-soft text-ink font-semibold text-xs rounded-card">{t("discussions.cancel")}</button>
                <button onClick={submitReport} disabled={reason.trim().length < 3} className="flex-1 py-2 bg-danger text-white font-semibold text-xs rounded-card disabled:opacity-50" data-testid="report-send">{t("discussions.report_send")}</button>
              </div>
            </div>
          </div>
        )}

        {toast && (
          <div role="status" className={`fixed bottom-6 right-6 z-50 text-white text-xs font-semibold px-4 py-3 rounded-card shadow-pop flex items-center gap-2 max-w-sm ${toast.ok ? "bg-ink" : "bg-danger"}`} data-testid="toast">
            {toast.ok ? <CheckCircle2 className="w-4 h-4 text-teal flex-shrink-0" /> : <AlertCircle className="w-4 h-4 flex-shrink-0" />} {toast.text}
          </div>
        )}
      </AppShell>
    </RoleGuard>
  );
}
