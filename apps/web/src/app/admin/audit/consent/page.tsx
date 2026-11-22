"use client";

/** Screen 48 · consent records per college (logged support view). */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { AuditTabs } from "@/components/admin/AuditTabs";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";

interface Item { student_id: string; name: string; register_no: string; batch: string; consents: Record<string, string | null> }
interface History { purpose: string; status: string; method: string; by: string; at: string }
const CHIP: Record<string, string> = { granted: "bg-[#DCFCE7] text-[#166534]", withdrawn: "bg-[#FEE2E2] text-[#991B1B]", missing: "bg-[#F1F5F9] text-[#64748B]" };

export default function ConsentPage() {
  const { t } = useLanguage();
  const [colleges, setColleges] = useState<{ id: string; name: string }[]>([]);
  const [collegeId, setCollegeId] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{ total: number; purposes: string[]; items: Item[] } | null>(null);
  const [history, setHistory] = useState<{ name: string; rows: History[] } | null>(null);
  const [error, setError] = useState("");
  const [needsSession, setNeedsSession] = useState(false);

  useEffect(() => {
    fetchApi<{ colleges: { id: string; name: string }[] }>("/admin/colleges")
      .then((r) => { setColleges(r.colleges); if (r.colleges[0]) setCollegeId((c) => c || r.colleges[0].id); })
      .catch(() => setError(t("admin_audit.load_failed")));
  }, [t]);

  const load = useCallback(async () => {
    if (!collegeId) return;
    try {
      setData(await fetchApi(`/admin/consent?college_id=${encodeURIComponent(collegeId)}&page=${page}&page_size=25`));
      setError(""); setNeedsSession(false);
    } catch (e) {
      // student data: IREP staff need an open support session for this college
      if (e instanceof ApiError && e.status === 403) { setData(null); setNeedsSession(true); setError(""); }
      else setError(e instanceof ApiError ? e.detail : t("admin_audit.load_failed"));
    }
  }, [collegeId, page, t]);

  useEffect(() => { load(); }, [load]);

  const showHistory = async (it: Item) => {
    try {
      const r = await fetchApi<{ history: History[] }>(`/admin/consent/${it.student_id}/history`);
      setHistory({ name: it.name, rows: r.history });
    } catch {
      setError(t("admin_audit.load_failed"));
    }
  };

  return (
    <RoleGuard allowedRoles={["admin"]}>
      <AppShell pageTitle={t("admin_audit.title")}>
        <div className="p-4 md:p-6 space-y-4 max-w-6xl">
          <AuditTabs />
          <div className="flex items-center gap-2 flex-wrap">
            <label className="text-xs font-bold text-[#0F1F3A]" htmlFor="consent-college">{t("admin_audit.college")}</label>
            <select id="consent-college" data-testid="consent-college" value={collegeId} onChange={(e) => { setPage(1); setCollegeId(e.target.value); }}
              className="px-2.5 py-1.5 border border-[#E2E8F0] rounded-lg text-xs bg-white">
              {colleges.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <span className="text-[11px] text-[#64748B]">{t("admin_audit.support_logged")}</span>
          </div>
          {error && <p className="text-xs text-red-600" role="alert">{error}</p>}
          {needsSession && (
            <p className="text-xs text-[#92400E] bg-[#FFFBEB] border border-[#FDE68A] rounded-lg p-3" role="status" data-testid="needs-support-session">
              {t("admin_audit.needs_session")}
            </p>
          )}
          {data && (
            <div className="bg-white rounded-xl border border-[#E2E8F0] overflow-x-auto">
              <table className="w-full text-xs" data-testid="consent-table">
                <thead className="bg-[#F8FAFC] text-[#64748B]">
                  <tr>
                    <th className="text-left font-semibold px-3 py-2">{t("admin_audit.student")}</th>
                    {data.purposes.map((p) => <th key={p} className="text-left font-semibold px-3 py-2">{t(`admin_audit.purpose_${p}`)}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((it) => (
                    <tr key={it.student_id} className="border-t border-[#F1F5F9]">
                      <td className="px-3 py-2">
                        <button type="button" onClick={() => showHistory(it)} className="font-bold text-[#2B5CD0] hover:underline text-left">{it.name}</button>
                        <div className="text-[10px] text-[#64748B]">{it.register_no} · {it.batch}</div>
                      </td>
                      {data.purposes.map((p) => {
                        const s = it.consents[p] || "missing";
                        return <td key={p} className="px-3 py-2"><span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${CHIP[s]}`}>{t(`admin_audit.consent_${s}`)}</span></td>;
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="flex items-center justify-between px-3 py-2 border-t border-[#F1F5F9] text-[11px] text-[#64748B]">
                <span>{data.total} {t("admin_audit.students")}</span>
                <div className="flex gap-2 items-center">
                  <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)} className="px-2 py-1 border rounded disabled:opacity-40">‹</button>
                  <span>{page}</span>
                  <button type="button" disabled={page * 25 >= data.total} onClick={() => setPage(page + 1)} className="px-2 py-1 border rounded disabled:opacity-40">›</button>
                </div>
              </div>
            </div>
          )}
          {history && (
            <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-2" data-testid="consent-history">
              <div className="flex justify-between items-center">
                <h2 className="text-sm font-black text-[#0F1F3A]">{t("admin_audit.history_for")} {history.name}</h2>
                <button type="button" onClick={() => setHistory(null)} className="text-xs text-[#2B5CD0] font-bold">{t("admin_audit.close")}</button>
              </div>
              {history.rows.length === 0 && <p className="text-xs text-[#64748B]">{t("admin_audit.no_history")}</p>}
              <ul className="text-xs space-y-1">
                {history.rows.map((h, i) => (
                  <li key={i}>{h.at.slice(0, 16).replace("T", " ")} · {t(`admin_audit.purpose_${h.purpose}`)} · <b>{t(`admin_audit.consent_${h.status}`)}</b> · {h.method}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
