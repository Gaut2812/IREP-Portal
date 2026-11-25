"use client";

/** Screen 20 · MoU reports (college): aggregates only (L35), with the active MoU terms. Usage figures (L23) follow with 47. */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi, fetchBlob } from "@/lib/api";
import { Download, FilePlus2 } from "lucide-react";

interface Report { id: string; title: string; type: string; period: string | null; generated_at: string | null; data_as_of: string | null; size_kb: number; status: string }

export default function CollegeReportsPage() {
  const { t, language } = useLanguage();
  const [reports, setReports] = useState<Report[]>([]);
  const [type, setType] = useState("progress");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setReports((await fetchApi<{ reports: Report[] }>(`/college/reports?lang=${language}`)).reports);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("reports.load_failed"));
    }
  }, [language, t]);

  useEffect(() => { load(); }, [load]);

  const generate = async () => {
    setBusy(true);
    setError("");
    try {
      await fetchApi("/college/reports/generate", { method: "POST", body: JSON.stringify({ report_type: type }) });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("reports.save_failed"));
    } finally {
      setBusy(false);
    }
  };

  const download = async (r: Report) => {
    try {
      const url = URL.createObjectURL(await fetchBlob(`/college/reports/${r.id}/download`));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${r.id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError(t("reports.download_failed"));
    }
  };

  return (
    <RoleGuard allowedRoles={["college"]}>
      <AppShell pageTitle={t("reports.mou_title")} pageSubtitle={t("reports.mou_help")}>
        <div className="space-y-6 max-w-4xl">
          <div className="flex flex-wrap gap-2 items-center">
            <select value={type} onChange={(e) => setType(e.target.value)} aria-label={t("reports.type")} data-testid="mou-type" className="px-2.5 py-1.5 border border-line-strong rounded-tile text-xs">
              {["progress", "performance", "readiness"].map((k) => <option key={k} value={k}>{t(`reports.type_${k}`)}</option>)}
            </select>
            <button type="button" disabled={busy} onClick={generate} data-testid="mou-generate" className="px-3 py-1.5 bg-brand text-white text-xs font-semibold rounded-tile inline-flex items-center gap-1 disabled:opacity-50">
              <FilePlus2 className="w-3.5 h-3.5" />{t("reports.generate_report")}
            </button>
          </div>
          {error && <p className="text-xs text-red-600" role="alert">{error}</p>}
          <ul className="bg-white rounded-card border border-line divide-y divide-line-soft" data-testid="mou-list">
            {reports.length === 0 && <li className="p-6 text-center text-xs text-muted">{t("reports.no_reports")}</li>}
            {reports.map((r) => (
              <li key={r.id} className="px-3 py-2.5 flex items-center justify-between gap-2" data-testid="mou-row">
                <div className="min-w-0">
                  <div className="text-xs font-semibold text-ink truncate">{r.title}</div>
                  <div className="text-caption text-muted">{t("reports.data_as_of")} {r.data_as_of} · {r.size_kb} KB</div>
                </div>
                <button type="button" onClick={() => download(r)} data-testid="mou-download" className="px-2.5 py-1 border border-line-strong text-xs font-semibold rounded-tile inline-flex items-center gap-1 shrink-0">
                  <Download className="w-3.5 h-3.5" />PDF
                </button>
              </li>
            ))}
          </ul>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
