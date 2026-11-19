"use client";

/** Screen 45 · college detail: MoU terms, feature switches, college admins. */
import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { fetchApi, ApiError } from "@/lib/api";
import { ArrowLeft, Copy, FileSignature, ToggleLeft, UserPlus } from "lucide-react";

interface Mou {
  id: string; starts_on: string; ends_on: string; students_cap: number; lab_hours_per_student: number;
  ai_calls_per_day: number; storage_gb: number; fee_per_student_inr: number; status: "draft" | "active" | "superseded"; notes: string | null;
}
interface Detail {
  college: { id: string; name: string; code: string; city: string | null; state: string | null; status: string; students: number };
  features: Record<string, boolean>;
  mou_terms: Mou[];
  admins: { id: string; name: string; email: string; phone: string | null }[];
}

const STATUS_STYLE: Record<string, string> = {
  active: "bg-[#DCFCE7] text-[#166534]",
  onboarding: "bg-[#FEF3C7] text-[#92400E]",
  suspended: "bg-[#FEE2E2] text-[#991B1B]",
  draft: "bg-[#F1F5F9] text-[#475569]",
  superseded: "bg-[#F1F5F9] text-[#94A3B8]",
};
const FEATURE_KEYS = ["virtual_labs", "cyber_range", "ai_study_buddy", "parent_sms", "whatsapp", "teams_live_classes"];

function nextYear(): { starts_on: string; ends_on: string } {
  const s = new Date();
  const e = new Date(s);
  e.setFullYear(e.getFullYear() + 1);
  e.setDate(e.getDate() - 1);
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  return { starts_on: iso(s), ends_on: iso(e) };
}

