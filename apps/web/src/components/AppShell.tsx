"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth, Role } from "@/lib/AuthContext";
import { useLanguage } from "@/lib/LanguageContext";
import {
  LayoutDashboard, BookOpen, Code2, FileCheck2, Cpu,
  KanbanSquare, Video, Bot, Award, Briefcase, Radio,
  MessageSquare, Calendar, Users, ClipboardCheck,
  Search, Bell, ChevronDown, Languages, LogOut
} from "lucide-react";

interface AppShellProps {
  children: React.ReactNode;
  pageTitle?: string;
}

export const AppShell: React.FC<AppShellProps> = ({ children, pageTitle = "Dashboard" }) => {
  const pathname = usePathname();
  const { user, logout, switchRoleDemo } = useAuth();
  const { language, toggleLanguage, t } = useLanguage();
  const [roleMenuOpen, setRoleMenuOpen] = useState(false);

  const role = user?.role || "student";

  // Role subtitle line matching Section 11.2
  const roleSubtitles: Record<Role, string> = {
    student: "STUDENT · SEM 5 · AI & DS",
    trainer: "TRAINER · ARUN KUMAR",
    college: "COLLEGE · PLACEMENT CELL",
    parent: "PARENT · MR. RAMESH K"
  };

  // Nav menus matching Section 11.2
  const studentNav = [
    { label: t("nav.dashboard"), href: "/student", icon: LayoutDashboard },
    { label: t("nav.my_courses"), href: "/student/courses", icon: BookOpen },
    { label: t("nav.coding_lab"), href: "/student/coding/prob_connected_components", icon: Code2 },
    { label: t("nav.practice_tests"), href: "/student/tests/test_service_aptitude", icon: FileCheck2 },
    { label: t("nav.virtual_labs"), href: "/student/labs", icon: Cpu },
    { label: t("nav.sprint_board"), href: "/student/projects/board", icon: KanbanSquare },
    { label: t("nav.mock_interviews"), href: "/student/interviews", icon: Video },
    { label: t("nav.ai_study_buddy"), href: "/student/buddy", icon: Bot },
    { label: t("nav.certificates"), href: "/student/certificates", icon: Award },
    { label: t("nav.portfolio"), href: "/student/portfolio", icon: Briefcase },
    { label: t("nav.live_sessions"), href: "/student/live", icon: Radio },
    { label: t("nav.discussions"), href: "/student/discussions", icon: MessageSquare }
  ];

  const trainerNav = [
    { label: t("nav.dashboard"), href: "/trainer", icon: LayoutDashboard },
    { label: t("nav.batches"), href: "/trainer/batches", icon: Users },
    { label: t("nav.schedule"), href: "/trainer/schedule", icon: Calendar },
    { label: t("nav.attendance"), href: "/trainer/attendance", icon: ClipboardCheck },
    { label: t("nav.assessments"), href: "/trainer/assessments", icon: FileCheck2 },
    { label: t("nav.code_reviews"), href: "/trainer/reviews", icon: Code2 },
    { label: t("nav.mock_interviews"), href: "/student/interviews", icon: Video },
    { label: t("nav.at_risk_students"), href: "/trainer/at-risk", icon: Users },
    { label: t("nav.reports"), href: "/trainer/reports", icon: BookOpen },
    { label: t("nav.messages"), href: "/trainer/messages", icon: MessageSquare },
    { label: t("nav.live_classroom"), href: "/live/sess_thu_rag", icon: Radio }
  ];

  const collegeNav = [
    { label: t("nav.overview"), href: "/college", icon: LayoutDashboard },
    { label: t("nav.branches_batches"), href: "/college/structure", icon: Users },
    { label: t("nav.placement_readiness"), href: "/college/readiness", icon: Award },
    { label: t("nav.certifications"), href: "/college/certifications", icon: Award },
    { label: t("nav.mock_drives"), href: "/college/drives", icon: Video },
    { label: t("nav.timetable"), href: "/college/timetable", icon: Calendar },
    { label: t("nav.mou_reports"), href: "/college/reports", icon: BookOpen },
    { label: t("nav.settings"), href: "/college/settings", icon: LayoutDashboard }
  ];

  const parentNav = [
    { label: t("nav.overview"), href: "/parent", icon: LayoutDashboard },
    { label: t("nav.progress_reports"), href: "/parent/reports", icon: BookOpen },
    { label: t("nav.attendance"), href: "/parent/attendance", icon: ClipboardCheck },
    { label: t("nav.projects_portfolio"), href: "/parent/portfolio", icon: Briefcase },
    { label: t("nav.certificates"), href: "/parent/certificates", icon: Award },
    { label: t("nav.events"), href: "/parent/events", icon: Calendar },
    { label: t("nav.message_trainer"), href: "/trainer/messages", icon: MessageSquare },
    { label: t("nav.feedback_survey"), href: "/parent/surveys", icon: MessageSquare }
  ];

  const currentNav = role === "trainer" ? trainerNav : (role === "college" ? collegeNav : (role === "parent" ? parentNav : studentNav));

  return (
    <div className="flex h-screen bg-[#F1F5F9] overflow-hidden">
      {/* 200px Sidebar */}
      <aside className="w-[200px] flex-shrink-0 bg-[#14284B] text-white flex flex-col justify-between z-20">
        <div>
          {/* Logo & Header */}
          <div className="p-4 border-b border-[#1E3A6E]">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-[#2BB3A0] to-[#2B5CD0] flex items-center justify-center font-bold text-white text-sm shadow">
                IR
              </div>
              <span className="font-bold text-base tracking-wide text-white">IREP Portal</span>
            </div>
            <div className="mt-2 text-[10px] font-semibold tracking-wider text-[#94A3B8] uppercase">
              {roleSubtitles[role]}
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="p-2 space-y-1 overflow-y-auto max-h-[calc(100vh-170px)] scrollbar-none">
            {currentNav.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href || (item.href !== "/student" && item.href !== "/trainer" && item.href !== "/college" && item.href !== "/parent" && pathname.startsWith(item.href));
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? "bg-[#2B5CD0] text-white shadow-sm font-semibold"
                      : "text-[#CBD5E1] hover:bg-[#1E3A6E] hover:text-white"
                  }`}
                >
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  <span className="truncate">{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-[#1E3A6E] text-[10px] text-[#94A3B8] leading-tight text-center">
          Industry-Ready Engineer Program<br />B.Tech Semesters 2 to 7
        </div>
      </aside>

      {/* Main App Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header Bar */}
        <header className="h-14 bg-white border-b border-[#E2E8F0] px-6 flex items-center justify-between flex-shrink-0 z-10">
          <div className="flex items-center gap-4">
            <h1 className="text-base font-bold text-[#0F1F3A]">{pageTitle}</h1>
          </div>

          <div className="flex items-center gap-4">
            {/* Search Box */}
            <div className="relative hidden md:block w-64">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#94A3B8]" />
              <input
                type="text"
                placeholder="Search courses, tests, students..."
                className="w-full pl-9 pr-3 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg text-xs text-[#0F1F3A] placeholder-[#94A3B8] focus:outline-none focus:border-[#2B5CD0] focus:bg-white"
              />
            </div>

            {/* Language Toggle */}
            <button
              onClick={toggleLanguage}
              className="flex items-center gap-1.5 px-2.5 py-1.5 bg-[#F1F5F9] hover:bg-[#E2E8F0] text-[#0F1F3A] text-xs font-semibold rounded-lg transition-colors border border-[#E2E8F0]"
              title="Toggle Tamil / English"
            >
              <Languages className="w-3.5 h-3.5 text-[#2B5CD0]" />
              <span>{language === "en" ? "தமிழ்" : "English"}</span>
            </button>

            {/* Role Switcher Pill (for previewing all 14 screens) */}
            <div className="relative">
              <button
                onClick={() => setRoleMenuOpen(!roleMenuOpen)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 bg-[#EFF6FF] border border-[#BFDBFE] text-[#1D4ED8] text-xs font-semibold rounded-lg hover:bg-[#DBEAFE] transition-all"
              >
                <span className="capitalize">View as: {role}</span>
                <ChevronDown className="w-3.5 h-3.5" />
              </button>

              {roleMenuOpen && (
                <div className="absolute right-0 mt-1.5 w-44 bg-white rounded-lg shadow-xl border border-[#E2E8F0] py-1 z-50 text-xs">
                  <div className="px-3 py-1 text-[10px] font-bold text-[#94A3B8] uppercase">Switch Role Demo</div>
                  {(["student", "trainer", "college", "parent"] as Role[]).map((r) => (
                    <button
                      key={r}
                      onClick={() => {
                        switchRoleDemo(r);
                        setRoleMenuOpen(false);
                      }}
                      className={`w-full text-left px-3 py-2 hover:bg-[#F1F5F9] capitalize flex items-center justify-between ${
                        role === r ? "font-bold text-[#2B5CD0] bg-[#EFF6FF]" : "text-[#0F1F3A]"
                      }`}
                    >
                      <span>{r} View</span>
                      {role === r && <span className="w-1.5 h-1.5 rounded-full bg-[#2B5CD0]" />}
                    </button>
                  ))}
                  <div className="border-t border-[#E2E8F0] mt-1 pt-1">
                    <button
                      onClick={logout}
                      className="w-full text-left px-3 py-2 text-red-600 hover:bg-red-50 flex items-center gap-2"
                    >
                      <LogOut className="w-3.5 h-3.5" />
                      <span>Sign Out</span>
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Notification Bell */}
            <div className="relative cursor-pointer p-1.5 hover:bg-[#F1F5F9] rounded-full">
              <Bell className="w-4 h-4 text-[#64748B]" />
              <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-[#D93636]" />
            </div>

            {/* User Avatar */}
            <div className="w-8 h-8 rounded-full bg-[#2BB3A0] text-white flex items-center justify-center font-bold text-xs shadow-sm">
              {user?.avatar || "PR"}
            </div>
          </div>
        </header>

        {/* Scrollable Page Body */}
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
};

