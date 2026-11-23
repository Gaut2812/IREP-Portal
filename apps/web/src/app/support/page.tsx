"use client";

/** Screen 49 · Report a problem and follow my tickets (any signed-in role; link L39). */
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { SupportDesk } from "@/components/SupportDesk";
import { useLanguage } from "@/lib/LanguageContext";

export default function SupportPage() {
  const { t } = useLanguage();
  return (
    <RoleGuard allowedRoles={["student", "trainer", "college", "parent", "admin"]}>
      <AppShell pageTitle={t("support.title")}>
        <SupportDesk staffView={false} />
      </AppShell>
    </RoleGuard>
  );
}
