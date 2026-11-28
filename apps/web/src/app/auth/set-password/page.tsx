"use client";

/** Phase 5 · Set your password (local sign-in): the one-time invitation link lands here as
 *  /auth/set-password#token=…. The token is read from the fragment (never sent to the web server), dropped from
 *  the address bar at once, checked with the API, and exchanged for a password and a session. In Keycloak mode
 *  Keycloak's own email link is used instead, and this page says so. */
import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/AuthContext";
import { useLanguage } from "@/lib/LanguageContext";
import { API_BASE } from "@/lib/api";
import { BrandMark } from "@/components/ui";

interface Invite { email: string; name: string | null; role: string; college: string | null; expires_at: string | null; min_length: number }

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : "";
    throw Object.assign(new Error(detail), { status: res.status, detail });
  }
  return data as T;
}

export default function SetPasswordPage() {
  const { login } = useAuth();
  const { t, language, setLanguage } = useLanguage();
  const token = useRef<string>("");
  const [invite, setInvite] = useState<Invite | null>(null);
  const [problem, setProblem] = useState<"" | "invalid" | "expired" | "sso">("");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const m = /(?:^|[#&])token=([^&]+)/.exec(window.location.hash);
    token.current = m ? decodeURIComponent(m[1]) : "";
    window.history.replaceState(null, "", "/auth/set-password");        // the token leaves the address bar and history
    if (!token.current) return setProblem("invalid");
    post<Invite>("/auth/invitations/lookup", { token: token.current })
      .then(setInvite)
      .catch((e) => setProblem(e.status === 410 && /single sign-on/i.test(e.detail) ? "sso" : e.status === 410 ? "expired" : "invalid"));
  }, []);

  const min = invite?.min_length ?? 10;
  const checks = [
    { ok: pw.length >= min, label: t("set_password.rule_length").replace("{n}", String(min)) },
    { ok: /[A-Za-z]/.test(pw) && /\d/.test(pw), label: t("set_password.rule_mix") },
    { ok: pw.length > 0 && pw === pw2, label: t("set_password.rule_match") },
  ];

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!checks.every((c) => c.ok)) return setError(t("set_password.err_rules"));
    setBusy(true);
    try {
      const data = await post<{ access_token: string; user: never }>("/auth/invitations/accept", { token: token.current, password: pw });
      setLanguage(language, true);
      login(data.access_token, data.user);
    } catch (err) {
      const ex = err as { status?: number; detail?: string };
      if (ex.status === 410) setProblem("expired");
      else if (ex.status === 404) setProblem("invalid");
      else setError(ex.detail || t("set_password.err_generic"));
    } finally {
      setBusy(false);
    }
  };

  const field = "w-full px-3 py-2.5 bg-surface-2 border border-line rounded-tile text-sm";
  return (
    <div className="min-h-screen flex items-center justify-center bg-danger-soft p-6">
      <div className="w-full max-w-sm bg-white rounded-card shadow-pop border border-line p-8 space-y-5" data-testid="set-password">
        <div className="flex items-center justify-between">
          <BrandMark className="w-10 h-10" />
          <button type="button" onClick={() => setLanguage(language === "ta" ? "en" : "ta", false)} data-testid="set-password-lang"
            className="text-caption font-semibold text-brand">{language === "ta" ? "English" : "தமிழ்"}</button>
        </div>
        {problem ? (
          <div className="space-y-3 text-center" role="alert" data-testid={`set-password-${problem}`}>
            <h1 className="text-base font-semibold text-ink">{t(`set_password.${problem}_title`)}</h1>
            <p className="text-xs text-ink-soft">{t(`set_password.${problem}_body`)}</p>
            <Link href="/login" className="inline-block px-4 py-2.5 bg-brand text-white text-xs font-semibold rounded-card">{t("auth.back_to_login")}</Link>
          </div>
        ) : !invite ? (
          <p className="text-sm text-ink text-center">{t("set_password.checking")}</p>
        ) : (
          <form onSubmit={submit} className="space-y-4" noValidate>
            <div>
              <h1 className="text-base font-semibold text-ink">{t("set_password.title")}</h1>
              <p className="text-xs text-ink-soft mt-1" data-testid="set-password-who">
                {t("set_password.welcome").replace("{name}", invite.name || invite.email)}{invite.college ? ` · ${invite.college}` : ""}
              </p>
              <p className="text-caption text-muted mt-0.5">{invite.email}</p>
            </div>
            <label className="block text-caption font-semibold text-muted">{t("set_password.new")}
              <input type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} className={field} data-testid="set-password-new" />
            </label>
            <label className="block text-caption font-semibold text-muted">{t("set_password.again")}
              <input type="password" autoComplete="new-password" value={pw2} onChange={(e) => setPw2(e.target.value)} className={field} data-testid="set-password-again" />
            </label>
            <ul className="space-y-1" aria-live="polite">
              {checks.map((c) => (
                <li key={c.label} className={`text-caption ${c.ok ? "text-success" : "text-muted"}`}>{c.ok ? "✓" : "•"} {c.label}</li>
              ))}
            </ul>
            {error && <p className="text-xs text-danger" role="alert" data-testid="set-password-error">{error}</p>}
            <button type="submit" disabled={busy} data-testid="set-password-submit"
              className="w-full px-4 py-2.5 bg-brand text-white text-sm font-semibold rounded-card disabled:opacity-50">{t("set_password.submit")}</button>
          </form>
        )}
      </div>
    </div>
  );
}
