"use client";

/** Screen 09 (student side): enter the class check-in code shown by the trainer. Not in the sidebar:
 *  the live session shows the same box; this page stays as the deep link SMS reminders use. */
import React from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { CheckinBox } from "@/components/live/CheckinBox";
import { useLanguage } from "@/lib/LanguageContext";

export default function StudentCheckinPage() {
  const { t } = useLanguage();
  return (
    <RoleGuard allowedRoles={["student"]}>
      <AppShell pageTitle={t("checkin.title")}>
        <div className="max-w-md bg-white rounded-card border border-line p-5">
          <CheckinBox t={t} />
        </div>
      </AppShell>
    </RoleGuard>
  );
}
