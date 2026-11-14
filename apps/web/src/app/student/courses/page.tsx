"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/lib/AuthContext";
import { useLanguage } from "@/lib/LanguageContext";
import { getCourses, CourseCard } from "@/lib/api";
import {
  BookOpen, AlertTriangle, RefreshCw, ChevronRight,
  Video, FileText, StickyNote, ClipboardList, ShieldAlert,
  GraduationCap,
} from "lucide-react";

// ----------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------

const TRACK_FILTERS = ["all", "DSA", "AI & DS", "Cloud & DevOps"] as const;
type TrackFilter = typeof TRACK_FILTERS[number];

const COLOR_MAP: Record<string, string> = {
  blue:   "from-blue-500 to-blue-700",
  teal:   "from-teal-500 to-teal-700",
  purple: "from-purple-500 to-purple-700",
  green:  "from-green-500 to-green-700",
  amber:  "from-amber-500 to-amber-700",
};

function ProgressRing({ pct, size = 48 }: { pct: number; size?: number }) {
  const r = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const dash = circ * (pct / 100);
  return (
    <svg width={size} height={size} className="rotate-[-90deg]">
      <circle cx={size / 2} cy={size / 2} r={r} stroke="#E2E8F0" strokeWidth={6} fill="none" />
      <circle
        cx={size / 2} cy={size / 2} r={r}
        stroke="#2BB3A0" strokeWidth={6} fill="none"
        strokeDasharray={`${dash} ${circ}`}
        strokeLinecap="round"
        style={{ transition: "stroke-dasharray 0.6s ease" }}
      />
    </svg>
  );
}

const typeIcon: Record<string, React.ReactNode> = {
  video:      <Video className="w-3.5 h-3.5" />,
  slides:     <FileText className="w-3.5 h-3.5" />,
  notes:      <StickyNote className="w-3.5 h-3.5" />,
  assignment: <ClipboardList className="w-3.5 h-3.5" />,
};

// ----------------------------------------------------------------
// Skeleton
// ----------------------------------------------------------------

function CourseSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm overflow-hidden animate-pulse">
      <div className="h-24 bg-[#E2E8F0]" />
      <div className="p-4 space-y-3">
        <div className="h-4 bg-[#E2E8F0] rounded w-3/4" />
        <div className="h-3 bg-[#E2E8F0] rounded w-1/2" />
        <div className="h-2 bg-[#E2E8F0] rounded w-full" />
        <div className="h-8 bg-[#E2E8F0] rounded w-full" />
      </div>
    </div>
  );
}

// ----------------------------------------------------------------
// Role Guard component (matches practice-test pattern)
// ----------------------------------------------------------------

