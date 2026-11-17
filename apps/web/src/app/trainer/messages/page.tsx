"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { useAuth } from "@/lib/AuthContext";
import { fetchApi, WS_BASE } from "@/lib/api";
import { Search, Send, Languages, Radio, AlertCircle, RefreshCw, CheckCircle2, X, Users, ExternalLink } from "lucide-react";

interface ThreadRow { id: string; kind: "thread" | "group"; name: string; category: string; role_chip: string; avatar: string; unread: number; last_message: string; time: string }
interface MatrixRow { key: string; label_en: string; label_ta: string; status_en: string; status_ta: string; color: string }
interface Child { id: string; name: string; batch: string; readiness: number | null; band: string | null }
interface ThreadDetail {
  thread: { id: string; category: string; contact_name: string; contact_role: string; prefers_tamil: boolean; trainer_name: string; child: Child | null };
  messages: { id: string; is_mine: boolean; sender_name: string; text: string; original_text: string; translated: boolean; time: string }[];
}
interface GroupMsg { id: string; sender_name: string; sender_role: string; message_text: string; is_removed: boolean; time: string }
interface ModItem { id: string; group: string; reason: string; author: string; snippet: string; time: string }
interface Delivery { students: number; parents: number; parents_sms: number; total_recipients: number }
interface BroadcastRow { id: string; title: string; audience: string; delivery: Delivery; time: string }

const CATS = ["All", "Parents", "College", "Groups"] as const;
const CHIP: Record<string, string> = { red: "chip-red", green: "chip-green", blue: "chip-blue" };

function fill(template: string, vars: Record<string, string | number>) {
  return Object.entries(vars).reduce((acc, [k, v]) => acc.split(`{${k}}`).join(String(v)), template);
}

