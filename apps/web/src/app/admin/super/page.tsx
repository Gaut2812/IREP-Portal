"use client";

/** Super admin (docs/PERMISSIONS.md): IREP staff accounts and logged support sessions.
 *  Only the super admin sees this page; the API answers 403 to everyone else. Every action here is
 *  written to the audit log, and staff accounts must sign in with two-factor (Keycloak). */
import React, { useCallback, useEffect, useState } from "react";
import { KeyRound, LifeBuoy, ShieldCheck, UserPlus } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";

type StaffRole = "irep_admin" | "super_admin";
interface Staff { id: string; name: string; email: string; role: StaffRole; is_active: boolean; two_factor: string; is_you: boolean }
interface Session {
  id: string; college_id: string; college_name: string | null; staff_name: string | null; reason: string;
  opened_at: string; expires_at: string; ended_at: string | null; active: boolean;
}
interface College { id: string; name: string }

const fmt = (iso: string) => new Date(iso + (iso.endsWith("Z") ? "" : "Z")).toLocaleString();

export default function SuperAdminPage() {
  const { t } = useLanguage();
  const [staff, setStaff] = useState<Staff[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [colleges, setColleges] = useState<College[]>([]);
  const [forbidden, setForbidden] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [invite, setInvite] = useState({ name: "", email: "", role: "irep_admin" as StaffRole });
  const [invited, setInvited] = useState<{ email: string; password?: string } | null>(null);
  const [sess, setSess] = useState({ college_id: "", minutes: "60", reason: "" });

  const load = useCallback(async () => {
    try {
      const [s, ss, c] = await Promise.all([
        fetchApi<{ items: Staff[] }>("/admin/staff"),
        fetchApi<{ items: Session[] }>("/admin/support-sessions"),
        fetchApi<{ colleges: College[] }>("/admin/colleges"),
      ]);
      setStaff(s.items); setSessions(ss.items); setColleges(c.colleges); setError("");
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) setForbidden(true);
      else setError(e instanceof ApiError ? String(e.detail) : t("super_admin.load_failed"));
    }
  }, [t]);
  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError("");
    try { await fn(); await load(); }
    catch (e) { setError(e instanceof ApiError ? String(e.detail) : t("super_admin.action_failed")); }
    finally { setBusy(false); }
  };

  const sendInvite = (e: React.FormEvent) => {
    e.preventDefault();
    if (invite.name.trim().length < 2 || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(invite.email.trim())) { setError(t("super_admin.invite_invalid")); return; }
    act(async () => {
      const r = await fetchApi<{ email: string; temporary_password?: string }>("/admin/staff", { method: "POST", body: JSON.stringify({ ...invite, email: invite.email.trim(), name: invite.name.trim() }) });
      setInvited({ email: r.email, password: r.temporary_password });
      setInvite({ name: "", email: "", role: "irep_admin" });
    });
  };

  const openSession = (e: React.FormEvent) => {
    e.preventDefault();
    if (!sess.college_id || sess.reason.trim().length < 10) { setError(t("super_admin.session_invalid")); return; }
    act(() => fetchApi("/admin/support-sessions", { method: "POST", body: JSON.stringify({ college_id: sess.college_id, minutes: Number(sess.minutes), reason: sess.reason.trim() }) })
      .then(() => setSess({ college_id: "", minutes: "60", reason: "" })));
  };

  const card = "bg-white rounded-card border border-line p-4 space-y-3";
  const field = "px-2.5 py-1.5 border border-line-strong rounded-tile text-xs";

  return (
    <RoleGuard allowedRoles={["admin"]}>
      <AppShell pageTitle={t("super_admin.title")}>
        <div className="space-y-6 max-w-5xl">
          {forbidden ? (
            <div className={card} data-testid="super-forbidden">
              <p className="text-sm font-semibold text-ink">{t("super_admin.only_title")}</p>
              <p className="text-xs text-muted">{t("super_admin.only_body")}</p>
            </div>
          ) : (
            <>
              <p className="text-xs text-muted flex items-center gap-1.5" data-testid="super-help"><ShieldCheck className="w-4 h-4 text-teal" />{t("super_admin.help")}</p>
              {error && <p className="text-xs text-red-600" role="alert" data-testid="super-error">{error}</p>}

              <section className={card} data-testid="staff-section">
                <h2 className="text-sm font-semibold text-ink flex items-center gap-2"><KeyRound className="w-4 h-4 text-brand" />{t("super_admin.staff")}</h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead><tr className="text-left text-muted border-b border-line">
                      <th className="py-2 pr-2">{t("super_admin.name")}</th><th className="pr-2">{t("super_admin.role")}</th>
                      <th className="pr-2">{t("super_admin.two_factor")}</th><th className="pr-2">{t("super_admin.status")}</th><th />
                    </tr></thead>
                    <tbody>
                      {staff.map((s) => (
                        <tr key={s.id} className="border-b border-line-soft" data-testid="staff-row">
                          <td className="py-2 pr-2"><div className="font-semibold text-ink">{s.name}{s.is_you && <span className="text-muted font-normal"> ({t("super_admin.you")})</span>}</div><div className="text-muted">{s.email}</div></td>
                          <td className="pr-2">
                            <select value={s.role} disabled={busy || s.is_you} aria-label={t("super_admin.role")} data-testid="staff-role" className={field}
                              onChange={(e) => act(() => fetchApi(`/admin/staff/${s.id}/role`, { method: "PUT", body: JSON.stringify({ role: e.target.value }) }))}>
                              <option value="irep_admin">{t("super_admin.role_irep_admin")}</option>
                              <option value="super_admin">{t("super_admin.role_super_admin")}</option>
                            </select>
                          </td>
                          <td className="pr-2"><span className="px-2 py-0.5 rounded-full text-caption font-semibold bg-success-soft text-success">{t("super_admin.required")}</span></td>
                          <td className="pr-2" data-testid="staff-status">{s.is_active ? t("super_admin.active") : t("super_admin.deactivated")}</td>
                          <td className="text-right">
                            {!s.is_you && (s.is_active
                              ? <button type="button" disabled={busy} data-testid="staff-deactivate" onClick={() => act(() => fetchApi(`/admin/staff/${s.id}/deactivate`, { method: "POST" }))} className="px-2.5 py-1 border border-line-strong rounded-tile font-semibold">{t("super_admin.deactivate")}</button>
                              : <button type="button" disabled={busy} data-testid="staff-reactivate" onClick={() => act(() => fetchApi(`/admin/staff/${s.id}/reactivate`, { method: "POST" }))} className="px-2.5 py-1 border border-line-strong rounded-tile font-semibold">{t("super_admin.reactivate")}</button>)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <form onSubmit={sendInvite} noValidate className="flex flex-wrap gap-2 items-end pt-2 border-t border-line-soft" data-testid="staff-invite">
                  <UserPlus className="w-4 h-4 text-brand mb-1.5" />
                  <input value={invite.name} onChange={(e) => setInvite({ ...invite, name: e.target.value })} placeholder={t("super_admin.name")} aria-label={t("super_admin.name")} data-testid="invite-name" className={field} />
                  <input value={invite.email} onChange={(e) => setInvite({ ...invite, email: e.target.value })} placeholder={t("super_admin.email")} aria-label={t("super_admin.email")} data-testid="invite-email" className={`${field} min-w-[220px]`} />
                  <select value={invite.role} onChange={(e) => setInvite({ ...invite, role: e.target.value as StaffRole })} aria-label={t("super_admin.role")} data-testid="invite-role" className={field}>
                    <option value="irep_admin">{t("super_admin.role_irep_admin")}</option>
                    <option value="super_admin">{t("super_admin.role_super_admin")}</option>
                  </select>
                  <button type="submit" disabled={busy} data-testid="invite-send" className="px-3.5 py-1.5 bg-brand text-white text-xs font-semibold rounded-tile disabled:opacity-50">{t("super_admin.invite")}</button>
                </form>
                {invited && (
                  <p className="text-caption text-success bg-success-faint rounded-tile p-2" data-testid="invite-result">
                    {invited.password ? `${t("super_admin.invited_dev")} ${invited.email}: ${invited.password}` : `${t("super_admin.invited")} ${invited.email}`}
                  </p>
                )}
              </section>

              <section className={card} data-testid="sessions-section">
                <h2 className="text-sm font-semibold text-ink flex items-center gap-2"><LifeBuoy className="w-4 h-4 text-brand" />{t("super_admin.sessions")}</h2>
                <p className="text-caption text-muted">{t("super_admin.sessions_help")}</p>
                <form onSubmit={openSession} noValidate className="flex flex-wrap gap-2 items-end" data-testid="session-form">
                  <select value={sess.college_id} onChange={(e) => setSess({ ...sess, college_id: e.target.value })} aria-label={t("super_admin.college")} data-testid="session-college" className={field}>
                    <option value="">{t("super_admin.choose_college")}</option>
                    {colleges.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                  <select value={sess.minutes} onChange={(e) => setSess({ ...sess, minutes: e.target.value })} aria-label={t("super_admin.minutes")} data-testid="session-minutes" className={field}>
                    {["15", "30", "60", "120", "240"].map((m) => <option key={m} value={m}>{m} {t("super_admin.min")}</option>)}
                  </select>
                  <input value={sess.reason} onChange={(e) => setSess({ ...sess, reason: e.target.value })} placeholder={t("super_admin.reason")} aria-label={t("super_admin.reason")} data-testid="session-reason" className={`${field} flex-1 min-w-[220px]`} />
                  <button type="submit" disabled={busy} data-testid="session-open" className="px-3.5 py-1.5 bg-brand text-white text-xs font-semibold rounded-tile disabled:opacity-50">{t("super_admin.open_session")}</button>
                </form>
                {sessions.length === 0 && <p className="text-xs text-muted">{t("super_admin.no_sessions")}</p>}
                <ul className="space-y-2">
                  {sessions.map((s) => (
                    <li key={s.id} className="border border-line-soft rounded-tile p-2.5 text-xs flex flex-wrap items-center justify-between gap-2" data-testid="session-row">
                      <div>
                        <div className="font-semibold text-ink">{s.college_name} · {s.staff_name}</div>
                        <div className="text-muted">{s.reason}</div>
                        <div className="text-subtle">{fmt(s.opened_at)} → {fmt(s.ended_at || s.expires_at)}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 rounded-full text-caption font-semibold ${s.active ? "bg-success-soft text-success" : "bg-line-soft text-ink-soft"}`} data-testid="session-state">
                          {s.active ? t("super_admin.session_active") : t("super_admin.session_closed")}
                        </span>
                        {s.active && <button type="button" disabled={busy} data-testid="session-end" onClick={() => act(() => fetchApi(`/admin/support-sessions/${s.id}/end`, { method: "POST" }))} className="px-2.5 py-1 border border-line-strong rounded-tile font-semibold">{t("super_admin.end_session")}</button>}
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            </>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
