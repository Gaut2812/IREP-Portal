"use client";

/** Trainer · Live classroom hub: classes live now, coming up (start or rejoin), and recent ones (attendance and
 *  recording). The sidebar used to open one fixed class, so an ended class left no way back in. */
import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { EmptyState } from "@/components/ui";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { Radio, Play, ClipboardCheck, Clock, Video } from "lucide-react";

interface Row {
  id: string; title: string; batch: string | null; starts_at: string; ends_at: string; room: string | null; type: string;
  state: "live" | "not_started" | "ended" | "missed_start" | "cancelled"; can_start: boolean; present: number; marked: number; recording_id: string | null;
}

const STATE_CHIP: Record<string, string> = { live: "chip-red", not_started: "chip-blue", ended: "chip-green", missed_start: "chip-amber", cancelled: "chip-amber" };

export default function TrainerLiveHub() {
  const { t, language } = useLanguage();
  const [data, setData] = useState<{ live: Row[]; upcoming: Row[]; past: Row[] } | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { setData(await fetchApi("/trainer/live/sessions")); } catch (e) { setError(e instanceof ApiError ? e.detail : t("live_hub.load_failed")); }
  }, [t]);
  useEffect(() => { load(); const id = setInterval(load, 30000); return () => clearInterval(id); }, [load]);

  const locale = language === "ta" ? "ta-IN" : "en-IN";
  const when = (r: Row) => {
    const s = new Date(r.starts_at), e = new Date(r.ends_at);
    return `${s.toLocaleDateString(locale, { weekday: "short", day: "numeric", month: "short" })} · ${s.toLocaleTimeString(locale, { hour: "numeric", minute: "2-digit" })}–${e.toLocaleTimeString(locale, { hour: "numeric", minute: "2-digit" })}`;
  };

  const row = (r: Row) => (
    <li key={r.id} className="bg-white rounded-card border border-line p-3 flex flex-wrap items-center justify-between gap-3" data-testid={`hub-${r.id}`}>
      <div className="min-w-0">
        <div className="text-sm font-semibold text-ink truncate">{r.title}</div>
        <div className="text-caption text-muted flex flex-wrap gap-x-2">
          <span className="inline-flex items-center gap-1"><Clock className="w-3 h-3" />{when(r)}</span>
          {r.batch && <span>{r.batch}</span>}{r.room && <span>· {r.room}</span>}
          {r.marked > 0 && <span>· {t("live_hub.present").replace("{p}", String(r.present)).replace("{n}", String(r.marked))}</span>}
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <span className={`${STATE_CHIP[r.state]} text-caption`} data-testid="hub-state">{t(`live_hub.state_${r.state}`)}</span>
        {r.state === "live" && <Link href={`/live/${r.id}`} className="px-3 py-1.5 bg-danger text-white text-xs font-semibold rounded-tile inline-flex items-center gap-1" data-testid="hub-rejoin"><Radio className="w-3.5 h-3.5" />{t("live_hub.rejoin")}</Link>}
        {r.state === "not_started" && (r.can_start
          ? <Link href={`/live/${r.id}`} className="px-3 py-1.5 bg-teal text-white text-xs font-semibold rounded-tile inline-flex items-center gap-1" data-testid="hub-start"><Play className="w-3.5 h-3.5" />{t("live_hub.start")}</Link>
          : <Link href={`/live/${r.id}`} className="px-3 py-1.5 border border-line-strong text-xs font-semibold rounded-tile" data-testid="hub-open">{t("live_hub.open")}</Link>)}
        {(r.state === "ended" || r.state === "missed_start") && (
          <Link href="/trainer/attendance" className="px-3 py-1.5 border border-line-strong text-xs font-semibold rounded-tile inline-flex items-center gap-1" data-testid="hub-attendance"><ClipboardCheck className="w-3.5 h-3.5" />{t("live_hub.attendance")}</Link>
        )}
        {r.recording_id && <span className="chip-purple text-caption inline-flex items-center gap-1"><Video className="w-3 h-3" />{t("live_hub.recorded")}</span>}
      </div>
    </li>
  );

  return (
    <RoleGuard allowedRoles={["trainer"]}>
      <AppShell pageTitle={t("live_hub.title")} pageSubtitle={t("live_hub.subtitle")}>
        <div className="max-w-5xl space-y-6" data-testid="live-hub">
          {error && <p className="text-xs text-danger" role="alert">{error}</p>}
          {data && (
            <>
              {data.live.length > 0 && (
                <section className="space-y-2"><h2 className="text-xs font-semibold text-danger">{t("live_hub.live_now")}</h2><ul className="space-y-2">{data.live.map(row)}</ul></section>
              )}
              <section className="space-y-2">
                <h2 className="text-xs font-semibold text-muted">{t("live_hub.upcoming")}</h2>
                {data.upcoming.length === 0 ? <EmptyState title={t("live_hub.none_upcoming")} /> : <ul className="space-y-2" data-testid="hub-upcoming">{data.upcoming.map(row)}</ul>}
              </section>
              <section className="space-y-2">
                <h2 className="text-xs font-semibold text-muted">{t("live_hub.past")}</h2>
                {data.past.length === 0 ? <EmptyState title={t("live_hub.none_past")} /> : <ul className="space-y-2" data-testid="hub-past">{data.past.map(row)}</ul>}
              </section>
            </>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
