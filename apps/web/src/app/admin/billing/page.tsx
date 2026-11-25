"use client";

/** S16 · Billing (super admin): generate the month's drafts, issue, mark paid or void, add credits.
 *  Spec: docs/screens/47-16-billing-and-dpdp.md */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { downloadWithAuth } from "@/components/admin/AuditTabs";
import { useLanguage } from "@/lib/LanguageContext";
import { API_BASE, ApiError, authHeaders, fetchApi } from "@/lib/api";
import { inr, Invoice, InvoiceLines, STATUS_STYLE } from "@/components/billing/InvoiceParts";

interface Credit { id: string; college: string | null; amount_paise: number; used_paise: number; reason: string; created_at: string }
interface Data { period: string; invoices: Invoice[]; totals_paise: Record<string, number>; credits: Credit[]; colleges: { id: string; name: string }[] }

const thisMonth = () => new Date().toISOString().slice(0, 7);

export default function AdminBillingPage() {
  const { t, language } = useLanguage();
  const [period, setPeriod] = useState(thisMonth());
  const [data, setData] = useState<Data | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [credit, setCredit] = useState({ college_id: "", amount_inr: "", reason: "" });

  const load = useCallback(async () => {
    try { setData(await fetchApi<Data>(`/admin/billing?period=${period}&lang=${language}`)); setError(""); }
    catch (e) {
      if (e instanceof ApiError && e.status === 403) setForbidden(true);
      else setError(e instanceof ApiError ? String(e.detail) : t("billing.load_failed"));
    }
  }, [period, language, t]);
  useEffect(() => { load(); }, [load]);

  const run = async (fn: () => Promise<unknown>, done: string) => {
    setBusy(true); setError(""); setMsg("");
    try { await fn(); await load(); setMsg(done); }
    catch (e) { setError(e instanceof ApiError ? String(e.detail) : t("billing.action_failed")); }
    finally { setBusy(false); }
  };
  const post = (path: string, body?: object) => fetchApi(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });

  const addCredit = (e: React.FormEvent) => {
    e.preventDefault();
    const amount = Number(credit.amount_inr);
    if (!credit.college_id || !(amount > 0) || credit.reason.trim().length < 5) { setError(t("billing.err_credit")); return; }
    run(() => post("/admin/billing/credits", { college_id: credit.college_id, amount_inr: amount, reason: credit.reason.trim() })
      .then(() => setCredit({ college_id: "", amount_inr: "", reason: "" })), t("billing.credit_added"));
  };

  const card = "bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-3";
  const field = "px-2.5 py-1.5 border border-[#CBD5E1] rounded-lg text-xs";

  return (
    <RoleGuard allowedRoles={["admin"]}>
      <AppShell pageTitle={t("billing.title")}>
        <div className="space-y-4 max-w-6xl">
          {forbidden ? (
            <div className={card} data-testid="billing-forbidden"><p className="text-sm font-bold">{t("billing.super_only")}</p></div>
          ) : (
            <>
              <p className="text-xs text-[#64748B]">{t("billing.help")}</p>
              <div className="flex flex-wrap items-center gap-2">
                <input type="month" value={period} onChange={(e) => setPeriod(e.target.value)} aria-label={t("billing.period")} data-testid="billing-period" className={field} />
                <button type="button" disabled={busy} data-testid="billing-generate" className="px-3.5 py-1.5 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg disabled:opacity-50"
                  onClick={() => run(() => post("/admin/billing/generate", { period }), t("billing.generated"))}>{t("billing.generate")}</button>
                {data && <span className="text-[11px] text-[#64748B]" data-testid="billing-totals">
                  {t("billing.status_draft")} {inr(data.totals_paise.draft || 0)} · {t("billing.status_issued")} {inr(data.totals_paise.issued || 0)} · {t("billing.status_paid")} {inr(data.totals_paise.paid || 0)}</span>}
              </div>
              {error && <p className="text-xs text-red-600" role="alert" data-testid="billing-error">{error}</p>}
              {msg && <p className="text-xs text-[#166534]" role="status" data-testid="billing-msg">{msg}</p>}

              <section className={card} data-testid="billing-invoices">
                {data && data.invoices.length === 0 && <p className="text-xs text-[#64748B]">{t("billing.none")}</p>}
                <ul className="space-y-2">
                  {data?.invoices.map((inv) => (
                    <li key={inv.id} className="border border-[#F1F5F9] rounded-lg p-2.5 text-xs space-y-2" data-testid={`invoice-${inv.college_id}`}>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <button type="button" onClick={() => setOpen(open === inv.id ? null : inv.id)} className="text-left">
                          <b className="text-[#0F1F3A]">{inv.college}</b> · {inv.number || t("billing.no_number")} · {inv.students} {t("billing.students")}
                          {" · "}<b data-testid="invoice-total">{inr(inv.total_paise)}</b>
                        </button>
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${STATUS_STYLE[inv.status]}`} data-testid="invoice-status">{t(`billing.status_${inv.status}`)}</span>
                          {inv.status === "draft" && <button type="button" disabled={busy} data-testid="invoice-issue" className="px-2.5 py-1 bg-[#2B5CD0] text-white rounded-lg font-bold"
                            onClick={() => { if (window.confirm(t("billing.confirm_issue"))) run(() => post(`/admin/billing/invoices/${inv.id}/issue`), t("billing.issued")); }}>{t("billing.issue")}</button>}
                          {inv.status === "issued" && <button type="button" disabled={busy} data-testid="invoice-pay" className="px-2.5 py-1 bg-[#166534] text-white rounded-lg font-bold"
                            onClick={() => { const ref = window.prompt(t("billing.payment_ref")); if (ref && ref.trim().length >= 3) run(() => post(`/admin/billing/invoices/${inv.id}/pay`, { reference: ref.trim() }), t("billing.marked_paid")); }}>{t("billing.mark_paid")}</button>}
                          {(inv.status === "draft" || inv.status === "issued") && <button type="button" disabled={busy} data-testid="invoice-void" className="px-2.5 py-1 border border-[#CBD5E1] rounded-lg font-bold"
                            onClick={() => { const r = window.prompt(t("billing.void_reason")); if (r && r.trim().length >= 5) run(() => post(`/admin/billing/invoices/${inv.id}/void`, { reason: r.trim() }), t("billing.voided")); }}>{t("billing.void")}</button>}
                          {inv.has_pdf && <button type="button" data-testid="invoice-pdf" className="px-2.5 py-1 border border-[#CBD5E1] rounded-lg font-bold"
                            onClick={() => downloadWithAuth(`${API_BASE}/admin/billing/invoices/${inv.id}/pdf`, authHeaders(), `${(inv.number || inv.id).replace(/\//g, "-")}.pdf`).catch(() => setError(t("billing.download_failed")))}>PDF</button>}
                        </div>
                      </div>
                      {open === inv.id && <InvoiceLines inv={inv} />}
                    </li>
                  ))}
                </ul>
              </section>

              <section className={card} data-testid="billing-credits">
                <h2 className="text-sm font-black text-[#0F1F3A]">{t("billing.credits")}</h2>
                <form onSubmit={addCredit} noValidate className="flex flex-wrap gap-2 items-end" data-testid="credit-form">
                  <select value={credit.college_id} onChange={(e) => setCredit({ ...credit, college_id: e.target.value })} aria-label={t("billing.college")} data-testid="credit-college" className={field}>
                    <option value="">{t("billing.choose_college")}</option>
                    {data?.colleges.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                  <input type="number" min={1} value={credit.amount_inr} onChange={(e) => setCredit({ ...credit, amount_inr: e.target.value })} placeholder={t("billing.amount_inr")}
                    aria-label={t("billing.amount_inr")} data-testid="credit-amount" className={`${field} w-32`} />
                  <input value={credit.reason} onChange={(e) => setCredit({ ...credit, reason: e.target.value })} placeholder={t("billing.reason")}
                    aria-label={t("billing.reason")} data-testid="credit-reason" className={`${field} flex-1 min-w-[200px]`} />
                  <button type="submit" disabled={busy} data-testid="credit-add" className="px-3.5 py-1.5 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg disabled:opacity-50">{t("billing.add_credit")}</button>
                </form>
                <ul className="space-y-1 text-xs">
                  {data?.credits.map((c) => (
                    <li key={c.id} className="flex justify-between border-b border-[#F1F5F9] py-1" data-testid="credit-row">
                      <span>{c.college} · {c.reason}</span>
                      <span>{inr(c.amount_paise)} · {t("billing.used")} {inr(c.used_paise)}</span>
                    </li>
                  ))}
                </ul>
              </section>
            </>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
