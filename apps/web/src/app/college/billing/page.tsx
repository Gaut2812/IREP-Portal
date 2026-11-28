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

  const card = "bg-white rounded-card border border-line p-4 space-y-3";
  return (
    <RoleGuard allowedRoles={["college"]}>
      <AppShell pageTitle={t("billing.title")} pageSubtitle={t("billing.college_help")}>
        <div className="space-y-6 max-w-5xl">
          {error && <p className="text-xs text-red-600" role="alert">{error}</p>}
          {data && (
            <section className="grid sm:grid-cols-2 gap-3" data-testid="billing-summary">
              <div className={card}><div className="text-caption text-muted">{t("billing.outstanding")}</div>
                <div className="text-2xl font-semibold text-ink" data-testid="billing-outstanding">{inr(data.outstanding_paise)}</div></div>
              <div className={card}><div className="text-caption text-muted">{t("billing.credit_left")}</div>
                <div className="text-2xl font-semibold text-success" data-testid="billing-credit">{inr(data.credit_available_paise)}</div></div>
            </section>
          )}
          <section className={card} data-testid="college-invoices">
            {data && data.invoices.length === 0 && <p className="text-xs text-muted">{t("billing.none_college")}</p>}
            <ul className="space-y-3">
              {data?.invoices.map((inv) => (
                <li key={inv.id} className="border border-line-soft rounded-tile p-3 text-xs space-y-2" data-testid={`college-invoice-${inv.number}`}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span><b className="text-ink">{inv.number}</b> · {inv.period}</span>
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded-full text-caption font-semibold ${STATUS_STYLE[inv.status]}`}>{t(`billing.status_${inv.status}`)}</span>
                      {inv.has_pdf && <button type="button" data-testid="college-invoice-pdf" className="px-2.5 py-1 border border-line-strong rounded-tile font-semibold"
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
