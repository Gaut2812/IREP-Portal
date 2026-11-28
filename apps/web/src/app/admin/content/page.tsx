"use client";

/** Screen 46 · Content library (IREP staff): courses, lessons, publishing, notification templates. */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { BookPlus, FileText, Send } from "lucide-react";
import { CourseMediaPanel, LessonVideo } from "@/components/admin/CourseMedia";
import { BankPanel } from "@/components/admin/BankPanel";
import { ConfirmDelete, DeleteButton } from "@/components/ui";

interface CourseRow {
  id: string; title_en: string; title_ta: string | null; track: string; semester: number; skill_key: string; status: string; lessons: number;
  description_en?: string | null; description_ta?: string | null; thumbnail_url?: string | null; intro_video_url?: string | null;
}
interface LessonRow { id: string; position: number; title_en: string; title_ta: string | null; body_en: string; body_ta: string | null; duration_min: number; video_url?: string | null }
interface Template { key: string; title_en: string; title_ta: string | null; body_en: string | null; body_ta: string | null }

export default function ContentLibraryPage() {
  const { t } = useLanguage();
  const [tab, setTab] = useState<"courses" | "templates" | "bank">("courses");
  const [courses, setCourses] = useState<CourseRow[]>([]);
  const [skills, setSkills] = useState<string[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [lessons, setLessons] = useState<LessonRow[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [del, setDel] = useState<{ kind: "course" | "lesson"; id: string; name: string } | null>(null);
  const [courseForm, setCourseForm] = useState({ title_en: "", title_ta: "", semester: "5", track: "All", skill_key: "future_skills" });
  const [lessonForm, setLessonForm] = useState({ title_en: "", title_ta: "", body_en: "", body_ta: "", duration_min: "20" });
  const [tplForm, setTplForm] = useState({ key: "", title_en: "", title_ta: "", body_en: "", body_ta: "" });

  const loadCourses = useCallback(async () => {
    try {
      const r = await fetchApi<{ courses: CourseRow[]; skills: string[] }>("/admin/content/courses");
      setCourses(r.courses);
      setSkills(r.skills);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("content.load_failed"));
    }
  }, [t]);

  const loadLessons = useCallback(async () => {
    if (!selected) return setLessons([]);
    const r = await fetchApi<{ lessons: LessonRow[] }>(`/admin/content/courses/${selected}`);
    setLessons(r.lessons);
  }, [selected]);

  const loadTemplates = useCallback(async () => {
    setTemplates((await fetchApi<{ templates: Template[] }>("/admin/content/templates")).templates);
  }, []);

  useEffect(() => { loadCourses(); }, [loadCourses]);
  useEffect(() => { loadLessons().catch(() => setError(t("content.load_failed"))); }, [loadLessons, t]);
  useEffect(() => { if (tab === "templates") loadTemplates().catch(() => setError(t("content.load_failed"))); }, [tab, loadTemplates, t]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try { await fn(); } catch (e) { setError(e instanceof ApiError ? e.detail : t("content.save_failed")); } finally { setBusy(false); }
  };

  const addCourse = (e: React.FormEvent) => {
    e.preventDefault();
    if (courseForm.title_en.trim().length < 3) return setError(t("content.err_title"));
    run(async () => {
      const c = await fetchApi<CourseRow>("/admin/content/courses", { method: "POST", body: JSON.stringify({ ...courseForm, semester: Number(courseForm.semester) }) });
      setCourseForm({ ...courseForm, title_en: "", title_ta: "" });
      await loadCourses();
      setSelected(c.id);
    });
  };

  const addLesson = (e: React.FormEvent) => {
    e.preventDefault();
    if (lessonForm.title_en.trim().length < 2) return setError(t("content.err_title"));
    run(async () => {
      await fetchApi(`/admin/content/courses/${selected}/lessons`, { method: "POST", body: JSON.stringify({ ...lessonForm, duration_min: Number(lessonForm.duration_min) }) });
      setLessonForm({ title_en: "", title_ta: "", body_en: "", body_ta: "", duration_min: lessonForm.duration_min });
      await Promise.all([loadLessons(), loadCourses()]);
    });
  };

  const setPublished = (c: CourseRow) => run(async () => {
    await fetchApi(`/admin/content/courses/${c.id}/${c.status === "published" ? "unpublish" : "publish"}`, { method: "POST" });
    await loadCourses();
  });

  const saveTemplate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!tplForm.key.trim() || tplForm.title_en.trim().length < 2) return setError(t("content.err_template"));
    run(async () => {
      const { key, ...body } = tplForm;
      await fetchApi(`/admin/content/templates/${encodeURIComponent(key.trim())}`, { method: "PUT", body: JSON.stringify(body) });
      setTplForm({ key: "", title_en: "", title_ta: "", body_en: "", body_ta: "" });
      await loadTemplates();
    });
  };

  const cls = "w-full px-2.5 py-1.5 bg-surface-2 border border-line rounded-tile text-xs";
  const current = courses.find((c) => c.id === selected);

  return (
    <RoleGuard allowedRoles={["admin"]}>
      <AppShell pageTitle={t("content.title")}>
        <div className="space-y-6 max-w-6xl">
          <div className="flex gap-2" role="tablist">
            {(["courses", "templates", "bank"] as const).map((k) => (
              <button key={k} type="button" role="tab" aria-selected={tab === k} onClick={() => setTab(k)} data-testid={`content-tab-${k}`}
                className={`px-3 py-1.5 rounded-tile text-xs font-semibold ${tab === k ? "bg-brand text-white" : "border border-line-strong"}`}>{t(`content.tab_${k}`)}</button>
            ))}
          </div>
          {error && <p className="text-xs text-red-600" role="alert" data-testid="content-error">{error}</p>}

          {tab === "courses" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <section className="space-y-3">
                <form onSubmit={addCourse} noValidate className="bg-white rounded-card border border-line p-3 space-y-2" data-testid="course-form">
                  <h2 className="text-sm font-semibold flex items-center gap-2"><BookPlus className="w-4 h-4 text-brand" />{t("content.new_course")}</h2>
                  <input className={cls} placeholder={t("content.title_en")} value={courseForm.title_en} data-testid="course-title-en" onChange={(e) => setCourseForm({ ...courseForm, title_en: e.target.value })} />
                  <input className={cls} placeholder={t("content.title_ta")} value={courseForm.title_ta} data-testid="course-title-ta" onChange={(e) => setCourseForm({ ...courseForm, title_ta: e.target.value })} />
                  <div className="grid grid-cols-3 gap-2">
                    <select className={cls} value={courseForm.semester} onChange={(e) => setCourseForm({ ...courseForm, semester: e.target.value })} aria-label={t("content.semester")} data-testid="course-semester">
                      {[2, 3, 4, 5, 6, 7].map((s) => <option key={s} value={s}>{t("content.sem")} {s}</option>)}
                    </select>
                    <input className={cls} value={courseForm.track} onChange={(e) => setCourseForm({ ...courseForm, track: e.target.value })} aria-label={t("content.track")} />
                    <select className={cls} value={courseForm.skill_key} onChange={(e) => setCourseForm({ ...courseForm, skill_key: e.target.value })} aria-label={t("content.skill")}>
                      {skills.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </div>
                  <button type="submit" disabled={busy} data-testid="course-save" className="px-3 py-1.5 bg-brand text-white text-xs font-semibold rounded-tile disabled:opacity-50">{t("content.create")}</button>
                </form>
                <ul className="bg-white rounded-card border border-line divide-y divide-line-soft" data-testid="course-list">
                  {courses.map((c) => (
                    <li key={c.id}>
                      <button type="button" onClick={() => setSelected(c.id)} data-testid="course-row" aria-pressed={selected === c.id}
                        className={`w-full text-left px-3 py-2 text-xs ${selected === c.id ? "bg-brand-soft" : "hover:bg-surface-2"}`}>
                        <div className="font-semibold">{c.title_en}</div>
                        <div className="text-caption text-muted">{t("content.sem")} {c.semester} · {c.track} · {c.lessons} {t("content.lessons")} · {t(`content.status_${c.status}`)}</div>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>

              {current && (
                <section className="lg:col-span-2 space-y-3">
                  <div className="bg-white rounded-card border border-line p-3 flex items-center justify-between gap-2">
                    <div><h2 className="text-sm font-semibold" data-testid="course-heading">{current.title_en}</h2><p className="text-caption text-muted">{current.title_ta}</p></div>
                    <button type="button" disabled={busy} onClick={() => setPublished(current)} data-testid="course-publish"
                      className={`px-3 py-1.5 text-xs font-semibold rounded-tile inline-flex items-center gap-1 ${current.status === "published" ? "border border-line-strong" : "bg-success text-white"}`}>
                      <Send className="w-3.5 h-3.5" />{current.status === "published" ? t("content.unpublish") : t("content.publish")}
                    </button>
                    {current.status !== "published" && (
                      <DeleteButton onClick={() => setDel({ kind: "course", id: current.id, name: current.title_en })} testId="course-delete" />
                    )}
                  </div>
                  {current.status === "published" && <p className="text-caption text-muted" data-testid="course-delete-hint">{t("content.unpublish_to_delete")}</p>}
                  <CourseMediaPanel key={current.id} course={current} t={t} onChange={loadCourses} />
                  <ol className="bg-white rounded-card border border-line divide-y divide-line-soft" data-testid="lesson-list">
                    {lessons.map((l) => (
                      <li key={l.id} className="px-3 py-2 text-xs flex items-start justify-between gap-2" data-testid="lesson-row">
                        <div className="min-w-0">
                          <div className="font-semibold">{l.position}. {l.title_en} <span className="font-normal text-muted">/ {l.title_ta || "—"} · {l.duration_min} {t("content.min")}</span></div>
                          {!l.body_ta && <div className="text-caption text-warning">{t("content.missing_ta")}</div>}
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <LessonVideo lessonId={l.id} hasVideo={!!l.video_url} t={t} onChange={loadLessons} />
                          <DeleteButton onClick={() => setDel({ kind: "lesson", id: l.id, name: l.title_en })} testId="lesson-delete" />
                        </div>
                      </li>
                    ))}
                  </ol>
                  <form onSubmit={addLesson} noValidate className="bg-white rounded-card border border-line p-3 grid grid-cols-1 md:grid-cols-2 gap-2" data-testid="lesson-form">
                    <input className={cls} placeholder={t("content.lesson_title_en")} value={lessonForm.title_en} data-testid="lesson-title-en" onChange={(e) => setLessonForm({ ...lessonForm, title_en: e.target.value })} />
                    <input className={cls} placeholder={t("content.lesson_title_ta")} value={lessonForm.title_ta} data-testid="lesson-title-ta" onChange={(e) => setLessonForm({ ...lessonForm, title_ta: e.target.value })} />
                    <textarea className={cls} rows={3} placeholder={t("content.body_en")} value={lessonForm.body_en} data-testid="lesson-body-en" onChange={(e) => setLessonForm({ ...lessonForm, body_en: e.target.value })} />
                    <textarea className={cls} rows={3} placeholder={t("content.body_ta")} value={lessonForm.body_ta} data-testid="lesson-body-ta" onChange={(e) => setLessonForm({ ...lessonForm, body_ta: e.target.value })} />
                    <button type="submit" disabled={busy} data-testid="lesson-save" className="md:col-span-2 px-3 py-1.5 bg-brand text-white text-xs font-semibold rounded-tile disabled:opacity-50">{t("content.add_lesson")}</button>
                  </form>
                </section>
              )}
            </div>
          )}

          {tab === "templates" && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <form onSubmit={saveTemplate} noValidate className="bg-white rounded-card border border-line p-3 space-y-2" data-testid="template-form">
                <h2 className="text-sm font-semibold flex items-center gap-2"><FileText className="w-4 h-4 text-brand" />{t("content.template")}</h2>
                <p className="text-caption text-muted">{t("content.template_help")}</p>
                <input className={cls} placeholder="leave.approved" value={tplForm.key} data-testid="template-key" onChange={(e) => setTplForm({ ...tplForm, key: e.target.value })} />
                <input className={cls} placeholder={t("content.title_en")} value={tplForm.title_en} data-testid="template-title-en" onChange={(e) => setTplForm({ ...tplForm, title_en: e.target.value })} />
                <input className={cls} placeholder={t("content.title_ta")} value={tplForm.title_ta} onChange={(e) => setTplForm({ ...tplForm, title_ta: e.target.value })} />
                <textarea className={cls} rows={2} placeholder={t("content.body_en")} value={tplForm.body_en} onChange={(e) => setTplForm({ ...tplForm, body_en: e.target.value })} />
                <textarea className={cls} rows={2} placeholder={t("content.body_ta")} value={tplForm.body_ta} onChange={(e) => setTplForm({ ...tplForm, body_ta: e.target.value })} />
                <button type="submit" disabled={busy} data-testid="template-save" className="px-3 py-1.5 bg-brand text-white text-xs font-semibold rounded-tile disabled:opacity-50">{t("content.save")}</button>
              </form>
              <ul className="bg-white rounded-card border border-line divide-y divide-line-soft h-fit" data-testid="template-list">
                {templates.length === 0 && <li className="p-3 text-xs text-muted">{t("content.no_templates")}</li>}
                {templates.map((tp) => (
                  <li key={tp.key} className="px-3 py-2 text-xs" data-testid="template-row">
                    <div className="font-mono font-semibold">{tp.key}</div>
                    <div>{tp.title_en}</div>
                    <div className="text-muted">{tp.title_ta}</div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {tab === "bank" && <BankPanel />}
        </div>
        {del && (
          <ConfirmDelete itemName={del.name} note={del.kind === "course" ? t("content.delete_course_note") : undefined}
            onConfirm={async () => {
              await fetchApi(del.kind === "course" ? `/admin/content/courses/${del.id}` : `/admin/content/lessons/${del.id}`, { method: "DELETE" });
              if (del.kind === "course") { setSelected(""); await loadCourses(); } else { await loadLessons(); await loadCourses(); }
            }}
            onClose={() => setDel(null)} />
        )}
      </AppShell>
    </RoleGuard>
  );
}
