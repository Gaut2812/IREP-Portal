"use client";

/** Screen 49 · Support desk. Requesters (any role) report problems and follow their tickets (L39);
 *  IREP staff see every ticket and reply, which reaches the requester's notification centre (L28). */
import React, { useCallback, useEffect, useState } from "react";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { LifeBuoy, Send } from "lucide-react";

interface Ticket {
  id: string; subject: string; category: string; status: string; page_path: string | null; requester_name: string;
  requester_role: string; college: string; messages: number; last_activity_at: string | null;
}
interface Detail extends Ticket { thread: { id: string; author: string; is_staff: boolean; body: string; at: string | null }[] }

export function SupportDesk({ staffView }: { staffView: boolean }) {
  const { t } = useLanguage();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [filter, setFilter] = useState("");
  const [open, setOpen] = useState<Detail | null>(null);
  const [form, setForm] = useState({ subject: "", body: "", category: "bug", page_path: "" });
  const [reply, setReply] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await fetchApi<{ tickets: Ticket[] }>(`/support/tickets${filter ? `?status_filter=${filter}` : ""}`);
      setTickets(r.tickets);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("support.load_failed"));
    }
  }, [filter, t]);

  const show = useCallback(async (id: string) => {
    try { setOpen(await fetchApi<Detail>(`/support/tickets/${id}`)); } catch { setOpen(null); }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    if (q.get("from")) setForm((f) => ({ ...f, page_path: q.get("from") || "" }));
    if (q.get("ticket")) show(q.get("ticket") as string);
  }, [show]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try { await fn(); } catch (e) { setError(e instanceof ApiError ? e.detail : t("support.save_failed")); } finally { setBusy(false); }
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (form.subject.trim().length < 4 || form.body.trim().length < 4) return setError(t("support.err_fields"));
    run(async () => {
      const tk = await fetchApi<Ticket>("/support/tickets", { method: "POST", body: JSON.stringify({ ...form, page_path: form.page_path || null }) });
      setForm({ subject: "", body: "", category: "bug", page_path: "" });
      await load();
      await show(tk.id);
    });
  };

  const send = () => {
    if (!open || !reply.trim()) return;
    run(async () => {
      await fetchApi(`/support/tickets/${open.id}/messages`, { method: "POST", body: JSON.stringify({ body: reply }) });
      setReply("");
      await Promise.all([show(open.id), load()]);
    });
  };

  const close = () => open && run(async () => {
    await fetchApi(`/support/tickets/${open.id}/close`, { method: "POST" });
    await Promise.all([show(open.id), load()]);
  });

  const cls = "w-full px-2.5 py-1.5 bg-surface-2 border border-line rounded-tile text-xs";
  const chip: Record<string, string> = { open: "bg-info-soft text-info", answered: "bg-success-soft text-success", closed: "bg-line-soft text-ink-soft" };

  return (
    <div className="p-4 md:p-6 grid grid-cols-1 lg:grid-cols-5 gap-4 max-w-6xl">
      <div className="lg:col-span-2 space-y-3">
        {!staffView && (
          <form onSubmit={submit} noValidate className="bg-white rounded-card border border-line p-4 space-y-2" data-testid="ticket-form">
            <h2 className="text-sm font-semibold flex items-center gap-2"><LifeBuoy className="w-4 h-4 text-brand" />{t("support.report")}</h2>
            {form.page_path && <p className="text-caption text-muted" data-testid="ticket-from">{t("support.from_page")}: <code>{form.page_path}</code></p>}
            <select className={cls} value={form.category} aria-label={t("support.category")} onChange={(e) => setForm({ ...form, category: e.target.value })} data-testid="ticket-category">
              {["bug", "question", "access", "data"].map((c) => <option key={c} value={c}>{t(`support.cat_${c}`)}</option>)}
            </select>
            <input className={cls} placeholder={t("support.subject")} value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} data-testid="ticket-subject" />
            <textarea className={cls} rows={4} placeholder={t("support.body")} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} data-testid="ticket-body" />
            <button type="submit" disabled={busy} className="w-full px-3 py-2 bg-brand text-white text-xs font-semibold rounded-tile disabled:opacity-50" data-testid="ticket-submit">{t("support.send")}</button>
          </form>
        )}
        <div className="flex gap-2" role="tablist">
          {["", "open", "answered", "closed"].map((f) => (
            <button key={f || "all"} type="button" role="tab" aria-selected={filter === f} onClick={() => setFilter(f)}
              className={`px-2.5 py-1 rounded-tile text-caption font-semibold ${filter === f ? "bg-ink text-white" : "border border-line-strong"}`}>{t(`support.filter_${f || "all"}`)}</button>
          ))}
        </div>
        {error && <p className="text-xs text-red-600" role="alert" data-testid="support-error">{error}</p>}
        <ul className="bg-white rounded-card border border-line divide-y divide-line-soft" data-testid="ticket-list">
          {tickets.length === 0 && <li className="p-4 text-xs text-muted text-center">{t("support.none")}</li>}
          {tickets.map((tk) => (
            <li key={tk.id}>
              <button type="button" onClick={() => show(tk.id)} aria-pressed={open?.id === tk.id} data-testid="ticket-row"
                className={`w-full text-left px-3 py-2 ${open?.id === tk.id ? "bg-brand-soft" : "hover:bg-surface-2"}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-ink truncate">{tk.subject}</span>
                  <span className={`text-caption font-semibold px-2 py-0.5 rounded-full ${chip[tk.status]}`}>{t(`support.status_${tk.status}`)}</span>
                </div>
                <div className="text-caption text-muted truncate">{staffView ? `${tk.requester_name} · ${tk.requester_role} · ${tk.college}` : t(`support.cat_${tk.category}`)}{tk.page_path ? ` · ${tk.page_path}` : ""}</div>
              </button>
            </li>
          ))}
        </ul>
      </div>

      {open && (
        <section className="lg:col-span-3 bg-white rounded-card border border-line p-4 space-y-3 h-fit" data-testid="ticket-detail">
          <div className="flex items-start justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold text-ink" data-testid="ticket-subject-heading">{open.subject}</h2>
              <p className="text-caption text-muted">{open.requester_name} · {t(`support.cat_${open.category}`)}{open.page_path ? ` · ${open.page_path}` : ""}</p>
            </div>
            <span className={`text-caption font-semibold px-2 py-0.5 rounded-full ${chip[open.status]}`} data-testid="ticket-status">{t(`support.status_${open.status}`)}</span>
          </div>
          <ol className="space-y-2" data-testid="ticket-thread">
            {open.thread.map((m) => (
              <li key={m.id} className={`rounded-tile p-2.5 text-xs ${m.is_staff ? "bg-success-faint border border-success-line" : "bg-surface-2 border border-line"}`} data-testid={m.is_staff ? "staff-message" : "user-message"}>
                <div className="font-semibold text-caption text-ink-soft">{m.author}</div>
                <div className="whitespace-pre-wrap text-ink">{m.body}</div>
              </li>
            ))}
          </ol>
          {open.status !== "closed" ? (
            <div className="space-y-2">
              <textarea rows={3} className={cls} value={reply} onChange={(e) => setReply(e.target.value)} placeholder={t("support.reply_ph")} data-testid="ticket-reply" />
              <div className="flex gap-2">
                <button type="button" disabled={busy || !reply.trim()} onClick={send} className="px-3 py-1.5 bg-brand text-white text-xs font-semibold rounded-tile inline-flex items-center gap-1 disabled:opacity-50" data-testid="ticket-send">
                  <Send className="w-3.5 h-3.5" />{t("support.reply")}
                </button>
                <button type="button" disabled={busy} onClick={close} className="px-3 py-1.5 border border-line-strong text-xs font-semibold rounded-tile disabled:opacity-50" data-testid="ticket-close">{t("support.close")}</button>
              </div>
            </div>
          ) : <p className="text-caption text-muted">{t("support.closed_note")}</p>}
        </section>
      )}
    </div>
  );
}