export default function TrainerMessageHubPage() {
  const { t, language } = useLanguage();
  const { token } = useAuth();
  const [category, setCategory] = useState<(typeof CATS)[number]>("All");
  const [query, setQuery] = useState("");
  const [threads, setThreads] = useState<ThreadRow[]>([]);
  const [matrix, setMatrix] = useState<MatrixRow[]>([]);
  const [selected, setSelected] = useState<ThreadRow | null>(null);
  const [detail, setDetail] = useState<ThreadDetail | null>(null);
  const [groupMsgs, setGroupMsgs] = useState<GroupMsg[] | null>(null);
  const [showTamil, setShowTamil] = useState(false);
  const [showCard, setShowCard] = useState(false);
  const [reply, setReply] = useState("");
  const [autoTranslate, setAutoTranslate] = useState(true);
  const [sending, setSending] = useState(false);
  const [queue, setQueue] = useState<ModItem[]>([]);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [batches, setBatches] = useState<{ id: string; name: string }[]>([]);
  const [history, setHistory] = useState<BroadcastRow[]>([]);
  const [modal, setModal] = useState(false);
  const [bc, setBc] = useState({ audience: "both", batch: "", title: "", body: "" });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ text: string; ok: boolean } | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const loadThreads = useCallback(async () => {
    try {
      const res = await fetchApi<{ threads: ThreadRow[]; permission_matrix: MatrixRow[] }>(`/trainer/threads?category=${category}`);
      setThreads(res.threads);
      setMatrix(res.permission_matrix);
      setSelected((cur) => (cur && res.threads.find((x) => x.id === cur.id)) || res.threads[0] || null);
      setError(null);
    } catch (err: any) {
      setError(err?.detail || err?.message || "error");
    } finally {
      setLoading(false);
    }
  }, [category]);

  const loadQueue = useCallback(async () => {
    try { setQueue((await fetchApi<{ items: ModItem[] }>("/trainer/moderation")).items); } catch { /* panel shows empty */ }
  }, []);
  const loadBroadcasts = useCallback(async () => {
    try {
      const res = await fetchApi<{ batches: { id: string; name: string }[]; broadcasts: BroadcastRow[] }>("/trainer/broadcasts");
      setBatches(res.batches); setHistory(res.broadcasts);
    } catch { /* optional panel */ }
  }, []);

  const loadSelected = useCallback(async (row: ThreadRow, tamil: boolean) => {
    try {
      if (row.kind === "group") {
        const res = await fetchApi<{ messages: GroupMsg[] }>(`/groups/${row.id}/messages`);
        setGroupMsgs(res.messages.slice(-30)); setDetail(null);
      } else {
        const res = await fetchApi<ThreadDetail>(`/threads/${row.id}/messages${tamil ? "?lang=ta" : ""}`);
        setDetail(res); setGroupMsgs(null);
        setThreads((prev) => prev.map((x) => (x.id === row.id ? { ...x, unread: 0 } : x)));
      }
    } catch (err: any) {
      setToast({ text: err?.detail || t("hub.error_title"), ok: false });
    }
  }, [t]);

  useEffect(() => { loadThreads(); }, [loadThreads]);
  useEffect(() => { loadQueue(); loadBroadcasts(); }, [loadQueue, loadBroadcasts]);
  useEffect(() => { if (selected) loadSelected(selected, showTamil); }, [selected?.id, showTamil, loadSelected]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [detail?.messages.length, groupMsgs?.length]);
  useEffect(() => { setShowCard(false); }, [selected?.id]);

  useEffect(() => {
    if (!selected || selected.kind !== "thread") return;
    const id = setInterval(() => loadSelected(selected, showTamil), 10000);
    let ws: WebSocket | null = null;
    if (token && !token.startsWith("mock")) {
      try {
        ws = new WebSocket(`${WS_BASE}/ws/threads/${selected.id}?token=${encodeURIComponent(token)}`);
        ws.onmessage = () => loadSelected(selected, showTamil);
      } catch { /* polling only */ }
    }
    return () => { clearInterval(id); try { ws?.close(); } catch { /* ignore */ } };
  }, [selected, showTamil, token, loadSelected]);

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(id);
  }, [toast]);

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected || !reply.trim()) return;
    setSending(true);
    try {
      if (selected.kind === "group") {
        await fetchApi(`/groups/${selected.id}/messages`, { method: "POST", body: JSON.stringify({ message_text: reply.trim() }) });
      } else {
        await fetchApi(`/threads/${selected.id}/messages`, { method: "POST", body: JSON.stringify({ text: reply.trim(), auto_translate: autoTranslate }) });
      }
      setReply("");
      await loadSelected(selected, showTamil);
      loadThreads();
    } catch (err: any) {
      setToast({ text: err?.detail || t("hub.send_failed"), ok: false });
    } finally {
      setSending(false);
    }
  };

  const moderate = async (item: ModItem, action: "remove" | "keep" | "mute") => {
    const reason = (reasons[item.id] || "").trim();
    if (action !== "keep" && reason.length < 3) { setToast({ text: t("hub.reason_required"), ok: false }); return; }
    try {
      await fetchApi(`/trainer/moderation/${item.id}`, { method: "POST", body: JSON.stringify({ action, reason: reason || null }) });
      setQueue((q) => q.filter((x) => x.id !== item.id));
      setToast({ text: t("hub.handled"), ok: true });
    } catch (err: any) {
      setToast({ text: err?.detail || t("hub.send_failed"), ok: false });
    }
  };

  const sendBroadcast = async () => {
    if (bc.title.trim().length < 3 || bc.body.trim().length < 3) return;
    try {
      const res = await fetchApi<{ delivery: Delivery }>("/broadcasts", {
        method: "POST", body: JSON.stringify({ audience: bc.audience, batch_ids: bc.batch ? [bc.batch] : [], title: bc.title.trim(), body: bc.body.trim() }),
      });
      const d = res.delivery;
      setToast({ text: fill(t("hub.delivery"), { total: d.total_recipients, students: d.students, parents: d.parents, sms: d.parents_sms }), ok: true });
      setModal(false); setBc({ audience: "both", batch: "", title: "", body: "" });
      loadBroadcasts();
    } catch (err: any) {
      setToast({ text: err?.detail || t("hub.send_failed"), ok: false });
    }
  };

  const visible = threads.filter((x) => !query || x.name.toLowerCase().includes(query.toLowerCase()) || x.last_message.toLowerCase().includes(query.toLowerCase()));
  const th = detail?.thread;
  const catLabel: Record<string, string> = { All: t("hub.all"), Parents: t("hub.parents"), College: t("hub.college"), Groups: t("hub.groups") };

  return (
    <RoleGuard allowedRoles={["trainer"]}>
      <AppShell pageTitle={t("hub.title")}>
        {loading && <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 max-w-7xl mx-auto animate-pulse" aria-busy="true" aria-label={t("hub.loading")}><div className="lg:col-span-3 h-96 bg-white rounded-xl" /><div className="lg:col-span-6 h-96 bg-white rounded-xl" /><div className="lg:col-span-3 h-96 bg-white rounded-xl" /></div>}

        {!loading && error && (
          <div className="bg-white rounded-2xl border border-[#FECACA] p-8 text-center space-y-3 max-w-md mx-auto">
            <AlertCircle className="w-8 h-8 text-[#D93636] mx-auto" />
            <h2 className="text-base font-bold text-[#0F1F3A]">{t("hub.error_title")}</h2>
            <p className="text-xs text-[#64748B]">{error}</p>
            <button onClick={loadThreads} className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg"><RefreshCw className="w-3.5 h-3.5" /> {t("hub.retry")}</button>
          </div>
        )}

        {!loading && !error && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 lg:h-[calc(100vh-120px)] max-w-7xl mx-auto" data-testid="message-hub">
            {/* Threads */}
            <div className="lg:col-span-3 bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-3 flex flex-col overflow-hidden max-h-[70vh] lg:max-h-none">
              <div className="relative mb-2 flex-shrink-0">
                <Search className="w-3.5 h-3.5 text-[#94A3B8] absolute left-2.5 top-1/2 -translate-y-1/2" />
                <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("hub.search")} aria-label={t("hub.search")} className="w-full pl-8 pr-2 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg text-xs focus:outline-none focus:border-[#2B5CD0]" />
              </div>
              <div className="flex gap-1.5 pb-3 border-b border-[#E2E8F0] overflow-x-auto flex-shrink-0" role="tablist">
                {CATS.map((c) => (
                  <button key={c} role="tab" aria-selected={category === c} onClick={() => setCategory(c)} data-testid={`cat-${c}`}
                    className={`px-2.5 py-1 rounded-full text-xs font-semibold whitespace-nowrap ${category === c ? "bg-[#2B5CD0] text-white" : "bg-[#F1F5F9] text-[#64748B] hover:bg-[#E2E8F0]"}`}>{catLabel[c]}</button>
                ))}
              </div>
              <div className="flex-1 overflow-y-auto space-y-1 pt-2" data-testid="thread-list">
                {visible.length === 0 && <p className="text-xs text-[#64748B] text-center py-6">{t("hub.no_threads")}</p>}
                {visible.map((row) => {
                  const active = selected?.id === row.id;
                  return (
                    <button key={row.id} onClick={() => setSelected(row)} data-testid={`thread-${row.id}`} aria-current={active}
                      className={`w-full p-2.5 rounded-xl text-left flex items-start gap-2.5 ${active ? "bg-[#EFF6FF] border border-[#BFDBFE]" : "hover:bg-[#F8FAFC] border border-transparent"}`}>
                      <div className={`w-8 h-8 rounded-full ${row.kind === "group" ? "bg-[#2BB3A0]" : "bg-[#14284B]"} text-white font-bold text-xs flex items-center justify-center flex-shrink-0`}>{row.kind === "group" ? <Users className="w-4 h-4" /> : row.avatar}</div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-1"><span className="font-bold text-xs text-[#0F1F3A] truncate">{row.name}</span><span className="text-[10px] text-[#94A3B8] flex-shrink-0">{row.time}</span></div>
                        <div className="text-[10px] font-semibold text-[#2B5CD0]">{row.role_chip}</div>
                        <p className="text-[11px] text-[#64748B] truncate mt-0.5">{row.last_message}</p>
                      </div>
                      {row.unread > 0 && <span className="min-w-[16px] h-4 px-1 rounded-full bg-[#D93636] text-white text-[9px] font-bold flex items-center justify-center flex-shrink-0 mt-1" data-testid={`unread-${row.id}`}>{row.unread}</span>}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Conversation */}
            <div className="lg:col-span-6 bg-white rounded-xl border border-[#E2E8F0] shadow-sm flex flex-col overflow-hidden min-h-[480px]" data-testid="conversation">
              {selected && (
                <>
                  <div className="p-3.5 border-b border-[#E2E8F0] flex items-center justify-between gap-2 flex-shrink-0 relative">
                    <div className="min-w-0">
                      <h3 className="text-sm font-bold text-[#0F1F3A] truncate">{selected.name}</h3>
                      <p className="text-[11px] text-[#64748B] truncate">
                        {selected.kind === "group" ? t("hub.group_note") : th?.child ? fill(t("hub.parent_of"), { child: th.child.name, batch: th.child.batch }) : selected.role_chip}
                        {th && th.contact_role === "parent" && <> · <span className="text-[#2B5CD0] font-semibold">{th.prefers_tamil ? t("hub.prefers_tamil") : t("hub.prefers_english")}</span></>}
                      </p>
                    </div>
                    {th?.child && <button onClick={() => setShowCard(!showCard)} aria-expanded={showCard} className="px-3 py-1 bg-[#F1F5F9] hover:bg-[#E2E8F0] text-[#2B5CD0] text-xs font-bold rounded-lg border border-[#CBD5E1] flex-shrink-0" data-testid="progress-toggle">{t("hub.progress")}</button>}
                    {selected.kind === "group" && <Link href="/student/discussions" className="px-3 py-1 bg-[#F1F5F9] text-[#2B5CD0] text-xs font-bold rounded-lg border border-[#CBD5E1] flex items-center gap-1 flex-shrink-0"><ExternalLink className="w-3 h-3" />{t("hub.open_group")}</Link>}
                    {showCard && th?.child && (
                      <div className="absolute right-3 top-full mt-1 z-10 bg-white border border-[#E2E8F0] rounded-xl shadow-lg p-3 text-xs w-60 space-y-1" data-testid="progress-card">
                        <div className="font-bold text-[#0F1F3A]">{th.child.name}</div>
                        <div className="text-[#64748B]">{th.child.batch}</div>
                        {th.child.readiness !== null && <div className="text-[#0F1F3A]">{fill(t("hub.readiness"), { score: th.child.readiness, band: th.child.band || "" })}</div>}
                      </div>
                    )}
                  </div>
                  {selected.kind === "thread" && (
                    <div className="bg-[#EFF6FF] border-b border-[#BFDBFE] px-4 py-1.5 flex items-center justify-between text-xs text-[#1D4ED8] flex-shrink-0">
                      <span className="flex items-center gap-1.5 font-medium"><Languages className="w-3.5 h-3.5 text-[#2B5CD0]" />{t("hub.translate_available")}</span>
                      <button onClick={() => setShowTamil(!showTamil)} aria-pressed={showTamil} className="text-[11px] font-bold underline hover:text-[#1E3A8A]" data-testid="toggle-tamil">{showTamil ? t("hub.show_original") : t("hub.show_tamil")}</button>
                    </div>
                  )}
                  <div className="flex-1 overflow-y-auto p-4 space-y-3.5" data-testid="messages">
                    {detail && detail.messages.length === 0 && <p className="text-xs text-[#64748B] text-center py-10">{t("hub.no_messages")}</p>}
                    {detail?.messages.map((m) => (
                      <div key={m.id} className={`flex flex-col ${m.is_mine ? "items-end" : "items-start"}`}>
                        <div className={`max-w-[80%] p-3.5 rounded-2xl text-xs space-y-1 ${m.is_mine ? "bg-[#2B5CD0] text-white" : "bg-[#F1F5F9] text-[#0F1F3A]"}`}>
                          <p className="leading-relaxed">{m.text}</p>
                          {m.translated && <p className={`text-[10px] italic ${m.is_mine ? "text-white/70" : "text-[#64748B]"}`} title={m.original_text}>{t("hub.translated")} · {t("hub.original")}: {m.original_text}</p>}
                          <div className={`text-[9px] text-right ${m.is_mine ? "text-white/70" : "text-[#94A3B8]"}`}>{m.time}</div>
                        </div>
                      </div>
                    ))}
                    {groupMsgs?.map((m) => (
                      <div key={m.id} className="text-xs">
                        <span className="font-bold text-[#0F1F3A]">{m.sender_name}</span>{m.sender_role === "Trainer" && <span className="ml-1 px-1 rounded bg-[#DCFCE7] text-[#15803D] text-[9px] font-bold">Trainer</span>}
                        <span className="text-[10px] text-[#94A3B8] ml-1.5">{m.time}</span>
                        <p className={m.is_removed ? "italic text-[#94A3B8]" : "text-[#334155]"}>{m.message_text}</p>
                      </div>
                    ))}
                    <div ref={endRef} />
                  </div>
                  <form onSubmit={send} className="p-3 border-t border-[#E2E8F0] space-y-1.5 flex-shrink-0">
                    {th?.prefers_tamil && (
                      <label className="flex items-center gap-1.5 text-[11px] text-[#64748B]"><input type="checkbox" checked={autoTranslate} onChange={(e) => setAutoTranslate(e.target.checked)} data-testid="auto-translate" /> {t("hub.auto_translate")}</label>
                    )}
                    <div className="flex items-center gap-2">
                      <input value={reply} onChange={(e) => setReply(e.target.value)} placeholder={t("hub.type")} aria-label={t("hub.type")} data-testid="reply-input"
                        className="flex-1 px-3.5 py-2 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-xs text-[#0F1F3A] focus:outline-none focus:border-[#2B5CD0] focus:bg-white" />
                      <button type="submit" disabled={sending} className="px-4 py-2 bg-[#2B5CD0] hover:bg-[#1E46B0] text-white font-bold text-xs rounded-xl flex items-center gap-1.5 disabled:opacity-50" data-testid="send"><span>{t("hub.send")}</span><Send className="w-3.5 h-3.5" /></button>
                    </div>
                  </form>
                </>
              )}
            </div>

            {/* Right column */}
            <div className="lg:col-span-3 space-y-4 overflow-y-auto">
              <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm space-y-3" data-testid="permission-matrix">
                <h4 className="text-xs font-bold text-[#0F1F3A] border-b border-[#E2E8F0] pb-2">{t("hub.who_can")}</h4>
                <div className="space-y-1.5">
                  {matrix.map((r) => (
                    <div key={r.key} className="flex items-center justify-between text-xs gap-2"><span className="text-[#64748B]">{language === "ta" ? r.label_ta : r.label_en}</span><span className={CHIP[r.color] || "chip-blue"}>{language === "ta" ? r.status_ta : r.status_en}</span></div>
                  ))}
                </div>
              </div>

              <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm space-y-3" data-testid="moderation-queue">
                <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
                  <h4 className="text-xs font-bold text-[#0F1F3A]">{t("hub.moderation")}</h4>
                  {queue.length > 0 && <span className="min-w-[16px] h-4 px-1 rounded-full bg-[#D93636] text-white text-[10px] font-bold flex items-center justify-center" data-testid="queue-count">{queue.length}</span>}
                </div>
                {queue.length === 0 ? <div className="text-xs text-[#64748B] italic py-2 text-center">{t("hub.queue_empty")}</div> : (
                  <div className="space-y-2">
                    {queue.map((item) => (
                      <div key={item.id} className="p-2.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg space-y-2 text-xs" data-testid={`mod-${item.id}`}>
                        <div>
                          <div className="text-[10px] text-[#64748B]">{item.author} · {item.group} · {item.time}</div>
                          <div className="font-medium text-[#0F1F3A]">{item.reason}</div>
                          <div className="text-[11px] text-[#64748B] italic mt-0.5">“{item.snippet}”</div>
                        </div>
                        <input value={reasons[item.id] || ""} onChange={(e) => setReasons({ ...reasons, [item.id]: e.target.value })} placeholder={t("hub.reason")} aria-label={t("hub.reason")}
                          className="w-full px-2 py-1 border border-[#E2E8F0] rounded text-[11px] bg-white focus:outline-none focus:border-[#2B5CD0]" data-testid={`reason-${item.id}`} />
                        <div className="flex gap-1.5">
                          <button onClick={() => moderate(item, "remove")} className="px-2.5 py-1 bg-red-100 hover:bg-red-200 text-red-700 font-bold text-[10px] rounded" data-testid={`remove-${item.id}`}>{t("hub.remove")}</button>
                          <button onClick={() => moderate(item, "mute")} className="px-2.5 py-1 bg-amber-100 hover:bg-amber-200 text-amber-800 font-bold text-[10px] rounded">{t("hub.mute")}</button>
                          <button onClick={() => moderate(item, "keep")} className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-[#0F1F3A] font-bold text-[10px] rounded" data-testid={`keep-${item.id}`}>{t("hub.keep")}</button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm space-y-2">
                <h4 className="text-xs font-bold text-[#0F1F3A]">{t("hub.broadcast")}</h4>
                <p className="text-[11px] text-[#64748B]">{t("hub.broadcast_body")}</p>
                <button onClick={() => setModal(true)} className="w-full py-2 bg-[#2BB3A0] hover:bg-[#249B8A] text-white font-bold text-xs rounded-xl flex items-center justify-center gap-1.5" data-testid="new-broadcast"><Radio className="w-3.5 h-3.5" /><span>{t("hub.new_announcement")}</span></button>
                {history.length > 0 && (
                  <div className="pt-2 space-y-1" data-testid="broadcast-history">
                    <div className="text-[10px] font-bold text-[#64748B] uppercase">{t("hub.recent")}</div>
                    {history.slice(0, 3).map((b) => <div key={b.id} className="text-[11px] text-[#0F1F3A] flex justify-between gap-2"><span className="truncate">{b.title}</span><span className="text-[#64748B] flex-shrink-0">{b.delivery.total_recipients} · {b.time}</span></div>)}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {modal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" role="dialog" aria-modal="true" aria-label={t("hub.bc_title")}>
            <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl border border-[#E2E8F0]">
              <div className="flex items-center justify-between"><h3 className="text-base font-bold text-[#0F1F3A]">{t("hub.bc_title")}</h3><button onClick={() => setModal(false)} aria-label={t("hub.cancel")} className="p-1 rounded hover:bg-[#F1F5F9]"><X className="w-4 h-4 text-[#64748B]" /></button></div>
              <div className="space-y-3 text-xs">
                <label className="block"><span className="font-bold text-[#0F1F3A] block mb-1">{t("hub.audience")}</span>
                  <select value={bc.audience} onChange={(e) => setBc({ ...bc, audience: e.target.value })} className="w-full p-2 border rounded-lg bg-[#F8FAFC]" data-testid="bc-audience">
                    <option value="students">{t("hub.aud_students")}</option><option value="parents">{t("hub.aud_parents")}</option><option value="both">{t("hub.aud_both")}</option>
                  </select></label>
                <label className="block"><span className="font-bold text-[#0F1F3A] block mb-1">{t("hub.batches")}</span>
                  <select value={bc.batch} onChange={(e) => setBc({ ...bc, batch: e.target.value })} className="w-full p-2 border rounded-lg bg-[#F8FAFC]" data-testid="bc-batch">
                    <option value="">{t("hub.all_batches")}</option>{batches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                  </select></label>
                <label className="block"><span className="font-bold text-[#0F1F3A] block mb-1">{t("hub.ann_title")}</span>
                  <input value={bc.title} onChange={(e) => setBc({ ...bc, title: e.target.value })} className="w-full p-2 border rounded-lg bg-[#F8FAFC]" data-testid="bc-title" /></label>
                <label className="block"><span className="font-bold text-[#0F1F3A] block mb-1">{t("hub.ann_body")}</span>
                  <textarea value={bc.body} onChange={(e) => setBc({ ...bc, body: e.target.value })} rows={3} className="w-full p-2 border rounded-lg bg-[#F8FAFC]" data-testid="bc-body" /></label>
              </div>
              <div className="flex gap-2 pt-2">
                <button onClick={() => setModal(false)} className="flex-1 py-2 bg-[#F1F5F9] text-[#0F1F3A] font-bold text-xs rounded-xl">{t("hub.cancel")}</button>
                <button onClick={sendBroadcast} disabled={bc.title.trim().length < 3 || bc.body.trim().length < 3} className="flex-1 py-2 bg-[#2BB3A0] text-white font-bold text-xs rounded-xl disabled:opacity-50" data-testid="bc-send">{t("hub.send_broadcast")}</button>
              </div>
            </div>
          </div>
        )}

        {toast && (
          <div role="status" className={`fixed bottom-6 right-6 z-50 text-white text-xs font-semibold px-4 py-3 rounded-xl shadow-2xl flex items-center gap-2 max-w-sm ${toast.ok ? "bg-[#0F1F3A]" : "bg-[#B91C1C]"}`} data-testid="toast">
            {toast.ok ? <CheckCircle2 className="w-4 h-4 text-[#2BB3A0] flex-shrink-0" /> : <AlertCircle className="w-4 h-4 flex-shrink-0" />} {toast.text}
          </div>
        )}
      </AppShell>
    </RoleGuard>
  );
}
