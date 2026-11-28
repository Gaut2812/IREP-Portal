"use client";

import Link from "next/link";
import { Construction, ArrowLeft } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { HOME_FOR_ROLE } from "@/components/RoleGuard";
import { useAuth } from "@/lib/AuthContext";
import { useLanguage } from "@/lib/LanguageContext";

/** Menu items for modules outside the 14 mockup screens land here instead of a bare 404. */
export default function NotFound() {
  const { user } = useAuth();
  const { t } = useLanguage();
  const body = (
    <div className="flex items-center justify-center min-h-[60vh] p-4">
      <div className="max-w-md w-full bg-white rounded-card border border-line p-8 shadow-card text-center space-y-4" data-testid="coming-soon">
        <div className="w-14 h-14 mx-auto rounded-full bg-brand-soft flex items-center justify-center text-brand"><Construction className="w-7 h-7" /></div>
        <h2 className="text-lg font-semibold text-ink">{t("shell.soon_title")}</h2>
        <p className="text-sm text-muted leading-relaxed">{t("shell.soon_body")}</p>
        <Link href={user ? HOME_FOR_ROLE[user.role] : "/login"} className="inline-flex items-center gap-2 px-4 py-2.5 bg-brand text-white text-xs font-semibold rounded-card">
          <ArrowLeft className="w-4 h-4" />{t("shell.go_home")}
        </Link>
      </div>
    </div>
  );
  return user ? <AppShell pageTitle={t("shell.soon_title")}>{body}</AppShell> : body;
}
