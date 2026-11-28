"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth, Role } from "@/lib/AuthContext";
import { useLanguage } from "@/lib/LanguageContext";
import { ShieldAlert, ArrowLeft, LogOut } from "lucide-react";

interface RoleGuardProps {
  allowedRoles: Role[];
  children: React.ReactNode;
}

export const HOME_FOR_ROLE: Record<Role, string> = { student: "/student", trainer: "/trainer", college: "/college", parent: "/parent", admin: "/admin/colleges" };

/** Signed-out visitors go to /login; a signed-in user with the wrong role sees
 *  "Access restricted" with a way back to their own dashboard. */
export const RoleGuard: React.FC<RoleGuardProps> = ({ allowedRoles, children }) => {
  const { user, isLoaded, logout } = useAuth();
  const { t } = useLanguage();
  const router = useRouter();

  useEffect(() => {
    if (isLoaded && !user) router.replace("/login");
  }, [isLoaded, user, router]);

  if (!isLoaded || !user) {
    return (
      <div className="flex items-center justify-center min-h-[60vh] p-6" aria-busy="true">
        <div className="w-8 h-8 border-2 border-teal border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  if (!allowedRoles.includes(user.role)) {
    return (
      <div className="flex items-center justify-center min-h-[60vh] p-6">
        <div className="max-w-md w-full bg-white rounded-card border border-line p-8 shadow-card text-center space-y-5">
          <div className="w-14 h-14 mx-auto rounded-full bg-danger-soft flex items-center justify-center text-danger">
            <ShieldAlert className="w-8 h-8" />
          </div>
          <div className="space-y-2">
            <h2 className="text-xl font-semibold text-ink">{t("shell.restricted_title")}</h2>
            <p className="text-sm text-muted leading-relaxed">{t("shell.restricted_body")}</p>
          </div>
          <div className="pt-2 flex flex-col sm:flex-row gap-3 justify-center">
            <Link href={HOME_FOR_ROLE[user.role]}
              className="flex items-center justify-center gap-2 px-4 py-2.5 bg-brand hover:bg-brand-hover text-white text-xs font-semibold rounded-card shadow-card transition-all">
              <ArrowLeft className="w-4 h-4" /><span>{t("shell.go_home")}</span>
            </Link>
            <button onClick={logout}
              className="flex items-center justify-center gap-2 px-4 py-2.5 bg-line-soft hover:bg-line text-ink text-xs font-semibold rounded-card border border-line-strong transition-all">
              <LogOut className="w-4 h-4" /><span>{t("shell.sign_in_other")}</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
};
