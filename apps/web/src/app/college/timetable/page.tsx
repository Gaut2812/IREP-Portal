"use client";

/** Screen 06 · Timetable (college): approve schedule changes with clash warnings (link L11 down). */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { ClashList, Clash, WeekSession, WeekView, isoDate } from "@/components/schedule/WeekView";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";

interface Req { id: string; kind: string; batch: string | null; session_title: string | null; current_start: string | null; title: string | null; start: string | null; end: string | null; room: string | null; substitute: string | null; requested_by: string | null; reason: string; status: string; clashes: Clash[]; decision_note: string | null }
interface Timetable { week: string; sessions: WeekSession[]; requests: Req[]; rooms: string[] }

function monday(): string {
  const d = new Date();
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  return isoDate(d);
}

const when = (iso: string | null) => (iso ? iso.slice(0, 16).replace("T", " ") : "");

export default function CollegeTimetablePage() {
  const { t } = useLanguage();
  const [week, setWeek] = useState(monday());
  const [data, setData] = useState<Timetable | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await fetchApi<Timetable>(`/college/timetable?week=${week}`));
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("schedule.load_failed"));
    }
  }, [week, t]);

  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try { await fn(); await load(); } catch (e) {
      setError(e instanceof ApiError ? (typeof e.detail === "string" && e.detail.startsWith("{") ? t("schedule.clash_blocked") : e.detail) : t("schedule.save_failed"));
    } finally { setBusy(false); }
  };

  const approve = (r: Req) => act(() => fetchApi(`/college/schedule-requests/${r.id}/approve${r.clashes.length ? "?override=true" : ""}`, { method: "POST" }));
  const reject = (r: Req) => {
    const reason = window.prompt(t("schedule.reject_reason"));
    if (reason && reason.trim().length >= 5) act(() => fetchApi(`/college/schedule-requests/${r.id}/reject`, { method: "POST", body: JSON.stringify({ reason: reason.trim() }) }));
  };

  const pending = data?.requests.filter((r) => r.status === "pending") || [];
  return (
    <RoleGuard allowedRoles={["college"]}>
      <AppShell pageTitle={t("schedule.college_title")}>
        <div className="space-y-6 max-w-6xl">
          {error && <p className="text-xs text-red-600" role="alert" data-testid="timetable-error">{error}</p>}
          <section className="bg-white rounded-card border border-line p-4 space-y-2" data-testid="pending-requests">
            <h2 className="text-sm font-semibold text-ink">{t("schedule.pending")} ({pending.length})</h2>
            {pending.length === 0 && <p className="text-xs text-muted">{t("schedule.no_pending")}</p>}
            <ul className="divide-y divide-line-soft">
              {pending.map((r) => (
                <li key={r.id} className="py-2 text-xs space-y-1" data-testid="pending-request">
                  <div className="flex flex-wrap justify-between gap-2">
                    <div>
                      <span className="font-semibold">{t(`schedule.kind_${r.kind}`)}</span> · {r.batch} · {r.title || r.session_title}
                      <div className="text-caption text-muted">
                        {r.kind === "reschedule" && `${when(r.current_start)} → `}{when(r.start)}{r.room ? ` · ${r.room}` : ""}{r.substitute ? ` · ${t("schedule.sub")}: ${r.substitute}` : ""} · {t("schedule.by")} {r.requested_by}
                      </div>
                      <div className="text-caption text-ink-soft">{r.reason}</div>
                    </div>
                    <div className="flex gap-2 items-start">
                      <button type="button" disabled={busy} onClick={() => approve(r)} data-testid="request-approve"
                        className={`px-2.5 py-1 font-semibold rounded text-white ${r.clashes.length ? "bg-warning" : "bg-brand"}`}>
                        {r.clashes.length ? t("schedule.approve_anyway") : t("schedule.approve")}
                      </button>
                      <button type="button" disabled={busy} onClick={() => reject(r)} data-testid="request-reject" className="px-2.5 py-1 border border-line-strong font-semibold rounded">{t("schedule.reject")}</button>
                    </div>
                  </div>
                  <ClashList clashes={r.clashes} />
                </li>
              ))}
            </ul>
          </section>
          {data && <WeekView week={data.week} sessions={data.sessions} onWeek={setWeek} />}
          {data && data.rooms.length > 0 && <p className="text-caption text-muted">{t("schedule.rooms")}: {data.rooms.join(", ")}</p>}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
