"use client";

/** Screen 41 · College messages: chat with trainers (L20) and announcements to students and parents (L30). */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { ThreadMessageBody, type ThreadMsg } from "@/components/messages/ThreadMessageBody";
import { Megaphone, MessageSquare, Send } from "lucide-react";

interface Thread { id: string; name: string; last_message?: string | null; unread?: number }
interface Msg extends ThreadMsg { sender_name: string }
interface Announcement { id: string; title: string; audience: string; batches: string[] | "all"; status: string; recipients: number; delivered: number; at: string | null }

export default function CollegeMessagesPage() {
  const { t, language } = useLanguage();
  const [tab, setTab] = useState<"chats" | "announcements">("chats");
  const [threads, setThreads] = useState<Thread[]>([]);
  const [contacts, setContacts] = useState<{ user_id: string; name: string }[]>([]);
  const [current, setCurrent] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [items, setItems] = useState<Announcement[]>([]);
  const [batches, setBatches] = useState<{ id: string; name: string }[]>([]);
  const [form, setForm] = useState({ title: "", body: "", title_ta: "", body_ta: "", audience: "both", batch: "" });
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const loadThreads = useCallback(async () => {
    try {
      setThreads((await fetchApi<{ threads: Thread[] }>("/college/threads")).threads);
      setContacts((await fetchApi<{ trainers: { user_id: string; name: string }[] }>("/college/message-contacts")).trainers);
    } catch (e) { setError(e instanceof ApiError ? String(e.detail) : t("cmsg.load_failed")); }
  }, [t]);
  const loadMsgs = useCallback(async (id: string) => {
    setMsgs((await fetchApi<{ messages: Msg[] }>(`/threads/${id}/messages?lang=${language}`)).messages);
  }, [language]);
  const loadAnn = useCallback(async () => {
    const r = await fetchApi<{ announcements: Announcement[]; batches: { id: string; name: string }[] }>("/college/announcements");
    setItems(r.announcements);
    setBatches(r.batches);
  }, []);

  useEffect(() => { loadThreads(); }, [loadThreads]);
  useEffect(() => { if (current) loadMsgs(current).catch(() => undefined); }, [current, loadMsgs]);
  useEffect(() => {
    if (tab !== "announcements") return;
    loadAnn().catch(() => setError(t("cmsg.load_failed")));
    const id = setInterval(() => loadAnn().catch(() => undefined), 5000);       // delivery progress
    return () => clearInterval(id);
  }, [tab, loadAnn, t]);

  const start = async (userId: string) => {
    if (!userId) return;
    const r = await fetchApi<{ thread_id: string }>("/college/threads", { method: "POST", body: JSON.stringify({ trainer_user_id: userId }) });
    await loadThreads();
    setCurrent(r.thread_id);
  };
  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!current || !text.trim()) return;
    await fetchApi(`/threads/${current}/messages`, { method: "POST", body: JSON.stringify({ text }) });
    setText("");
    await loadMsgs(current);
  };
  const announce = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setMsg("");
    if (form.title.trim().length < 3 || form.body.trim().length < 3) return setError(t("cmsg.err_fields"));
    try {
      const r = await fetchApi<Announcement>("/college/announcements", { method: "POST", body: JSON.stringify({
        title: form.title, body: form.body, title_ta: form.title_ta || null, body_ta: form.body_ta || null, audience: form.audience,
        batch_ids: form.batch ? [form.batch] : null }) });
      setMsg(`${t("cmsg.sending_to")} ${r.recipients}`);
      setForm({ title: "", body: "", title_ta: "", body_ta: "", audience: "both", batch: "" });
      await loadAnn();
    } catch (err) { setError(err instanceof ApiError ? String(err.detail) : t("cmsg.save_failed")); }
  };

  const cls = "w-full px-2.5 py-1.5 bg-surface-2 border border-line rounded-tile text-xs";
  return (
    <RoleGuard allowedRoles={["college"]}>
      <AppShell pageTitle={t("cmsg.title")}>
        <div className="space-y-6 max-w-6xl">
          <div className="flex gap-2" role="tablist">
            {(["chats", "announcements"] as const).map((k) => (
              <button key={k} type="button" role="tab" aria-selected={tab === k} onClick={() => setTab(k)} data-testid={`cmsg-tab-${k}`}
                className={`px-3 py-1.5 rounded-tile text-xs font-semibold inline-flex items-center gap-1 ${tab === k ? "bg-brand text-white" : "border border-line-strong"}`}>
                {k === "chats" ? <MessageSquare className="w-3.5 h-3.5" /> : <Megaphone className="w-3.5 h-3.5" />}{t(`cmsg.tab_${k}`)}
              </button>
            ))}
          </div>
          {msg && <p className="text-xs text-success font-semibold" role="status" data-testid="cmsg-msg">{msg}</p>}
          {error && <p className="text-xs text-red-600" role="alert" data-testid="cmsg-error">{error}</p>}

          {tab === "chats" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
              <div className="space-y-2">
                <select onChange={(e) => start(e.target.value)} value="" aria-label={t("cmsg.new_chat")} className={cls} data-testid="cmsg-new">
                  <option value="">{t("cmsg.new_chat")}</option>
                  {contacts.map((c) => <option key={c.user_id} value={c.user_id}>{c.name}</option>)}
                </select>
                <ul className="bg-white rounded-card border border-line divide-y divide-line-soft" data-testid="cmsg-threads">
                  {threads.length === 0 && <li className="p-4 text-xs text-muted text-center">{t("cmsg.no_chats")}</li>}
                  {threads.map((th) => (
                    <li key={th.id}>
                      <button type="button" onClick={() => setCurrent(th.id)} aria-pressed={current === th.id} data-testid="cmsg-thread"
                        className={`w-full text-left px-3 py-2 text-xs ${current === th.id ? "bg-brand-soft" : "hover:bg-surface-2"}`}>
                        <div className="font-semibold">{th.name}</div>
                        {th.last_message && <div className="text-muted truncate">{th.last_message}</div>}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
              {current && (
                <div className="lg:col-span-2 bg-white rounded-card border border-line flex flex-col h-[60vh]">
                  <div className="flex-1 overflow-y-auto p-3 space-y-2" data-testid="cmsg-chat">
                    {msgs.map((m) => (
                      <div key={m.id} className={`flex ${m.is_mine ? "justify-end" : "justify-start"}`}>
                        <div className={`max-w-[80%] rounded-card px-3 py-2 text-sm ${m.is_mine ? "bg-brand text-white" : "bg-line-soft"}`} data-testid="dm-bubble">
                          <ThreadMessageBody m={m} meta={m.time} onChanged={() => current ? loadMsgs(current) : undefined} />
                        </div>
                      </div>
                    ))}
                  </div>
                  <form onSubmit={send} className="border-t border-line p-2 flex gap-2">
                    <input value={text} onChange={(e) => setText(e.target.value)} placeholder={t("cmsg.type")} aria-label={t("cmsg.type")} className={cls} data-testid="cmsg-input" />
                    <button type="submit" className="px-3 bg-brand text-white rounded-tile" aria-label={t("cmsg.send")} data-testid="cmsg-send"><Send className="w-4 h-4" /></button>
                  </form>
                </div>
              )}
            </div>
          )}

          {tab === "announcements" && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <form onSubmit={announce} noValidate className="bg-white rounded-card border border-line p-3 space-y-2" data-testid="ann-form">
                <p className="text-caption text-muted">{t("cmsg.ann_help")}</p>
                <input className={cls} placeholder={t("cmsg.title_en")} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} data-testid="ann-title" />
                <input className={cls} placeholder={t("cmsg.title_ta")} value={form.title_ta} onChange={(e) => setForm({ ...form, title_ta: e.target.value })} />
                <textarea className={cls} rows={3} placeholder={t("cmsg.body_en")} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} data-testid="ann-body" />
                <textarea className={cls} rows={3} placeholder={t("cmsg.body_ta")} value={form.body_ta} onChange={(e) => setForm({ ...form, body_ta: e.target.value })} />
                <div className="grid grid-cols-2 gap-2">
                  <select className={cls} value={form.audience} onChange={(e) => setForm({ ...form, audience: e.target.value })} aria-label={t("cmsg.audience")} data-testid="ann-audience">
                    {["both", "students", "parents"].map((a) => <option key={a} value={a}>{t(`cmsg.aud_${a}`)}</option>)}
                  </select>
                  <select className={cls} value={form.batch} onChange={(e) => setForm({ ...form, batch: e.target.value })} aria-label={t("cmsg.batch")} data-testid="ann-batch">
                    <option value="">{t("cmsg.whole_college")}</option>
                    {batches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                  </select>
                </div>
                <button type="submit" className="w-full px-3 py-2 bg-brand text-white text-xs font-semibold rounded-tile" data-testid="ann-send">{t("cmsg.post")}</button>
              </form>
              <ul className="space-y-2" data-testid="ann-list">
                {items.map((a) => (
                  <li key={a.id} className="bg-white rounded-card border border-line p-3 text-xs" data-testid="ann-row">
                    <div className="font-semibold text-ink">{a.title}</div>
                    <div className="text-muted">{t(`cmsg.aud_${a.audience}`)} · {a.batches === "all" ? t("cmsg.whole_college") : a.batches.join(", ")}</div>
                    <div className="mt-1 flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-line-soft rounded-full overflow-hidden"><div className="h-full bg-teal" style={{ width: `${a.recipients ? Math.round(100 * a.delivered / a.recipients) : 100}%` }} /></div>
                      <span data-testid="ann-delivery">{a.delivered}/{a.recipients}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
