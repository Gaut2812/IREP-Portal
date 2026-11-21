"use client";

/** Week view shared by screens 05 (trainer) and 06 (college). */
import React from "react";
import { useLanguage } from "@/lib/LanguageContext";
import { ChevronLeft, ChevronRight } from "lucide-react";

export interface WeekSession { id: string; title: string; batch: string | null; start: string; end: string; room: string | null; status: string; substitute: string | null }
export interface Clash { kind: "batch" | "trainer" | "room"; session_id: string; title: string; batch: string | null; start: string; room: string | null }

export function isoDate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function shiftWeek(week: string, days: number): string {
  const d = new Date(`${week}T00:00:00`);
  d.setDate(d.getDate() + days);
  return isoDate(d);
}

const hhmm = (iso: string) => iso.slice(11, 16);

export function WeekView({ week, sessions, onWeek }: { week: string; sessions: WeekSession[]; onWeek: (w: string) => void }) {
  const { t } = useLanguage();
  const days = Array.from({ length: 7 }, (_, i) => shiftWeek(week, i));
  return (
    <section className="bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-3" data-testid="week-view">
      <div className="flex items-center justify-between">
        <button type="button" onClick={() => onWeek(shiftWeek(week, -7))} className="p-1.5 border border-[#E2E8F0] rounded-lg" aria-label={t("schedule.prev_week")} data-testid="week-prev"><ChevronLeft className="w-4 h-4" /></button>
        <h2 className="text-sm font-black text-[#0F1F3A]" data-testid="week-label">{t("schedule.week_of")} {week}</h2>
        <button type="button" onClick={() => onWeek(shiftWeek(week, 7))} className="p-1.5 border border-[#E2E8F0] rounded-lg" aria-label={t("schedule.next_week")} data-testid="week-next"><ChevronRight className="w-4 h-4" /></button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-7 gap-2">
        {days.map((day) => {
          const items = sessions.filter((s) => s.start.slice(0, 10) === day);
          return (
            <div key={day} className="border border-[#F1F5F9] rounded-lg p-2 min-h-[80px]">
              <div className="text-[11px] font-bold text-[#64748B]">{t(`schedule.day_${new Date(`${day}T00:00:00`).getDay()}`)} {day.slice(8)}</div>
              <ul className="space-y-1 mt-1">
                {items.map((s) => (
                  <li key={s.id} data-testid="week-session" className={`rounded px-1.5 py-1 text-[11px] ${s.status === "Cancelled" ? "bg-[#F1F5F9] text-[#94A3B8] line-through" : "bg-[#EFF6FF] text-[#0F1F3A]"}`}>
                    <div className="font-bold">{hhmm(s.start)}–{hhmm(s.end)} {s.batch}</div>
                    <div className="truncate" title={s.title}>{s.title}</div>
                    {(s.room || s.substitute) && <div className="text-[10px] text-[#64748B]">{[s.room, s.substitute && `${t("schedule.sub")}: ${s.substitute}`].filter(Boolean).join(" · ")}</div>}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export function ClashList({ clashes }: { clashes: Clash[] }) {
  const { t } = useLanguage();
  if (!clashes.length) return null;
  return (
    <ul className="text-[11px] text-[#B45309] space-y-0.5" data-testid="clash-list">
      {clashes.map((c, i) => (
        <li key={i}>⚠ {t(`schedule.clash_${c.kind}`)}: {c.title} ({c.batch ?? "—"}, {c.start.slice(0, 16).replace("T", " ")}{c.room ? `, ${c.room}` : ""})</li>
      ))}
    </ul>
  );
}
