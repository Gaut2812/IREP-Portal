"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { fetchApi } from "@/lib/api";
import { Send, Clock, AlertCircle, RefreshCw } from "lucide-react";

interface ThreadRow { id: string; name: string; role_chip: string; avatar: string; unread: number }
interface Detail {
  thread: { id: string; trainer_name: string; child: { name: string; batch: string } | null };
  messages: { id: string; is_mine: boolean; sender_name: string; text: string; original_text: string; translated: boolean; time: string; date: string }[];
}

export default function ParentMessagesPage() {
  const { t, language } = useLanguage();
  const [threads, setThreads] = useState<ThreadRow[]>([]);
  const [sla, setSla] = useState(24);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [showOriginal, setShowOriginal] = useState<Record<string, boolean>>({});
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetchApi<{ threads: ThreadRow[]; reply_sla_hours: number }>("/parent/threads");
      setThreads(res.threads); setSla(res.reply_sla_hours);
      setSelected((cur) => cur || res.threads[0]?.id || null);
      setError(null);
    } catch (err: any) {
      setError(err?.detail || err?.message || "error");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadThread = useCallback(async (id: string) => {
    try { setDetail(await fetchApi<Detail>(`/threads/${id}/messages?lang=${language}`)); } catch (err: any) { setSendError(err?.detail || t("parent_messages.error_title")); }
  }, [language, t]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (selected) loadThread(selected); }, [selected, loadThread]);
  useEffect(() => {
    if (!selected) return;
    const id = setInterval(() => loadThread(selected), 15000);
    return () => clearInterval(id);
  }, [selected, loadThread]);
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [detail?.messages.length]);

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected || !text.trim()) return;
    setSending(true); setSendError(null);
    try {
      await fetchApi(`/threads/${selected}/messages`, { method: "POST", body: JSON.stringify({ text: text.trim() }) });
      setText("");
      await loadThread(selected);
    } catch (err: any) {
      setSendError(err?.detail || t("parent_messages.send_failed"));
    } finally {
      setSending(false);
    }
  };

  return (
    <RoleGuard allowedRoles={["parent"]}>
      <AppShell pageTitle={t("parent_messages.title")}>
        <div className="max-w-xl mx-auto flex flex-col gap-3 h-[calc(100vh-120px)]" data-testid="parent-messages">
          <div className="bg-brand-soft border border-brand-line rounded-card p-3 text-xs text-info flex items-start gap-2 flex-shrink-0" data-testid="sla-banner">
            <Clock className="w-4 h-4 flex-shrink-0 mt-0.5" /><span>{t("parent_messages.sla").replace("{h}", String(sla))}</span>
          </div>

          {loading && <div className="flex-1 bg-white rounded-card animate-pulse" aria-busy="true" aria-label={t("parent_messages.loading")} />}
          {!loading && error && (
            <div className="bg-white rounded-card border border-danger-line p-6 text-center space-y-3">
              <AlertCircle className="w-7 h-7 text-danger mx-auto" />
              <h2 className="text-sm font-semibold text-ink">{t("parent_messages.error_title")}</h2>
              <button onClick={load} className="inline-flex items-center gap-1.5 px-4 py-2 bg-brand text-white text-xs font-semibold rounded-tile"><RefreshCw className="w-3.5 h-3.5" /> {t("parent_messages.retry")}</button>
            </div>
          )}
          {!loading && !error && threads.length === 0 && <p className="text-sm text-muted text-center py-10">{t("parent_messages.no_threads")}</p>}

          {!loading && !error && threads.length > 1 && (
            <div className="flex gap-2 overflow-x-auto flex-shrink-0">
              {threads.map((th) => (
                <button key={th.id} onClick={() => setSelected(th.id)} aria-current={selected === th.id}
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap ${selected === th.id ? "bg-brand text-white" : "bg-white border border-line text-ink"}`}>{th.name} · {th.role_chip}</button>
              ))}
            </div>
          )}

          {!loading && !error && detail && (
            <div className="flex-1 bg-white rounded-card border border-line shadow-card flex flex-col overflow-hidden min-h-0">
              <div className="p-3.5 border-b border-line flex-shrink-0">
                <h3 className="text-sm font-semibold text-ink">{detail.thread.trainer_name}</h3>
                {detail.thread.child && <p className="text-caption text-muted">{t("parent_messages.about").replace("{child}", detail.thread.child.name)} · {detail.thread.child.batch}</p>}
              </div>
              <div className="flex-1 overflow-y-auto p-4 space-y-3" data-testid="messages">
                {detail.messages.map((m) => (
                  <div key={m.id} className={`flex flex-col ${m.is_mine ? "items-end" : "items-start"}`}>
                    <div className={`max-w-[85%] p-3 rounded-card text-sm space-y-1 ${m.is_mine ? "bg-brand text-white" : "bg-line-soft text-ink"}`}>
                      <p className="leading-relaxed">{showOriginal[m.id] ? m.original_text : m.text}</p>
                      <div className={`flex items-center justify-between gap-3 text-caption ${m.is_mine ? "text-white/70" : "text-subtle"}`}>
                        {m.translated ? <button onClick={() => setShowOriginal({ ...showOriginal, [m.id]: !showOriginal[m.id] })} className="underline">{showOriginal[m.id] ? t("parent_messages.translated") : t("parent_messages.show_original")}</button> : <span />}
                        <span>{m.date}</span>
                      </div>
                    </div>
                  </div>
                ))}
                <div ref={endRef} />
              </div>
              {sendError && <div className="px-3 py-1.5 text-caption text-danger bg-danger-faint" role="alert">{sendError}</div>}
              <form onSubmit={send} className="p-3 border-t border-line flex items-center gap-2 flex-shrink-0">
                <input value={text} onChange={(e) => setText(e.target.value)} placeholder={t("parent_messages.type")} aria-label={t("parent_messages.type")} data-testid="parent-input"
                  className="flex-1 min-w-0 px-3.5 py-2.5 bg-surface-2 border border-line rounded-card text-sm focus:outline-none focus:border-brand focus:bg-white" />
                <button type="submit" disabled={sending} className="px-4 py-2.5 bg-brand text-white font-semibold text-sm rounded-card flex items-center gap-1.5 disabled:opacity-50" data-testid="parent-send"><Send className="w-4 h-4" /><span>{t("parent_messages.send")}</span></button>
              </form>
            </div>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
