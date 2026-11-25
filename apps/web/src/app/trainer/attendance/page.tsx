"use client";

/** Screen 09 · Attendance (trainer). Spec: docs/screens/09-trainer-attendance.md */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { KeyRound } from "lucide-react";

interface Sess { id: string; title: string; batch: string | null; start: string; end: string; session_type: string; checkin_open: boolean; past: boolean; students: number; present: number; absent: number; unmarked: number }
interface Row { student_id: string; name: string; register_no: string; status: string | null; minutes_present: number; source: string | null; override_reason: string | null }
interface Detail { session: Sess & { duration_min: number }; roster: Row[] }

const when = (iso: string) => iso.slice(0, 16).replace("T", " ");
const STATUS: Record<string, string> = { Present: "bg-[#DCFCE7] text-[#166534]", Absent: "bg-[#FEE2E2] text-[#991B1B]" };

export default function TrainerAttendancePage() {
  const { t } = useLanguage();
  const [sessions, setSessions] = useState<Sess[] | null>(null);
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState<Detail | null>(null);
  const [code, setCode] = useState<{ code: string; expires_in: number } | null>(null);
  const [editing, setEditing] = useState<{ student_id: string; status: string; reason: string } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchApi<{ sessions: Sess[] }>("/trainer/attendance/sessions")
      .then((r) => { setSessions(r.sessions); if (r.sessions[0]) setSelected((s) => s || r.sessions[0].id); })
      .catch((e) => setError(e instanceof ApiError ? e.detail : t("attendance.load_failed")));
  }, [t]);

  const load = useCallback(async () => {
    if (!selected) return;
    try {
      setDetail(await fetchApi<Detail>(`/trainer/attendance/${selected}`));
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("attendance.load_failed"));
    }
  }, [selected, t]);

  useEffect(() => { load(); setCode(null); }, [load]);

  // keep the check-in code current while it is shown (it rotates every minute)
  useEffect(() => {
    if (!code || !selected) return;
    const id = setTimeout(() => {
      fetchApi<{ code: string; expires_in: number }>(`/trainer/attendance/${selected}/checkin-code`).then(setCode).catch(() => setCode(null));
    }, Math.max(2, code.expires_in) * 1000);
    return () => clearTimeout(id);
  }, [code, selected]);

  const showCode = () => fetchApi<{ code: string; expires_in: number }>(`/trainer/attendance/${selected}/checkin-code`).then(setCode)
    .catch((e) => setError(e instanceof ApiError ? e.detail : t("attendance.load_failed")));

  const saveOverride = async () => {
    if (!editing) return;
    if (editing.reason.trim().length < 5) return setError(t("attendance.err_reason"));
    try {
      await fetchApi(`/trainer/attendance/${selected}/override`, { method: "POST", body: JSON.stringify({ ...editing, reason: editing.reason.trim() }) });
      setEditing(null);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("attendance.save_failed"));
    }
  };

  return (
    <RoleGuard allowedRoles={["trainer"]}>
      <AppShell pageTitle={t("attendance.title")}>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 max-w-6xl">
          <section className="bg-white rounded-xl border border-[#E2E8F0] p-3 space-y-1 h-fit" data-testid="att-sessions">
            {error && <p className="text-xs text-red-600" role="alert" data-testid="att-error">{error}</p>}
            {sessions?.length === 0 && <p className="text-xs text-[#64748B]">{t("attendance.no_sessions")}</p>}
            {sessions?.map((s) => (
              <button key={s.id} type="button" onClick={() => setSelected(s.id)} data-testid="att-session" aria-pressed={selected === s.id}
                className={`w-full text-left rounded-lg px-2.5 py-2 text-xs ${selected === s.id ? "bg-[#EFF6FF] ring-1 ring-[#2B5CD0]" : "hover:bg-[#F8FAFC]"}`}>
                <div className="font-bold text-[#0F1F3A] truncate">{s.title}</div>
                <div className="text-[11px] text-[#64748B]">{when(s.start)} · {s.batch} · {s.present}/{s.students}{s.checkin_open ? ` · ${t("attendance.checkin_open")}` : ""}</div>
              </button>
            ))}
          </section>

          <section className="lg:col-span-2 space-y-3">
            {detail && (
              <>
                <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h2 className="text-sm font-black text-[#0F1F3A]" data-testid="att-title">{detail.session.title}</h2>
                    <p className="text-[11px] text-[#64748B]">{when(detail.session.start)} · {detail.session.present} {t("attendance.present")} · {detail.session.absent} {t("attendance.absent")} · {detail.session.unmarked} {t("attendance.unmarked")}</p>
                    <p className="text-[11px] text-[#64748B]">{t("attendance.rule_note")}</p>
                  </div>
                  {detail.session.checkin_open && (code ? (
                    <div className="text-center" data-testid="checkin-code-panel">
                      <div className="text-[11px] text-[#64748B]">{t("attendance.code_label")}</div>
                      <div className="text-3xl font-black tracking-[0.3em] text-[#2B5CD0]" data-testid="checkin-code">{code.code}</div>
                      <div className="text-[10px] text-[#64748B]">{t("attendance.code_help")}</div>
                    </div>
                  ) : (
                    <button type="button" onClick={showCode} data-testid="checkin-show" className="px-3 py-1.5 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg inline-flex items-center gap-1"><KeyRound className="w-3.5 h-3.5" />{t("attendance.show_code")}</button>
                  ))}
                </div>
                <div className="bg-white rounded-xl border border-[#E2E8F0] overflow-x-auto">
                  <table className="w-full text-xs" data-testid="att-roster">
                    <thead className="bg-[#F8FAFC] text-[#64748B]">
                      <tr>
                        <th className="text-left font-semibold px-3 py-2">{t("attendance.student")}</th>
                        <th className="text-left font-semibold px-3 py-2">{t("attendance.status")}</th>
                        <th className="text-left font-semibold px-3 py-2">{t("attendance.minutes")}</th>
                        <th className="text-left font-semibold px-3 py-2">{t("attendance.source")}</th>
                        <th className="px-3 py-2" />
                      </tr>
                    </thead>
                    <tbody>
                      {detail.roster.map((r) => (
                        <React.Fragment key={r.student_id}>
                          <tr className="border-t border-[#F1F5F9]" data-testid="att-row">
                            <td className="px-3 py-2"><span className="font-bold">{r.name}</span><div className="text-[10px] text-[#64748B]">{r.register_no}</div></td>
                            <td className="px-3 py-2">{r.status ? <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${STATUS[r.status] || ""}`} data-testid="att-status">{t(`attendance.status_${r.status}`)}</span> : <span className="text-[#94A3B8]">—</span>}</td>
                            <td className="px-3 py-2">{r.minutes_present}</td>
                            <td className="px-3 py-2 text-[11px] text-[#64748B]">{r.source ? t(`attendance.source_${r.source}`) : ""}{r.override_reason ? ` · ${r.override_reason}` : ""}</td>
                            <td className="px-3 py-2 text-right">
                              <button type="button" onClick={() => setEditing({ student_id: r.student_id, status: r.status === "Present" ? "Absent" : "Present", reason: "" })}
                                data-testid="att-override" className="text-[11px] text-[#2B5CD0] font-bold">{t("attendance.override")}</button>
                            </td>
                          </tr>
                          {editing?.student_id === r.student_id && (
                            <tr className="bg-[#F8FAFC]"><td colSpan={5} className="px-3 py-2">
                              <div className="flex flex-wrap gap-2 items-center">
                                <select value={editing.status} onChange={(e) => setEditing({ ...editing, status: e.target.value })} data-testid="override-status" className="px-2 py-1 border rounded text-xs" aria-label={t("attendance.status")}>
                                  <option value="Present">{t("attendance.status_Present")}</option>
                                  <option value="Absent">{t("attendance.status_Absent")}</option>
                                </select>
                                <input value={editing.reason} onChange={(e) => setEditing({ ...editing, reason: e.target.value })} placeholder={t("attendance.reason")} data-testid="override-reason" className="flex-1 min-w-[180px] px-2 py-1 border rounded text-xs" />
                                <button type="button" onClick={saveOverride} data-testid="override-save" className="px-2.5 py-1 bg-[#2B5CD0] text-white font-bold rounded text-xs">{t("attendance.save")}</button>
                                <button type="button" onClick={() => setEditing(null)} className="text-xs text-[#64748B]">{t("attendance.cancel")}</button>
                              </div>
                            </td></tr>
                          )}
                        </React.Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </section>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
