"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/lib/AuthContext";
import { useLanguage } from "@/lib/LanguageContext";
import { getCourseDetail, markLessonProgress, CourseDetail, LessonItem, ModuleItem } from "@/lib/api";
import {
  ArrowLeft, Video, FileText, StickyNote, ClipboardList,
  CheckCircle2, Circle, ChevronDown, ChevronRight,
  AlertTriangle, RefreshCw, ShieldAlert, Check, Lock, Play,
} from "lucide-react";

// ----------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------

type LessonType = "video" | "slides" | "notes" | "assignment";

const TYPE_ICONS: Record<string, React.ReactNode> = {
  video:      <Video className="w-4 h-4" />,
  slides:     <FileText className="w-4 h-4" />,
  notes:      <StickyNote className="w-4 h-4" />,
  assignment: <ClipboardList className="w-4 h-4" />,
};

const TYPE_COLORS: Record<string, string> = {
  video:      "text-blue-600 bg-blue-50",
  slides:     "text-purple-600 bg-purple-50",
  notes:      "text-amber-600 bg-amber-50",
  assignment: "text-teal-600 bg-teal-50",
};

const TRACK_COLORS: Record<string, string> = {
  blue:   "#2B5CD0",
  teal:   "#2BB3A0",
  purple: "#7C3AED",
  green:  "#15803D",
  amber:  "#D97706",
};

// ----------------------------------------------------------------
// Viewer Panel
// ----------------------------------------------------------------

interface LessonViewerProps {
  lesson: LessonItem | null;
  courseId: string;
  t: (k: string) => string;
  onComplete: (lessonId: string) => Promise<void>;
  completing: boolean;
  justCompleted: string | null;
}

function LessonViewer({ lesson, courseId, t, onComplete, completing, justCompleted }: LessonViewerProps) {
  if (!lesson) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-center p-8">
        <Play className="w-10 h-10 text-[#CBD5E1]" />
        <p className="text-sm text-[#94A3B8]">Select a lesson from the left to begin</p>
      </div>
    );
  }

  const typeLabelKey = `courses.type_${lesson.type}` as const;
  const isCompleted = lesson.completed || justCompleted === lesson.id;
  const typeColor = TYPE_COLORS[lesson.type] || "text-[#64748B] bg-[#F1F5F9]";

  return (
    <div className="flex flex-col h-full">
      {/* Lesson header */}
      <div className="p-5 border-b border-[#E2E8F0] space-y-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${typeColor}`}>
            {TYPE_ICONS[lesson.type]}
            {t(typeLabelKey)}
          </span>
          {lesson.duration_min && (
            <span className="text-xs text-[#94A3B8]">{lesson.duration_min} min</span>
          )}
        </div>
        <h2 className="text-base font-black text-[#0F1F3A]">{lesson.title}</h2>
      </div>

      {/* Content placeholder */}
      <div className="flex-1 overflow-y-auto p-5">
        {lesson.type === "video" && (
          <div className="bg-black rounded-xl aspect-video flex items-center justify-center mb-4">
            <div className="text-center space-y-2">
              <div className="w-14 h-14 rounded-full bg-white/20 flex items-center justify-center mx-auto">
                <Play className="w-7 h-7 text-white ml-1" />
              </div>
              <p className="text-white/60 text-xs">
                {lesson.content_url ? "Video ready to play" : "Video will be embedded here"}
              </p>
            </div>
          </div>
        )}

        {lesson.type === "slides" && (
          <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl aspect-[16/9] flex items-center justify-center mb-4">
            <div className="text-center space-y-2">
              <FileText className="w-10 h-10 text-[#CBD5E1] mx-auto" />
              <p className="text-xs text-[#94A3B8]">Slide deck will load here</p>
            </div>
          </div>
        )}

        {lesson.type === "notes" && (
          <div className="prose prose-sm max-w-none">
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 space-y-3">
              <h4 className="text-sm font-bold text-amber-900">{lesson.title}</h4>
              <p className="text-sm text-amber-800">
                Study notes for this topic will appear here. The trainer publishes notes
                alongside the video session for offline review.
              </p>
              <ul className="list-disc pl-4 text-sm text-amber-800 space-y-1">
                <li>Key concept summary</li>
                <li>Interview tips & common patterns</li>
                <li>Further reading links</li>
              </ul>
            </div>
          </div>
        )}

        {lesson.type === "assignment" && (
          <div className="bg-teal-50 border border-teal-200 rounded-xl p-5 space-y-3">
            <h4 className="text-sm font-bold text-teal-900">{lesson.title}</h4>
            <p className="text-sm text-teal-800">
              Complete the problem set below and upload your solution. Your trainer will
              review and provide feedback within 48 hours.
            </p>
            <div className="bg-white rounded-lg p-3 border border-teal-200 text-xs text-[#64748B] font-mono">
              Assignment instructions will be loaded from the content store.
            </div>
          </div>
        )}
      </div>

      {/* Footer: Mark Complete */}
      <div className="p-4 border-t border-[#E2E8F0] flex items-center justify-between gap-3">
        <span className="text-xs text-[#94A3B8]">
          {isCompleted ? t("courses.completed_badge") : `${t("courses.type_" + lesson.type as "courses.type_video")}`}
        </span>
        {isCompleted ? (
          <div className="flex items-center gap-1.5 px-4 py-2 bg-[#DCFCE7] text-[#15803D] text-xs font-bold rounded-lg">
            <CheckCircle2 className="w-4 h-4" />
            {t("courses.completed_badge")}
          </div>
        ) : (
          <button
            onClick={() => onComplete(lesson.id)}
            disabled={completing}
            className="flex items-center gap-1.5 px-4 py-2 bg-[#2BB3A0] hover:bg-[#249B8A] disabled:opacity-60 text-white text-xs font-bold rounded-lg transition-colors"
          >
            {completing ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Check className="w-3.5 h-3.5" />
            )}
            {t("courses.mark_complete")}
          </button>
        )}
      </div>
    </div>
  );
}

