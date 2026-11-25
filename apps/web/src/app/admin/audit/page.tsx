"use client";

/** Screen 48 · audit trail (read-only). Spec: docs/screens/48-audit-and-consent.md */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { AuditTabs, downloadWithAuth } from "@/components/admin/AuditTabs";
import { useLanguage } from "@/lib/LanguageContext";
import { API_BASE, ApiError, authHeaders, fetchApi } from "@/lib/api";
import { Download } from "lucide-react";

interface Row {
  id: string; at: string; college_id: string; actor_user_id: string | null; actor_name: string | null; actor_role: string | null;
  action: string; entity_type: string | null; entity_id: string | null; detail: Record<string, unknown> | null;
}
const PAGE = 25;

export default function AuditTrailPage() {
  const { t } = useLanguage();
  const [filters, setFilters] = useState({ college_id: "", action: "", actor: "", date_from: "", date_to: "" });
  const [applied, setApplied] = useState(filters);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{ total: number; items: Row[] } | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [error, setError] = useState("");

  const query = useCallback((f: typeof filters) => {
    const q = new URLSearchParams();
    Object.entries(f).forEach(([k, v]) => { if (v.trim()) q.set(k, v.trim()); });
    return q;
  }, []);

  const load = useCallback(async () => {
    try {
      const q = query(applied);
      q.set("page", String(page));
      q.set("page_size", String(PAGE));
      setData(await fetchApi(`/admin/audit?${q.toString()}`));
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("admin_audit.load_failed"));
    }
  }, [applied, page, query, t]);

  useEffect(() => { load(); }, [load]);

  const apply = (e: React.FormEvent) => { e.preventDefault(); setPage(1); setApplied(filters); };
  const csv = async () => {
    try {
      await downloadWithAuth(`${API_BASE}/admin/audit/export.csv?${query(applied).toString()}`, authHeaders(), "irep-audit.csv");
    } catch {
      setError(t("admin_audit.download_failed"));
    }
  };
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE)) : 1;
  const f = (key: keyof typeof filters, label: string, type = "text") => (
    <label className="text-caption font-semibold text-ink">
      {label}
      <input type={type} value={filters[key]} data-testid={`filter-${key}`} onChange={(e) => setFilters({ ...filters, [key]: e.target.value })}
        className="mt-1 w-full px-2.5 py-1.5 bg-surface-2 border border-line rounded-tile text-xs font-normal" />
    </label>
  );

  return (
    <RoleGuard allowedRoles={["admin"]}>
      <AppShell pageTitle={t("admin_audit.title")}>
        <div className="space-y-6 max-w-6xl">
          <AuditTabs />
          <form onSubmit={apply} className="bg-white rounded-card border border-line p-3 grid grid-cols-2 md:grid-cols-6 gap-2 items-end">
            {f("college_id", t("admin_audit.college"))}
            {f("action", t("admin_audit.action"))}
            {f("actor", t("admin_audit.actor"))}
            {f("date_from", t("admin_audit.from"), "date")}
            {f("date_to", t("admin_audit.to"), "date")}
            <div className="flex gap-2">
              <button type="submit" data-testid="filter-apply" className="flex-1 px-3 py-1.5 bg-brand text-white text-xs font-semibold rounded-tile">{t("admin_audit.apply")}</button>
              <button type="button" onClick={csv} data-testid="audit-csv" title={t("admin_audit.csv")} className="px-2.5 py-1.5 border border-line-strong rounded-tile"><Download className="w-3.5 h-3.5" /></button>
            </div>
          </form>
          <p className="text-caption text-muted">{t("admin_audit.read_only_note")}</p>
          {error && <p className="text-xs text-red-600" role="alert">{error}</p>}
          {data && (
            <div className="bg-white rounded-card border border-line overflow-x-auto">
              <table className="w-full text-xs" data-testid="audit-table">
                <thead className="bg-surface-2 text-muted">
                  <tr>
                    <th className="text-left font-semibold px-3 py-2">{t("admin_audit.when")}</th>
                    <th className="text-left font-semibold px-3 py-2">{t("admin_audit.action")}</th>
                    <th className="text-left font-semibold px-3 py-2">{t("admin_audit.actor")}</th>
                    <th className="text-left font-semibold px-3 py-2">{t("admin_audit.entity")}</th>
                    <th className="text-left font-semibold px-3 py-2">{t("admin_audit.college")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.length === 0 && <tr><td colSpan={5} className="px-3 py-6 text-center text-muted">{t("admin_audit.empty")}</td></tr>}
                  {data.items.map((r) => (
                    <React.Fragment key={r.id}>
                      <tr className="border-t border-line-soft cursor-pointer hover:bg-surface-2" onClick={() => setOpen(open === r.id ? null : r.id)} data-testid="audit-row">
                        <td className="px-3 py-2 whitespace-nowrap">{r.at.replace("T", " ").slice(0, 19)}</td>
                        <td className="px-3 py-2 font-mono">{r.action}</td>
                        <td className="px-3 py-2">{r.actor_name || r.actor_user_id || t("admin_audit.system")}{r.actor_role ? ` · ${r.actor_role}` : ""}</td>
                        <td className="px-3 py-2">{r.entity_type ? `${r.entity_type} ${r.entity_id ?? ""}` : "—"}</td>
                        <td className="px-3 py-2">{r.college_id}</td>
                      </tr>
                      {open === r.id && (
                        <tr className="bg-surface-2"><td colSpan={5} className="px-3 py-2">
                          <pre className="text-caption whitespace-pre-wrap break-all" data-testid="audit-detail">{JSON.stringify(r.detail ?? {}, null, 2)}</pre>
                        </td></tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
              <div className="flex items-center justify-between px-3 py-2 border-t border-line-soft text-caption text-muted">
                <span data-testid="audit-total">{data.total} {t("admin_audit.entries")}</span>
                <div className="flex gap-2 items-center">
                  <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)} className="px-2 py-1 border rounded disabled:opacity-40">‹</button>
                  <span>{page} / {pages}</span>
                  <button type="button" disabled={page >= pages} onClick={() => setPage(page + 1)} className="px-2 py-1 border rounded disabled:opacity-40">›</button>
                </div>
              </div>
            </div>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
