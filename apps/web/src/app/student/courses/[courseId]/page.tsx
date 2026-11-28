"use client";

/** Screen 11 · a course's lessons; completing one feeds the dashboard skill bar (link L33). The intro video plays at
 *  the top, a lesson's video inside it, `?lesson=<id>` opens that lesson, and "Next lesson" moves on. */
import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi, mediaSrc } from "@/lib/api";
import { ArrowLeft, ArrowRight, CheckCircle2, Circle, PlayCircle } from "lucide-react";

interface LessonRow { id: string; position: number; title: string; body: string; duration_min: number; completed: boolean; video_url: string | null }
interface Data {
  course: { id: string; title: string; skill_key: string; description: string | null; intro_video_url: string | null };
  lessons: LessonRow[]; next_lesson_id: string | null;
}

export default function CoursePage() {
  const { t, language } = useLanguage();
  const { courseId } = useParams<{ courseId: string }>();
  const [data, setData] = useState<Data | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [skill, setSkill] = useState<number | null>(null);
  const [error, setError] = useState("");
  const opened = useRef(false);

  const load = useCallback(async () => {
    try {
      const d = await fetchApi<Data>(`/student/courses/${courseId}?lang=${language}`);
      setData(d);
      if (!opened.current) {                          // ?lesson=<id> (from "Continue") opens that lesson once
        opened.current = true;
        const want = new URLSearchParams(window.location.search).get("lesson");
        if (want && d.lessons.some((l) => l.id === want)) setOpen(want);
      }
    } catch (e) {
      // a course that was unpublished after its "new course" notification went out answers 404
      setError(e instanceof ApiError && e.status === 404 ? t("courses.not_available") : e instanceof ApiError ? e.detail : t("courses.load_failed"));
    }
  }, [courseId, language, t]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (open) document.getElementById(`lesson-${open}`)?.scrollIntoView({ block: "start", behavior: "smooth" }); }, [open]);

  const complete = async (l: LessonRow) => {
    try {
      const r = await fetchApi<{ skill_pct: number }>(`/student/lessons/${l.id}/complete`, { method: "POST" });
      setSkill(r.skill_pct);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("courses.save_failed"));
    }
  };

  const nextAfter = (l: LessonRow) => data?.lessons.find((x) => x.position > l.position) || null;

  return (
    <RoleGuard allowedRoles={["student"]}>
      <AppShell pageTitle={data?.course.title || t("courses.title")}>
        <div className="space-y-6 max-w-3xl">
          <Link href="/student/courses" className="inline-flex items-center gap-1 text-xs text-brand font-semibold"><ArrowLeft className="w-3.5 h-3.5" />{t("courses.back")}</Link>
          {error && <p className="text-xs text-danger" role="alert">{error}</p>}
          {data?.course.description && <p className="text-sm text-ink-soft" data-testid="course-description">{data.course.description}</p>}
          {data?.course.intro_video_url && (
            <video controls preload="metadata" className="w-full rounded-card border border-line bg-ink" src={mediaSrc(data.course.intro_video_url)} data-testid="course-intro-video">
              {t("courses.no_video_support")}
            </video>
          )}
          {data?.next_lesson_id && open !== data.next_lesson_id && (
            <button type="button" onClick={() => setOpen(data.next_lesson_id)} data-testid="course-continue-here"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-brand text-white text-xs font-semibold rounded-tile">
              <PlayCircle className="w-4 h-4" />{t("courses.continue_where")}
            </button>
          )}
          {skill !== null && <p className="text-xs text-success font-semibold" data-testid="skill-updated">{t("courses.skill_now")} {skill}%</p>}
          <ol className="space-y-2" data-testid="lessons">
            {data?.lessons.map((l) => (
              <li key={l.id} id={`lesson-${l.id}`} className="bg-white rounded-card border border-line scroll-mt-24" data-testid="lesson">
                <button type="button" onClick={() => setOpen(open === l.id ? null : l.id)} aria-expanded={open === l.id}
                  className="w-full text-left px-4 py-3 flex items-center gap-2 text-sm font-semibold text-ink">
                  {l.completed ? <CheckCircle2 className="w-4 h-4 text-success" data-testid="lesson-done" /> : <Circle className="w-4 h-4 text-subtle" />}
                  {l.position}. {l.title}
                  {l.video_url && <PlayCircle className="w-4 h-4 text-brand" aria-label={t("courses.has_video")} />}
                  <span className="ml-auto text-caption font-normal text-muted">{l.duration_min} {t("courses.min")}</span>
                </button>
                {open === l.id && (
                  <div className="px-4 pb-4 space-y-3">
                    {l.video_url && (
                      <video controls preload="metadata" className="w-full rounded-tile bg-ink" src={mediaSrc(l.video_url)} data-testid="lesson-video">
                        {t("courses.no_video_support")}
                      </video>
                    )}
                    <div className="text-xs text-ink-soft whitespace-pre-wrap leading-relaxed" data-testid="lesson-body">{l.body}</div>
                    <div className="flex flex-wrap gap-2">
                      {!l.completed && <button type="button" onClick={() => complete(l)} data-testid="lesson-complete" className="px-3 py-1.5 bg-brand text-white text-xs font-semibold rounded-tile">{t("courses.mark_done")}</button>}
                      {nextAfter(l) && (
                        <button type="button" onClick={() => setOpen(nextAfter(l)!.id)} data-testid="lesson-next"
                          className="px-3 py-1.5 border border-brand text-brand text-xs font-semibold rounded-tile inline-flex items-center gap-1">
                          {t("courses.next_lesson")}<ArrowRight className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
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