// ----------------------------------------------------------------
// Module Accordion
// ----------------------------------------------------------------

interface ModuleAccordionProps {
  mod: ModuleItem;
  selectedLessonId: string | null;
  onSelectLesson: (lesson: LessonItem) => void;
  t: (k: string) => string;
  justCompleted: string | null;
  defaultOpen?: boolean;
}

function ModuleAccordion({ mod, selectedLessonId, onSelectLesson, t, justCompleted, defaultOpen }: ModuleAccordionProps) {
  const [open, setOpen] = useState(defaultOpen ?? true);
  const completedCount = mod.lessons.filter((l) => l.completed || justCompleted === l.id).length;

  return (
    <div className="border border-[#E2E8F0] rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 bg-[#F8FAFC] hover:bg-[#F1F5F9] text-left transition-colors"
        aria-expanded={open}
      >
        <div className="flex-1 min-w-0">
          <span className="text-xs font-bold text-[#0F1F3A] block truncate">{mod.title}</span>
          <span className="text-[11px] text-[#94A3B8]">
            {completedCount}/{mod.lessons.length} {t("courses.lessons_label")}
          </span>
        </div>
        <div className="flex items-center gap-2 ml-2 flex-shrink-0">
          {completedCount === mod.lessons.length && mod.lessons.length > 0 && (
            <CheckCircle2 className="w-4 h-4 text-[#2BB3A0]" />
          )}
          {open ? <ChevronDown className="w-4 h-4 text-[#94A3B8]" /> : <ChevronRight className="w-4 h-4 text-[#94A3B8]" />}
        </div>
      </button>

      {open && (
        <div className="divide-y divide-[#E2E8F0]">
          {mod.lessons.map((les) => {
            const isActive = selectedLessonId === les.id;
            const isDone = les.completed || justCompleted === les.id;
            const typeColor = TYPE_COLORS[les.type] || "text-[#64748B] bg-[#F1F5F9]";

            return (
              <button
                key={les.id}
                onClick={() => onSelectLesson(les)}
                className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors text-xs ${
                  isActive
                    ? "bg-[#EFF6FF] border-l-2 border-[#2B5CD0]"
                    : "hover:bg-[#F8FAFC]"
                }`}
              >
                {/* Completion indicator */}
                <span className="flex-shrink-0">
                  {isDone ? (
                    <CheckCircle2 className="w-4 h-4 text-[#2BB3A0]" />
                  ) : (
                    <Circle className="w-4 h-4 text-[#CBD5E1]" />
                  )}
                </span>

                {/* Type icon */}
                <span className={`flex-shrink-0 p-1 rounded ${typeColor}`}>
                  {TYPE_ICONS[les.type]}
                </span>

                {/* Title */}
                <span className={`flex-1 min-w-0 font-medium truncate ${isActive ? "text-[#2B5CD0]" : "text-[#0F1F3A]"}`}>
                  {les.title}
                </span>

                {/* Duration */}
                {les.duration_min && (
                  <span className="flex-shrink-0 text-[11px] text-[#94A3B8]">{les.duration_min}m</span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ----------------------------------------------------------------
// Main Page
// ----------------------------------------------------------------

export default function CourseDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const courseId = (params?.courseId as string) || "";
  const initialLessonId = searchParams?.get("lesson") ?? null;

  const { user, switchRoleDemo } = useAuth();
  const { t } = useLanguage();

  const [data, setData] = useState<CourseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedLesson, setSelectedLesson] = useState<LessonItem | null>(null);
  const [completing, setCompleting] = useState(false);
  const [justCompleted, setJustCompleted] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  // Role guard
  if (user && user.role !== "student") {
    return (
      <AppShell pageTitle={t("courses.page_title")}>
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6 text-center px-4">
          <div className="w-16 h-16 rounded-full bg-amber-100 flex items-center justify-center">
            <ShieldAlert className="w-8 h-8 text-amber-600" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-[#0F1F3A] mb-1">{t("courses.unauthorized_role")}</h2>
            <p className="text-sm text-[#64748B] max-w-sm">{t("courses.unauthorized_sub")}</p>
          </div>
          <button
            onClick={() => switchRoleDemo("student")}
            className="px-5 py-2.5 bg-[#2B5CD0] hover:bg-[#1D4ED8] text-white text-sm font-semibold rounded-lg transition-colors"
          >
            Switch to Student View
          </button>
        </div>
      </AppShell>
    );
  }

  const load = useCallback(async () => {
    if (!courseId) return;
    setLoading(true);
    setError(null);
    try {
      const detail = await getCourseDetail(courseId);
      setData(detail);

      // Auto-select the lesson from URL param, or first incomplete, or first
      let target: LessonItem | null = null;
      for (const mod of detail.modules) {
        for (const les of mod.lessons) {
          if (initialLessonId && les.id === initialLessonId) {
            target = les;
            break;
          }
          if (!target && !les.completed) target = les;
        }
        if (target && initialLessonId) break;
      }
      // Fallback: very first lesson
      if (!target && detail.modules[0]?.lessons[0]) {
        target = detail.modules[0].lessons[0];
      }
      setSelectedLesson(target);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [courseId, initialLessonId]);

  useEffect(() => { load(); }, [load]);

  const handleComplete = async (lessonId: string) => {
    if (!data) return;
    setCompleting(true);
    try {
      await markLessonProgress(courseId, lessonId);
      setJustCompleted(lessonId);
      setToast(t("courses.lesson_complete_toast"));
      setTimeout(() => setToast(null), 3000);

      // Also update the lesson.completed flag in local state
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          modules: prev.modules.map((mod) => ({
            ...mod,
            lessons: mod.lessons.map((l) =>
              l.id === lessonId ? { ...l, completed: true } : l
            ),
          })),
        };
      });
      if (selectedLesson?.id === lessonId) {
        setSelectedLesson((prev) => prev ? { ...prev, completed: true } : prev);
      }
    } catch (err) {
      console.error("Failed to mark lesson complete", err);
    } finally {
      setCompleting(false);
    }
  };

  const pageTitle = data?.course
    ? data.course.title
    : t("courses.page_title");

  return (
    <AppShell pageTitle={pageTitle}>
      {/* Toast */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 flex items-center gap-2 bg-[#2BB3A0] text-white px-4 py-2.5 rounded-lg shadow-lg text-sm font-semibold animate-in fade-in slide-in-from-top-2">
          <CheckCircle2 className="w-4 h-4" />
          {toast}
        </div>
      )}

      <div className="max-w-7xl mx-auto space-y-4">
        {/* Back link */}
        <Link
          href="/student/courses"
          className="inline-flex items-center gap-1.5 text-xs text-[#64748B] hover:text-[#2B5CD0] font-medium transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          {t("courses.back_to_courses")}
        </Link>

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center min-h-[60vh] gap-3 text-sm text-[#64748B]">
            <RefreshCw className="w-5 h-5 animate-spin text-[#2B5CD0]" />
            {t("courses.loading")}
          </div>
        )}

        {/* Error */}
        {!loading && error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-8 flex flex-col items-center gap-3 text-center">
            <AlertTriangle className="w-8 h-8 text-red-500" />
            <p className="font-bold text-red-800 text-sm">{t("courses.error_title")}</p>
            <p className="text-xs text-red-600">{t("courses.error_sub")}</p>
            <button
              onClick={load}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-bold rounded-lg transition-colors flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              {t("courses.retry")}
            </button>
          </div>
        )}

        {/* Main two-panel layout */}
        {!loading && !error && data && (
          <>
            {/* Course title bar */}
            <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-4 flex items-center gap-4">
              <div
                className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{ backgroundColor: TRACK_COLORS[data.course.thumbnail_color] || "#2B5CD0" }}
              >
                <Lock className="w-5 h-5 text-white opacity-0" />
              </div>
              <div className="flex-1 min-w-0">
                <h1 className="text-sm font-black text-[#0F1F3A] truncate">{data.course.title}</h1>
                <span className="text-[11px] font-semibold text-[#2B5CD0] bg-[#EFF6FF] px-2 py-0.5 rounded-full border border-[#BFDBFE]">
                  {data.course.track}
                </span>
              </div>
              <div className="flex-shrink-0 text-xs text-[#94A3B8]">
                {data.modules.length} {t("courses.modules_label")}
              </div>
            </div>

            {/* Two-panel: sidebar + viewer */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5" style={{ minHeight: "65vh" }}>
              {/* Left panel: module accordion */}
              <div className="lg:col-span-4 space-y-3 overflow-y-auto max-h-[70vh] lg:max-h-none">
                {data.modules.length === 0 && (
                  <div className="bg-white border border-[#E2E8F0] rounded-xl p-8 text-center">
                    <p className="text-sm text-[#94A3B8]">{t("courses.empty_title")}</p>
                  </div>
                )}
                {data.modules.map((mod, idx) => (
                  <ModuleAccordion
                    key={mod.id}
                    mod={mod}
                    selectedLessonId={selectedLesson?.id ?? null}
                    onSelectLesson={setSelectedLesson}
                    t={t}
                    justCompleted={justCompleted}
                    defaultOpen={idx === 0}
                  />
                ))}
              </div>

              {/* Right panel: lesson viewer */}
              <div className="lg:col-span-8 bg-white rounded-xl border border-[#E2E8F0] shadow-sm flex flex-col overflow-hidden">
                <LessonViewer
                  lesson={selectedLesson}
                  courseId={courseId}
                  t={t}
                  onComplete={handleComplete}
                  completing={completing}
                  justCompleted={justCompleted}
                />
              </div>
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}

