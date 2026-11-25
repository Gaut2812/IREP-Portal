"use client";

/** Screen 11 · a course's lessons; completing one feeds the dashboard skill bar (link L33). */
import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { ArrowLeft, CheckCircle2, Circle } from "lucide-react";

interface LessonRow { id: string; position: number; title: string; body: string; duration_min: number; completed: boolean }

export default function CoursePage() {
  const { t, language } = useLanguage();
  const { courseId } = useParams<{ courseId: string }>();
  const [data, setData] = useState<{ course: { id: string; title: string; skill_key: string }; lessons: LessonRow[] } | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [skill, setSkill] = useState<number | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setData(await fetchApi(`/student/courses/${courseId}?lang=${language}`));
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("courses.load_failed"));
    }
  }, [courseId, language, t]);

  useEffect(() => { load(); }, [load]);

  const complete = async (l: LessonRow) => {
    try {
      const r = await fetchApi<{ skill_pct: number }>(`/student/lessons/${l.id}/complete`, { method: "POST" });
      setSkill(r.skill_pct);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("courses.save_failed"));
    }
  };

  return (
    <RoleGuard allowedRoles={["student"]}>
      <AppShell pageTitle={data?.course.title || t("courses.title")}>
        <div className="space-y-6 max-w-3xl">
          <Link href="/student/courses" className="inline-flex items-center gap-1 text-xs text-brand font-semibold"><ArrowLeft className="w-3.5 h-3.5" />{t("courses.back")}</Link>
          {error && <p className="text-xs text-red-600" role="alert">{error}</p>}
          {skill !== null && <p className="text-xs text-success font-semibold" data-testid="skill-updated">{t("courses.skill_now")} {skill}%</p>}
          <ol className="space-y-2" data-testid="lessons">
            {data?.lessons.map((l) => (
              <li key={l.id} className="bg-white rounded-card border border-line" data-testid="lesson">
                <button type="button" onClick={() => setOpen(open === l.id ? null : l.id)} className="w-full text-left px-4 py-3 flex items-center gap-2 text-sm font-semibold text-ink">
                  {l.completed ? <CheckCircle2 className="w-4 h-4 text-success" data-testid="lesson-done" /> : <Circle className="w-4 h-4 text-subtle" />}
                  {l.position}. {l.title} <span className="ml-auto text-caption font-normal text-muted">{l.duration_min} {t("courses.min")}</span>
                </button>
                {open === l.id && (
                  <div className="px-4 pb-4 space-y-3">
                    <div className="text-xs text-ink-soft whitespace-pre-wrap leading-relaxed" data-testid="lesson-body">{l.body}</div>
                    {!l.completed && <button type="button" onClick={() => complete(l)} data-testid="lesson-complete" className="px-3 py-1.5 bg-brand text-white text-xs font-semibold rounded-tile">{t("courses.mark_done")}</button>}
                  </div>
                )}
              </li>
            ))}
          </ol>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
