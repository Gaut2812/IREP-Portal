"use client";

/** Screen 23 · Practice tests list: tests published to my batch by the trainer (screen 22, L13). */
import React, { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { FileCheck2 } from "lucide-react";

interface Row { id: string; title: string; category: string; questions: number; duration_min: number; due_at: string | null; best_score: string | null }

export default function StudentTestsPage() {
  const { t } = useLanguage();
  const [tests, setTests] = useState<Row[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchApi<{ tests: Row[] }>("/student/tests").then((r) => setTests(r.tests))
      .catch((e) => setError(e instanceof ApiError ? e.detail : t("assess.load_failed")));
  }, [t]);

  return (
    <RoleGuard allowedRoles={["student"]}>
      <AppShell pageTitle={t("assess.tests_title")}>
        <div className="max-w-3xl space-y-6">
          {error && <p className="text-xs text-red-600" role="alert">{error}</p>}
          {tests?.length === 0 && <p className="text-xs text-muted bg-white rounded-card border border-dashed border-line-strong p-6 text-center">{t("assess.no_tests")}</p>}
          <ul className="space-y-2" data-testid="student-tests">
            {tests?.map((r) => (
              <li key={r.id}>
                <Link href={`/student/tests/${r.id}`} className="block bg-white rounded-card border border-line p-4 hover:border-brand" data-testid="student-test">
                  <div className="flex items-center gap-2 text-sm font-semibold text-ink"><FileCheck2 className="w-4 h-4 text-brand" />{r.title}</div>
                  <div className="text-caption text-muted mt-1">
                    {r.questions} {t("assess.questions")} · {r.duration_min} {t("assess.minutes")}
                    {r.due_at ? ` · ${t("assess.due_on")} ${new Date(r.due_at).toLocaleString()}` : ""}
                    {r.best_score ? ` · ${t("assess.best")} ${r.best_score}` : ""}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
