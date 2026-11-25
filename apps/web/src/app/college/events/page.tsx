"use client";

/** Screen 42 · Events (college): create, publish and cancel; RSVP counts come back from 17 (L05); drives post to 34 (L29). */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { CalendarPlus, Send, XCircle } from "lucide-react";

interface Counts { yes: number; maybe: number; no: number; guests: number }
interface Ev {
  id: string; title_en: string; title_ta: string | null; kind: string; starts_at: string; when: string; location: string | null;
  audience: string; batch_id: string | null; rsvp_enabled: boolean; status: string; rsvp: Counts;
}

const EMPTY = { title_en: "", title_ta: "", kind: "event", starts_at: "", location: "", description_en: "", description_ta: "", audience: "all", batch_id: "", rsvp_enabled: true };

export default function CollegeEventsPage() {
  const { t, language } = useLanguage();
  const [events, setEvents] = useState<Ev[]>([]);
  const [kinds, setKinds] = useState<string[]>([]);
  const [batches, setBatches] = useState<{ id: string; name: string }[]>([]);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await fetchApi<{ events: Ev[]; kinds: string[]; batches: { id: string; name: string }[] }>("/college/events");
      setEvents(r.events);
      setKinds(r.kinds);
      setBatches(r.batches);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("events.load_failed"));
    }
  }, [t]);

  useEffect(() => { load(); }, [load]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try { await fn(); } catch (e) { setError(e instanceof ApiError ? e.detail : t("events.save_failed")); } finally { setBusy(false); }
  };

  const save = (e: React.FormEvent) => {
    e.preventDefault();
    if (form.title_en.trim().length < 3) return setError(t("events.err_title"));
    if (!form.starts_at) return setError(t("events.err_start"));
    run(async () => {
      await fetchApi("/college/events", {
        method: "POST",
        body: JSON.stringify({ ...form, starts_at: `${form.starts_at}:00`, batch_id: form.batch_id || null,
          title_ta: form.title_ta || null, location: form.location || null, description_en: form.description_en || null, description_ta: form.description_ta || null }),
      });
      setForm(EMPTY);
      await load();
    });
  };

  const act = (ev: Ev, action: "publish" | "cancel") => run(async () => {
    const r = await fetchApi<{ notified?: { students: number; parents: number }; parents_told?: number; placement_posts?: number }>(
      `/college/events/${ev.id}/${action}`, { method: "POST" });
    setToast(action === "publish"
      ? `${t("events.published_to")} ${r.notified?.students ?? 0} ${t("events.students")} · ${r.notified?.parents ?? 0} ${t("events.parents")}${r.placement_posts ? ` · ${t("events.posted_placement")}` : ""}`
      : `${t("events.cancelled_told")} ${r.parents_told ?? 0}`);
    await load();
  });

  const cls = "w-full px-2.5 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg text-xs";
  const statusChip: Record<string, string> = { draft: "bg-[#F1F5F9] text-[#475569]", published: "bg-[#DCFCE7] text-[#166534]", cancelled: "bg-[#FEE2E2] text-[#991B1B]" };

  return (
    <RoleGuard allowedRoles={["college"]}>
      <AppShell pageTitle={t("events.college_title")}>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 max-w-6xl">
          <form onSubmit={save} noValidate className="bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-2 h-fit" data-testid="event-form">
            <h2 className="text-sm font-black flex items-center gap-2"><CalendarPlus className="w-4 h-4 text-[#2B5CD0]" />{t("events.new")}</h2>
            <input className={cls} placeholder={t("events.title_en")} value={form.title_en} data-testid="event-title-en" onChange={(e) => setForm({ ...form, title_en: e.target.value })} />
            <input className={cls} placeholder={t("events.title_ta")} value={form.title_ta} data-testid="event-title-ta" onChange={(e) => setForm({ ...form, title_ta: e.target.value })} />
            <div className="grid grid-cols-2 gap-2">
              <select className={cls} value={form.kind} aria-label={t("events.kind")} data-testid="event-kind" onChange={(e) => setForm({ ...form, kind: e.target.value })}>
                {kinds.map((k) => <option key={k} value={k}>{t(`events.kind_${k}`)}</option>)}
              </select>
              <select className={cls} value={form.audience} aria-label={t("events.audience")} data-testid="event-audience" onChange={(e) => setForm({ ...form, audience: e.target.value })}>
                {["all", "parents", "students"].map((a) => <option key={a} value={a}>{t(`events.aud_${a}`)}</option>)}
              </select>
            </div>
            <label className="block text-[11px] text-[#64748B]">{t("events.starts")}
              <input type="datetime-local" className={cls} value={form.starts_at} data-testid="event-start" onChange={(e) => setForm({ ...form, starts_at: e.target.value })} />
            </label>
            <input className={cls} placeholder={t("events.location")} value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
            <select className={cls} value={form.batch_id} aria-label={t("events.batch")} data-testid="event-batch" onChange={(e) => setForm({ ...form, batch_id: e.target.value })}>
              <option value="">{t("events.all_batches")}</option>
              {batches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
            <textarea className={cls} rows={2} placeholder={t("events.desc_en")} value={form.description_en} onChange={(e) => setForm({ ...form, description_en: e.target.value })} />
            <textarea className={cls} rows={2} placeholder={t("events.desc_ta")} value={form.description_ta} onChange={(e) => setForm({ ...form, description_ta: e.target.value })} />
            <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={form.rsvp_enabled} onChange={(e) => setForm({ ...form, rsvp_enabled: e.target.checked })} />{t("events.takes_rsvp")}</label>
            {error && <p className="text-xs text-red-600" role="alert" data-testid="event-error">{error}</p>}
            <button type="submit" disabled={busy} data-testid="event-save" className="w-full px-3 py-2 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg disabled:opacity-50">{t("events.save_draft")}</button>
          </form>

          <section className="lg:col-span-2 space-y-2">
            {toast && <p className="text-xs text-[#166534] font-bold" role="status" data-testid="event-toast">{toast}</p>}
            {events.length === 0 && <p className="text-xs text-[#64748B] bg-white rounded-xl border border-dashed border-[#CBD5E1] p-6 text-center">{t("events.none")}</p>}
            <ul className="space-y-2" data-testid="event-list">
              {events.map((ev) => (
                <li key={ev.id} className="bg-white rounded-xl border border-[#E2E8F0] p-3" data-testid="event-row">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="text-sm font-black text-[#0F1F3A]">{language === "ta" && ev.title_ta ? ev.title_ta : ev.title_en}</div>
                      <div className="text-[11px] text-[#64748B]">{ev.when} · {t(`events.kind_${ev.kind}`)} · {t(`events.aud_${ev.audience}`)}{ev.location ? ` · ${ev.location}` : ""}</div>
                    </div>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${statusChip[ev.status]}`} data-testid="event-status">{t(`events.status_${ev.status}`)}</span>
                  </div>
                  {ev.rsvp_enabled && ev.status !== "draft" && (
                    <div className="mt-2 flex gap-3 text-[11px] font-semibold" data-testid="rsvp-counts">
                      <span className="text-[#166534]">{t("events.yes")} {ev.rsvp.yes}</span>
                      <span className="text-[#B45309]">{t("events.maybe")} {ev.rsvp.maybe}</span>
                      <span className="text-[#991B1B]">{t("events.no")} {ev.rsvp.no}</span>
                      <span className="text-[#334155]">{t("events.guests")} {ev.rsvp.guests}</span>
                    </div>
                  )}
                  <div className="mt-2 flex gap-2">
                    {ev.status === "draft" && (
                      <button type="button" disabled={busy} onClick={() => act(ev, "publish")} data-testid="event-publish" className="px-3 py-1.5 bg-[#166534] text-white text-xs font-bold rounded-lg inline-flex items-center gap-1 disabled:opacity-50">
                        <Send className="w-3.5 h-3.5" />{t("events.publish")}
                      </button>
                    )}
                    {ev.status !== "cancelled" && (
                      <button type="button" disabled={busy} onClick={() => act(ev, "cancel")} data-testid="event-cancel" className="px-3 py-1.5 border border-[#FCA5A5] text-[#991B1B] text-xs font-bold rounded-lg inline-flex items-center gap-1 disabled:opacity-50">
                        <XCircle className="w-3.5 h-3.5" />{t("events.cancel")}
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
