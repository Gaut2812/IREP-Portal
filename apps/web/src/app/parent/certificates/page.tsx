"use client";

/** Screen 27 · Certificates (parent): a read-only copy of the child's verified certificates (L32). */
import React, { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { BadgeCheck, Clock } from "lucide-react";

interface Cert { id: string; title: string; issuer: string; issued_on: string | null; exam_date: string | null; verify_code: string | null; status_label: string }
interface Data { consent_required: boolean; ward: { name: string }; earned: Cert[]; upcoming: Cert[] }

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
                    <div>
                      <div className="text-sm font-semibold text-ink">{c.title}</div>
                      <div className="text-caption text-muted">{c.issuer}{c.issued_on ? ` · ${c.issued_on}` : ""} · {c.status_label}</div>
                    </div>
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
