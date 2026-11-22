"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth, Role } from "@/lib/AuthContext";
import { useLanguage } from "@/lib/LanguageContext";
import { fetchApi, ApiError } from "@/lib/api";
import { AuthConfig, getAuthConfig, startKeycloakSignIn } from "@/lib/oidc";
import { GraduationCap, Users, UserCheck, Building2, Languages, ArrowRight, ShieldCheck } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const { language, setLanguage, t } = useLanguage();

  const [selectedRole, setSelectedRole] = useState<Role>("student");
  const [identifier, setIdentifier] = useState("priya.r@demo.edu");
  const [password, setPassword] = useState("password123");
  const [phone, setPhone] = useState("9876543210");
  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [otpChannel, setOtpChannel] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [demoOtp, setDemoOtp] = useState<string | null>(null);
  const [langTouched, setLangTouched] = useState(false);
  const [authCfg, setAuthCfg] = useState<AuthConfig>({ provider: "local" });
  const [reauth2fa, setReauth2fa] = useState(false);

  useEffect(() => {
    getAuthConfig().then(setAuthCfg);
    // IREP staff sent back by the API: sign in again with the authenticator code
    if (new URLSearchParams(window.location.search).get("reauth") === "2fa") {
      setReauth2fa(true);
      setSelectedRole("admin");
      setIdentifier("staff@irep.demo");          // same default as the IREP staff link
    }
  }, []);

  // Keycloak mode: staff and students use single sign-on; parents keep mobile OTP
  const sso = authCfg.provider === "keycloak" && selectedRole !== "parent";

  const roleConfigs = [
    { id: "student" as Role, title: t("login.roles.student"), icon: GraduationCap, defaultEmail: "priya.r@demo.edu" },
    { id: "parent" as Role, title: t("login.roles.parent"), icon: Users, defaultEmail: "ramesh.k@example.com" },
    { id: "trainer" as Role, title: t("login.roles.trainer"), icon: UserCheck, defaultEmail: "arun.k@demo.edu" },
    { id: "college" as Role, title: t("login.roles.college"), icon: Building2, defaultEmail: "admin@demo.edu" },
    // IREP staff (screens 45-49): reached from the small link under the grid, not a card
    { id: "admin" as Role, title: t("login.roles.admin"), icon: ShieldCheck, defaultEmail: "staff@irep.demo" },
  ];

  const handleRoleSelect = (role: Role) => {
    setSelectedRole(role);
    setError("");
    setFieldErrors({});
    setOtpSent(false);
    setOtp("");
    const cfg = roleConfigs.find(r => r.id === role);
    if (cfg) setIdentifier(cfg.defaultEmail);
  };

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (selectedRole === "parent") {
      if (phone.replace(/\D/g, "").length < 10) errs.phone = t("login.err_phone");
      if (otpSent && !/^\d{6}$/.test(otp.trim())) errs.otp = t("login.err_otp");
    } else if (!sso) {
      if (!identifier.trim()) errs.identifier = t("login.err_identifier");
      if (!password) errs.password = t("login.err_password");
    }
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const finish = (data: { access_token: string; user: any }) => {
    login(data.access_token, data.user);
    const pref = data.user?.language_pref;
    if (langTouched) setLanguage(language, true);            // choice made on this screen is saved
    else if (pref === "en" || pref === "ta") setLanguage(pref, false);   // otherwise use the saved preference
  };

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!validate()) return;
    setLoading(true);
    try {
      if (sso) {
        await startKeycloakSignIn(authCfg, language, { forceLogin: reauth2fa });   // leaves the page
        return;
      }
      if (selectedRole === "parent") {
        if (!otpSent) {
          const data = await fetchApi<{ demo_otp?: string; message: string; channel?: string }>("/auth/parent/otp/request", { method: "POST", body: JSON.stringify({ phone }) });
          setOtpSent(true);
          setOtpChannel(data.channel || null);
          setDemoOtp(data.demo_otp || null);
          return;
        }
        finish(await fetchApi("/auth/parent/otp/verify", { method: "POST", body: JSON.stringify({ phone, otp: otp.trim() }) }));
        return;
      }
      finish(await fetchApi("/auth/login", { method: "POST", body: JSON.stringify({ role: selectedRole, identifier: identifier.trim(), password }) }));
    } catch (err: any) {
      // No offline fallback: a failed sign-in never logs anyone in.
      setError(err instanceof ApiError ? err.detail : t("login.err_offline"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col md:flex-row w-full font-sans">
      {/* LEFT PANEL (~60%): Navy-to-Teal Gradient */}
      <div className="hidden md:flex md:w-[58%] bg-gradient-to-br from-[#14284B] via-[#1E3A6E] to-[#1E6B7B] text-white p-12 flex-col justify-between relative overflow-hidden">
        {/* Subtle decorative circles */}
        <div className="absolute top-0 right-0 -mt-16 -mr-16 w-80 h-80 rounded-full bg-white/5 blur-2xl" />
        <div className="absolute bottom-0 left-0 -mb-20 -ml-20 w-96 h-96 rounded-full bg-[#2BB3A0]/10 blur-3xl" />

        {/* Brand */}
        <div className="flex items-center gap-3 z-10">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#2BB3A0] to-[#2B5CD0] flex items-center justify-center font-bold text-white text-lg shadow-lg">
            IR
          </div>
          <div>
            <div className="font-extrabold text-xl tracking-tight leading-none">IREP Portal</div>
            <div className="text-xs text-[#94A3B8] font-medium tracking-wide mt-1">Industry-Ready Engineer Program</div>
          </div>
        </div>

        {/* Headline & Description */}
        <div className="max-w-xl z-10 space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 backdrop-blur-md text-xs font-semibold text-[#2BB3A0] border border-white/15">
            <ShieldCheck className="w-4 h-4" /> B.Tech Semesters 2 to 7
          </div>
          <h1 className="text-3xl lg:text-4xl font-extrabold leading-tight text-white tracking-tight">
            {t("login.hero_headline")}
          </h1>
          <p className="text-[#CBD5E1] text-sm lg:text-base leading-relaxed">
            {t("login.hero_subline")}
          </p>

          {/* 3 Stats from Mockup */}
          <div className="grid grid-cols-3 gap-4 pt-4 border-t border-white/15">
            <div>
              <div className="text-2xl font-black text-[#2BB3A0]">576</div>
              <div className="text-xs text-[#94A3B8] font-medium mt-0.5">{t("login.stats_hours")}</div>
            </div>
            <div>
              <div className="text-2xl font-black text-white">6</div>
              <div className="text-xs text-[#94A3B8] font-medium mt-0.5">{t("login.stats_projects")}</div>
            </div>
            <div>
              <div className="text-2xl font-black text-[#2BB3A0]">4</div>
              <div className="text-xs text-[#94A3B8] font-medium mt-0.5">{t("login.stats_roles")}</div>
            </div>
          </div>
        </div>

        {/* Footer info */}
        <div className="text-xs text-[#94A3B8] z-10 flex items-center justify-between">
          <span>Demo Engineering College · Autonomous Institute</span>
          <span>v1.0 (2026)</span>
        </div>
      </div>

      {/* RIGHT PANEL: Pink Background with Centered White Card */}
      <div className="flex-1 bg-[#FDE8E8] flex items-center justify-center p-6 md:p-12 relative">
        {/* Language switch button top right */}
        <div className="absolute top-6 right-6">
          <button
            onClick={() => { setLangTouched(true); setLanguage(language === "en" ? "ta" : "en", false); }}
            data-testid="login-lang"
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white shadow-sm border border-[#E2E8F0] rounded-lg text-xs font-bold text-[#0F1F3A] hover:bg-[#F8FAFC] transition-all"
          >
            <Languages className="w-3.5 h-3.5 text-[#2B5CD0]" />
            <span>{language === "en" ? "தமிழ்" : "English"}</span>
          </button>
        </div>

        {/* Centered White Card (PDF 1) */}
        <div className="w-full max-w-md bg-white rounded-2xl shadow-xl border border-[#E2E8F0] p-8 space-y-6">
          <div>
            <h2 className="text-2xl font-black text-[#881337] tracking-tight">{t("login.welcome")}</h2>
            <p className="text-xs text-[#64748B] mt-1 font-medium">{t("login.choose_role")}</p>
          </div>

          {/* 2 by 2 Role Grid */}
          <div className="grid grid-cols-2 gap-2.5">
            {roleConfigs.filter((r) => r.id !== "admin").map((r) => {
              const Icon = r.icon;
              const isSelected = selectedRole === r.id;
              return (
                <button
                  key={r.id}
                  type="button"
                  data-testid={`role-${r.id}`}
                  aria-pressed={isSelected}
                  onClick={() => handleRoleSelect(r.id)}
                  className={`flex items-center gap-2.5 p-3 rounded-xl border text-left transition-all ${
                    isSelected
                      ? "border-[#2B5CD0] bg-[#EFF6FF] text-[#2B5CD0] font-bold shadow-sm ring-1 ring-[#2B5CD0]"
                      : "border-[#E2E8F0] bg-white text-[#0F1F3A] hover:bg-[#F8FAFC]"
                  }`}
                >
                  <div className={`p-2 rounded-lg ${isSelected ? "bg-[#2B5CD0] text-white" : "bg-[#F1F5F9] text-[#64748B]"}`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-semibold leading-none">{r.title}</div>
                    <div className="text-[10px] text-[#64748B] font-normal mt-0.5">
                      {r.id === "student" ? t("login.sem_hint") : (r.id === "parent" ? t("login.otp_hint") : t("login.staff_hint"))}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          <button
            type="button"
            data-testid="role-admin"
            aria-pressed={selectedRole === "admin"}
            onClick={() => handleRoleSelect("admin")}
            className={`w-full text-[11px] font-semibold underline-offset-2 hover:underline ${selectedRole === "admin" ? "text-[#2B5CD0]" : "text-[#64748B]"}`}
          >
            {t("login.staff_link")}
          </button>

          {reauth2fa && (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 font-medium" role="status" data-testid="login-reauth-2fa">
              {t("login.reauth_2fa")}
            </div>
          )}
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-600 font-medium" role="alert" data-testid="login-error">
              {error}
            </div>
          )}

          {/* Login Form */}
          <form onSubmit={handleSignIn} className="space-y-4" noValidate>
            {selectedRole === "parent" ? (
              /* Parent Mobile + OTP view */
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-bold text-[#0F1F3A] mb-1">{t("login.phone_label")}</label>
                  <input
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder={t("login.phone_placeholder")}
                    disabled={otpSent}
                    aria-invalid={!!fieldErrors.phone}
                    data-testid="login-phone"
                    className={`w-full px-3.5 py-2.5 bg-[#F8FAFC] border ${fieldErrors.phone ? "border-red-400" : "border-[#E2E8F0]"} rounded-xl text-xs text-[#0F1F3A] focus:outline-none focus:border-[#2B5CD0] focus:bg-white transition-all disabled:opacity-70`}
                  />
                  {fieldErrors.phone && <p className="text-[11px] text-red-600 mt-1">{fieldErrors.phone}</p>}
                  {otpSent && <button type="button" onClick={() => { setOtpSent(false); setOtp(""); setDemoOtp(null); }} className="text-[11px] text-[#2B5CD0] underline mt-1">{t("login.resend")}</button>}
                </div>

                {otpSent && (
                  <div>
                    <div className="flex justify-between items-center mb-1">
                      <label className="block text-xs font-bold text-[#0F1F3A]">{t("login.otp_label")}</label>
                      {demoOtp ? <span className="text-[10px] text-[#2BB3A0] font-bold" data-testid="demo-otp">{t("login.demo_otp").replace("{otp}", demoOtp)}</span> : <span className="text-[10px] text-[#64748B]" data-testid="otp-sent">{t(otpChannel === "email" ? "login.otp_sent_email" : "login.otp_sent")}</span>}
                    </div>
                    <input
                      type="text"
                      maxLength={6}
                      value={otp}
                      onChange={(e) => setOtp(e.target.value)}
                      placeholder={t("login.otp_placeholder")}
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      aria-invalid={!!fieldErrors.otp}
                      data-testid="login-otp"
                      className={`w-full px-3.5 py-2.5 bg-[#F8FAFC] border ${fieldErrors.otp ? "border-red-400" : "border-[#E2E8F0]"} rounded-xl text-xs text-[#0F1F3A] tracking-widest font-mono text-center focus:outline-none focus:border-[#2B5CD0] focus:bg-white transition-all`}
                    />
                    {fieldErrors.otp && <p className="text-[11px] text-red-600 mt-1">{fieldErrors.otp}</p>}
                  </div>
                )}
              </div>
            ) : sso ? (
              /* Keycloak single sign-on */
              <p className="text-xs text-[#64748B] leading-relaxed" data-testid="login-sso-hint">{t("login.sso_hint")}</p>
            ) : (
              /* Student / Trainer / College Username + Password view */
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-bold text-[#0F1F3A] mb-1">
                    {selectedRole === "student" ? t("login.student_id_label") : t("login.staff_id_label")}
                  </label>
                  <input
                    type="text"
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    placeholder={t("login.id_placeholder")}
                    aria-invalid={!!fieldErrors.identifier}
                    data-testid="login-identifier"
                    className={`w-full px-3.5 py-2.5 bg-[#F8FAFC] border ${fieldErrors.identifier ? "border-red-400" : "border-[#E2E8F0]"} rounded-xl text-xs text-[#0F1F3A] focus:outline-none focus:border-[#2B5CD0] focus:bg-white transition-all`}
                  />
                  {fieldErrors.identifier && <p className="text-[11px] text-red-600 mt-1">{fieldErrors.identifier}</p>}
                </div>

                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="block text-xs font-bold text-[#0F1F3A]">{t("login.password_label")}</label>
                    <span className="text-[10px] text-[#64748B]">{t("login.demo_password")}</span>
                  </div>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    aria-invalid={!!fieldErrors.password}
                    data-testid="login-password"
                    className={`w-full px-3.5 py-2.5 bg-[#F8FAFC] border ${fieldErrors.password ? "border-red-400" : "border-[#E2E8F0]"} rounded-xl text-xs text-[#0F1F3A] focus:outline-none focus:border-[#2B5CD0] focus:bg-white transition-all`}
                  />
                  {fieldErrors.password && <p className="text-[11px] text-red-600 mt-1">{fieldErrors.password}</p>}
                </div>
              </div>
            )}

            {/* Full-width primary action button */}
            <button
              type="submit"
              disabled={loading}
              data-testid="login-submit"
              className="w-full py-3 px-4 bg-[#2B5CD0] hover:bg-[#1E46B0] text-white font-bold text-xs rounded-xl shadow-md transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
            >
              <span>
                {selectedRole === "parent"
                  ? (otpSent ? t("login.verify_otp_btn") : t("login.get_otp_btn"))
                  : (sso ? t("login.sso_btn") : t("login.sign_in_btn"))}
              </span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </form>

          {/* Footer remark */}
          <div className="pt-2 text-center text-[11px] text-[#64748B]">
            {t("login.parent_help")}
          </div>
        </div>
      </div>
    </div>
  );
}

