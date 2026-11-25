"use client";

/** Screen 11 · My courses (student): published library courses for my semester and track (link L12). */
import React, { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { BookOpen } from "lucide-react";

interface Row { id: string; title: string; track: string; skill_key: string; lessons: number; completed: number; pct: number }

export default function MyCoursesPage() {
  const { t, language } = useLanguage();
  const [data, setData] = useState<{ semester: number; track: string; courses: Row[] } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchApi<{ semester: number; track: string; courses: Row[] }>(`/student/courses?lang=${language}`)
      .then(setData).catch((e) => setError(e instanceof ApiError ? e.detail : t("courses.load_failed")));
  }, [language, t]);

  return (
    <RoleGuard allowedRoles={["student"]}>
      <AppShell pageTitle={t("courses.title")}>
        <div className="space-y-6 max-w-4xl">
          {error && <p className="text-xs text-red-600" role="alert">{error}</p>}
          {data && <p className="text-xs text-muted">{t("courses.for")} {t("courses.sem")} {data.semester} · {data.track}</p>}
          {data?.courses.length === 0 && <div className="bg-white rounded-card border border-dashed border-line-strong p-6 text-center text-xs text-muted" data-testid="courses-empty">{t("courses.empty")}</div>}
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-3" data-testid="course-cards">
            {data?.courses.map((c) => (
              <li key={c.id}>
                <Link href={`/student/courses/${c.id}`} className="block bg-white rounded-card border border-line p-4 hover:border-brand" data-testid="course-card">
                  <div className="flex items-center gap-2 text-sm font-semibold text-ink"><BookOpen className="w-4 h-4 text-brand" />{c.title}</div>
                  <div className="text-caption text-muted mt-1">{c.completed}/{c.lessons} {t("courses.lessons_done")}</div>
                  <div className="h-1.5 bg-line-soft rounded-full mt-2 overflow-hidden" aria-label={`${c.pct}%`}>
                    <div className="h-full bg-teal" style={{ width: `${c.pct}%` }} />
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
