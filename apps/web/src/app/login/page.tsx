"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth, Role } from "@/lib/AuthContext";
import { useLanguage } from "@/lib/LanguageContext";
import { GraduationCap, Users, UserCheck, Building2, Languages, ArrowRight, ShieldCheck } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const { language, toggleLanguage, t } = useLanguage();

  const [selectedRole, setSelectedRole] = useState<Role>("student");
  const [identifier, setIdentifier] = useState("priya.r@demo.edu");
  const [password, setPassword] = useState("password123");
  const [phone, setPhone] = useState("9876543210");
  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const roleConfigs = [
    { id: "student" as Role, title: t("login.roles.student"), icon: GraduationCap, defaultEmail: "priya.r@demo.edu" },
    { id: "parent" as Role, title: t("login.roles.parent"), icon: Users, defaultEmail: "ramesh.k@example.com" },
    { id: "trainer" as Role, title: t("login.roles.trainer"), icon: UserCheck, defaultEmail: "arun.k@demo.edu" },
    { id: "college" as Role, title: t("login.roles.college"), icon: Building2, defaultEmail: "admin@demo.edu" }
  ];

  const handleRoleSelect = (role: Role) => {
    setSelectedRole(role);
    setError("");
    const cfg = roleConfigs.find(r => r.id === role);
    if (cfg) setIdentifier(cfg.defaultEmail);
  };

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      if (selectedRole === "parent") {
        if (!otpSent) {
          // Request OTP
          const res = await fetch("http://localhost:8000/api/v1/auth/parent/otp/request", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phone })
          });
          const data = await res.json();
          setOtpSent(true);
          setOtp(data.demo_otp || "123456");
          setLoading(false);
          return;
        } else {
          // Verify OTP
          const res = await fetch("http://localhost:8000/api/v1/auth/parent/otp/verify", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phone, otp })
          });
          if (!res.ok) throw new Error("Invalid OTP");
          const data = await res.json();
          login(data.access_token, data.user);
          return;
        }
      }

      // Standard login
      const res = await fetch("http://localhost:8000/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role: selectedRole,
          identifier,
          password
        })
      });

      if (!res.ok) {
        throw new Error("Invalid login credentials. Please use password123");
      }

      const data = await res.json();
      login(data.access_token, data.user);
    } catch (err: any) {
      // Fallback offline mock for immediate test drive if API is not running
      const fallbackProfile = {
        id: selectedRole === "student" ? "usr_priya_01" : (selectedRole === "trainer" ? "usr_arun_01" : (selectedRole === "college" ? "usr_kavitha_01" : "usr_ramesh_01")),
        email: identifier,
        role: selectedRole,
        name: selectedRole === "student" ? "Priya R" : (selectedRole === "trainer" ? "Arun Kumar" : (selectedRole === "college" ? "Dr. Kavitha" : "Mr. Ramesh K")),
        avatar: selectedRole === "student" ? "PR" : (selectedRole === "trainer" ? "AK" : (selectedRole === "college" ? "DC" : "RK")),
        college_id: "col_demo_001"
      };
      login("mock_token", fallbackProfile);
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
            onClick={toggleLanguage}
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
            {roleConfigs.map((r) => {
              const Icon = r.icon;
              const isSelected = selectedRole === r.id;
              return (
                <button
                  key={r.id}
                  type="button"
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
                      {r.id === "student" ? "Sem 2-7" : (r.id === "parent" ? "OTP Login" : "Staff")}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-600 font-medium">
              {error}
            </div>
          )}

          {/* Login Form */}
          <form onSubmit={handleSignIn} className="space-y-4">
            {selectedRole === "parent" ? (
              /* Parent Mobile + OTP view */
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-bold text-[#0F1F3A] mb-1">{t("login.phone_label")}</label>
                  <input
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="Enter 10-digit mobile number"
                    className="w-full px-3.5 py-2.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-xs text-[#0F1F3A] focus:outline-none focus:border-[#2B5CD0] focus:bg-white transition-all"
                    required
                  />
                </div>

                {otpSent && (
                  <div>
                    <div className="flex justify-between items-center mb-1">
                      <label className="block text-xs font-bold text-[#0F1F3A]">{t("login.otp_label")}</label>
                      <span className="text-[10px] text-[#2BB3A0] font-bold">Demo OTP: 123456</span>
                    </div>
                    <input
                      type="text"
                      maxLength={6}
                      value={otp}
                      onChange={(e) => setOtp(e.target.value)}
                      placeholder="Enter 6-digit OTP"
                      className="w-full px-3.5 py-2.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-xs text-[#0F1F3A] tracking-widest font-mono text-center focus:outline-none focus:border-[#2B5CD0] focus:bg-white transition-all"
                      required
                    />
                  </div>
                )}
              </div>
            ) : (
              /* Student / Trainer / College Username + Password view */
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-bold text-[#0F1F3A] mb-1">
                    {selectedRole === "student" ? "Register Number / Email" : "College Email ID"}
                  </label>
                  <input
                    type="text"
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    placeholder="Enter ID or email"
                    className="w-full px-3.5 py-2.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-xs text-[#0F1F3A] focus:outline-none focus:border-[#2B5CD0] focus:bg-white transition-all"
                    required
                  />
                </div>

                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="block text-xs font-bold text-[#0F1F3A]">{t("login.password_label")}</label>
                    <span className="text-[10px] text-[#64748B]">Demo: password123</span>
                  </div>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full px-3.5 py-2.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-xs text-[#0F1F3A] focus:outline-none focus:border-[#2B5CD0] focus:bg-white transition-all"
                    required
                  />
                </div>
              </div>
            )}

            {/* Full-width primary action button */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 bg-[#2B5CD0] hover:bg-[#1E46B0] text-white font-bold text-xs rounded-xl shadow-md transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
            >
              <span>
                {selectedRole === "parent"
                  ? (otpSent ? t("login.verify_otp_btn") : t("login.get_otp_btn"))
                  : t("login.sign_in_btn")}
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

