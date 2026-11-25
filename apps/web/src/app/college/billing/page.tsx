"use client";

/** S16 · Billing (college admin): the college's issued invoices, what is outstanding, credit left,
 *  and the PDFs. Spec: docs/screens/47-16-billing-and-dpdp.md */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { downloadWithAuth } from "@/components/admin/AuditTabs";
import { useLanguage } from "@/lib/LanguageContext";
import { API_BASE, ApiError, authHeaders, fetchApi } from "@/lib/api";
import { inr, Invoice, InvoiceLines, STATUS_STYLE } from "@/components/billing/InvoiceParts";

interface Data { invoices: Invoice[]; outstanding_paise: number; credit_available_paise: number }

export default function CollegeBillingPage() {
  const { t, language } = useLanguage();
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { setData(await fetchApi<Data>(`/college/billing?lang=${language}`)); setError(""); }
    catch (e) { setError(e instanceof ApiError ? String(e.detail) : t("billing.load_failed")); }
  }, [language, t]);
  useEffect(() => { load(); }, [load]);

  const card = "bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-3";
  return (
    <RoleGuard allowedRoles={["college"]}>
      <AppShell pageTitle={t("billing.title")}>
        <div className="space-y-4 max-w-5xl">
          <p className="text-xs text-[#64748B]">{t("billing.college_help")}</p>
          {error && <p className="text-xs text-red-600" role="alert">{error}</p>}
          {data && (
            <section className="grid sm:grid-cols-2 gap-3" data-testid="billing-summary">
              <div className={card}><div className="text-[11px] text-[#64748B]">{t("billing.outstanding")}</div>
                <div className="text-2xl font-black text-[#0F1F3A]" data-testid="billing-outstanding">{inr(data.outstanding_paise)}</div></div>
              <div className={card}><div className="text-[11px] text-[#64748B]">{t("billing.credit_left")}</div>
                <div className="text-2xl font-black text-[#166534]" data-testid="billing-credit">{inr(data.credit_available_paise)}</div></div>
            </section>
          )}
          <section className={card} data-testid="college-invoices">
            {data && data.invoices.length === 0 && <p className="text-xs text-[#64748B]">{t("billing.none_college")}</p>}
            <ul className="space-y-3">
              {data?.invoices.map((inv) => (
                <li key={inv.id} className="border border-[#F1F5F9] rounded-lg p-3 text-xs space-y-2" data-testid={`college-invoice-${inv.number}`}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span><b className="text-[#0F1F3A]">{inv.number}</b> · {inv.period}</span>
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${STATUS_STYLE[inv.status]}`}>{t(`billing.status_${inv.status}`)}</span>
                      {inv.has_pdf && <button type="button" data-testid="college-invoice-pdf" className="px-2.5 py-1 border border-[#CBD5E1] rounded-lg font-bold"
                        onClick={() => downloadWithAuth(`${API_BASE}/college/billing/invoices/${inv.id}/pdf`, authHeaders(), `${(inv.number || inv.id).replace(/\//g, "-")}.pdf`).catch(() => setError(t("billing.download_failed")))}>PDF</button>}
                    </div>
                  </div>
                  <InvoiceLines inv={inv} />
                </li>
              ))}
            </ul>
          </section>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
