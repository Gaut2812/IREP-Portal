"use client";

/** Screen 11 · My courses (student): published library courses for my semester and track (link L12), with a
 *  thumbnail, a short description and "Continue" to the first lesson not done yet. */
import React, { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi, mediaSrc } from "@/lib/api";
import { BookOpen, PlayCircle, CheckCircle2 } from "lucide-react";

interface Row {
  id: string; title: string; track: string; skill_key: string; lessons: number; completed: number; pct: number;
  description: string | null; thumbnail_url: string | null; next_lesson: { id: string; position: number; title: string } | null;
}
interface Data { semester: number; track: string; courses: Row[]; continue_course_id: string | null }

export default function MyCoursesPage() {
  const { t, language } = useLanguage();
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchApi<Data>(`/student/courses?lang=${language}`)
      .then(setData).catch((e) => setError(e instanceof ApiError ? e.detail : t("courses.load_failed")));
  }, [language, t]);

  const resume = data?.courses.find((c) => c.id === data.continue_course_id && c.next_lesson);

  return (
    <RoleGuard allowedRoles={["student"]}>
      <AppShell pageTitle={t("courses.title")}>
        <div className="space-y-6 max-w-5xl">
          {error && <p className="text-xs text-danger" role="alert">{error}</p>}
          {data && <p className="text-xs text-muted">{t("courses.for")} {t("courses.sem")} {data.semester} · {data.track}</p>}

          {resume && resume.next_lesson && (
            <Link href={`/student/courses/${resume.id}?lesson=${resume.next_lesson.id}`} data-testid="continue-banner"
              className="flex items-center gap-3 bg-brand-soft border border-brand-line rounded-card p-4 hover:border-brand">
              <PlayCircle className="w-8 h-8 text-brand shrink-0" />
              <div className="min-w-0">
                <div className="text-caption text-muted">{t("courses.continue_where")}</div>
                <div className="text-sm font-semibold text-ink truncate">{resume.title} · {resume.next_lesson.position}. {resume.next_lesson.title}</div>
              </div>
            </Link>
          )}

          {data?.courses.length === 0 && <div className="bg-white rounded-card border border-dashed border-line-strong p-6 text-center text-xs text-muted" data-testid="courses-empty">{t("courses.empty")}</div>}
          <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="course-cards">
            {data?.courses.map((c) => (
              <li key={c.id} className="bg-white rounded-card border border-line overflow-hidden flex flex-col" data-testid="course-card">
                <Link href={`/student/courses/${c.id}`} className="block">
                  {c.thumbnail_url
                    ? <img src={mediaSrc(c.thumbnail_url)} alt="" className="w-full aspect-video object-cover" data-testid="course-thumbnail" />
                    : <div className="w-full aspect-video bg-gradient-to-br from-brand-soft to-line-soft flex items-center justify-center"><BookOpen className="w-10 h-10 text-brand" /></div>}
                </Link>
                <div className="p-4 flex-1 flex flex-col gap-2">
                  <Link href={`/student/courses/${c.id}`} className="text-sm font-semibold text-ink hover:text-brand">{c.title}</Link>
                  {c.description && <p className="text-caption text-ink-soft line-clamp-3">{c.description}</p>}
                  <div className="mt-auto space-y-2">
                    <div className="text-caption text-muted">{c.completed}/{c.lessons} {t("courses.lessons_done")}</div>
                    <div className="h-1.5 bg-line-soft rounded-full overflow-hidden" aria-label={`${c.pct}%`}><div className="h-full bg-teal" style={{ width: `${c.pct}%` }} /></div>
                    {c.next_lesson ? (
                      <Link href={`/student/courses/${c.id}?lesson=${c.next_lesson.id}`} data-testid="course-continue"
                        className="inline-flex items-center gap-1 px-3 py-1.5 bg-brand text-white text-xs font-semibold rounded-tile">
                        <PlayCircle className="w-3.5 h-3.5" />{c.completed ? t("courses.continue") : t("courses.start")}: {c.next_lesson.position}
                      </Link>
                    ) : c.lessons > 0 && (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-success"><CheckCircle2 className="w-3.5 h-3.5" />{t("courses.all_done")}</span>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
