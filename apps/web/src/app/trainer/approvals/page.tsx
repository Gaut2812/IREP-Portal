"use client";

/** Screen 43 · Approvals (trainer): one queue for leave, Cyber Range access and certificate proofs (links L08, L09, L10). */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi, fetchBlob } from "@/lib/api";
import { Award, CalendarDays, ShieldAlert } from "lucide-react";

interface Item {
  type: "leave" | "lab_access" | "certificate"; id: string; student_id: string; student_name: string; batch: string; status: string;
  detail: { start_date?: string; end_date?: string; reason?: string; requested_by?: string; lab_name?: string; aup_accepted?: boolean; title?: string; issuer?: string; issued_on?: string | null; credential_id?: string | null };
  decision_note: string | null; requested_at: string | null;
}

export default function ApprovalsPage() {
  const { t } = useLanguage();
  const [status, setStatus] = useState("pending");
  const [items, setItems] = useState<Item[] | null>(null);
  const [denying, setDenying] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setItems((await fetchApi<{ items: Item[] }>(`/trainer/approvals?status=${status}`)).items);
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("approvals.load_failed"));
    }
  }, [status, t]);

  useEffect(() => { load(); }, [load]);

  const decide = async (it: Item, decision: "approve" | "deny") => {
    if (decision === "deny" && note.trim().length < 3) return setError(t("approvals.err_note"));
    setBusy(true);
    setError("");
    try {
      const url = it.type === "leave" ? `/trainer/approvals/leave/${it.id}` : it.type === "certificate" ? `/trainer/approvals/certificates/${it.id}` : `/trainer/approvals/labs/${it.id}`;
      const body = it.type === "lab_access" ? { decision, reason: note.trim() || null } : { decision, note: note.trim() || null };
      await fetchApi(url, { method: "POST", body: JSON.stringify(body) });
      setDenying(null);
      setNote("");
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("approvals.save_failed"));
    } finally {
      setBusy(false);
    }
  };

  const viewProof = async (it: Item) => {
    try { window.open(URL.createObjectURL(await fetchBlob(`/trainer/certificates/${it.id}/proof`)), "_blank", "noopener"); }
    catch { setError(t("approvals.load_failed")); }
  };

  return (
    <RoleGuard allowedRoles={["trainer"]}>
      <AppShell pageTitle={t("approvals.title")}>
        <div className="p-4 md:p-6 space-y-3 max-w-4xl">
          <div className="flex gap-2" role="tablist">
            {["pending", "decided"].map((s) => (
              <button key={s} type="button" role="tab" aria-selected={status === s} onClick={() => setStatus(s)} data-testid={`tab-${s}`}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold ${status === s ? "bg-[#2B5CD0] text-white" : "border border-[#CBD5E1]"}`}>{t(`approvals.tab_${s}`)}</button>
            ))}
          </div>
          <p className="text-[11px] text-[#64748B]">{t("approvals.rule")}</p>
          {error && <p className="text-xs text-red-600" role="alert" data-testid="approvals-error">{error}</p>}
          {items?.length === 0 && <div className="bg-white rounded-xl border border-dashed border-[#CBD5E1] p-6 text-center text-xs text-[#64748B]" data-testid="approvals-empty">{t("approvals.empty")}</div>}
          <ul className="space-y-2">
            {items?.map((it) => (
              <li key={`${it.type}-${it.id}`} className="bg-white rounded-xl border border-[#E2E8F0] p-3 text-xs space-y-1.5" data-testid={`approval-${it.type}`}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="font-bold text-[#0F1F3A] flex items-center gap-1.5">
                      {it.type === "leave" ? <CalendarDays className="w-3.5 h-3.5 text-[#2B5CD0]" /> : it.type === "certificate" ? <Award className="w-3.5 h-3.5 text-[#166534]" /> : <ShieldAlert className="w-3.5 h-3.5 text-[#B45309]" />}
                      {t(`approvals.type_${it.type}`)} · {it.student_name} <span className="font-normal text-[#64748B]">({it.batch})</span>
                    </div>
                    {it.type === "leave" ? (
                      <div className="text-[#475569]">{it.detail.start_date} → {it.detail.end_date} · {it.detail.reason} · {t("approvals.by")} {it.detail.requested_by}</div>
                    ) : it.type === "certificate" ? (
                      <div className="text-[#475569]">
                        {it.detail.title} · {it.detail.issuer}{it.detail.issued_on ? ` · ${it.detail.issued_on}` : ""}{it.detail.credential_id ? ` · ${it.detail.credential_id}` : ""}
                        <button type="button" onClick={() => viewProof(it)} data-testid="view-proof" className="ml-2 text-[#2B5CD0] font-bold underline">{t("approvals.view_proof")}</button>
                      </div>
                    ) : (
                      <div className="text-[#475569]">{it.detail.lab_name} · {it.detail.aup_accepted ? t("approvals.aup_yes") : t("approvals.aup_no")}</div>
                    )}
                    {it.decision_note && <div className="text-[11px] text-[#64748B]">{it.decision_note}</div>}
                  </div>
                  <span className="text-[11px] font-bold text-[#64748B]" data-testid="approval-status">{t(`approvals.status_${it.status}`)}</span>
                </div>
                {it.status === "pending" && (denying === it.id ? (
                  <div className="flex gap-2">
                    <input value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("approvals.note")} data-testid="deny-note" className="flex-1 px-2 py-1 border rounded text-xs" />
                    <button type="button" disabled={busy} onClick={() => decide(it, "deny")} data-testid="deny-confirm" className="px-2.5 py-1 bg-[#DC2626] text-white font-bold rounded">{t("approvals.deny")}</button>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <button type="button" disabled={busy} onClick={() => decide(it, "approve")} data-testid="approve" className="px-3 py-1 bg-[#2B5CD0] text-white font-bold rounded">{t("approvals.approve")}</button>
                    <button type="button" disabled={busy} onClick={() => { setDenying(it.id); setNote(""); }} data-testid="deny" className="px-3 py-1 border border-[#CBD5E1] font-bold rounded">{t("approvals.deny")}</button>
                  </div>
                ))}
              </li>
            ))}
          </ul>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
