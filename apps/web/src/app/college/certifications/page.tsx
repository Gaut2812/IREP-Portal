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
      <AppShell pageTitle={t("certs.college_title")} pageSubtitle={t("certs.college_help")}>
        <div className="space-y-6 max-w-5xl">
          {error && <p className="text-xs text-red-600" role="alert">{error}</p>}
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3" data-testid="cert-tiles">
            {tiles.map(([k, v]) => (
              <div key={k} className="bg-white rounded-card border border-line p-3">
                <div className="text-xl font-semibold text-ink" data-testid={`tile-${k}`}>{v}</div>
                <div className="text-caption text-muted">{t(`certs.tile_${k}`)}</div>
              </div>
            ))}
          </div>
          {d && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <section className="bg-white rounded-card border border-line p-4">
                <h2 className="text-xs font-semibold mb-2">{t("certs.by_month")}</h2>
                <ul className="space-y-1.5" aria-label={t("certs.by_month")}>
                  {d.monthly.map((m) => (
                    <li key={m.month} className="text-caption flex items-center gap-2">
                      <span className="w-14 text-muted">{m.month}</span>
                      <span className="h-2 bg-teal rounded" style={{ width: `${Math.round(100 * m.earned / max)}%` }} />
                      <span className="font-semibold">{m.earned}</span>
                    </li>
                  ))}
                </ul>
              </section>
              <section className="bg-white rounded-card border border-line p-4">
                <h2 className="text-xs font-semibold mb-2">{t("certs.by_issuer")}</h2>
                <table className="w-full text-caption"><tbody>
                  {d.issuers.map((i) => <tr key={i.issuer} className="border-t border-line-soft"><td className="py-1">{i.issuer}</td><td className="text-right font-semibold">{i.earned}</td></tr>)}
                </tbody></table>
              </section>
              <section className="bg-white rounded-card border border-line p-4">
                <h2 className="text-xs font-semibold mb-2">{t("certs.by_batch")}</h2>
                <table className="w-full text-caption" data-testid="cert-batches"><tbody>
                  {d.batches.map((b) => <tr key={b.batch} className="border-t border-line-soft"><td className="py-1">{b.batch}</td><td className="text-right">{b.students} {t("certs.students")}</td><td className="text-right font-semibold">{b.earned}</td></tr>)}
                </tbody></table>
              </section>
            </div>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
