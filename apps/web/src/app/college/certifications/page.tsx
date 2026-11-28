"use client";

/** Screen 28 · Certifications (college): counts, proof status and vouchers (L35), plus who holds which earned
 *  certificate (decision D1: names, register numbers, title, issuer, date; never proof files or notes). */
import React, { useCallback, useEffect, useState } from "react";
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

interface Holder { certificate_id: string; title: string; issuer: string; type: string; issued_on: string | null; register_no: string; name: string; batch: string | null }
interface Holders { total: number; page: number; page_size: number; holders: Holder[] }

export default function CollegeCertificationsPage() {
  const { t } = useLanguage();
  const [d, setD] = useState<Data | null>(null);
  const [error, setError] = useState("");
  const [holders, setHolders] = useState<Holders | null>(null);
  const [search, setSearch] = useState("");
  const [batch, setBatch] = useState("");
  const [issuer, setIssuer] = useState("");
  const [page, setPage] = useState(1);

  const loadHolders = useCallback(async () => {
    const q = new URLSearchParams({ page: String(page) });
    if (search.trim().length >= 2) q.set("search", search.trim());
    if (batch) q.set("batch", batch);
    if (issuer) q.set("issuer", issuer);
    try {
      setHolders(await fetchApi<Holders>(`/college/certifications/holders?${q}`));
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : t("certs.load_failed"));
    }
  }, [page, search, batch, issuer, t]);

  useEffect(() => {
    const id = setTimeout(loadHolders, 250);
    return () => clearTimeout(id);
  }, [loadHolders]);
  const pages = holders ? Math.max(1, Math.ceil(holders.total / holders.page_size)) : 1;

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
          <section className="bg-white rounded-card border border-line p-4 space-y-3" data-testid="cert-holders">
            <div>
              <h2 className="text-xs font-semibold">{t("certs.holders_title")}</h2>
              <p className="text-caption text-muted">{t("certs.holders_help")}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder={t("certs.holders_search")} data-testid="holders-search"
                aria-label={t("certs.holders_search")} className="flex-1 min-w-48 px-2.5 py-1.5 bg-surface-2 border border-line rounded-tile text-xs" />
              <select value={batch} onChange={(e) => { setBatch(e.target.value); setPage(1); }} data-testid="holders-batch" aria-label={t("certs.by_batch")}
                className="px-2 py-1.5 bg-surface-2 border border-line rounded-tile text-xs">
                <option value="">{t("certs.all_batches")}</option>
                {d?.batches.map((b) => <option key={b.batch} value={b.batch}>{b.batch}</option>)}
              </select>
              <select value={issuer} onChange={(e) => { setIssuer(e.target.value); setPage(1); }} data-testid="holders-issuer" aria-label={t("certs.by_issuer")}
                className="px-2 py-1.5 bg-surface-2 border border-line rounded-tile text-xs">
                <option value="">{t("certs.all_issuers")}</option>
                {d?.issuers.map((i) => <option key={i.issuer} value={i.issuer}>{i.issuer}</option>)}
              </select>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-caption">
                <thead>
                  <tr className="text-left text-muted">
                    <th className="py-1 font-semibold">{t("certs.col_student")}</th>
                    <th className="py-1 font-semibold">{t("certs.col_register")}</th>
                    <th className="py-1 font-semibold">{t("certs.col_batch")}</th>
                    <th className="py-1 font-semibold">{t("certs.col_certificate")}</th>
                    <th className="py-1 font-semibold">{t("certs.col_issuer")}</th>
                    <th className="py-1 font-semibold text-right">{t("certs.col_date")}</th>
                  </tr>
                </thead>
                <tbody>
                  {holders?.holders.length === 0 && <tr><td colSpan={6} className="py-4 text-center text-muted">{t("certs.holders_none")}</td></tr>}
                  {holders?.holders.map((h) => (
                    <tr key={h.certificate_id} className="border-t border-line-soft" data-testid="holder-row">
                      <td className="py-1.5 font-semibold text-ink">{h.name}</td>
                      <td className="py-1.5">{h.register_no}</td>
                      <td className="py-1.5">{h.batch ?? "—"}</td>
                      <td className="py-1.5">{h.title}</td>
                      <td className="py-1.5">{h.issuer}</td>
                      <td className="py-1.5 text-right">{h.issued_on ?? ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {holders && holders.total > holders.page_size && (
              <div className="flex items-center justify-end gap-2 text-caption">
                <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)} className="px-2 py-1 border border-line-strong rounded-tile disabled:opacity-50">{t("certs.prev")}</button>
                <span data-testid="holders-page">{page} / {pages}</span>
                <button type="button" disabled={page >= pages} onClick={() => setPage(page + 1)} className="px-2 py-1 border border-line-strong rounded-tile disabled:opacity-50">{t("certs.next")}</button>
              </div>
            )}
            {holders && <p className="text-caption text-muted" data-testid="holders-total">{t("certs.holders_total").replace("{n}", String(holders.total))}</p>}
          </section>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
