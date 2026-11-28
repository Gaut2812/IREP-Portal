"use client";

/** Screen 42 · Events (college): create, edit or delete drafts, publish and cancel; RSVP counts come back from 17 (L05); drives post to 34 (L29). */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { CalendarPlus, Pencil, Send, XCircle } from "lucide-react";
import { ConfirmDelete, DeleteButton } from "@/components/ui";

interface Counts { yes: number; maybe: number; no: number; guests: number }
interface Ev {
  id: string; title_en: string; title_ta: string | null; kind: string; starts_at: string; when: string; location: string | null;
  audience: string; batch_id: string | null; rsvp_enabled: boolean; rsvp_deadline: string | null; status: string; rsvp: Counts;
  description_en: string | null; description_ta: string | null;
}

const EMPTY = { title_en: "", title_ta: "", kind: "event", starts_at: "", location: "", description_en: "", description_ta: "", audience: "all", batch_id: "", rsvp_enabled: true, rsvp_deadline: "" };

/** Why parents can't come: reasons only, no names (aggregates, rule 8). Loaded when opened. */
function DeclineReasons({ eventId }: { eventId: string }) {
  const { t } = useLanguage();
  const [reasons, setReasons] = useState<string[] | null>(null);
  const open = async () => {
    if (reasons) return setReasons(null);
    const r = await fetchApi<{ decline_reasons: string[] }>(`/college/events/${eventId}`).catch(() => ({ decline_reasons: [] as string[] }));
    setReasons(r.decline_reasons);
  };
  return (
    <div className="mt-1">
      <button type="button" onClick={open} className="text-caption text-brand font-semibold" data-testid="decline-reasons-toggle">{t("events.decline_reasons")}</button>
      {reasons && (
        <ul className="mt-1 space-y-0.5" data-testid="decline-reasons">
          {reasons.length === 0 && <li className="text-caption text-subtle">{t("events.no_reasons")}</li>}
          {reasons.map((r, i) => <li key={i} className="text-caption text-ink-soft">“{r}”</li>)}
        </ul>
      )}
    </div>
  );
}

