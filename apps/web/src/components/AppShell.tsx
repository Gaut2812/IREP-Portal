"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth, Role } from "@/lib/AuthContext";
import { useLanguage } from "@/lib/LanguageContext";
import { NotificationBell } from "@/components/NotificationBell";
import {
  LifeBuoy,
  LayoutDashboard, BookOpen, Code2, FileCheck2, Cpu,
  KanbanSquare, Video, Bot, Award, Briefcase, Radio,
  MessageSquare, Calendar, Users, ClipboardCheck,
  Search, ChevronDown, Languages, LogOut, Menu, X, Mail, ShieldCheck, Building2,
} from "lucide-react";

interface AppShellProps {
  children: React.ReactNode;
  pageTitle?: string;
}

export const AppShell: React.FC<AppShellProps> = ({ children, pageTitle = "Dashboard" }) => {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { language, toggleLanguage, t } = useLanguage();
  const [profileOpen, setProfileOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);

  const role: Role = user?.role || "student";

  // close menus on navigation and on outside click / Escape
  useEffect(() => { setNavOpen(false); setProfileOpen(false); }, [pathname]);
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) setProfileOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { setProfileOpen(false); setNavOpen(false); } };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onClick); document.removeEventListener("keydown", onKey); };
  }, []);

  const roleLabel: Record<Role, string> = {
    student: t("shell.role_student"),
    trainer: t("shell.role_trainer"),
    college: t("shell.role_college"),
    parent: t("shell.role_parent"),
    admin: t("shell.role_admin"),
  };

  const studentNav = [
    { label: t("nav.dashboard"), href: "/student", icon: LayoutDashboard },
    { label: t("nav.my_courses"), href: "/student/courses", icon: BookOpen },
    { label: t("nav.coding_lab"), href: "/student/coding/prob_connected_components", icon: Code2 },
    { label: t("nav.practice_tests"), href: "/student/tests", icon: FileCheck2 },
    { label: t("nav.virtual_labs"), href: "/student/labs", icon: Cpu },
    { label: t("nav.sprint_board"), href: "/student/projects/board", icon: KanbanSquare },
    { label: t("nav.mock_interviews"), href: "/student/interviews", icon: Video },
    { label: t("nav.ai_study_buddy"), href: "/student/buddy", icon: Bot },
    { label: t("nav.certificates"), href: "/student/certificates", icon: Award },
    { label: t("nav.portfolio"), href: "/student/portfolio", icon: Briefcase },
    { label: t("nav.live_sessions"), href: "/student/live", icon: Radio },
    { label: t("nav.checkin"), href: "/student/checkin", icon: ClipboardCheck },
    { label: t("nav.discussions"), href: "/student/discussions", icon: MessageSquare },
  ];

  const trainerNav = [
    { label: t("nav.dashboard"), href: "/trainer", icon: LayoutDashboard },
    { label: t("nav.batches"), href: "/trainer/batches", icon: Users },
    { label: t("nav.schedule"), href: "/trainer/schedule", icon: Calendar },
    { label: t("nav.attendance"), href: "/trainer/attendance", icon: ClipboardCheck },
    { label: t("nav.approvals"), href: "/trainer/approvals", icon: ShieldCheck },
    { label: t("nav.assessments"), href: "/trainer/assessments", icon: FileCheck2 },
    { label: t("nav.code_reviews"), href: "/trainer/reviews", icon: Code2 },
    { label: t("nav.at_risk_students"), href: "/trainer/at-risk", icon: Users },
    { label: t("nav.lab_board"), href: "/trainer/labs", icon: Cpu },
    { label: t("nav.reports"), href: "/trainer/reports", icon: BookOpen },
    { label: t("nav.messages"), href: "/trainer/messages", icon: MessageSquare },
    { label: t("nav.live_classroom"), href: "/live/sess_thu_rag", icon: Radio },
  ];

  const collegeNav = [
    { label: t("nav.overview"), href: "/college", icon: LayoutDashboard },
    { label: t("nav.branches_batches"), href: "/college/structure", icon: Users },
    { label: t("nav.placement_readiness"), href: "/college/readiness", icon: Award },
    { label: t("nav.certifications"), href: "/college/certifications", icon: Award },
    { label: t("nav.events"), href: "/college/events", icon: Calendar },
    { label: t("nav.mock_drives"), href: "/college/drives", icon: Video },
    { label: t("nav.timetable"), href: "/college/timetable", icon: Calendar },
    { label: t("nav.moderation"), href: "/college/moderation", icon: ShieldCheck },
    { label: t("nav.college_messages"), href: "/college/messages", icon: MessageSquare },
    { label: t("nav.surveys"), href: "/college/surveys", icon: BookOpen },
    { label: t("nav.mou_reports"), href: "/college/reports", icon: BookOpen },
    { label: t("nav.settings"), href: "/college/settings", icon: LayoutDashboard },
  ];

  const parentNav = [
    { label: t("nav.overview"), href: "/parent", icon: LayoutDashboard },
    { label: t("nav.progress_reports"), href: "/parent/reports", icon: BookOpen },
    { label: t("nav.attendance"), href: "/parent/attendance", icon: ClipboardCheck },
    { label: t("nav.projects_portfolio"), href: "/parent/portfolio", icon: Briefcase },
    { label: t("nav.certificates"), href: "/parent/certificates", icon: Award },
    { label: t("nav.events"), href: "/parent/events", icon: Calendar },
    { label: t("nav.message_trainer"), href: "/parent/messages", icon: MessageSquare },
    { label: t("nav.feedback_survey"), href: "/parent/surveys", icon: MessageSquare },
  ];

  // IREP staff (screens 45-49)
  const adminNav = [
    { label: t("nav.colleges"), href: "/admin/colleges", icon: Building2 },
    { label: t("nav.content_library"), href: "/admin/content", icon: BookOpen },
    { label: t("nav.usage_billing"), href: "/admin/usage", icon: Cpu },
    { label: t("nav.audit_consent"), href: "/admin/audit", icon: ShieldCheck },
    { label: t("nav.support_desk"), href: "/admin/support", icon: MessageSquare },
  ];

  const currentNav = role === "admin" ? adminNav : role === "trainer" ? trainerNav : role === "college" ? collegeNav : role === "parent" ? parentNav : studentNav;
  const homes = ["/student", "/trainer", "/college", "/parent", "/admin/colleges"];

  const sidebar = (
    <>
      <div>
        <div className="p-4 border-b border-[#1E3A6E] flex items-start justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-[#2BB3A0] to-[#2B5CD0] flex items-center justify-center font-bold text-white text-sm shadow">IR</div>
              <span className="font-bold text-base tracking-wide text-white">IREP Portal</span>
            </div>
            <div className="mt-2 text-[10px] font-semibold tracking-wider text-[#94A3B8] uppercase truncate max-w-[170px]">
              {roleLabel[role]} · {user?.name || ""}
            </div>
          </div>
          <button onClick={() => setNavOpen(false)} className="lg:hidden p-1 rounded hover:bg-[#1E3A6E]" aria-label={t("shell.close_menu")}>
            <X className="w-4 h-4" />
          </button>
        </div>
        <nav className="p-2 space-y-1 overflow-y-auto max-h-[calc(100vh-170px)] scrollbar-none" aria-label={t("shell.main_menu")}>
          {currentNav.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href || (!homes.includes(item.href) && pathname.startsWith(item.href));
            return (
              <Link key={item.href} href={item.href} aria-current={isActive ? "page" : undefined}
                className={`flex items-center gap-2.5 px-3 py-2.5 lg:py-2 rounded-lg text-sm lg:text-xs font-medium transition-all ${isActive ? "bg-[#2B5CD0] text-white shadow-sm font-semibold" : "text-[#CBD5E1] hover:bg-[#1E3A6E] hover:text-white"}`}>
                <Icon className="w-4 h-4 flex-shrink-0" />
                <span className="truncate">{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>
      <div className="p-3 border-t border-[#1E3A6E] text-[10px] text-[#94A3B8] leading-tight text-center">
        Industry-Ready Engineer Program<br />B.Tech Semesters 2 to 7
      </div>
    </>
  );

  return (
    <div className="flex h-screen bg-[#F1F5F9] overflow-hidden">
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex w-[200px] flex-shrink-0 bg-[#14284B] text-white flex-col justify-between z-20">{sidebar}</aside>

      {/* Mobile / tablet drawer */}
      {navOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex" role="dialog" aria-modal="true" aria-label={t("shell.main_menu")}>
          <div className="absolute inset-0 bg-black/50" onClick={() => setNavOpen(false)} />
          <aside className="relative w-[260px] max-w-[80vw] bg-[#14284B] text-white flex flex-col justify-between shadow-2xl" data-testid="mobile-nav">{sidebar}</aside>
        </div>
      )}

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="h-14 bg-white border-b border-[#E2E8F0] px-3 sm:px-6 flex items-center justify-between gap-2 flex-shrink-0 z-10">
          <div className="flex items-center gap-2 min-w-0">
            <button onClick={() => setNavOpen(true)} className="lg:hidden p-2 -ml-1 rounded-lg hover:bg-[#F1F5F9]" aria-label={t("shell.open_menu")} data-testid="open-nav">
              <Menu className="w-5 h-5 text-[#0F1F3A]" />
            </button>
            <h1 className="text-sm sm:text-base font-bold text-[#0F1F3A] truncate">{pageTitle}</h1>
          </div>

          <div className="flex items-center gap-1.5 sm:gap-3 flex-shrink-0">
            <div className="relative hidden md:block w-56 xl:w-64">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#94A3B8]" />
              <input type="text" placeholder={t("shell.search")} aria-label={t("shell.search")}
                className="w-full pl-9 pr-3 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg text-xs text-[#0F1F3A] placeholder-[#94A3B8] focus:outline-none focus:border-[#2B5CD0] focus:bg-white" />
            </div>

            <button onClick={toggleLanguage} title="Tamil / English" data-testid="lang-toggle"
              className="flex items-center gap-1.5 px-2 sm:px-2.5 py-1.5 bg-[#F1F5F9] hover:bg-[#E2E8F0] text-[#0F1F3A] text-xs font-semibold rounded-lg transition-colors border border-[#E2E8F0]">
              <Languages className="w-3.5 h-3.5 text-[#2B5CD0]" />
              <span>{language === "en" ? "தமிழ்" : "English"}</span>
            </button>

            <NotificationBell />

            {/* Profile menu (sign out lives here) */}
            <div className="relative" ref={profileRef}>
              <button onClick={() => setProfileOpen(!profileOpen)} aria-haspopup="menu" aria-expanded={profileOpen} data-testid="profile-button"
                className="flex items-center gap-1.5 p-0.5 sm:pr-2 rounded-full hover:bg-[#F1F5F9] transition-colors" aria-label={t("shell.profile")}>
                <span className="w-8 h-8 rounded-full bg-[#2BB3A0] text-white flex items-center justify-center font-bold text-xs shadow-sm">{user?.avatar || "?"}</span>
                <ChevronDown className="w-3.5 h-3.5 text-[#64748B] hidden sm:block" />
              </button>
              {profileOpen && (
                <div role="menu" data-testid="profile-menu" className="absolute right-0 mt-1.5 w-64 max-w-[calc(100vw-24px)] bg-white rounded-xl shadow-xl border border-[#E2E8F0] z-50 text-xs overflow-hidden">
                  <div className="p-4 bg-[#F8FAFC] border-b border-[#E2E8F0] flex items-center gap-3">
                    <span className="w-11 h-11 rounded-full bg-[#2BB3A0] text-white flex items-center justify-center font-bold text-sm flex-shrink-0">{user?.avatar || "?"}</span>
                    <div className="min-w-0">
                      <div className="font-bold text-sm text-[#0F1F3A] truncate" data-testid="profile-name">{user?.name}</div>
                      <div className="text-[11px] font-semibold text-[#2B5CD0]">{roleLabel[role]}</div>
                    </div>
                  </div>
                  <div className="p-3 space-y-2 text-[#334155]">
                    {user?.email && <div className="flex items-center gap-2 min-w-0"><Mail className="w-3.5 h-3.5 text-[#94A3B8] flex-shrink-0" /><span className="truncate">{user.email}</span></div>}
                    <div className="flex items-center gap-2"><Building2 className="w-3.5 h-3.5 text-[#94A3B8]" /><span>{t("shell.college_name")}</span></div>
                    <div className="flex items-center gap-2"><ShieldCheck className="w-3.5 h-3.5 text-[#94A3B8]" /><span>{t("shell.language")}: {language === "ta" ? "தமிழ்" : "English"}</span></div>
                  </div>
                  <div className="border-t border-[#E2E8F0] p-1">
                    {/* L39: report a problem from any screen (screen 49) */}
                    <Link role="menuitem" href={`/support?from=${encodeURIComponent(pathname || "/")}`} data-testid="report-problem"
                      className="w-full text-left px-3 py-2.5 text-[#334155] hover:bg-[#F1F5F9] rounded-lg flex items-center gap-2 font-semibold">
                      <LifeBuoy className="w-4 h-4" /><span>{t("shell.report_problem")}</span>
                    </Link>
                    <button role="menuitem" onClick={logout} data-testid="sign-out"
                      className="w-full text-left px-3 py-2.5 text-red-600 hover:bg-red-50 rounded-lg flex items-center gap-2 font-semibold">
                      <LogOut className="w-4 h-4" /><span>{t("shell.sign_out")}</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-3 sm:p-6">{children}</main>
      </div>
    </div>
  );
};
