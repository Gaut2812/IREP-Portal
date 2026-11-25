"use client";

/** Screen 48 · export and deletion requests (L27: raised from college settings). */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { AuditTabs, downloadWithAuth } from "@/components/admin/AuditTabs";
import { useLanguage } from "@/lib/LanguageContext";
import { API_BASE, ApiError, authHeaders, fetchApi } from "@/lib/api";

interface Req {
  id: string; kind: "export" | "deletion"; college_id: string; student_id: string; student_name: string | null; reason: string;
  status: "received" | "in_progress" | "completed" | "rejected"; due_on: string; days_left: number | null; overdue: boolean;
  has_export: boolean; decision_note: string | null;
  can_decide?: boolean;
  name_hidden?: boolean;
}
const STATUS: Record<string, string> = {
  received: "bg-[#FEF3C7] text-[#92400E]", in_progress: "bg-[#DBEAFE] text-[#1E40AF]",
  completed: "bg-[#DCFCE7] text-[#166534]", rejected: "bg-[#F1F5F9] text-[#475569]",
};

export default function DataRequestsPage() {
  const { t } = useLanguage();
  const [items, setItems] = useState<Req[] | null>(null);
  const [rejecting, setRejecting] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setItems((await fetchApi<{ items: Req[] }>("/admin/data-requests")).items);
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("admin_audit.load_failed"));
    }
  }, [t]);

  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("admin_audit.action_failed"));
    } finally {
      setBusy(false);
    }
  };

  const complete = (r: Req) => act(() => fetchApi(`/admin/data-requests/${r.id}/complete`, { method: "POST" }));
  const reject = (r: Req) => {
    if (reason.trim().length < 5) { setError(t("admin_audit.err_reason")); return; }
    act(async () => {
      await fetchApi(`/admin/data-requests/${r.id}/reject`, { method: "POST", body: JSON.stringify({ reason: reason.trim() }) });
      setRejecting(null);
      setReason("");
    });
  };
  const download = (r: Req) => downloadWithAuth(`${API_BASE}/admin/data-requests/${r.id}/export`, authHeaders(), `irep-export-${r.student_id}.json`)
    .catch(() => setError(r.name_hidden ? t("admin_audit.needs_session") : t("admin_audit.download_failed")));

  return (
    <RoleGuard allowedRoles={["admin"]}>
      <AppShell pageTitle={t("admin_audit.title")}>
        <div className="space-y-4 max-w-6xl">
          <AuditTabs />
          <p className="text-[11px] text-[#64748B]">{t("admin_audit.requests_note")}</p>
          {error && <p className="text-xs text-red-600" role="alert" data-testid="requests-error">{error}</p>}
          {items && items.length === 0 && (
            <div className="bg-white rounded-xl border border-dashed border-[#CBD5E1] p-8 text-center text-xs text-[#64748B]">{t("admin_audit.no_requests")}</div>
          )}
          <ul className="space-y-2">
            {items?.map((r) => {
              const open = r.status === "received" || r.status === "in_progress";
              return (
                <li key={r.id} className="bg-white rounded-xl border border-[#E2E8F0] p-3 text-xs space-y-2" data-testid={`request-${r.id}`}>
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <div>
                      <span className="font-bold text-[#0F1F3A]">{t(`admin_audit.kind_${r.kind}`)}</span> · {r.name_hidden ? <span data-testid="request-name-hidden">{t("admin_audit.name_hidden")} ({r.student_id})</span> : (r.student_name || r.student_id)}
                      <span className="text-[#64748B]"> · {r.college_id}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {open && r.days_left !== null && (
                        <span className={r.overdue ? "text-[#DC2626] font-bold" : "text-[#64748B]"} data-testid="request-due">
                          {r.overdue ? t("admin_audit.overdue") : `${t("admin_audit.due_in")} ${r.days_left} ${t("admin_audit.days")}`}
                        </span>
                      )}
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${STATUS[r.status]}`} data-testid="request-status">{t(`admin_audit.status_${r.status}`)}</span>
                    </div>
                  </div>
                  <p className="text-[#475569]">{r.reason}</p>
                  {r.decision_note && <p className="text-[#64748B]">{t("admin_audit.decision")}: {r.decision_note}</p>}
                  <div className="flex gap-2 flex-wrap">
                    {open && !r.can_decide && (
                      <span className="text-[11px] text-[#64748B]" data-testid="request-super-only">{t("admin_audit.super_only_deletion")}</span>
                    )}
                    {r.status === "received" && r.can_decide && (
                      <button type="button" disabled={busy} onClick={() => complete(r)} data-testid="request-complete"
                        className="px-3 py-1.5 bg-[#2B5CD0] text-white font-bold rounded-lg disabled:opacity-50">
                        {r.kind === "export" ? t("admin_audit.build_export") : t("admin_audit.anonymise")}
                      </button>
                    )}
                    {open && r.can_decide && rejecting !== r.id && (
                      <button type="button" disabled={busy} onClick={() => { setRejecting(r.id); setReason(""); }} data-testid="request-reject"
                        className="px-3 py-1.5 border border-[#CBD5E1] font-bold rounded-lg">{t("admin_audit.reject")}</button>
                    )}
                    {r.has_export && (
                      <button type="button" onClick={() => download(r)} data-testid="request-download" className="px-3 py-1.5 border border-[#CBD5E1] font-bold rounded-lg">
                        {t("admin_audit.download")}
                      </button>
                    )}
                  </div>
                  {rejecting === r.id && (
                    <div className="flex gap-2 items-center">
                      <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t("admin_audit.reject_reason")}
                        data-testid="reject-reason" className="flex-1 px-2.5 py-1.5 border border-[#E2E8F0] rounded-lg" />
                      <button type="button" disabled={busy} onClick={() => reject(r)} data-testid="reject-confirm"
                        className="px-3 py-1.5 bg-[#DC2626] text-white font-bold rounded-lg disabled:opacity-50">{t("admin_audit.reject")}</button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