export default function AdminCollegeDetailPage() {
  const { t } = useLanguage();
  const params = useParams<{ collegeId: string }>();
  const collegeId = params.collegeId;
  const [d, setD] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [mou, setMou] = useState({ ...nextYear(), students_cap: "500", lab_hours_per_student: "40", ai_calls_per_day: "30", storage_gb: "50", fee_per_student_inr: "0" });
  const [mouError, setMouError] = useState("");
  const [admin, setAdmin] = useState({ name: "", email: "", phone: "" });
  const [adminError, setAdminError] = useState("");
  const [tempPassword, setTempPassword] = useState<{ email: string; password: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setD(await fetchApi<Detail>(`/admin/colleges/${collegeId}`));
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("admin_colleges.load_failed"));
    }
  }, [collegeId, t]);

  useEffect(() => { load(); }, [load]);

  const run = async (fn: () => Promise<void>, setErr: (m: string) => void) => {
    setBusy(true);
    setErr("");
    try {
      await fn();
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.detail : t("admin_colleges.save_failed"));
    } finally {
      setBusy(false);
    }
  };

  const addMou = (e: React.FormEvent) => {
    e.preventDefault();
    if (mou.ends_on <= mou.starts_on) return setMouError(t("admin_colleges.err_mou_dates"));
    if (!(Number(mou.students_cap) > 0)) return setMouError(t("admin_colleges.err_mou_cap"));
    run(async () => {
      await fetchApi(`/admin/colleges/${collegeId}/mou`, {
        method: "POST",
        body: JSON.stringify({
          starts_on: mou.starts_on, ends_on: mou.ends_on, activate: true,
          students_cap: Number(mou.students_cap), lab_hours_per_student: Number(mou.lab_hours_per_student),
          ai_calls_per_day: Number(mou.ai_calls_per_day), storage_gb: Number(mou.storage_gb), fee_per_student_inr: Number(mou.fee_per_student_inr),
        }),
      });
    }, setMouError);
  };

  const toggle = (key: string, value: boolean) =>
    run(async () => {
      await fetchApi(`/admin/colleges/${collegeId}/features`, { method: "PUT", body: JSON.stringify({ features: { [key]: value } }) });
    }, setError);

  const addAdmin = (e: React.FormEvent) => {
    e.preventDefault();
    if (admin.name.trim().length < 2) return setAdminError(t("admin_colleges.err_admin_name"));
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(admin.email.trim())) return setAdminError(t("admin_colleges.err_admin_email"));
    run(async () => {
      const res = await fetchApi<{ email: string; temporary_password?: string }>(`/admin/colleges/${collegeId}/admins`, {
        method: "POST",
        body: JSON.stringify({ name: admin.name.trim(), email: admin.email.trim(), phone: admin.phone.trim() || null }),
      });
      setTempPassword(res.temporary_password ? { email: res.email, password: res.temporary_password } : null);
      setAdmin({ name: "", email: "", phone: "" });
    }, setAdminError);
  };

  const input = (value: string, onChange: (v: string) => void, testid: string, label: string, type = "text") => (
    <label className="block text-[11px] font-bold text-[#0F1F3A]">
      {label}
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)} data-testid={testid}
        className="mt-1 w-full px-2.5 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg text-xs font-normal focus:outline-none focus:border-[#2B5CD0]" />
    </label>
  );

  return (
    <RoleGuard allowedRoles={["admin"]}>
      <AppShell pageTitle={t("admin_colleges.title")}>
        <div className="p-4 md:p-6 space-y-4 max-w-6xl">
          <Link href="/admin/colleges" className="inline-flex items-center gap-1 text-xs text-[#2B5CD0] font-bold">
            <ArrowLeft className="w-3.5 h-3.5" /> {t("admin_colleges.back")}
          </Link>
          {error && <p className="text-xs text-red-600" role="alert">{error}</p>}
          {d && (
            <>
              <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 flex items-center justify-between gap-3 flex-wrap">
                <div>
                  <h2 className="text-lg font-black text-[#0F1F3A]" data-testid="college-name">{d.college.name}</h2>
                  <p className="text-xs text-[#64748B]">{d.college.code} · {[d.college.city, d.college.state].filter(Boolean).join(", ")} · {d.college.students} {t("admin_colleges.students").toLowerCase()}</p>
                </div>
                <span data-testid="college-status" className={`px-2.5 py-1 rounded-full text-[11px] font-bold ${STATUS_STYLE[d.college.status] || ""}`}>
                  {t(`admin_colleges.status_${d.college.status}`)}
                </span>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* MoU terms */}
                <section className="bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-3" data-testid="mou-section">
                  <h2 className="text-sm font-black text-[#0F1F3A] flex items-center gap-2"><FileSignature className="w-4 h-4 text-[#2B5CD0]" />{t("admin_colleges.mou_terms")}</h2>
                  {d.mou_terms.length === 0 && <p className="text-xs text-[#64748B]">{t("admin_colleges.no_mou")}</p>}
                  <ul className="space-y-2">
                    {d.mou_terms.map((m) => (
                      <li key={m.id} className="border border-[#F1F5F9] rounded-lg p-2.5 text-xs flex items-center justify-between gap-2" data-testid={`mou-${m.status}`}>
                        <span>{m.starts_on} → {m.ends_on} · {m.students_cap} {t("admin_colleges.students").toLowerCase()} · {m.lab_hours_per_student} {t("admin_colleges.lab_hours")}</span>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${STATUS_STYLE[m.status]}`}>{t(`admin_colleges.mou_${m.status}`)}</span>
                      </li>
                    ))}
                  </ul>
                  <form onSubmit={addMou} noValidate className="grid grid-cols-2 gap-2 pt-2 border-t border-[#F1F5F9]" data-testid="mou-form">
                    {input(mou.starts_on, (v) => setMou({ ...mou, starts_on: v }), "mou-starts", t("admin_colleges.starts_on"), "date")}
                    {input(mou.ends_on, (v) => setMou({ ...mou, ends_on: v }), "mou-ends", t("admin_colleges.ends_on"), "date")}
                    {input(mou.students_cap, (v) => setMou({ ...mou, students_cap: v }), "mou-cap", t("admin_colleges.students_cap"), "number")}
                    {input(mou.lab_hours_per_student, (v) => setMou({ ...mou, lab_hours_per_student: v }), "mou-lab", t("admin_colleges.lab_hours"), "number")}
                    {input(mou.ai_calls_per_day, (v) => setMou({ ...mou, ai_calls_per_day: v }), "mou-ai", t("admin_colleges.ai_calls"), "number")}
                    {input(mou.fee_per_student_inr, (v) => setMou({ ...mou, fee_per_student_inr: v }), "mou-fee", t("admin_colleges.fee"), "number")}
                    {mouError && <p className="col-span-2 text-xs text-red-600" role="alert" data-testid="mou-error">{mouError}</p>}
                    <div className="col-span-2 flex justify-end">
                      <button type="submit" disabled={busy} data-testid="mou-save" className="px-3.5 py-1.5 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg disabled:opacity-50">{t("admin_colleges.save_activate_mou")}</button>
                    </div>
                  </form>
                </section>

                {/* Feature switches */}
                <section className="bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-3" data-testid="features-section">
                  <h2 className="text-sm font-black text-[#0F1F3A] flex items-center gap-2"><ToggleLeft className="w-4 h-4 text-[#2B5CD0]" />{t("admin_colleges.features")}</h2>
                  <ul className="space-y-2">
                    {FEATURE_KEYS.map((k) => (
                      <li key={k} className="flex items-center justify-between text-xs">
                        <span>{t(`admin_colleges.feature_${k}`)}</span>
                        <button type="button" role="switch" aria-checked={!!d.features[k]} disabled={busy} data-testid={`feature-${k}`}
                          onClick={() => toggle(k, !d.features[k])}
                          className={`w-10 h-5 rounded-full relative transition-colors ${d.features[k] ? "bg-[#2BB3A0]" : "bg-[#CBD5E1]"}`}>
                          <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-all ${d.features[k] ? "left-5" : "left-0.5"}`} />
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              </div>

              {/* College admins */}
              <section className="bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-3" data-testid="admins-section">
                <h2 className="text-sm font-black text-[#0F1F3A] flex items-center gap-2"><UserPlus className="w-4 h-4 text-[#2B5CD0]" />{t("admin_colleges.college_admins")}</h2>
                {d.admins.length === 0 && <p className="text-xs text-[#64748B]">{t("admin_colleges.no_admins")}</p>}
                <ul className="text-xs space-y-1">
                  {d.admins.map((a) => <li key={a.id} data-testid="admin-row"><span className="font-bold">{a.name}</span> · {a.email}</li>)}
                </ul>
                {tempPassword && (
                  <div className="p-3 rounded-lg bg-[#FEF3C7] border border-[#FDE68A] text-xs space-y-1" data-testid="temp-password">
                    <p className="font-bold text-[#92400E]">{t("admin_colleges.temp_password_title")}</p>
                    <p>{tempPassword.email} · <code className="font-mono font-bold" data-testid="temp-password-value">{tempPassword.password}</code>
                      <button type="button" className="ml-2 inline-flex items-center gap-1 text-[#2B5CD0] font-bold"
                        onClick={() => navigator.clipboard?.writeText(tempPassword.password)}><Copy className="w-3 h-3" />{t("admin_colleges.copy")}</button></p>
                    <p className="text-[#92400E]">{t("admin_colleges.temp_password_note")}</p>
                  </div>
                )}
                <form onSubmit={addAdmin} noValidate className="grid grid-cols-1 md:grid-cols-4 gap-2 items-end" data-testid="admin-form">
                  {input(admin.name, (v) => setAdmin({ ...admin, name: v }), "admin-name", t("admin_colleges.admin_name"))}
                  {input(admin.email, (v) => setAdmin({ ...admin, email: v }), "admin-email", t("admin_colleges.admin_email"), "email")}
                  {input(admin.phone, (v) => setAdmin({ ...admin, phone: v }), "admin-phone", t("admin_colleges.admin_phone"), "tel")}
                  <button type="submit" disabled={busy} data-testid="admin-save" className="px-3.5 py-2 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg disabled:opacity-50">{t("admin_colleges.add_admin")}</button>
                  {adminError && <p className="md:col-span-4 text-xs text-red-600" role="alert" data-testid="admin-error">{adminError}</p>}
                </form>
              </section>
            </>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
