"use client";

/** Screen 17 · Events (parent): invitations from the college; RSVP goes back to 42 (L05).
 *  After replying the card shows the reply, and it can be changed until the college's reply deadline (or the start). */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { CalendarDays, CheckCircle2, MapPin } from "lucide-react";

type Reply = "yes" | "maybe" | "no";
interface Ev {
  id: string; title: string; kind: string; kind_label: string; when: string; location: string | null; description: string | null;
  can_rsvp: boolean; rsvp_enabled: boolean; rsvp_closes_at: string | null; rsvp_status: Reply | null; guests: number; reason: string | null;
}

export default function ParentEventsPage() {
  const { t, language } = useLanguage();
  const [data, setData] = useState<{ ward: { name: string }; upcoming: Ev[]; past: Ev[] } | null>(null);
  const [guests, setGuests] = useState<Record<string, number>>({});
  const [editing, setEditing] = useState<Record<string, boolean>>({});
  const [confirmNo, setConfirmNo] = useState<string | null>(null);     // event id asking "Not attending?"
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await fetchApi(`/parent/events?lang=${language}`));
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("events.load_failed"));
    }
  }, [language, t]);

  useEffect(() => { load(); }, [load]);

  const fmt = (iso: string) => new Date(iso).toLocaleString(language === "ta" ? "ta-IN" : "en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

  const reply = async (ev: Ev, status: Reply) => {
    setError("");
    setBusy(true);
    try {
      await fetchApi(`/parent/events/${ev.id}/rsvp`, {
        method: "POST",
        body: JSON.stringify({ status, guests: status === "no" ? 0 : guests[ev.id] ?? Math.max(ev.guests, 1), reason: status === "no" ? reason.trim() || null : null }),
      });
      setSaved(ev.id);
      setEditing({ ...editing, [ev.id]: false });
      setConfirmNo(null);
      setReason("");
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("events.save_failed"));
    } finally {
      setBusy(false);
    }
  };

  const answered = (ev: Ev) => (
    <div className="rounded-tile border border-success-line bg-success-faint p-3 space-y-1.5" data-testid="rsvp-confirm">
      <p className="text-xs text-ink inline-flex items-center gap-1.5">
        <CheckCircle2 className="w-3.5 h-3.5 text-teal" />
        <span>{t("events.you_replied")} <span className="font-semibold" data-testid="rsvp-answer">
          {t(`events.reply_${ev.rsvp_status}`)}{ev.rsvp_status !== "no" ? ` · ${t("events.n_guests").replace("{n}", String(ev.guests))}` : ""}
        </span></span>
      </p>
      {ev.rsvp_status === "no" && ev.reason && <p className="text-caption text-ink-soft">“{ev.reason}”</p>}
      {saved === ev.id && <p className="text-caption text-success font-semibold" role="status" data-testid="rsvp-saved">{t("events.rsvp_saved")}</p>}
      {ev.can_rsvp ? (
        <div className="flex flex-wrap items-center justify-between gap-2">
          {ev.rsvp_closes_at && <span className="text-caption text-muted" data-testid="rsvp-change-until">{t("events.change_until").replace("{d}", fmt(ev.rsvp_closes_at))}</span>}
          <button type="button" onClick={() => { setEditing({ ...editing, [ev.id]: true }); setSaved(""); }} data-testid="rsvp-change"
            className="px-3 py-1.5 border border-line-strong bg-white text-xs font-semibold rounded-tile">{t("events.change_reply")}</button>
        </div>
      ) : <p className="text-caption text-muted" data-testid="rsvp-closed">{t("events.replies_closed")}</p>}
    </div>
  );

  const choose = (ev: Ev) => (
    <div className="space-y-2 pt-1">
      <label className="flex items-center gap-2 text-xs text-ink-soft">{t("events.coming_with")}
        <select value={guests[ev.id] ?? Math.max(ev.guests, 1)} onChange={(e) => setGuests({ ...guests, [ev.id]: Number(e.target.value) })}
          className="px-2 py-1 border border-line-strong rounded-tile text-xs" data-testid="guest-count" aria-label={t("events.guests")}>
          {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
      </label>
      <div className="grid grid-cols-3 gap-2" role="group" aria-label={t("events.rsvp")}>
        {(["yes", "maybe", "no"] as const).map((s) => (
          <button key={s} type="button" disabled={busy} onClick={() => (s === "no" ? (setConfirmNo(ev.id), setReason(ev.reason || "")) : reply(ev, s))}
            aria-pressed={ev.rsvp_status === s} data-testid={`rsvp-${s}`}
            className={`py-2 rounded-tile text-xs font-semibold border disabled:opacity-50 ${ev.rsvp_status === s ? "bg-teal border-teal text-white" : "border-line-strong text-ink-soft"}`}>
            {t(`events.reply_${s}`)}
          </button>
        ))}
      </div>
      {confirmNo === ev.id && (
        <div role="alertdialog" aria-labelledby={`no-title-${ev.id}`} className="rounded-tile border border-danger-line bg-danger-soft p-3 space-y-2" data-testid="rsvp-no-dialog">
          <p id={`no-title-${ev.id}`} className="text-xs font-semibold text-danger">{t("events.confirm_no_title")}</p>
          <p className="text-caption text-ink-soft">{t("events.confirm_no_body")}</p>
          <input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={255} placeholder={t("events.reason_ph")} data-testid="rsvp-no-reason"
            aria-label={t("events.reason_ph")} className="w-full px-2.5 py-1.5 bg-white border border-line rounded-tile text-xs" />
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={() => setConfirmNo(null)} className="px-3 py-1.5 border border-line-strong bg-white text-xs font-semibold rounded-tile">{t("events.go_back")}</button>
            <button type="button" disabled={busy} onClick={() => reply(ev, "no")} data-testid="rsvp-no-confirm"
              className="px-3 py-1.5 bg-danger text-white text-xs font-semibold rounded-tile disabled:opacity-50">{t("events.confirm_no")}</button>
          </div>
        </div>
      )}
      {ev.rsvp_status && (
        <button type="button" onClick={() => { setEditing({ ...editing, [ev.id]: false }); setConfirmNo(null); }} data-testid="rsvp-keep"
          className="text-caption text-brand font-semibold">{t("events.keep_reply")}</button>
      )}
    </div>
  );

  const card = (ev: Ev, past = false) => (
    <li key={ev.id} className={`bg-white rounded-card border p-4 space-y-2 ${past ? "border-line opacity-70" : "border-line"}`} data-testid={past ? "past-event" : "event-card"}>
      <div className="text-caption font-semibold text-brand">{ev.kind_label}</div>
      <div className="text-sm font-semibold text-ink">{ev.title}</div>
      <div className="text-xs text-ink-soft flex flex-wrap gap-x-3 gap-y-1">
        <span className="inline-flex items-center gap-1"><CalendarDays className="w-3.5 h-3.5" />{ev.when}</span>
        {ev.location && <span className="inline-flex items-center gap-1"><MapPin className="w-3.5 h-3.5" />{ev.location}</span>}
      </div>
      {ev.description && <p className="text-xs text-ink-soft">{ev.description}</p>}
      {!past && ev.rsvp_enabled && (
        ev.rsvp_status && !editing[ev.id] ? answered(ev)
          : ev.can_rsvp ? choose(ev)
            : <p className="text-caption text-muted" data-testid="rsvp-closed">{t("events.replies_closed")}</p>
      )}
    </li>
  );

  return (
    <RoleGuard allowedRoles={["parent"]}>
      <AppShell pageTitle={t("events.parent_title")}>
        <div className="max-w-2xl mx-auto space-y-6">
          {data && <p className="text-xs text-muted">{t("events.for_child")} {data.ward.name}</p>}
          {error && <p className="text-xs text-red-600" role="alert" data-testid="rsvp-error">{error}</p>}
          {data && data.upcoming.length === 0 && <p className="text-xs text-muted bg-white rounded-card border border-dashed border-line-strong p-6 text-center" data-testid="no-events">{t("events.none_upcoming")}</p>}
          <ul className="space-y-3" data-testid="upcoming-events">{data?.upcoming.map((ev) => card(ev))}</ul>
          {data && data.past.length > 0 && (
            <>
              <h2 className="text-xs font-semibold text-muted pt-2">{t("events.past")}</h2>
              <ul className="space-y-3">{data.past.map((ev) => card(ev, true))}</ul>
            </>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
