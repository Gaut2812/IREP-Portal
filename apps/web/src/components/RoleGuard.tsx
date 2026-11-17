"use client";

import React from "react";
import { useAuth, Role } from "@/lib/AuthContext";
import { useLanguage } from "@/lib/LanguageContext";
import { ShieldAlert, ArrowLeft, RefreshCw } from "lucide-react";
import Link from "next/link";

interface RoleGuardProps {
  allowedRoles: Role[];
  children: React.ReactNode;
}

export const RoleGuard: React.FC<RoleGuardProps> = ({ allowedRoles, children }) => {
  const { user, isLoaded, switchRoleDemo } = useAuth();
  const { t } = useLanguage();

  if (!isLoaded) {
    return (
      <div className="flex items-center justify-center min-h-[60vh] p-6">
        <div className="w-8 h-8 border-2 border-[#2BB3A0] border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  if (!user || !allowedRoles.includes(user.role)) {
    return (
      <div className="flex items-center justify-center min-h-[60vh] p-6">
        <div className="max-w-md w-full bg-white rounded-2xl border border-[#E2E8F0] p-8 shadow-sm text-center space-y-5">
          <div className="w-14 h-14 mx-auto rounded-full bg-[#FEE2E2] flex items-center justify-center text-[#DC2626]">
            <ShieldAlert className="w-8 h-8" />
          </div>

          <div className="space-y-2">
            <h2 className="text-xl font-bold text-[#0F1F3A]">
              {t("coding.unauthorized_title") || "Access Restricted"}
            </h2>
            <p className="text-sm text-[#64748B] leading-relaxed">
              {t("coding.unauthorized_desc") || "This section is accessible only to students and trainers."}
            </p>
          </div>

          <div className="pt-2 flex flex-col sm:flex-row gap-3 justify-center">
            <button
              onClick={() => switchRoleDemo("student")}
              className="flex items-center justify-center gap-2 px-4 py-2.5 bg-[#2BB3A0] hover:bg-[#249B8A] text-white text-xs font-bold rounded-xl shadow transition-all cursor-pointer"
            >
              <RefreshCw className="w-4 h-4" />
              <span>{t("coding.switch_role") || "Switch to Student"}</span>
            </button>
            <Link
              href="/"
              className="flex items-center justify-center gap-2 px-4 py-2.5 bg-[#F1F5F9] hover:bg-[#E2E8F0] text-[#0F1F3A] text-xs font-bold rounded-xl border border-[#CBD5E1] transition-all"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>{t("coding.back_to_dashboard") || "Go Back"}</span>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
};