export default function CollegeEventsPage() {
  const { t, language } = useLanguage();
  const [events, setEvents] = useState<Ev[]>([]);
  const [kinds, setKinds] = useState<string[]>([]);
  const [batches, setBatches] = useState<{ id: string; name: string }[]>([]);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState("");
  const [editing, setEditing] = useState<string | null>(null);      // id of the draft in the form, or null for a new one
  const [delEv, setDelEv] = useState<Ev | null>(null);

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
      await fetchApi(editing ? `/college/events/${editing}` : "/college/events", {
        method: editing ? "PUT" : "POST",
        body: JSON.stringify({ ...form, starts_at: `${form.starts_at}:00`, batch_id: form.batch_id || null,
          rsvp_deadline: form.rsvp_enabled && form.rsvp_deadline ? `${form.rsvp_deadline}:00` : null,
          title_ta: form.title_ta || null, location: form.location || null, description_en: form.description_en || null, description_ta: form.description_ta || null }),
      });
      setForm(EMPTY);
      if (editing) setToast(t("events.draft_updated"));
      setEditing(null);
      await load();
    });
  };

  // Only drafts are editable (nobody has been told yet); the form switches to "Edit draft"
  const startEdit = (ev: Ev) => {
    setEditing(ev.id);
    setError("");
    setForm({ title_en: ev.title_en, title_ta: ev.title_ta || "", kind: ev.kind, starts_at: ev.starts_at.slice(0, 16), location: ev.location || "",
      description_en: ev.description_en || "", description_ta: ev.description_ta || "", audience: ev.audience, batch_id: ev.batch_id || "",
      rsvp_enabled: ev.rsvp_enabled, rsvp_deadline: ev.rsvp_deadline ? ev.rsvp_deadline.slice(0, 16) : "" });
  };
  const stopEdit = () => { setEditing(null); setForm(EMPTY); setError(""); };

  const act = (ev: Ev, action: "publish" | "cancel") => run(async () => {
    const r = await fetchApi<{ notified?: { students: number; parents: number }; parents_told?: number; placement_posts?: number }>(
      `/college/events/${ev.id}/${action}`, { method: "POST" });
    setToast(action === "publish"
      ? `${t("events.published_to")} ${r.notified?.students ?? 0} ${t("events.students")} · ${r.notified?.parents ?? 0} ${t("events.parents")}${r.placement_posts ? ` · ${t("events.posted_placement")}` : ""}`
      : `${t("events.cancelled_told")} ${r.parents_told ?? 0}`);
    await load();
  });

  const cls = "w-full px-2.5 py-1.5 bg-surface-2 border border-line rounded-tile text-xs";
  const statusChip: Record<string, string> = { draft: "bg-line-soft text-ink-soft", published: "bg-success-soft text-success", cancelled: "bg-danger-soft text-danger" };

  return (
    <RoleGuard allowedRoles={["college"]}>
      <AppShell pageTitle={t("events.college_title")}>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 max-w-6xl">
          <form onSubmit={save} noValidate className="bg-white rounded-card border border-line p-4 space-y-2 h-fit" data-testid="event-form">
            <h2 className="text-sm font-semibold flex items-center gap-2" data-testid="event-form-title">
              {editing ? <Pencil className="w-4 h-4 text-brand" /> : <CalendarPlus className="w-4 h-4 text-brand" />}{editing ? t("events.edit_draft") : t("events.new")}
            </h2>
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
            <label className="block text-caption text-muted">{t("events.starts")}
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
            {form.rsvp_enabled && (
              <label className="block text-caption text-muted">{t("events.rsvp_deadline")}
                <input type="datetime-local" className={cls} value={form.rsvp_deadline} max={form.starts_at || undefined} data-testid="event-rsvp-deadline"
                  onChange={(e) => setForm({ ...form, rsvp_deadline: e.target.value })} />
                <span className="block mt-0.5">{t("events.rsvp_deadline_help")}</span>
              </label>
            )}
            {error && <p className="text-xs text-red-600" role="alert" data-testid="event-error">{error}</p>}
            <button type="submit" disabled={busy} data-testid="event-save" className="w-full px-3 py-2 bg-brand text-white text-xs font-semibold rounded-tile disabled:opacity-50">{editing ? t("events.save_changes") : t("events.save_draft")}</button>
            {editing && <button type="button" onClick={stopEdit} data-testid="event-edit-cancel" className="w-full px-3 py-2 border border-line-strong text-xs font-semibold rounded-tile">{t("events.stop_editing")}</button>}
          </form>

          <section className="lg:col-span-2 space-y-2">
            {toast && <p className="text-xs text-success font-semibold" role="status" data-testid="event-toast">{toast}</p>}
            {events.length === 0 && <p className="text-xs text-muted bg-white rounded-card border border-dashed border-line-strong p-6 text-center">{t("events.none")}</p>}
            <ul className="space-y-2" data-testid="event-list">
              {events.map((ev) => (
                <li key={ev.id} className="bg-white rounded-card border border-line p-3" data-testid="event-row">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="text-sm font-semibold text-ink">{language === "ta" && ev.title_ta ? ev.title_ta : ev.title_en}</div>
                      <div className="text-caption text-muted">{ev.when} · {t(`events.kind_${ev.kind}`)} · {t(`events.aud_${ev.audience}`)}{ev.location ? ` · ${ev.location}` : ""}</div>
                    </div>
                    <span className={`text-caption font-semibold px-2 py-0.5 rounded-full ${statusChip[ev.status]}`} data-testid="event-status">{t(`events.status_${ev.status}`)}</span>
                  </div>
                  {ev.rsvp_enabled && ev.status !== "draft" && (
                    <div className="mt-2 flex gap-3 text-caption font-semibold" data-testid="rsvp-counts">
                      <span className="text-success">{t("events.yes")} {ev.rsvp.yes}</span>
                      <span className="text-warning">{t("events.maybe")} {ev.rsvp.maybe}</span>
                      <span className="text-danger">{t("events.no")} {ev.rsvp.no}</span>
                      <span className="text-ink-soft">{t("events.guests")} {ev.rsvp.guests}</span>
                      {ev.rsvp_deadline && <span className="text-muted" data-testid="rsvp-deadline">{t("events.replies_close")} {ev.rsvp_deadline.slice(0, 16).replace("T", " ")}</span>}
                    </div>
                  )}
                  {ev.rsvp_enabled && ev.status !== "draft" && ev.rsvp.no > 0 && <DeclineReasons eventId={ev.id} />}
                  <div className="mt-2 flex gap-2">
                    {ev.status === "draft" && (
                      <button type="button" disabled={busy} onClick={() => act(ev, "publish")} data-testid="event-publish" className="px-3 py-1.5 bg-success text-white text-xs font-semibold rounded-tile inline-flex items-center gap-1 disabled:opacity-50">
                        <Send className="w-3.5 h-3.5" />{t("events.publish")}
                      </button>
                    )}
                    {ev.status === "draft" && (
                      <>
                        <button type="button" disabled={busy} onClick={() => startEdit(ev)} data-testid="event-edit" className="px-3 py-1.5 border border-line-strong text-xs font-semibold rounded-tile inline-flex items-center gap-1 disabled:opacity-50">
                          <Pencil className="w-3.5 h-3.5" />{t("events.edit")}
                        </button>
                        <DeleteButton onClick={() => setDelEv(ev)} testId="event-delete" />
                      </>
                    )}
                    {ev.status === "published" && (
                      <button type="button" disabled={busy} onClick={() => act(ev, "cancel")} data-testid="event-cancel" className="px-3 py-1.5 border border-danger-line text-danger text-xs font-semibold rounded-tile inline-flex items-center gap-1 disabled:opacity-50">
                        <XCircle className="w-3.5 h-3.5" />{t("events.cancel")}
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </div>
        {delEv && (
          <ConfirmDelete itemName={delEv.title_en} note={t("events.delete_note")}
            onConfirm={async () => {
              await fetchApi(`/college/events/${delEv.id}`, { method: "DELETE" });
              if (editing === delEv.id) stopEdit();
              setToast(t("events.deleted"));
              await load();
            }}
            onClose={() => setDelEv(null)} />
        )}
      </AppShell>
    </RoleGuard>
  );
}
