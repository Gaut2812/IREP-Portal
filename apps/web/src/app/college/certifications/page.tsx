"use client";

/** Screen 28 · Certifications (college): counts, proof status and vouchers as aggregates only (L35). */
import React, { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";

interface Data {
  totals: { earned: number; scheduled_exams: number; proofs_pending: number; proofs_rejected: number; students_with_certificate_pct: number };
  monthly: { month: string; earned: number }[];
  issuers: { issuer: string; earned: number }[];
  batches: { batch: string; earned: number; students: number }[];
  vouchers: { issued: number; used: number; unused: number };
}

export default function CollegeCertificationsPage() {
  const { t } = useLanguage();
  const [d, setD] = useState<Data | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchApi<Data>("/college/certifications").then(setD).catch((e) => setError(e instanceof ApiError ? String(e.detail) : t("certs.load_failed")));
  }, [t]);

  const max = Math.max(1, ...(d?.monthly.map((m) => m.earned) || [1]));
  const tiles: [string, number | string][] = d ? [
    ["earned", d.totals.earned], ["holders", `${d.totals.students_with_certificate_pct}%`], ["scheduled", d.totals.scheduled_exams],
    ["pending", d.totals.proofs_pending], ["rejected", d.totals.proofs_rejected], ["vouchers", `${d.vouchers.used}/${d.vouchers.issued}`],
  ] : [];

  return (
    <RoleGuard allowedRoles={["college"]}>
      <AppShell pageTitle={t("certs.college_title")}>
        <div className="space-y-4 max-w-5xl">
          <p className="text-xs text-[#64748B]">{t("certs.college_help")}</p>
          {error && <p className="text-xs text-red-600" role="alert">{error}</p>}
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3" data-testid="cert-tiles">
            {tiles.map(([k, v]) => (
              <div key={k} className="bg-white rounded-xl border border-[#E2E8F0] p-3">
                <div className="text-xl font-black text-[#0F1F3A]" data-testid={`tile-${k}`}>{v}</div>
                <div className="text-[11px] text-[#64748B]">{t(`certs.tile_${k}`)}</div>
              </div>
            ))}
          </div>
          {d && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <section className="bg-white rounded-xl border border-[#E2E8F0] p-4">
                <h2 className="text-xs font-black mb-2">{t("certs.by_month")}</h2>
                <ul className="space-y-1.5" aria-label={t("certs.by_month")}>
                  {d.monthly.map((m) => (
                    <li key={m.month} className="text-[11px] flex items-center gap-2">
                      <span className="w-14 text-[#64748B]">{m.month}</span>
                      <span className="h-2 bg-[#2BB3A0] rounded" style={{ width: `${Math.round(100 * m.earned / max)}%` }} />
                      <span className="font-bold">{m.earned}</span>
                    </li>
                  ))}
                </ul>
              </section>
              <section className="bg-white rounded-xl border border-[#E2E8F0] p-4">
                <h2 className="text-xs font-black mb-2">{t("certs.by_issuer")}</h2>
                <table className="w-full text-[11px]"><tbody>
                  {d.issuers.map((i) => <tr key={i.issuer} className="border-t border-[#F1F5F9]"><td className="py-1">{i.issuer}</td><td className="text-right font-bold">{i.earned}</td></tr>)}
                </tbody></table>
              </section>
              <section className="bg-white rounded-xl border border-[#E2E8F0] p-4">
                <h2 className="text-xs font-black mb-2">{t("certs.by_batch")}</h2>
                <table className="w-full text-[11px]" data-testid="cert-batches"><tbody>
                  {d.batches.map((b) => <tr key={b.batch} className="border-t border-[#F1F5F9]"><td className="py-1">{b.batch}</td><td className="text-right">{b.students} {t("certs.students")}</td><td className="text-right font-bold">{b.earned}</td></tr>)}
                </tbody></table>
              </section>
            </div>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
