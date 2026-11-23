"use client";

/** Screen 05 · Schedule (trainer): my week and change proposals (link L11 up). */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { ClashList, Clash, WeekSession, WeekView, isoDate } from "@/components/schedule/WeekView";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { CalendarPlus } from "lucide-react";

interface Req { id: string; kind: string; batch: string | null; session_title: string | null; title: string | null; start: string | null; status: string; clashes: Clash[]; decision_note: string | null; reason: string }
interface Week { week: string; my_batches: { id: string; short_name: string }[]; sessions: (WeekSession & { batch_id: string })[]; requests: Req[]; substitutes: { id: string; name: string }[] }

function monday(): string {
  const d = new Date();
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  return isoDate(d);
}

export default function TrainerSchedulePage() {
  const { t } = useLanguage();
  const [week, setWeek] = useState(monday());
  const [data, setData] = useState<Week | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [lastClashes, setLastClashes] = useState<Clash[] | null>(null);
  const tomorrow = isoDate(new Date(Date.now() + 86400000));
  const [form, setForm] = useState({ kind: "new", batch_id: "", session_id: "", title: "", date: tomorrow, time: "16:00", minutes: "60", room: "", substitute_trainer_id: "", reason: "" });

  const load = useCallback(async () => {
    try {
      setData(await fetchApi<Week>(`/trainer/schedule?week=${week}`));
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("schedule.load_failed"));
    }
  }, [week, t]);

  useEffect(() => { load(); }, [load]);

  const upcoming = (data?.sessions || []).filter((s) => s.status !== "Cancelled" && new Date(s.start) > new Date());

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLastClashes(null);
    if (form.reason.trim().length < 5) return setError(t("schedule.err_reason"));
    const start = new Date(`${form.date}T${form.time}:00`);
    const end = new Date(start.getTime() + Number(form.minutes) * 60000);
    const local = (d: Date) => `${isoDate(d)}T${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:00`;
    const body: Record<string, unknown> = { kind: form.kind, reason: form.reason.trim() };
    if (form.kind === "new") Object.assign(body, { batch_id: form.batch_id || data?.my_batches[0]?.id, title: form.title.trim(), start: local(start), end: local(end), room: form.room.trim() || null });
    else body.session_id = form.session_id || upcoming[0]?.id;
    if (form.kind === "reschedule") Object.assign(body, { start: local(start), end: local(end), room: form.room.trim() || null });
    if (form.kind === "substitute") body.substitute_trainer_id = form.substitute_trainer_id || data?.substitutes[0]?.id;
    setBusy(true);
    try {
      const r = await fetchApi<{ clashes: Clash[] }>("/trainer/schedule/requests", { method: "POST", body: JSON.stringify(body) });
      setLastClashes(r.clashes);
      setForm({ ...form, title: "", reason: "" });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : t("schedule.save_failed"));
    } finally {
      setBusy(false);
    }
  };

  const cls = "w-full px-2.5 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg text-xs";
  const needsTime = form.kind === "new" || form.kind === "reschedule";

  return (
    <RoleGuard allowedRoles={["trainer"]}>
      <AppShell pageTitle={t("schedule.trainer_title")}>
        <div className="p-4 md:p-6 space-y-4 max-w-6xl">
          {error && <p className="text-xs text-red-600" role="alert" data-testid="schedule-error">{error}</p>}
          {data && <WeekView week={data.week} sessions={data.sessions} onWeek={setWeek} />}

          <form onSubmit={submit} noValidate className="bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-2" data-testid="proposal-form">
            <h2 className="text-sm font-black text-[#0F1F3A] flex items-center gap-2"><CalendarPlus className="w-4 h-4 text-[#2B5CD0]" />{t("schedule.propose")}</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <select className={cls} value={form.kind} data-testid="proposal-kind" onChange={(e) => setForm({ ...form, kind: e.target.value })} aria-label={t("schedule.kind")}>
                {["new", "reschedule", "cancel", "substitute"].map((k) => <option key={k} value={k}>{t(`schedule.kind_${k}`)}</option>)}
              </select>
              {form.kind === "new" ? (
                <>
                  <select className={cls} value={form.batch_id} data-testid="proposal-batch" onChange={(e) => setForm({ ...form, batch_id: e.target.value })} aria-label={t("schedule.batch")}>
                    {data?.my_batches.map((b) => <option key={b.id} value={b.id}>{b.short_name}</option>)}
                  </select>
                  <input className={`${cls} md:col-span-2`} placeholder={t("schedule.title")} value={form.title} data-testid="proposal-title" onChange={(e) => setForm({ ...form, title: e.target.value })} />
                </>
              ) : (
                <select className={`${cls} md:col-span-3`} value={form.session_id} data-testid="proposal-session" onChange={(e) => setForm({ ...form, session_id: e.target.value })} aria-label={t("schedule.session")}>
                  {upcoming.map((s) => <option key={s.id} value={s.id}>{s.start.slice(0, 16).replace("T", " ")} · {s.batch} · {s.title}</option>)}
                </select>
              )}
              {needsTime && (
                <>
                  <input type="date" className={cls} value={form.date} data-testid="proposal-date" onChange={(e) => setForm({ ...form, date: e.target.value })} aria-label={t("schedule.date")} />
                  <input type="time" className={cls} value={form.time} data-testid="proposal-time" onChange={(e) => setForm({ ...form, time: e.target.value })} aria-label={t("schedule.time")} />
                  <select className={cls} value={form.minutes} onChange={(e) => setForm({ ...form, minutes: e.target.value })} aria-label={t("schedule.duration")}>
                    {[30, 45, 60, 90, 120, 180].map((m) => <option key={m} value={m}>{m} {t("schedule.min")}</option>)}
                  </select>
                  <input className={cls} placeholder={t("schedule.room")} value={form.room} data-testid="proposal-room" onChange={(e) => setForm({ ...form, room: e.target.value })} />
                </>
              )}
              {form.kind === "substitute" && (
                <select className={`${cls} md:col-span-2`} value={form.substitute_trainer_id} onChange={(e) => setForm({ ...form, substitute_trainer_id: e.target.value })} aria-label={t("schedule.substitute")}>
                  {data?.substitutes.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              )}
              <input className={`${cls} md:col-span-3`} placeholder={t("schedule.reason")} value={form.reason} data-testid="proposal-reason" onChange={(e) => setForm({ ...form, reason: e.target.value })} />
              <button type="submit" disabled={busy} data-testid="proposal-send" className="px-3 py-1.5 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg disabled:opacity-50">{t("schedule.send")}</button>
            </div>
            {lastClashes && (lastClashes.length ? (
              <div className="p-2 rounded-lg bg-[#FFFBEB] border border-[#FDE68A]"><p className="text-[11px] font-bold text-[#92400E]">{t("schedule.sent_with_clashes")}</p><ClashList clashes={lastClashes} /></div>
            ) : <p className="text-[11px] text-[#166534] font-bold" data-testid="proposal-sent">{t("schedule.sent")}</p>)}
          </form>

          <section className="bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-2" data-testid="my-requests">
            <h2 className="text-sm font-black text-[#0F1F3A]">{t("schedule.my_requests")}</h2>
            {data?.requests.length === 0 && <p className="text-xs text-[#64748B]">{t("schedule.no_requests")}</p>}
            <ul className="divide-y divide-[#F1F5F9] text-xs">
              {data?.requests.map((r) => (
                <li key={r.id} className="py-2" data-testid="my-request">
                  <span className="font-bold">{t(`schedule.kind_${r.kind}`)}</span> · {r.title || r.session_title} · {r.batch}{r.start ? ` · ${r.start.slice(0, 16).replace("T", " ")}` : ""}
                  <span className="ml-2 text-[#64748B]" data-testid="my-request-status">{t(`schedule.status_${r.status}`)}</span>
                  {r.decision_note && <div className="text-[11px] text-[#64748B]">{r.decision_note}</div>}
                </li>
              ))}
            </ul>
          </section>
        </div>
      </AppShell>
    </RoleGuard>
  );
}

