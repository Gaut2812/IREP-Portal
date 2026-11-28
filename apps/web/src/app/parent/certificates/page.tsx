"use client";

/** Screen 27 · Certificates (parent): a read-only copy of the child's verified certificates (L32). */
import React, { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi, fetchBlob } from "@/lib/api";
import { BadgeCheck, Clock, Download } from "lucide-react";

interface Cert { id: string; title: string; issuer: string; issued_on: string | null; exam_date: string | null; verify_code: string | null; status_label: string }
interface Data { consent_required: boolean; ward: { name: string }; earned: Cert[]; upcoming: Cert[] }

/** Save an earned certificate's PDF (the API builds it with the verification code). */
async function saveCertificate(endpoint: string, title: string) {
  const url = URL.createObjectURL(await fetchBlob(endpoint));
  const a = document.createElement("a");
  a.href = url;
  a.download = `${title.replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "") || "certificate"}.pdf`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export default function ParentCertificatesPage() {
  const { t, language } = useLanguage();
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchApi<Data>(`/parent/certificates?lang=${language}`).then(setData)
      .catch((e) => setError(e instanceof ApiError ? String(e.detail) : t("certs.load_failed")));
  }, [language, t]);

  return (
    <RoleGuard allowedRoles={["parent"]}>
      <AppShell pageTitle={t("certs.parent_title")}>
        <div className="max-w-2xl mx-auto space-y-6">
          {error && <p className="text-xs text-red-600" role="alert">{error}</p>}
          {data?.consent_required && (
            <div className="bg-white rounded-card border border-brand-line p-4 text-xs">{t("reports.consent_needed")} <Link href="/parent" className="text-brand font-semibold">{t("reports.open_overview")}</Link></div>
          )}
          {data && !data.consent_required && (
            <>
              <p className="text-xs text-muted">{t("certs.for_child")} {data.ward.name}</p>
              <ul className="space-y-2" data-testid="parent-earned">
                {data.earned.length === 0 && <li className="bg-white rounded-card border border-dashed border-line-strong p-6 text-center text-xs text-muted">{t("certs.none_parent")}</li>}
                {data.earned.map((c) => (
                  <li key={c.id} className="bg-white rounded-card border border-line p-4 flex items-start gap-3" data-testid="parent-cert">
                    <BadgeCheck className="w-5 h-5 text-success shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-semibold text-ink">{c.title}</div>
                      <div className="text-caption text-muted">{c.issuer}{c.issued_on ? ` · ${c.issued_on}` : ""} · {c.status_label}</div>
                    </div>
                    <button type="button" onClick={() => saveCertificate(`/parent/certificates/${c.id}/download`, c.title).catch(() => undefined)}
                      data-testid={`parent-cert-download-${c.id}`} className="px-2.5 py-1 border border-brand text-brand text-caption font-semibold rounded-tile inline-flex items-center gap-1 shrink-0">
                      <Download className="w-3.5 h-3.5" />{t("certs.download")}
                    </button>
                  </li>
                ))}
              </ul>
              {data.upcoming.length > 0 && (
                <>
                  <h2 className="text-xs font-semibold text-muted pt-2">{t("certs.upcoming")}</h2>
                  <ul className="space-y-2">
                    {data.upcoming.map((c) => (
                      <li key={c.id} className="bg-white rounded-card border border-line p-4 flex items-start gap-3" data-testid="parent-upcoming">
                        <Clock className="w-5 h-5 text-info shrink-0" />
                        <div><div className="text-sm font-semibold">{c.title}</div><div className="text-caption text-muted">{t("certs.exam_on")} {c.exam_date}</div></div>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
