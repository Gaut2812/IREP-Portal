"use client";

/** Screen 17 · Events (parent): invitations from the college; RSVP goes back to 42 (L05). */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { CalendarDays, MapPin } from "lucide-react";

interface Ev {
  id: string; title: string; kind: string; kind_label: string; when: string; location: string | null; description: string | null;
  can_rsvp: boolean; rsvp_status: "yes" | "maybe" | "no" | null; guests: number;
}

export default function ParentEventsPage() {
  const { t, language } = useLanguage();
  const [data, setData] = useState<{ ward: { name: string }; upcoming: Ev[]; past: Ev[] } | null>(null);
  const [guests, setGuests] = useState<Record<string, number>>({});
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  const load = useCallback(async () => {
    try {
      setData(await fetchApi(`/parent/events?lang=${language}`));
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("events.load_failed"));
    }
  }, [language, t]);

  useEffect(() => { load(); }, [load]);

  const reply = async (ev: Ev, status: "yes" | "maybe" | "no") => {
    setError("");
    try {
      await fetchApi(`/parent/events/${ev.id}/rsvp`, { method: "POST", body: JSON.stringify({ status, guests: status === "no" ? 0 : guests[ev.id] ?? Math.max(ev.guests, 1) }) });
      setSaved(ev.id);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("events.save_failed"));
    }
  };

  const card = (ev: Ev, past = false) => (
    <li key={ev.id} className={`bg-white rounded-2xl border p-4 space-y-2 ${past ? "border-[#E2E8F0] opacity-70" : "border-[#E2E8F0]"}`} data-testid={past ? "past-event" : "event-card"}>
      <div className="text-[10px] font-bold uppercase tracking-wide text-[#2B5CD0]">{ev.kind_label}</div>
      <div className="text-sm font-black text-[#0F1F3A]">{ev.title}</div>
      <div className="text-xs text-[#475569] flex flex-wrap gap-x-3 gap-y-1">
        <span className="inline-flex items-center gap-1"><CalendarDays className="w-3.5 h-3.5" />{ev.when}</span>
        {ev.location && <span className="inline-flex items-center gap-1"><MapPin className="w-3.5 h-3.5" />{ev.location}</span>}
      </div>
      {ev.description && <p className="text-xs text-[#334155]">{ev.description}</p>}
      {ev.can_rsvp && (
        <div className="space-y-2 pt-1">
          <label className="flex items-center gap-2 text-xs text-[#475569]">{t("events.coming_with")}
            <select value={guests[ev.id] ?? Math.max(ev.guests, 1)} onChange={(e) => setGuests({ ...guests, [ev.id]: Number(e.target.value) })}
              className="px-2 py-1 border border-[#CBD5E1] rounded-lg text-xs" data-testid="guest-count" aria-label={t("events.guests")}>
              {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <div className="grid grid-cols-3 gap-2" role="group" aria-label={t("events.rsvp")}>
            {(["yes", "maybe", "no"] as const).map((s) => (
              <button key={s} type="button" onClick={() => reply(ev, s)} aria-pressed={ev.rsvp_status === s} data-testid={`rsvp-${s}`}
                className={`py-2 rounded-lg text-xs font-bold border ${ev.rsvp_status === s ? "bg-[#2BB3A0] border-[#2BB3A0] text-white" : "border-[#CBD5E1] text-[#334155]"}`}>
                {t(`events.reply_${s}`)}
              </button>
            ))}
          </div>
          {saved === ev.id && <p className="text-[11px] text-[#166534] font-semibold" role="status" data-testid="rsvp-saved">{t("events.rsvp_saved")}</p>}
        </div>
      )}
    </li>
  );

  return (
    <RoleGuard allowedRoles={["parent"]}>
      <AppShell pageTitle={t("events.parent_title")}>
        <div className="max-w-2xl mx-auto space-y-3">
          {data && <p className="text-xs text-[#64748B]">{t("events.for_child")} {data.ward.name}</p>}
          {error && <p className="text-xs text-red-600" role="alert">{error}</p>}
          {data && data.upcoming.length === 0 && <p className="text-xs text-[#64748B] bg-white rounded-2xl border border-dashed border-[#CBD5E1] p-6 text-center" data-testid="no-events">{t("events.none_upcoming")}</p>}
          <ul className="space-y-3" data-testid="upcoming-events">{data?.upcoming.map((ev) => card(ev))}</ul>
          {data && data.past.length > 0 && (
            <>
              <h2 className="text-xs font-black text-[#64748B] uppercase tracking-wide pt-2">{t("events.past")}</h2>
              <ul className="space-y-3">{data.past.map((ev) => card(ev, true))}</ul>
            </>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
