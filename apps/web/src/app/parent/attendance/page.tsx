"use client";

/** Screen 10 · Attendance (parent): the child's month and leave requests (links L07, L09). */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { CalendarDays, ChevronLeft, ChevronRight, Send } from "lucide-react";

interface Row { session_id: string; date: string; time: string; title: string; status: string }
interface Leave { id: string; start_date: string; end_date: string; reason: string; status: string; decision_note: string | null }
interface Data {
  consent_required: boolean; ward: { id: string; name: string; batch?: string }; month?: string; sessions?: Row[];
  summary?: { present: number; absent: number; excused: number; pct: number | null; overall_pct: number }; leave_requests?: Leave[];
}

const CHIP: Record<string, string> = {
  Present: "bg-[#DCFCE7] text-[#166534]", Absent: "bg-[#FEE2E2] text-[#991B1B]", Excused: "bg-[#DBEAFE] text-[#1E40AF]",
  Upcoming: "bg-[#F1F5F9] text-[#475569]", Cancelled: "bg-[#F1F5F9] text-[#94A3B8] line-through", "Not marked": "bg-[#F1F5F9] text-[#64748B]",
};

function shiftMonth(m: string, by: number): string {
  const [y, mm] = m.split("-").map(Number);
  const d = new Date(y, mm - 1 + by, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

const today = () => new Date().toISOString().slice(0, 10);

export default function ParentAttendancePage() {
  const { t, language } = useLanguage();
  const [month, setMonth] = useState(today().slice(0, 7));
  const [data, setData] = useState<Data | null>(null);
  const [form, setForm] = useState({ start_date: today(), end_date: today(), reason: "" });
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await fetchApi<Data>(`/parent/attendance?month=${month}&lang=${language}`));
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("parent_attendance.load_failed"));
    }
  }, [month, language, t]);

  useEffect(() => { load(); }, [load]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSent(false);
    setError("");
    if (form.end_date < form.start_date) return setError(t("parent_attendance.err_dates"));
    if (form.reason.trim().length < 5) return setError(t("parent_attendance.err_reason"));
    setBusy(true);
    try {
      await fetchApi("/parent/leave-requests", { method: "POST", body: JSON.stringify({ ...form, child_id: data?.ward.id, reason: form.reason.trim() }) });
      setSent(true);
      setForm({ ...form, reason: "" });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : t("parent_attendance.save_failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <RoleGuard allowedRoles={["parent"]}>
      <AppShell pageTitle={t("parent_attendance.title")}>
        <div className="w-full max-w-[420px] md:max-w-3xl mx-auto p-4 space-y-4" data-testid="parent-attendance">
          {error && <p className="text-xs text-red-600" role="alert" data-testid="pa-error">{error}</p>}
          {data?.consent_required && (
            <div className="bg-white rounded-2xl border border-[#BFDBFE] p-5 text-xs text-[#475569]" data-testid="pa-consent">{t("parent_attendance.consent_needed")}</div>
          )}
          {data && !data.consent_required && data.summary && (
            <>
              <div className="bg-white rounded-2xl border border-[#E2E8F0] p-4">
                <div className="flex items-center justify-between">
                  <button type="button" onClick={() => setMonth(shiftMonth(month, -1))} className="p-1.5 border rounded-lg" aria-label={t("parent_attendance.prev_month")}><ChevronLeft className="w-4 h-4" /></button>
                  <div className="text-center">
                    <div className="text-sm font-black text-[#0F1F3A]">{data.ward.name}</div>
                    <div className="text-[11px] text-[#64748B]" data-testid="pa-month">{data.month}</div>
                  </div>
                  <button type="button" onClick={() => setMonth(shiftMonth(month, 1))} className="p-1.5 border rounded-lg" aria-label={t("parent_attendance.next_month")}><ChevronRight className="w-4 h-4" /></button>
                </div>
                <div className="grid grid-cols-4 gap-2 mt-3 text-center text-xs" data-testid="pa-summary">
                  <div><div className="text-lg font-black text-[#166534]">{data.summary.present}</div>{t("parent_attendance.present")}</div>
                  <div><div className="text-lg font-black text-[#991B1B]">{data.summary.absent}</div>{t("parent_attendance.absent")}</div>
                  <div><div className="text-lg font-black text-[#1E40AF]">{data.summary.excused}</div>{t("parent_attendance.excused")}</div>
                  <div><div className="text-lg font-black">{data.summary.pct ?? "—"}{data.summary.pct !== null ? "%" : ""}</div>{t("parent_attendance.this_month")}</div>
                </div>
              </div>

              <ul className="bg-white rounded-2xl border border-[#E2E8F0] divide-y divide-[#F1F5F9]" data-testid="pa-sessions">
                {data.sessions?.length === 0 && <li className="p-4 text-xs text-center text-[#64748B]">{t("parent_attendance.no_classes")}</li>}
                {data.sessions?.map((s) => (
                  <li key={s.session_id} className="px-4 py-2.5 flex items-center justify-between gap-2 text-xs" data-testid="pa-session">
                    <div><div className="font-semibold text-[#0F1F3A]">{s.title}</div><div className="text-[11px] text-[#64748B]">{s.date} · {s.time}</div></div>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${CHIP[s.status] || ""}`}>{t(`parent_attendance.status_${s.status.replace(" ", "_")}`)}</span>
                  </li>
                ))}
              </ul>

              <form onSubmit={submit} noValidate className="bg-white rounded-2xl border border-[#E2E8F0] p-4 space-y-2" data-testid="leave-form">
                <h2 className="text-sm font-black text-[#0F1F3A] flex items-center gap-2"><CalendarDays className="w-4 h-4 text-[#2B5CD0]" />{t("parent_attendance.request_leave")}</h2>
                <div className="grid grid-cols-2 gap-2">
                  <label className="text-[11px] font-bold">{t("parent_attendance.from")}
                    <input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} data-testid="leave-start" className="mt-1 w-full px-2 py-1.5 border rounded-lg text-xs font-normal" /></label>
                  <label className="text-[11px] font-bold">{t("parent_attendance.to")}
                    <input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} data-testid="leave-end" className="mt-1 w-full px-2 py-1.5 border rounded-lg text-xs font-normal" /></label>
                </div>
                <textarea value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} rows={2} placeholder={t("parent_attendance.reason")}
                  data-testid="leave-reason" className="w-full px-2.5 py-1.5 border rounded-lg text-xs" />
                <p className="text-[11px] text-[#64748B]">{t("parent_attendance.rule")}</p>
                <button type="submit" disabled={busy} data-testid="leave-send" className="w-full py-2.5 bg-[#2B5CD0] text-white text-xs font-bold rounded-xl inline-flex items-center justify-center gap-1.5 disabled:opacity-50"><Send className="w-3.5 h-3.5" />{t("parent_attendance.send")}</button>
                {sent && <p className="text-xs text-[#166534] font-bold" data-testid="leave-sent">{t("parent_attendance.sent")}</p>}
              </form>

              <ul className="bg-white rounded-2xl border border-[#E2E8F0] divide-y divide-[#F1F5F9]" data-testid="leave-list">
                {data.leave_requests?.map((l) => (
                  <li key={l.id} className="px-4 py-2.5 text-xs" data-testid="leave-row">
                    <div className="flex justify-between gap-2"><span className="font-semibold">{l.start_date} → {l.end_date}</span>
                      <span className="font-bold" data-testid="leave-status">{t(`parent_attendance.leave_${l.status}`)}</span></div>
                    <div className="text-[11px] text-[#64748B]">{l.reason}{l.decision_note ? ` · ${l.decision_note}` : ""}</div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
