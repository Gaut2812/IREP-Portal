"use client";

/** Coding lab entry (sidebar and "Resume practice"): opens the student's next problem, decided by the API. */
import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { EmptyState } from "@/components/ui";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";

export default function CodingLabEntry() {
  const router = useRouter();
  const { t } = useLanguage();
  const [state, setState] = useState<"loading" | "none" | "error">("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    fetchApi<{ problem_id: string | null }>("/student/coding/resume")
      .then((r) => {
        if (r.problem_id) router.replace(`/student/coding/${r.problem_id}`);
        else setState("none");
      })
      .catch((e) => { setError(e instanceof ApiError ? e.detail : t("coding.load_failed")); setState("error"); });
  }, [router, t]);

  return (
    <RoleGuard allowedRoles={["student"]}>
      <AppShell pageTitle={t("coding.title")}>
        <div className="max-w-md" data-testid="coding-entry">
          {state === "loading" && <p className="text-body text-muted">{t("coding.opening")}</p>}
          {state === "none" && <EmptyState title={t("coding.no_problems")} />}
          {state === "error" && <p className="text-body text-danger" role="alert">{error}</p>}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
