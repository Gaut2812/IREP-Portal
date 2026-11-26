"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth, Role } from "@/lib/AuthContext";
import { useLanguage } from "@/lib/LanguageContext";
import { NotificationBell } from "@/components/NotificationBell";
import { PageHeader } from "@/components/ui/PageHeader";
import { cn } from "@/lib/cn";
import { KeyRound,
  LifeBuoy,
  LayoutDashboard, BookOpen, Code2, FileCheck2, Cpu,
  KanbanSquare, Video, Bot, Award, Briefcase, Radio,
  MessageSquare, Calendar, Users, ClipboardCheck,
  Search, ChevronDown, Languages, LogOut, Menu, X, Mail, ShieldCheck, Building2,
} from "lucide-react";
import { BrandMark } from "@/components/ui/BrandMark";

interface AppShellProps {
  children: React.ReactNode;
  /** The screen's h1, shown at the top of the page body. */
  pageTitle?: string;
  /** One line under the title. */
  pageSubtitle?: React.ReactNode;
  /** Buttons on the right of the title. */
  pageActions?: React.ReactNode;
  /** false when the page draws its own h1 (legacy hero headers). */
  header?: boolean;
}

export const AppShell: React.FC<AppShellProps> = ({ children, pageTitle = "Dashboard", pageSubtitle, pageActions, header = true }) => {
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
    { label: t("nav.my_privacy"), href: "/student/privacy", icon: KeyRound },
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
    { label: t("nav.mock_interviews"), href: "/trainer/interviews", icon: Video },
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
    { label: t("nav.billing"), href: "/college/billing", icon: BookOpen },
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
    { label: t("nav.consent"), href: "/parent/consent", icon: ShieldCheck },
  ];

  // IREP staff (screens 45-49)
  const adminNav = [
    { label: t("nav.colleges"), href: "/admin/colleges", icon: Building2 },
    { label: t("nav.content_library"), href: "/admin/content", icon: BookOpen },
    { label: t("nav.usage_billing"), href: "/admin/usage", icon: Cpu },
    { label: t("nav.audit_consent"), href: "/admin/audit", icon: ShieldCheck },
    { label: t("nav.support_desk"), href: "/admin/support", icon: MessageSquare },
    ...(user?.super_admin ? [{ label: t("nav.super_admin"), href: "/admin/super", icon: KeyRound },
                             { label: t("nav.billing"), href: "/admin/billing", icon: Cpu }] : []),
  ];

  const currentNav = role === "admin" ? adminNav : role === "trainer" ? trainerNav : role === "college" ? collegeNav : role === "parent" ? parentNav : studentNav;
  const homes = ["/student", "/trainer", "/college", "/parent", "/admin/colleges"];

  const sidebar = (
    <>
      <div className="flex items-center justify-between gap-2 h-16 px-5 flex-shrink-0">
        <div className="flex items-center gap-2.5 min-w-0">
          <BrandMark className="w-8 h-8" />
          <span className="font-semibold text-heading text-white truncate">IREP Portal</span>
        </div>
        <button onClick={() => setNavOpen(false)} className="lg:hidden p-1.5 rounded-tile text-white/70 hover:bg-navy-2 hover:text-white" aria-label={t("shell.close_menu")}>
          <X className="w-4 h-4" />
        </button>
      </div>
      <nav className="flex-1 min-h-0 px-3 py-2 space-y-0.5 overflow-y-auto scrollbar-none" aria-label={t("shell.main_menu")}>
        {currentNav.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href || (!homes.includes(item.href) && pathname.startsWith(item.href));
          return (
            <Link key={item.href} href={item.href} aria-current={isActive ? "page" : undefined}
              className={cn("flex items-center gap-3 min-h-9 py-2 px-3 rounded-tile text-body leading-5 font-medium transition-colors",
                isActive ? "bg-navy-2 text-white" : "text-white/70 hover:bg-white/5 hover:text-white")}>
              <Icon className={cn("w-4 h-4 flex-shrink-0", isActive ? "text-white" : "text-white/60")} />
              <span className="min-w-0 break-words">{item.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="flex items-center gap-3 px-5 py-4 border-t border-white/10 flex-shrink-0" data-testid="sidebar-user">
        <span className="w-9 h-9 rounded-full bg-navy-2 text-white flex items-center justify-center font-semibold text-label flex-shrink-0">{user?.avatar || "?"}</span>
        <div className="min-w-0">
          <div className="text-label font-semibold text-white truncate">{user?.name || ""}</div>
          <div className="text-caption text-white/60 truncate">{roleLabel[role]} · {t("shell.college_name")}</div>
        </div>
      </div>
    </>
  );

  return (
    <div className="flex h-screen bg-canvas overflow-hidden">
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex w-[240px] flex-shrink-0 bg-navy text-white flex-col z-20">{sidebar}</aside>

      {/* Mobile / tablet drawer */}
      {navOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex" role="dialog" aria-modal="true" aria-label={t("shell.main_menu")}>
          <div className="absolute inset-0 bg-ink/50" onClick={() => setNavOpen(false)} />
          <aside className="relative w-[260px] max-w-[80vw] bg-navy text-white flex flex-col shadow-pop" data-testid="mobile-nav">{sidebar}</aside>
        </div>
      )}

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="h-16 bg-surface border-b border-line px-4 sm:px-6 lg:px-8 flex items-center justify-between gap-3 flex-shrink-0 z-10">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <button onClick={() => setNavOpen(true)} className="lg:hidden p-2 -ml-2 rounded-tile hover:bg-line-soft" aria-label={t("shell.open_menu")} data-testid="open-nav">
              <Menu className="w-5 h-5 text-ink" />
            </button>
            <div className="relative hidden lg:block w-full max-w-sm">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-subtle" />
              <input type="text" placeholder={t("shell.search")} aria-label={t("shell.search")}
                className="w-full h-9 pl-9 pr-3 bg-surface-2 border border-line rounded-tile text-body text-ink placeholder:text-subtle focus:outline-none focus:border-brand focus:bg-surface focus:ring-2 focus:ring-brand/15" />
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-3 flex-shrink-0">
            <button onClick={toggleLanguage} title="Tamil / English" data-testid="lang-toggle"
              className="flex items-center gap-1.5 h-9 px-3 bg-surface hover:bg-surface-2 text-ink text-label font-medium rounded-tile transition-colors border border-line">
              <Languages className="w-4 h-4 text-brand" />
              <span>{language === "en" ? "தமிழ்" : "English"}</span>
            </button>

            <NotificationBell />

            {/* Profile menu (sign out lives here) */}
            <div className="relative" ref={profileRef}>
              <button onClick={() => setProfileOpen(!profileOpen)} aria-haspopup="menu" aria-expanded={profileOpen} data-testid="profile-button"
                className="flex items-center gap-1.5 p-0.5 sm:pr-2 rounded-full hover:bg-line-soft transition-colors" aria-label={t("shell.profile")}>
                <span className="w-8 h-8 rounded-full bg-teal text-white flex items-center justify-center font-semibold text-caption">{user?.avatar || "?"}</span>
                <ChevronDown className="w-4 h-4 text-muted hidden sm:block" />
              </button>
              {profileOpen && (
                <div role="menu" data-testid="profile-menu" className="absolute right-0 mt-2 w-72 max-w-[calc(100vw-24px)] bg-surface rounded-card shadow-pop border border-line z-50 overflow-hidden">
                  <div className="p-4 border-b border-line flex items-center gap-3">
                    <span className="w-10 h-10 rounded-full bg-teal text-white flex items-center justify-center font-semibold text-label flex-shrink-0">{user?.avatar || "?"}</span>
                    <div className="min-w-0">
                      <div className="font-semibold text-body text-ink truncate" data-testid="profile-name">{user?.name}</div>
                      <div className="text-caption text-muted">{roleLabel[role]}</div>
                    </div>
                  </div>
                  <div className="p-4 space-y-2.5 text-label text-ink-soft">
                    {user?.email && <div className="flex items-center gap-2.5 min-w-0"><Mail className="w-4 h-4 text-subtle flex-shrink-0" /><span className="truncate">{user.email}</span></div>}
                    <div className="flex items-center gap-2.5"><Building2 className="w-4 h-4 text-subtle" /><span>{t("shell.college_name")}</span></div>
                    <div className="flex items-center gap-2.5"><ShieldCheck className="w-4 h-4 text-subtle" /><span>{t("shell.language")}: {language === "ta" ? "தமிழ்" : "English"}</span></div>
                  </div>
                  <div className="border-t border-line p-1.5">
                    {/* L39: report a problem from any screen (screen 49) */}
                    <Link role="menuitem" href={`/support?from=${encodeURIComponent(pathname || "/")}`} data-testid="report-problem"
                      className="w-full text-left px-3 h-9 text-label text-ink-soft hover:bg-line-soft rounded-tile flex items-center gap-2.5 font-medium">
                      <LifeBuoy className="w-4 h-4" /><span>{t("shell.report_problem")}</span>
                    </Link>
                    <button role="menuitem" onClick={logout} data-testid="sign-out"
                      className="w-full text-left px-3 h-9 text-label text-danger hover:bg-danger-soft rounded-tile flex items-center gap-2.5 font-medium">
                      <LogOut className="w-4 h-4" /><span>{t("shell.sign_out")}</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {header && <PageHeader title={pageTitle} subtitle={pageSubtitle} actions={pageActions} />}
          {children}
        </main>
      </div>
    </div>
  );
};
