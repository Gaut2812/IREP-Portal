"use client";

/** Student dashboard: what is behind each tile (problems by topic, practice heat map, all badges, how skills grow).
 *  A side drawer, opened from the tile. */
import React, { useEffect, useState } from "react";
import { X } from "lucide-react";
import { fetchApi } from "@/lib/api";

export type DetailKind = "problems" | "streak" | "badges" | "skills";
interface Details {
  problems: { total: number; in_lab: number; this_month: number; by_topic: { topic: string; solved: number }[]; recent: { title: string; solved_on: string }[] };
  activity: { days: { date: string; count: number }[]; current: number; best: number };
  badges: { id: string; name: string; description: string; icon: string; earned: boolean; earned_on: string | null }[];
  skills: { key: string; skill: string; percentage: number; how: string }[];
}

const shade = (n: number) => (n === 0 ? "bg-line-soft" : n === 1 ? "bg-brand/30" : n === 2 ? "bg-brand/60" : "bg-brand");

export function TileDetails({ kind, onClose, t, lang }: { kind: DetailKind; onClose: () => void; t: (k: string) => string; lang: string }) {
  const [d, setD] = useState<Details | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => { fetchApi<Details>(`/student/dashboard/details?lang=${lang}`).then(setD).catch(() => setFailed(true)); }, [lang]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const title = { problems: t("dashboard.problems_solved"), streak: t("dashboard.practice_streak"), badges: t("dashboard.all_badges"), skills: t("dashboard.how_skills_grow") }[kind];
  const maxTopic = Math.max(1, ...(d?.problems.by_topic.map((x) => x.solved) || [1]));
  // the heat map in weeks (columns) of 7 days
  const weeks: { date: string; count: number }[][] = [];
  (d?.activity.days || []).forEach((day, i) => { (weeks[Math.floor(i / 7)] ||= []).push(day); });

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label={title}>
      <button type="button" className="absolute inset-0 bg-ink/40" onClick={onClose} aria-label={t("dashboard.close")} tabIndex={-1} />
      <div className="relative w-full max-w-md bg-surface h-full shadow-pop p-6 overflow-y-auto space-y-4" data-testid={`details-${kind}`}>
        <div className="flex items-start justify-between">
          <h2 className="text-heading font-semibold text-ink">{title}</h2>
          <button type="button" onClick={onClose} className="p-1.5 rounded-tile hover:bg-line-soft" aria-label={t("dashboard.close")}><X className="w-4 h-4 text-muted" /></button>
        </div>
        {failed && <p className="text-body text-danger" role="alert">{t("dashboard.details_failed")}</p>}
        {!d && !failed && <div className="h-40 bg-line-soft rounded-card animate-pulse" />}

        {d && kind === "problems" && (
          <div className="space-y-4">
            <p className="text-body text-ink-soft">{t("dashboard.problems_note").replace("{total}", String(d.problems.total)).replace("{lab}", String(d.problems.in_lab)).replace("{month}", String(d.problems.this_month))}</p>
            {d.problems.by_topic.length === 0 ? <p className="text-label text-muted">{t("dashboard.no_lab_problems")}</p> : (
              <ul className="space-y-2" data-testid="problems-by-topic">
                {d.problems.by_topic.map((x) => (
                  <li key={x.topic}>
                    <div className="flex justify-between text-label"><span className="text-ink">{x.topic}</span><span className="tabular text-ink-soft">{x.solved}</span></div>
                    <div className="h-1.5 bg-line-soft rounded-full overflow-hidden"><div className="h-full bg-brand" style={{ width: `${(x.solved / maxTopic) * 100}%` }} /></div>
                  </li>
                ))}
              </ul>
            )}
            {d.problems.recent.length > 0 && (
              <div>
                <div className="text-label font-semibold text-ink mb-1">{t("dashboard.recently_solved")}</div>
                <ul className="text-label text-ink-soft space-y-0.5">{d.problems.recent.map((r) => <li key={r.title}>{r.title} · <span className="text-muted">{r.solved_on}</span></li>)}</ul>
              </div>
            )}
          </div>
        )}

        {d && kind === "streak" && (
          <div className="space-y-3">
            <div className="flex gap-6 text-body">
              <div><div className="text-kpi font-semibold text-ink">🔥 {d.activity.current}</div><div className="text-label text-muted">{t("dashboard.current_streak")}</div></div>
              <div><div className="text-kpi font-semibold text-ink">{d.activity.best}</div><div className="text-label text-muted">{t("dashboard.best_streak")}</div></div>
            </div>
            <div className="flex gap-1" data-testid="heatmap" aria-label={t("dashboard.heatmap")}>
              {weeks.map((w, i) => (
                <div key={i} className="flex flex-col gap-1">
                  {w.map((day) => <span key={day.date} title={`${day.date}: ${day.count}`} className={`w-3.5 h-3.5 rounded-sm ${shade(day.count)}`} data-count={day.count} />)}
                </div>
              ))}
            </div>
            <p className="text-label text-muted">{t("dashboard.streak_note")}</p>
          </div>
        )}

        {d && kind === "badges" && (
          <ul className="grid grid-cols-1 gap-2" data-testid="all-badges">
            {d.badges.map((b) => (
              <li key={b.id} className={`flex items-center gap-3 p-3 rounded-card border ${b.earned ? "border-success-line bg-success-faint" : "border-line opacity-70"}`} data-testid={b.earned ? "badge-earned" : "badge-locked"}>
                <span className={`w-10 h-10 rounded-card flex items-center justify-center text-xl ${b.earned ? "bg-white" : "bg-line-soft grayscale"}`}>{b.icon}</span>
                <div className="min-w-0">
                  <div className="text-body font-medium text-ink">{b.name}</div>
                  <div className="text-label text-muted">{b.earned ? `${t("dashboard.earned_on")} ${b.earned_on}` : `${t("dashboard.how_to_earn")}: ${b.description}`}</div>
                </div>
              </li>
            ))}
          </ul>
        )}

        {d && kind === "skills" && (
          <ul className="space-y-3" data-testid="skill-how">
            {d.skills.map((s) => (
              <li key={s.key} className="space-y-0.5">
                <div className="flex justify-between text-body"><span className="text-ink font-medium">{s.skill}</span><span className="tabular text-ink-soft">{s.percentage}%</span></div>
                <p className="text-label text-muted">{s.how}</p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
