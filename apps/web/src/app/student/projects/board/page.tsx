"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { fetchApi } from "@/lib/api";
import { Users } from "lucide-react";

/** Sidebar "Projects" entry: send the student to their own team's board. */
export default function MyTeamBoardRedirect() {
  const router = useRouter();
  const { t } = useLanguage();
  const [noTeam, setNoTeam] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchApi<{ team_id: string | null }>("/student/projects/my-team")
      .then((res) => {
        if (res.team_id) router.replace(`/student/projects/${res.team_id}/board`);
        else setNoTeam(true);
      })
      .catch((err) => setError(err?.detail || err?.message || "error"));
  }, [router]);

  return (
    <RoleGuard allowedRoles={["student"]}>
      <AppShell pageTitle={t("nav.sprint_board")}>
        <div className="max-w-md mx-auto mt-10 bg-white rounded-card border border-line p-8 text-center space-y-6">
          <Users className="w-8 h-8 text-brand mx-auto" />
          <p className="text-xs text-muted">{noTeam ? t("board.no_team") : error ? `${t("board.error_title")}: ${error}` : t("board.loading")}</p>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
