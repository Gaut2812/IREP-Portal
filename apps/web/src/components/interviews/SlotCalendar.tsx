"use client";

/** Mock interview booking calendar (screen 36): a month view where days with open slots are marked; picking a day
 *  lists its times. With no day picked, the next slots are listed. A slot you cannot book says why. */
import React, { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Clock, User } from "lucide-react";

export interface CalSlot {
  id: string; starts_at: string; date: string; time: string; round_type: string; type_label: string; trainer: string;
  duration_min?: number; blocked_reason?: string | null;
}

const dayKey = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const TYPE_DOT: Record<string, string> = { technical: "bg-brand", hr: "bg-teal", ai_coding: "bg-violet" };

export function SlotCalendar({ slots, busyId, onBook, t, locale }: {
  slots: CalSlot[]; busyId: string | null; onBook: (s: CalSlot) => void; t: (k: string) => string; locale: string;
}) {
  const byDay = useMemo(() => {
    const m: Record<string, CalSlot[]> = {};
    for (const s of slots) (m[dayKey(new Date(s.starts_at))] ||= []).push(s);
    return m;
  }, [slots]);
  const first = slots[0] ? new Date(slots[0].starts_at) : new Date();
  const [month, setMonth] = useState(() => new Date(first.getFullYear(), first.getMonth(), 1));
  const [picked, setPicked] = useState<string | null>(null);

  const today = new Date();
  const thisMonth = new Date(today.getFullYear(), today.getMonth(), 1);
  const lastSlot = slots.length ? new Date(slots[slots.length - 1].starts_at) : today;
  const lastMonth = new Date(lastSlot.getFullYear(), lastSlot.getMonth(), 1);

  // Monday-first grid
  const offset = (month.getDay() + 6) % 7;
  const daysIn = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const cells: (Date | null)[] = [...Array(offset).fill(null), ...Array.from({ length: daysIn }, (_, i) => new Date(month.getFullYear(), month.getMonth(), i + 1))];
  while (cells.length % 7) cells.push(null);
  const weekdays = Array.from({ length: 7 }, (_, i) => new Date(2024, 0, 1 + i).toLocaleDateString(locale, { weekday: "narrow" }));

  const list = picked ? byDay[picked] || [] : slots.slice(0, 8);

  return (
    <div className="space-y-3" data-testid="slot-calendar">
      <div className="flex items-center justify-between">
        <button type="button" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))} disabled={month <= thisMonth}
          className="p-1 rounded-tile hover:bg-line-soft disabled:opacity-30" aria-label={t("interviews.prev_month")}><ChevronLeft className="w-4 h-4" /></button>
        <span className="text-xs font-semibold text-ink" data-testid="calendar-month">{month.toLocaleDateString(locale, { month: "long", year: "numeric" })}</span>
        <button type="button" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))} disabled={month >= lastMonth}
          className="p-1 rounded-tile hover:bg-line-soft disabled:opacity-30" aria-label={t("interviews.next_month")}><ChevronRight className="w-4 h-4" /></button>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center" role="grid" aria-label={t("interviews.calendar")}>
        {weekdays.map((w, i) => <div key={i} className="text-caption text-muted">{w}</div>)}
        {cells.map((d, i) => {
          if (!d) return <div key={i} />;
          const k = dayKey(d);
          const daySlots = byDay[k] || [];
          const has = daySlots.length > 0;
          const isToday = k === dayKey(today);
          return (
            <button key={i} type="button" disabled={!has} onClick={() => setPicked(picked === k ? null : k)} aria-pressed={picked === k}
              aria-label={`${d.toLocaleDateString(locale, { day: "numeric", month: "long" })}${has ? ` · ${daySlots.length} ${t("interviews.slots_word")}` : ""}`}
              data-testid={`day-${k}`} data-has-slots={has ? "true" : "false"}
              className={`h-9 rounded-tile text-xs flex flex-col items-center justify-center gap-0.5 ${picked === k ? "bg-brand text-white" : has ? "bg-brand-soft text-ink font-semibold hover:ring-1 hover:ring-brand" : "text-subtle"} ${isToday && picked !== k ? "ring-1 ring-line-strong" : ""}`}>
              {d.getDate()}
              {has && <span className="flex gap-0.5">{[...new Set(daySlots.map((s) => s.round_type))].map((rt) => <span key={rt} className={`w-1 h-1 rounded-full ${picked === k ? "bg-white" : TYPE_DOT[rt] || "bg-brand"}`} />)}</span>}
            </button>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-3 text-caption text-muted">
        {(["technical", "hr", "ai_coding"] as const).map((rt) => <span key={rt} className="inline-flex items-center gap-1"><span className={`w-2 h-2 rounded-full ${TYPE_DOT[rt]}`} />{t(`interviews.type_${rt}`)}</span>)}
      </div>

      <div className="text-caption font-semibold text-muted" data-testid="slot-list-title">
        {picked ? new Date(`${picked}T00:00:00`).toLocaleDateString(locale, { weekday: "long", day: "numeric", month: "long" }) : t("interviews.next_slots")}
      </div>
      {list.length === 0 ? (
        <p className="text-xs text-muted py-3 text-center">{t("interviews.no_slots")}</p>
      ) : list.map((s) => (
        <div key={s.id} className="p-2.5 rounded-tile border border-line bg-surface-2 text-xs space-y-1" data-testid={`slot-${s.id}`}>
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <div className="font-semibold text-ink flex items-center gap-1.5"><span className={`w-2 h-2 rounded-full ${TYPE_DOT[s.round_type] || "bg-brand"}`} />{s.type_label}</div>
              <div className="text-caption text-muted flex flex-wrap items-center gap-x-2">
                <span className="inline-flex items-center gap-1"><Clock className="w-3 h-3" />{s.date} · {s.time}{s.duration_min ? ` · ${s.duration_min} ${t("interviews.min")}` : ""}</span>
                <span className="inline-flex items-center gap-1"><User className="w-3 h-3" />{s.trainer}</span>
              </div>
            </div>
            <button onClick={() => onBook(s)} disabled={busyId === s.id || !!s.blocked_reason}
              className="px-3 py-1 rounded-tile text-xs font-semibold bg-teal hover:bg-teal-hover text-white disabled:opacity-50 shrink-0"
              aria-label={`${t("interviews.book")} ${s.date} ${s.time} ${s.type_label}`} data-testid={`book-${s.id}`}>
              {busyId === s.id ? t("interviews.booking") : t("interviews.book")}
            </button>
          </div>
          {s.blocked_reason && <p className="text-caption text-warning" data-testid={`blocked-${s.id}`}>{s.blocked_reason}</p>}
        </div>
      ))}
    </div>
  );
}
