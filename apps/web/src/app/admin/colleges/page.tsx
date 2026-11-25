"use client";

/** Screen 45 · Colleges and MoU terms (IREP staff). Spec: docs/screens/45-colleges-and-mou.md */
import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { fetchApi, ApiError } from "@/lib/api";
import { Building2, Plus } from "lucide-react";
import type { RequestBody } from "@irep/api-client";

/** The create form is typed against the API contract (packages/api-client). */
type NewCollege = RequestBody<"/api/v1/admin/colleges", "post">;

interface CollegeRow {
  id: string; name: string; code: string; city: string | null; state: string | null;
  status: "onboarding" | "active" | "suspended"; students: number; admins: number;
  mou_ends_on: string | null; students_cap: number | null;
}

const STATUS_STYLE: Record<string, string> = {
  active: "bg-[#DCFCE7] text-[#166534]",
  onboarding: "bg-[#FEF3C7] text-[#92400E]",
  suspended: "bg-[#FEE2E2] text-[#991B1B]",
};

const EMPTY: NewCollege = { name: "", code: "", city: "", state: "Tamil Nadu" };

export default function AdminCollegesPage() {
  const { t } = useLanguage();
  const [rows, setRows] = useState<CollegeRow[] | null>(null);
  const [loadError, setLoadError] = useState("");
  const [form, setForm] = useState(EMPTY);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    try {
      const data = await fetchApi<{ colleges: CollegeRow[] }>("/admin/colleges");
      setRows(data.colleges);
      setLoadError("");
    } catch (e) {
      setLoadError(e instanceof ApiError ? e.detail : t("admin_colleges.load_failed"));
    }
  }, [t]);

  useEffect(() => { load(); }, [load]);

  const validate = () => {
    const errs: Record<string, string> = {};
    if (form.name.trim().length < 3) errs.name = t("admin_colleges.err_name");
    if (!/^[A-Za-z0-9]{2,16}$/.test(form.code.trim())) errs.code = t("admin_colleges.err_code");
    if (form.city.trim().length < 2) errs.city = t("admin_colleges.err_city");
    if (form.state.trim().length < 2) errs.state = t("admin_colleges.err_state");
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    if (!validate()) return;
    setSaving(true);
    try {
      await fetchApi("/admin/colleges", { method: "POST", body: JSON.stringify(form) });
      setForm(EMPTY);
      setShowForm(false);
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.detail : t("admin_colleges.save_failed"));
    } finally {
      setSaving(false);
    }
  };

  const field = (key: keyof typeof EMPTY, label: string) => (
    <div>
      <label className="block text-xs font-bold text-[#0F1F3A] mb-1" htmlFor={`college-${key}`}>{label}</label>
      <input
        id={`college-${key}`}
        data-testid={`college-${key}`}
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        aria-invalid={!!fieldErrors[key]}
        className={`w-full px-3 py-2 bg-[#F8FAFC] border ${fieldErrors[key] ? "border-red-400" : "border-[#E2E8F0]"} rounded-lg text-xs focus:outline-none focus:border-[#2B5CD0]`}
      />
      {fieldErrors[key] && <p className="text-[11px] text-red-600 mt-1">{fieldErrors[key]}</p>}
    </div>
  );

  return (
    <RoleGuard allowedRoles={["admin"]}>
      <AppShell pageTitle={t("admin_colleges.title")}>
        <div className="space-y-4 max-w-6xl">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            {/* the shell renders the page title as the only h1 */}
            <p className="text-xs text-[#64748B] mt-1 max-w-2xl">{t("admin_colleges.subtitle")}</p>
            <button
              type="button"
              data-testid="new-college"
              onClick={() => setShowForm((v) => !v)}
              className="flex items-center gap-1.5 px-3.5 py-2 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg"
            >
              <Plus className="w-3.5 h-3.5" /> {t("admin_colleges.new_college")}
            </button>
          </div>

          {showForm && (
            <form onSubmit={create} noValidate className="bg-white rounded-xl border border-[#E2E8F0] p-4 grid grid-cols-1 md:grid-cols-2 gap-3" data-testid="college-form">
              {field("name", t("admin_colleges.name"))}
              {field("code", t("admin_colleges.code"))}
              {field("city", t("admin_colleges.city"))}
              {field("state", t("admin_colleges.state"))}
              {formError && <p className="md:col-span-2 text-xs text-red-600 font-medium" role="alert" data-testid="college-form-error">{formError}</p>}
              <div className="md:col-span-2 flex justify-end">
                <button type="submit" disabled={saving} data-testid="college-save" className="px-4 py-2 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg disabled:opacity-50">
                  {t("admin_colleges.create")}
                </button>
              </div>
            </form>
          )}

          {loadError && <p className="text-xs text-red-600" role="alert">{loadError}</p>}

          {rows && rows.length === 0 && (
            <div className="bg-white rounded-xl border border-dashed border-[#CBD5E1] p-8 text-center text-xs text-[#64748B]">{t("admin_colleges.empty")}</div>
          )}

          {rows && rows.length > 0 && (
            <div className="bg-white rounded-xl border border-[#E2E8F0] overflow-x-auto">
              <table className="w-full text-xs" data-testid="colleges-table">
                <thead className="bg-[#F8FAFC] text-[#64748B]">
                  <tr>
                    <th className="text-left font-semibold px-4 py-2.5">{t("admin_colleges.name")}</th>
                    <th className="text-left font-semibold px-4 py-2.5">{t("admin_colleges.code")}</th>
                    <th className="text-left font-semibold px-4 py-2.5">{t("admin_colleges.city")}</th>
                    <th className="text-left font-semibold px-4 py-2.5">{t("admin_colleges.status")}</th>
                    <th className="text-right font-semibold px-4 py-2.5">{t("admin_colleges.students")}</th>
                    <th className="text-left font-semibold px-4 py-2.5">{t("admin_colleges.mou_until")}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((c) => (
                    <tr key={c.id} className="border-t border-[#F1F5F9]" data-testid={`college-row-${c.code}`}>
                      <td className="px-4 py-2.5">
                        <Link href={`/admin/colleges/${c.id}`} className="font-bold text-[#2B5CD0] hover:underline inline-flex items-center gap-1.5">
                          <Building2 className="w-3.5 h-3.5" /> {c.name}
                        </Link>
                      </td>
                      <td className="px-4 py-2.5 font-mono">{c.code}</td>
                      <td className="px-4 py-2.5">{[c.city, c.state].filter(Boolean).join(", ")}</td>
                      <td className="px-4 py-2.5">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${STATUS_STYLE[c.status] || ""}`}>{t(`admin_colleges.status_${c.status}`)}</span>
                      </td>
                      <td className="px-4 py-2.5 text-right">{c.students}{c.students_cap ? ` / ${c.students_cap}` : ""}</td>
                      <td className="px-4 py-2.5">{c.mou_ends_on ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
