"use client";

/** Screen 02 · College settings (college admin). Spec: docs/screens/02-college-settings.md */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { downloadWithAuth } from "@/components/admin/AuditTabs";
import { useLanguage } from "@/lib/LanguageContext";
import { API_BASE, ApiError, authHeaders, fetchApi } from "@/lib/api";
import { Copy, FileDown, Palette, Users } from "lucide-react";

interface CollegeUser { id: string; name: string; email: string; phone: string | null; role: "college_admin" | "placement_officer"; is_active: boolean; is_me: boolean }
interface Settings { college: { id: string; name: string; code: string; city: string | null; state: string | null; status: string; logo_url: string | null; chat_retention_days: number }; users: CollegeUser[] }
interface Req { id: string; kind: "export" | "deletion"; student_id: string; student_name: string | null; reason: string; status: string; due_on: string; days_left: number | null; overdue: boolean; has_export: boolean; decision_note: string | null }
interface StudentHit { id: string; register_no: string; name: string; batch: string }

export default function CollegeSettingsPage() {
  const { t } = useLanguage();
  const [s, setS] = useState<Settings | null>(null);
  const [requests, setRequests] = useState<Req[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [userForm, setUserForm] = useState({ name: "", email: "", phone: "", role: "placement_officer" });
  const [temp, setTemp] = useState<{ email: string; password: string } | null>(null);
  const [brand, setBrand] = useState({ logo_url: "", chat_retention_days: "365" });
  const [brandSaved, setBrandSaved] = useState(false);
  const [search, setSearch] = useState("");
  const [hits, setHits] = useState<StudentHit[]>([]);
  const [picked, setPicked] = useState<StudentHit | null>(null);
  const [reqForm, setReqForm] = useState({ kind: "export", reason: "" });

  const load = useCallback(async () => {
    try {
      const [st, rq] = await Promise.all([
        fetchApi<Settings>("/college/settings"),
        fetchApi<{ items: Req[] }>("/college/data-requests"),
      ]);
      setS(st);
      setRequests(rq.items);
      setBrand({ logo_url: st.college.logo_url || "", chat_retention_days: String(st.college.chat_retention_days) });
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("college_settings.load_failed"));
    }
  }, [t]);

  useEffect(() => { load(); }, [load]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("college_settings.save_failed"));
    } finally {
      setBusy(false);
    }
  };

  const addUser = (e: React.FormEvent) => {
    e.preventDefault();
    if (userForm.name.trim().length < 2 || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(userForm.email.trim())) return setError(t("college_settings.err_user"));
    run(async () => {
      const r = await fetchApi<{ email: string; temporary_password?: string }>("/college/users", {
        method: "POST", body: JSON.stringify({ ...userForm, name: userForm.name.trim(), email: userForm.email.trim(), phone: userForm.phone.trim() || null }),
      });
      setTemp(r.temporary_password ? { email: r.email, password: r.temporary_password } : null);
      setUserForm({ name: "", email: "", phone: "", role: userForm.role });
    });
  };

  const toggleUser = (u: CollegeUser) => run(async () => {
    await fetchApi(`/college/users/${u.id}/${u.is_active ? "deactivate" : "reactivate"}`, { method: "POST" });
  });

  const saveBrand = (e: React.FormEvent) => {
    e.preventDefault();
    setBrandSaved(false);
    run(async () => {
      await fetchApi("/college/settings/branding", { method: "PUT", body: JSON.stringify({ logo_url: brand.logo_url.trim() || null, chat_retention_days: Number(brand.chat_retention_days) }) });
      setBrandSaved(true);
    });
  };

  useEffect(() => {
    if (search.trim().length < 2 || picked) { setHits([]); return; }
    const id = setTimeout(() => {
      fetchApi<{ students: StudentHit[] }>(`/college/students?search=${encodeURIComponent(search.trim())}`).then((r) => setHits(r.students)).catch(() => setHits([]));
    }, 250);
    return () => clearTimeout(id);
  }, [search, picked]);

  const raise = (e: React.FormEvent) => {
    e.preventDefault();
    if (!picked) return setError(t("college_settings.err_student"));
    if (reqForm.reason.trim().length < 10) return setError(t("college_settings.err_reason"));
    run(async () => {
      await fetchApi("/college/data-requests", { method: "POST", body: JSON.stringify({ student_id: picked.id, kind: reqForm.kind, reason: reqForm.reason.trim() }) });
      setPicked(null);
      setSearch("");
      setReqForm({ kind: "export", reason: "" });
    });
  };

  const download = (r: Req) => downloadWithAuth(`${API_BASE}/college/data-requests/${r.id}/export`, authHeaders(), `irep-export-${r.student_id}.json`)
    .catch(() => setError(t("college_settings.download_failed")));

  const inputCls = "w-full px-2.5 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg text-xs";

  return (
    <RoleGuard allowedRoles={["college"]}>
      <AppShell pageTitle={t("college_settings.title")}>
        <div className="space-y-4 max-w-6xl">
          {error && <p className="text-xs text-red-600" role="alert" data-testid="settings-error">{error}</p>}
          {s && (
            <p className="text-xs text-[#64748B]">{s.college.name} · {s.college.code} · {[s.college.city, s.college.state].filter(Boolean).join(", ")} — {t("college_settings.profile_note")}</p>
          )}

          {/* Users and roles */}
          <section className="bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-3" data-testid="users-section">
            <h2 className="text-sm font-black text-[#0F1F3A] flex items-center gap-2"><Users className="w-4 h-4 text-[#2B5CD0]" />{t("college_settings.users")}</h2>
            <ul className="divide-y divide-[#F1F5F9] text-xs">
              {s?.users.map((u) => (
                <li key={u.id} className="py-2 flex items-center justify-between gap-2" data-testid="user-row">
                  <div>
                    <span className="font-bold">{u.name}</span> · {u.email}
                    <span className="ml-2 px-2 py-0.5 rounded-full bg-[#EFF6FF] text-[#1D4ED8] text-[10px] font-bold">{t(`college_settings.role_${u.role}`)}</span>
                    {!u.is_active && <span className="ml-1 px-2 py-0.5 rounded-full bg-[#F1F5F9] text-[#64748B] text-[10px] font-bold">{t("college_settings.inactive")}</span>}
                  </div>
                  <button type="button" disabled={busy || u.is_me} onClick={() => toggleUser(u)} data-testid="user-toggle"
                    className="px-2.5 py-1 border border-[#CBD5E1] rounded font-bold disabled:opacity-40">
                    {u.is_active ? t("college_settings.deactivate") : t("college_settings.reactivate")}
                  </button>
                </li>
              ))}
            </ul>
            {temp && (
              <div className="p-3 rounded-lg bg-[#FEF3C7] border border-[#FDE68A] text-xs space-y-1" data-testid="user-temp-password">
                <p className="font-bold text-[#92400E]">{t("admin_colleges.temp_password_title")}</p>
                <p>{temp.email} · <code className="font-mono font-bold" data-testid="user-temp-password-value">{temp.password}</code>
                  <button type="button" className="ml-2 inline-flex items-center gap-1 text-[#2B5CD0] font-bold" onClick={() => navigator.clipboard?.writeText(temp.password)}><Copy className="w-3 h-3" />{t("admin_colleges.copy")}</button></p>
                <p className="text-[#92400E]">{t("admin_colleges.temp_password_note")}</p>
              </div>
            )}
            <form onSubmit={addUser} noValidate className="grid grid-cols-1 md:grid-cols-5 gap-2 items-end" data-testid="user-form">
              <input className={inputCls} placeholder={t("admin_colleges.admin_name")} value={userForm.name} data-testid="user-name" onChange={(e) => setUserForm({ ...userForm, name: e.target.value })} />
              <input className={inputCls} placeholder={t("admin_colleges.admin_email")} value={userForm.email} data-testid="user-email" onChange={(e) => setUserForm({ ...userForm, email: e.target.value })} />
              <input className={inputCls} placeholder={t("admin_colleges.admin_phone")} value={userForm.phone} onChange={(e) => setUserForm({ ...userForm, phone: e.target.value })} />
              <select className={inputCls} value={userForm.role} data-testid="user-role" onChange={(e) => setUserForm({ ...userForm, role: e.target.value })} aria-label={t("college_settings.role")}>
                <option value="placement_officer">{t("college_settings.role_placement_officer")}</option>
                <option value="college_admin">{t("college_settings.role_college_admin")}</option>
              </select>
              <button type="submit" disabled={busy} data-testid="user-save" className="px-3 py-1.5 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg disabled:opacity-50">{t("college_settings.add_user")}</button>
            </form>
          </section>

          {/* Branding and policy */}
          <form onSubmit={saveBrand} noValidate className="bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-3" data-testid="branding-form">
            <h2 className="text-sm font-black text-[#0F1F3A] flex items-center gap-2"><Palette className="w-4 h-4 text-[#2B5CD0]" />{t("college_settings.branding")}</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 items-end">
              <label className="text-[11px] font-bold md:col-span-2">{t("college_settings.logo_url")}
                <input className={`${inputCls} mt-1 font-normal`} value={brand.logo_url} data-testid="brand-logo" onChange={(e) => setBrand({ ...brand, logo_url: e.target.value })} placeholder="https://… or /logo.png" />
              </label>
              <label className="text-[11px] font-bold">{t("college_settings.retention")}
                <input type="number" className={`${inputCls} mt-1 font-normal`} value={brand.chat_retention_days} data-testid="brand-retention" onChange={(e) => setBrand({ ...brand, chat_retention_days: e.target.value })} />
              </label>
            </div>
            <p className="text-[11px] text-[#64748B]">{t("college_settings.retention_help")}</p>
            <div className="flex items-center gap-2">
              <button type="submit" disabled={busy} data-testid="brand-save" className="px-3 py-1.5 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg disabled:opacity-50">{t("college_settings.save")}</button>
              {brandSaved && <span className="text-xs text-[#166534] font-bold" data-testid="brand-saved">{t("college_settings.saved")}</span>}
            </div>
          </form>

          {/* Data requests (L27 -> screen 48) */}
          <section className="bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-3" data-testid="requests-section">
            <h2 className="text-sm font-black text-[#0F1F3A] flex items-center gap-2"><FileDown className="w-4 h-4 text-[#2B5CD0]" />{t("college_settings.data_requests")}</h2>
            <p className="text-[11px] text-[#64748B]">{t("college_settings.requests_help")}</p>
            <form onSubmit={raise} noValidate className="space-y-2" data-testid="request-form">
              <div className="relative">
                <input className={inputCls} placeholder={t("college_settings.find_student")} value={picked ? `${picked.name} · ${picked.register_no}` : search}
                  data-testid="request-student" onChange={(e) => { setPicked(null); setSearch(e.target.value); }} />
                {hits.length > 0 && (
                  <ul className="absolute z-10 left-0 right-0 mt-1 bg-white border border-[#E2E8F0] rounded-lg shadow text-xs max-h-48 overflow-auto">
                    {hits.map((h) => (
                      <li key={h.id}><button type="button" className="w-full text-left px-3 py-1.5 hover:bg-[#F8FAFC]" data-testid="student-hit" onClick={() => { setPicked(h); setHits([]); }}>
                        {h.name} · {h.register_no} · {h.batch}</button></li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                <select className={inputCls} value={reqForm.kind} data-testid="request-kind" onChange={(e) => setReqForm({ ...reqForm, kind: e.target.value })} aria-label={t("college_settings.kind")}>
                  <option value="export">{t("admin_audit.kind_export")}</option>
                  <option value="deletion">{t("admin_audit.kind_deletion")}</option>
                </select>
                <input className={`${inputCls} md:col-span-2`} placeholder={t("college_settings.reason")} value={reqForm.reason} data-testid="request-reason" onChange={(e) => setReqForm({ ...reqForm, reason: e.target.value })} />
                <button type="submit" disabled={busy} data-testid="request-save" className="px-3 py-1.5 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg disabled:opacity-50">{t("college_settings.raise")}</button>
              </div>
            </form>
            <ul className="divide-y divide-[#F1F5F9] text-xs">
              {requests.length === 0 && <li className="py-2 text-[#64748B]">{t("admin_audit.no_requests")}</li>}
              {requests.map((r) => (
                <li key={r.id} className="py-2 flex flex-wrap items-center justify-between gap-2" data-testid="college-request">
                  <div>
                    <span className="font-bold">{t(`admin_audit.kind_${r.kind}`)}</span> · {r.student_name || r.student_id}
                    <span className="ml-2 text-[#64748B]">{t(`admin_audit.status_${r.status}`)}</span>
                    {r.days_left !== null && <span className={`ml-2 ${r.overdue ? "text-[#DC2626] font-bold" : "text-[#64748B]"}`}>{r.overdue ? t("admin_audit.overdue") : `${t("admin_audit.due_in")} ${r.days_left} ${t("admin_audit.days")}`}</span>}
                    {r.decision_note && <div className="text-[11px] text-[#64748B]">{t("admin_audit.decision")}: {r.decision_note}</div>}
                  </div>
                  {r.has_export && (
                    <button type="button" onClick={() => download(r)} data-testid="college-request-download" className="px-2.5 py-1 border border-[#CBD5E1] rounded font-bold">{t("admin_audit.download")}</button>
                  )}
                </li>
              ))}
            </ul>
          </section>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
