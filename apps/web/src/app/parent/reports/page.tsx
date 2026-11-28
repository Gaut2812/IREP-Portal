"use client";

/** Screen 16 · Progress reports (parent): monthly cards released by the trainer (L22). */
import React, { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi, fetchBlob } from "@/lib/api";
import { Download, FileText } from "lucide-react";

interface Card {
  id: string; month_label: string; trainer_name: string | null; trainer_remark: string | null; how_to_help: string | null;
  rows: { area: string; prev: string; curr: string; status: string; color: string }[];
}

export default function ParentReportsPage() {
  const { t, language } = useLanguage();
  const [data, setData] = useState<{ consent_required: boolean; ward: { name: string }; cards: Card[] } | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchApi<{ consent_required: boolean; ward: { name: string }; cards: Card[] }>(`/parent/reports?lang=${language}`)
      .then((d) => { setData(d); setOpen((o) => o ?? d.cards[0]?.id ?? null); })
      .catch((e) => setError(e instanceof ApiError ? e.detail : t("reports.load_failed")));
  }, [language, t]);

  const download = async (c: Card) => {
    try {
      const blob = await fetchBlob(`/parent/reports/${c.id}/pdf`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `progress-${c.month_label.replace(/\s+/g, "-")}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError(t("reports.download_failed"));
    }
  };

  return (
    <RoleGuard allowedRoles={["parent"]}>
      <AppShell pageTitle={t("reports.parent_title")}>
        <div className="max-w-2xl mx-auto space-y-6">
          {error && <p className="text-xs text-red-600" role="alert">{error}</p>}
          {data?.consent_required && (
            <div className="bg-white rounded-card border border-brand-line p-4 text-xs" data-testid="reports-consent">
              {t("reports.consent_needed")} <Link href="/parent" className="text-brand font-semibold">{t("reports.open_overview")}</Link>
            </div>
          )}
          {data && !data.consent_required && <p className="text-xs text-muted">{t("reports.for_child")} {data.ward.name}</p>}
          {data && !data.consent_required && data.cards.length === 0 && <p className="text-xs text-muted bg-white rounded-card border border-dashed border-line-strong p-6 text-center">{t("reports.no_cards")}</p>}
          <ul className="space-y-3" data-testid="report-cards">
            {data?.cards.map((c) => (
              <li key={c.id} className="bg-white rounded-card border border-line" data-testid="report-card">
                <button type="button" onClick={() => setOpen(open === c.id ? null : c.id)} aria-expanded={open === c.id}
                  className="w-full text-left px-4 py-3 flex items-center gap-2 text-sm font-semibold text-ink">
                  <FileText className="w-4 h-4 text-brand" />{c.month_label}
                </button>
                {open === c.id && (
                  <div className="px-4 pb-4 space-y-3">
                    <table className="w-full text-xs">
                      <thead><tr className="text-left text-muted"><th className="py-1">{t("reports.area")}</th><th>{t("reports.last_month")}</th><th>{t("reports.this_month")}</th></tr></thead>
                      <tbody>
                        {c.rows.map((r) => (
                          <tr key={r.area} className="border-t border-line-soft">
                            <td className="py-1.5 font-semibold">{r.area}<div className={`text-caption ${r.color === "green" ? "text-success" : "text-warning"}`}>{r.status}</div></td>
                            <td>{r.prev}</td><td className="font-semibold">{r.curr}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {c.trainer_remark && <p className="text-xs text-ink-soft" data-testid="report-remark"><b>{t("reports.remark")}{c.trainer_name ? ` (${c.trainer_name})` : ""}:</b> {c.trainer_remark}</p>}
                    {c.how_to_help && <p className="text-xs bg-success-faint border border-success-line rounded-tile p-2.5 text-success"><b>{t("reports.how_to_help")}:</b> {c.how_to_help}</p>}
                    <button type="button" onClick={() => download(c)} data-testid="report-pdf" className="px-3 py-1.5 border border-line-strong text-xs font-semibold rounded-tile inline-flex items-center gap-1">
                      <Download className="w-3.5 h-3.5" />{t("reports.pdf")}
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
