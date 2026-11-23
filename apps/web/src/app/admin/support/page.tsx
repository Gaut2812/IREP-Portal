"use client";

/** Screen 49 · Support desk for IREP staff: every college's tickets; replies notify the requester (L28). */
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { SupportDesk } from "@/components/SupportDesk";
import { useLanguage } from "@/lib/LanguageContext";

export default function AdminSupportPage() {
  const { t } = useLanguage();
  return (
    <RoleGuard allowedRoles={["admin"]}>
      <AppShell pageTitle={t("support.desk_title")}>
        <SupportDesk staffView />
      </AppShell>
    </RoleGuard>
  );
}