function RoleGuard({ t, switchRoleDemo }: { t: (k: string) => string; switchRoleDemo: (r: "student") => void }) {
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

// ----------------------------------------------------------------
// Course Card
// ----------------------------------------------------------------

function CourseCardUI({ course, t, language }: { course: CourseCard; t: (k: string) => string; language: string }) {
  const gradClass = COLOR_MAP[course.thumbnail_color] || COLOR_MAP.blue;
  const title = language === "ta" && course.title_ta ? course.title_ta : course.title;
  const isComplete = course.progress_pct === 100;

  return (
    <div className="course-card bg-white rounded-xl border border-[#E2E8F0] shadow-sm overflow-hidden hover:shadow-md transition-shadow flex flex-col">
      {/* Thumbnail strip */}
      <div className={`h-24 bg-gradient-to-br ${gradClass} flex items-center justify-center`}>
        <GraduationCap className="w-10 h-10 text-white/70" />
      </div>

      <div className="p-4 flex flex-col flex-1 gap-3">
        {/* Track chip */}
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold bg-[#EFF6FF] text-[#2B5CD0] px-2 py-0.5 rounded-full border border-[#BFDBFE]">
            {course.track}
          </span>
          {isComplete && (
            <span className="text-[10px] font-bold bg-[#DCFCE7] text-[#15803D] px-2 py-0.5 rounded-full border border-[#BBF7D0]">
              {t("courses.completed_badge")}
            </span>
          )}
        </div>

        {/* Title */}
        <h3 className="text-sm font-bold text-[#0F1F3A] leading-snug line-clamp-2 flex-1">{title}</h3>

        {/* Progress bar + ring */}
        <div className="flex items-center gap-3">
          <ProgressRing pct={course.progress_pct} size={44} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-[#64748B]">{t("courses.progress_label")}</span>
              <span className="font-bold text-[#0F1F3A]">{course.progress_pct}%</span>
            </div>
            <div className="h-1.5 bg-[#E2E8F0] rounded-full overflow-hidden">
              <div
                className="h-full bg-[#2BB3A0] rounded-full transition-all"
                style={{ width: `${course.progress_pct}%` }}
              />
            </div>
            <div className="text-[11px] text-[#94A3B8] mt-0.5">
              {course.completed_lessons} {t("courses.of")} {course.total_lessons} {t("courses.lessons_label")}
            </div>
          </div>
        </div>

        {/* CTA */}
        <Link
          href={`/student/courses/${course.id}${course.resume_lesson_id ? `?lesson=${course.resume_lesson_id}` : ""}`}
          className="flex items-center justify-center gap-1.5 px-4 py-2 bg-[#2B5CD0] hover:bg-[#1D4ED8] text-white text-xs font-bold rounded-lg transition-colors mt-auto"
        >
          {isComplete ? t("courses.completed_badge") : (course.completed_lessons > 0 ? t("courses.resume_btn") : t("courses.start_btn"))}
          <ChevronRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    </div>
  );
}

// ----------------------------------------------------------------
// Main Page
// ----------------------------------------------------------------

export default function CoursesPage() {
  const { user, switchRoleDemo } = useAuth();
  const { t, language } = useLanguage();

  const [activeTab, setActiveTab] = useState<TrackFilter>("all");
  const [courses, setCourses] = useState<CourseCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Role guard
  if (user && user.role !== "student") {
    return <RoleGuard t={t} switchRoleDemo={switchRoleDemo} />;
  }

  const loadCourses = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const track = activeTab === "all" ? undefined : activeTab;
      const data = await getCourses(track);
      setCourses(data.courses);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    loadCourses();
  }, [loadCourses]);

  const tabLabels: Record<TrackFilter, string> = {
    all:             t("courses.tab_all"),
    DSA:             t("courses.tab_dsa"),
    "AI & DS":       t("courses.tab_ai"),
    "Cloud & DevOps": t("courses.tab_cloud"),
  };

  return (
    <AppShell pageTitle={t("courses.page_title")}>
      <div className="space-y-6 max-w-7xl mx-auto">

        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h2 className="text-xl font-black text-[#0F1F3A]">{t("courses.page_title")}</h2>
            <p className="text-sm text-[#64748B] mt-0.5">{t("courses.subtitle")}</p>
          </div>
          <div className="flex items-center gap-2 text-xs text-[#64748B]">
            <BookOpen className="w-4 h-4 text-[#2B5CD0]" />
            <span>{courses.length} {t("courses.lessons_label")}</span>
          </div>
        </div>

        {/* Track Tabs */}
        <div className="flex gap-2 flex-wrap">
          {TRACK_FILTERS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                activeTab === tab
                  ? "bg-[#2B5CD0] text-white border-[#2B5CD0] shadow-sm"
                  : "bg-white text-[#64748B] border-[#E2E8F0] hover:border-[#2B5CD0] hover:text-[#2B5CD0]"
              }`}
            >
              {tabLabels[tab]}
            </button>
          ))}
        </div>

        {/* Loading State */}
        {loading && (
          <div>
            <p className="text-xs text-[#64748B] mb-4 flex items-center gap-2">
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              {t("courses.loading")}
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
              {[1, 2, 3].map((i) => <CourseSkeleton key={i} />)}
            </div>
          </div>
        )}

        {/* Error State */}
        {!loading && error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-6 flex flex-col items-center gap-3 text-center">
            <AlertTriangle className="w-8 h-8 text-red-500" />
            <div>
              <p className="font-bold text-red-800 text-sm">{t("courses.error_title")}</p>
              <p className="text-xs text-red-600 mt-1">{t("courses.error_sub")}</p>
            </div>
            <button
              onClick={loadCourses}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-bold rounded-lg transition-colors flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              {t("courses.retry")}
            </button>
          </div>
        )}

        {/* Empty State */}
        {!loading && !error && courses.length === 0 && (
          <div className="bg-white border border-[#E2E8F0] rounded-xl p-10 flex flex-col items-center gap-4 text-center">
            <div className="w-16 h-16 rounded-full bg-[#EFF6FF] flex items-center justify-center">
              <BookOpen className="w-8 h-8 text-[#2B5CD0]" />
            </div>
            <div>
              <p className="font-bold text-[#0F1F3A] text-base">{t("courses.empty_title")}</p>
              <p className="text-sm text-[#64748B] mt-1 max-w-xs">{t("courses.empty_sub")}</p>
            </div>
          </div>
        )}

        {/* Course Grid */}
        {!loading && !error && courses.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {courses.map((c) => (
              <CourseCardUI key={c.id} course={c} t={t} language={language} />
            ))}
          </div>
        )}

      </div>
    </AppShell>
  );
}

