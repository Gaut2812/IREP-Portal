"use client";

/** Shared invoice pieces for the super admin's and the college's billing pages (S16). */
import React from "react";
import { useLanguage } from "@/lib/LanguageContext";

export interface InvoiceLine { kind: string; label: string; quantity: number; unit_paise: number; amount_paise: number }
export interface Invoice {
  id: string; college_id: string; college?: string | null; period: string; number: string | null; status: "draft" | "issued" | "paid" | "void";
  students: number; subtotal_paise: number; credit_paise: number; gst_pct: number; gst_paise: number; total_paise: number;
  usage: Record<string, { used: number; quota: number | null }>; issued_at: string | null; due_on: string | null; paid_at: string | null;
  payment_ref: string | null; void_reason: string | null; has_pdf: boolean; lines: InvoiceLine[];
}

export const STATUS_STYLE: Record<string, string> = {
  draft: "bg-[#F1F5F9] text-[#475569]", issued: "bg-[#DBEAFE] text-[#1E40AF]", paid: "bg-[#DCFCE7] text-[#166534]", void: "bg-[#FEE2E2] text-[#991B1B]",
};

/** Paise to "₹12,345.67" (Indian grouping). */
export function inr(paise: number): string {
  const sign = paise < 0 ? "-" : "";
  return `${sign}₹${(Math.abs(paise) / 100).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function InvoiceLines({ inv }: { inv: Invoice }) {
  const { t } = useLanguage();
  return (
    <div className="space-y-2" data-testid="invoice-lines">
      <table className="w-full text-xs">
        <tbody>
          {inv.lines.map((l, i) => (
            <tr key={i} className="border-b border-[#F1F5F9]" data-testid={`line-${l.kind}`}>
              <td className="py-1 pr-2">{l.label}</td>
              <td className={`py-1 text-right ${l.amount_paise < 0 ? "text-[#166534]" : ""}`}>{inr(l.amount_paise)}</td>
            </tr>
          ))}
          <tr><td className="py-1 pr-2 text-[#64748B]">{t("billing.subtotal")}</td><td className="py-1 text-right">{inr(inv.subtotal_paise)}</td></tr>
          {inv.credit_paise > 0 && <tr><td className="py-1 pr-2 text-[#64748B]">{t("billing.credit_applied")}</td><td className="py-1 text-right text-[#166534]">-{inr(inv.credit_paise)}</td></tr>}
          <tr><td className="py-1 pr-2 text-[#64748B]">GST {inv.gst_pct}%</td><td className="py-1 text-right">{inr(inv.gst_paise)}</td></tr>
          <tr className="font-black"><td className="py-1 pr-2">{t("billing.total")}</td><td className="py-1 text-right" data-testid="lines-total">{inr(inv.total_paise)}</td></tr>
        </tbody>
      </table>
      <p className="text-[11px] text-[#64748B]" data-testid="invoice-usage">{t("billing.usage")}:{" "}
        {Object.entries(inv.usage).map(([k, v]) => `${t(`billing.m_${k}`)} ${v.used}${v.quota !== null ? ` / ${v.quota}` : ""}`).join(" · ")}</p>
      {inv.due_on && <p className="text-[11px] text-[#64748B]">{t("billing.due")} {inv.due_on}{inv.payment_ref ? ` · ${t("billing.paid_ref")} ${inv.payment_ref}` : ""}</p>}
      {inv.void_reason && <p className="text-[11px] text-[#991B1B]">{t("billing.void_reason")}: {inv.void_reason}</p>}
    </div>
  );
}
