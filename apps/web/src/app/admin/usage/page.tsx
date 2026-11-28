"use client";

/** Screen 47 · Usage and quotas (IREP staff): each college's use this month against its MoU (L36).
 *  The quotas themselves are MoU terms, edited on 45. Full billing comes in S16. */
import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";

interface Metric { used: number; quota: number | null; pct: number | null; level: "ok" | "warn" | "over" }
interface Row { college_id: string; name: string; code: string; students: number; mou: { ends_on: string } | null; usage: Record<string, Metric> }
const METRICS = ["lab_minutes", "ai_calls", "recording_mb", "cloud_credits"] as const;
const BAR: Record<string, string> = { ok: "bg-teal", warn: "bg-warning-fill", over: "bg-danger" };

function thisMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function UsagePage() {
  const { t } = useLanguage();
  const [period, setPeriod] = useState(thisMonth());
  const [data, setData] = useState<{ colleges: Row[]; summary: { colleges: number; warn: number; over: number } } | null>(null);
  const [onlyFlagged, setOnlyFlagged] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { setData(await fetchApi(`/admin/usage?period=${period}`)); setError(""); }
    catch (e) { setError(e instanceof ApiError ? String(e.detail) : t("usage.load_failed")); }
  }, [period, t]);
  useEffect(() => { load(); }, [load]);

  const rows = (data?.colleges || []).filter((c) => !onlyFlagged || Object.values(c.usage).some((m) => m.level !== "ok"));

  return (
    <RoleGuard allowedRoles={["admin"]}>
      <AppShell pageTitle={t("usage.title")} pageSubtitle={t("usage.help")}>
        <div className="space-y-6 max-w-6xl">
          <div className="flex flex-wrap items-center gap-3">
            <input type="month" value={period} onChange={(e) => setPeriod(e.target.value)} aria-label={t("usage.month")} data-testid="usage-month"
              className="px-2.5 py-1.5 border border-line-strong rounded-tile text-xs" />
            <label className="text-xs flex items-center gap-1.5"><input type="checkbox" checked={onlyFlagged} onChange={(e) => setOnlyFlagged(e.target.checked)} data-testid="usage-flagged" />{t("usage.only_flagged")}</label>
            {data && <span className="text-caption text-muted" data-testid="usage-summary">{data.summary.colleges} {t("usage.colleges")} · {data.summary.warn} {t("usage.near")} · {data.summary.over} {t("usage.over")}</span>}
          </div>
          {error && <p className="text-xs text-red-600" role="alert">{error}</p>}
          <div className="bg-white rounded-card border border-line overflow-x-auto">
            <table className="w-full text-xs" data-testid="usage-table">
              <thead><tr className="text-left text-muted border-b border-line">
                <th className="px-3 py-2">{t("usage.college")}</th>
                {METRICS.map((m) => <th key={m} className="px-2">{t(`usage.m_${m}`)}</th>)}
              </tr></thead>
              <tbody>
                {rows.map((c) => (
                  <tr key={c.college_id} className="border-b border-line-soft align-top" data-testid="usage-row">
                    <td className="px-3 py-2">
                      <Link href={`/admin/colleges/${c.college_id}`} className="font-semibold text-ink hover:underline">{c.name}</Link>
                      <div className="text-caption text-muted">{c.students} {t("usage.students")}{c.mou ? ` · ${t("usage.mou_until")} ${c.mou.ends_on}` : ` · ${t("usage.no_mou")}`}</div>
                    </td>
                    {METRICS.map((m) => {
                      const v = c.usage[m];
                      return (
                        <td key={m} className="px-2 py-2 min-w-[120px]" data-testid={`usage-${m}`} data-level={v.level}>
                          <div className="font-semibold">{v.used.toLocaleString()}{v.quota !== null ? ` / ${v.quota.toLocaleString()}` : ""}</div>
                          {v.pct !== null && (
                            <div className="h-1.5 bg-line-soft rounded-full mt-1 overflow-hidden" aria-label={`${v.pct}%`}>
                              <div className={`h-full ${BAR[v.level]}`} style={{ width: `${Math.min(100, v.pct)}%` }} />
                            </div>
                          )}
                          {v.level !== "ok" && <div className={`text-caption font-semibold mt-0.5 ${v.level === "over" ? "text-danger" : "text-warning"}`}>{t(`usage.level_${v.level}`)}</div>}
                        </td>
                      );
                    })}
                  </tr>
                ))}
                {rows.length === 0 && <tr><td colSpan={5} className="px-3 py-6 text-center text-muted">{t("usage.none")}</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
