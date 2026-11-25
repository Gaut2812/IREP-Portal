"use client";

import React, { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { fetchApi } from "@/lib/api";
import {
  Briefcase, Calendar, CheckCircle2, ExternalLink,
  Award, Sparkles, UserCheck, Clock, MapPin, Users,
  AlertCircle, RefreshCw, ThumbsUp, XCircle, HeartHandshake,
  Laptop
} from "lucide-react";

interface ParentProject {
  id: string;
  title: string;
  tagline?: string;
  category: string;
  what_ward_built: string;
  role_description?: string;
  team_size: number;
  team_name: string;
  tech_stack: string[];
  live_demo_url?: string;
  github_url: string;
  status: string;
  score_percent: number;
  trainer_feedback?: string;
  is_featured: boolean;
}

interface DemoDayInfo {
  id: string;
  title: string;
  event_date: string;
  venue: string;
  description: string;
  rsvp_status: string; // none, attending, declined
  guest_count: number;
}

interface PracticalSkill {
  skill: string;
  tamil_label: string;
  description: string;
  level: string;
}

interface ParentPortfolioData {
  ward: {
    name: string;
    details: string;
    college: string;
    readiness_score: number;
    readiness_band: string;
  };
  milestone_progress: {
    sprint_name: string;
    active_project: string;
    progress_percent: number;
    completed_points: number;
    total_points: number;
    status_text: string;
    deadline: string;
    build_status: string;
  };
  featured_projects: ParentProject[];
  mentor_evaluation: {
    trainer_name: string;
    title: string;
    remark: string;
  };
  demo_day_invitation: DemoDayInfo;
  practical_skills: PracticalSkill[];
}

export default function ParentPortfolioPage() {
  const { t, language } = useLanguage();
  const [data, setData] = useState<ParentPortfolioData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rsvpLoading, setRsvpLoading] = useState(false);
  const [rsvpFeedback, setRsvpFeedback] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchApi<ParentPortfolioData>(`/parent/portfolio?lang=${language}`);
      setData(res);
    } catch (err: any) {
      console.warn("API fetch failed, falling back to offline defaults:", err);
      setData({
        ward: {
          name: "Priya R",
          details: "Sem 5 · AI & DS",
          college: "Demo Engineering College",
          readiness_score: 74,
          readiness_band: language === "ta" ? "கிட்டத்தட்ட தயார்" : "Nearly Ready"
        },
        milestone_progress: {
          sprint_name: "Sprint 2 of 3",
          active_project: "Clinic Appointment & Token System",
          progress_percent: 58,
          completed_points: 21,
          total_points: 36,
          status_text: language === "ta" ? "சரியான பாதையில் உள்ளது" : "On Track",
          deadline: "Week 8 Capstone Deadline",
          build_status: "Passing · Deployed to Staging"
        },
        featured_projects: [
          {
            id: "proj_crop_01",
            title: "Crop Price Predictor",
            tagline: "Machine learning system for forecasting agricultural market prices",
            category: "machine_learning",
            what_ward_built: "Priya led the machine learning forecasting model for this farming tool, helping farmers predict market selling prices before harvesting.",
            role_description: "Led ML pipeline development and FastAPI prediction endpoints.",
            team_size: 3,
            team_name: "Team AgriVision",
            tech_stack: ["Python", "FastAPI", "Scikit-Learn", "Streamlit"],
            live_demo_url: "https://crop-price-demo.demo.edu",
            github_url: "https://github.com/priya-r/crop-price-predictor",
            status: "deployed",
            score_percent: 94,
            trainer_feedback: "Exceptional model validation and clear modular structure. Priya demonstrated deep grasp of cross-validation.",
            is_featured: true
          },
          {
            id: "proj_clinic_02",
            title: "Clinic Appointment & Token System",
            tagline: "Real-time patient scheduling and digital queue management portal",
            category: "fullstack",
            what_ward_built: "Priya developed the secure patient appointment engine and doctor availability schedule.",
            role_description: "Architected backend REST APIs and Next.js patient booking UI.",
            team_size: 4,
            team_name: "Team Phoenix",
            tech_stack: ["React", "Next.js", "FastAPI", "PostgreSQL"],
            live_demo_url: "https://clinic-demo.demo.edu",
            github_url: "https://github.com/priya-r/clinic-appointment-portal",
            status: "in_progress",
            score_percent: 88,
            trainer_feedback: "Clean separation of concerns between appointment scheduling and notification queues.",
            is_featured: true
          }
        ],
        mentor_evaluation: {
          trainer_name: "Arun Kumar",
          title: "Lead Software Architecture Trainer",
          remark: language === "ta"
            ? "பயிர் விலை கணிப்பு மற்றும் கிளினிக் நியமனத் திட்டங்கள் இரண்டிலும் பிரியா பாராட்டத்தக்க தலைமைப் பாத்திரத்தை வகித்துள்ளார்."
            : "Priya has taken an admirable leadership role in both the Crop Price Predictor and Clinic Appointment projects. Her code passes all automated unit tests."
        },
        demo_day_invitation: {
          id: "event_demo_day_nov",
          title: "Project Demo Day – Capstone Showcase",
          event_date: "Sat, Nov 8 · 10:00 AM – 1:00 PM",
          venue: "Auditorium A & Live Stream",
          description: "Annual Industry-Ready Engineer Program Capstone Presentation. Parents and industry mentors are invited to watch students present live working software applications.",
          rsvp_status: "none",
          guest_count: 1
        },
        practical_skills: [
          {
            skill: "Full-Stack Web Development",
            tamil_label: "முழுமையான வலைப்பயன்பாட்டு உருவாக்கம்",
            description: "Able to design and build complete web applications with modern frontend and backend databases.",
            level: "Proficient"
          },
          {
            skill: "Machine Learning & AI Modeling",
            tamil_label: "இயந்திரக் கற்றல் மற்றும் AI மாடலிங்",
            description: "Applies predictive algorithms to solve real-world agricultural and business forecasting problems.",
            level: "Advanced"
          },
          {
            skill: "API & Database Architecture",
            tamil_label: "API மற்றும் தரவுத்தள வடிவமைப்பு",
            description: "Designs high-speed, secure data pipelines and structured PostgreSQL storage.",
            level: "Proficient"
          }
        ]
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [language]);

  const handleRsvp = async (status: "attending" | "declined") => {
    if (!data) return;
    setRsvpLoading(true);
    setRsvpFeedback(null);
    try {
      await fetchApi("/parent/portfolio/rsvp", {
        method: "POST",
        body: JSON.stringify({
          event_id: data.demo_day_invitation.id,
          status,
          guest_count: 1
        })
      });
    } catch (err: any) {
      console.warn("RSVP API call failed, updating optimistically:", err);
    } finally {
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          demo_day_invitation: {
            ...prev.demo_day_invitation,
            rsvp_status: status
          }
        };
      });

      setRsvpFeedback(
        status === "attending"
          ? t("parent_portfolio.rsvp_status_confirmed")
          : t("parent_portfolio.rsvp_status_updated")
      );
      setRsvpLoading(false);
    }
  };

  return (
    <RoleGuard allowedRoles={["parent"]}>
      <AppShell pageTitle={t("parent_portfolio.title")} header={false}>
        <div className="max-w-5xl mx-auto space-y-8 pb-16">
          {/* Header & Subtitle */}
          <div>
            <h1 className="text-2xl font-black text-[#0F1F3A] tracking-tight flex items-center gap-2.5">
              <Briefcase className="w-6 h-6 text-[#2B5CD0]" />
              <span>{t("parent_portfolio.title")}</span>
            </h1>
            <p className="text-sm text-[#64748B] mt-1 font-medium">
              {t("parent_portfolio.subtitle")}
            </p>
          </div>

          {/* Loading Skeleton */}
          {loading && !data && (
            <div className="space-y-6">
              <div className="h-40 bg-white rounded-2xl border border-[#E2E8F0] p-6 animate-pulse" />
              <div className="h-32 bg-white rounded-2xl border border-[#E2E8F0] animate-pulse" />
              <div className="h-64 bg-white rounded-2xl border border-[#E2E8F0] animate-pulse" />
            </div>
          )}

          {/* Error State */}
          {error && (
            <div className="bg-[#FEF2F2] border border-[#FCA5A5] rounded-2xl p-6 text-center space-y-3">
              <AlertCircle className="w-8 h-8 text-[#DC2626] mx-auto" />
              <h3 className="text-base font-bold text-[#991B1B]">{t("parent_portfolio.error_loading")}</h3>
              <p className="text-xs text-[#B91C1C]">{error}</p>
              <button
                onClick={loadData}
                className="px-4 py-2 bg-[#DC2626] text-white text-xs font-bold rounded-xl hover:bg-[#B91C1C] transition cursor-pointer"
              >
                {t("parent_portfolio.retry")}
              </button>
            </div>
          )}

          {data && (
            <>
              {/* Ward Overview Banner */}
              <div className="bg-gradient-to-r from-[#14284B] via-[#1E3A6E] to-[#2B5CD0] rounded-2xl p-6 md:p-8 text-white shadow-md relative overflow-hidden">
                <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
                  <div className="flex items-center gap-4">
                    <div className="w-16 h-16 rounded-2xl bg-white/10 backdrop-blur-xs border border-white/20 flex items-center justify-center font-black text-2xl text-white shadow-inner flex-shrink-0">
                      PR
                    </div>
                    <div>
                      <div className="text-[11px] uppercase tracking-wider text-[#93C5FD] font-bold">
                        {t("parent_portfolio.ward_banner_title")}
                      </div>
                      <h2 className="text-2xl font-black text-white mt-0.5">
                        {data.ward.name}
                      </h2>
                      <p className="text-xs text-[#CBD5E1] mt-1 font-medium">
                        {data.ward.details} · {data.ward.college}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 bg-white/10 backdrop-blur-xs border border-white/20 px-4 py-3 rounded-xl self-stretch md:self-auto justify-between md:justify-start">
                    <div className="text-right">
                      <div className="text-[10px] uppercase font-bold text-[#93C5FD]">
                        {language === "ta" ? "தயார்நிலை மதிப்பீடு" : "Placement Readiness"}
                      </div>
                      <div className="text-xl font-black text-white">
                        {data.ward.readiness_score} / 100
                      </div>
                    </div>
                    <span className="text-[11px] font-bold px-2.5 py-1 rounded-full bg-[#DCFCE7] text-[#15803D]">
                      {data.ward.readiness_band}
                    </span>
                  </div>
                </div>
              </div>

              {/* Active Capstone Milestone Progress */}
              <div className="bg-white rounded-2xl border border-[#E2E8F0] p-6 shadow-sm space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[#2B5CD0] bg-[#EFF6FF] px-2 py-0.5 rounded-md">
                      {t("parent_portfolio.active_capstone")}
                    </span>
                    <h3 className="text-base font-bold text-[#0F1F3A] mt-1">
                      {data.milestone_progress.active_project}
                    </h3>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 text-xs font-bold text-[#15803D] bg-[#DCFCE7] px-2.5 py-1 rounded-full border border-[#86EFAC]">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>{data.milestone_progress.status_text}</span>
                    </span>
                    <span className="text-xs font-semibold text-[#64748B]">
                      {data.milestone_progress.sprint_name}
                    </span>
                  </div>
                </div>

                {/* Progress Bar */}
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs font-bold text-[#0F1F3A]">
                    <span>{t("parent_portfolio.sprint_progress")}</span>
                    <span>{data.milestone_progress.progress_percent}%</span>
                  </div>
                  <div className="w-full h-3 bg-[#F1F5F9] rounded-full overflow-hidden border border-[#E2E8F0]">
                    <div
                      className="h-full bg-gradient-to-r from-[#2BB3A0] to-[#2B5CD0] rounded-full transition-all duration-500"
                      style={{ width: `${data.milestone_progress.progress_percent}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-[11px] text-[#64748B] pt-0.5">
                    <span>{data.milestone_progress.completed_points} / {data.milestone_progress.total_points} Story Points Delivered</span>
                    <span className="font-semibold text-[#2B5CD0]">{data.milestone_progress.build_status}</span>
                  </div>
                </div>
              </div>

              {/* Parent-Friendly Projects Showcase */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-bold text-[#0F1F3A] flex items-center gap-2">
                    <Laptop className="w-5 h-5 text-[#2B5CD0]" />
                    <span>{language === "ta" ? "பிரியாவின் பொறியியல் திட்டப்பணிகள்" : "Priya's Working Software Projects"}</span>
                  </h3>
                  <span className="text-xs text-[#64748B] font-semibold">
                    {data.featured_projects.length} {t("parent_portfolio.live_projects_count")}
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {data.featured_projects.map((proj) => (
                    <div
                      key={proj.id}
                      className="bg-white rounded-2xl border border-[#E2E8F0] p-6 shadow-sm hover:shadow-md transition flex flex-col justify-between space-y-5"
                    >
                      <div className="space-y-3">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-[#EEF2FF] text-[#4338CA] uppercase">
                            {proj.category.replace("_", " ")}
                          </span>
                          <span className="text-xs font-bold text-[#15803D] bg-[#DCFCE7] px-2 py-0.5 rounded-full border border-[#86EFAC]">
                            Score: {proj.score_percent}%
                          </span>
                        </div>

                        <div>
                          <h4 className="text-base font-bold text-[#0F1F3A]">{proj.title}</h4>
                          <p className="text-xs text-[#475569] mt-1 font-medium leading-relaxed">
                            {proj.what_ward_built}
                          </p>
                        </div>

                        {/* Team Contribution */}
                        <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-3 text-[11px] space-y-1">
                          <div className="font-bold text-[#0F1F3A] flex items-center gap-1.5">
                            <Users className="w-3.5 h-3.5 text-[#2B5CD0]" />
                            <span>{t("parent_portfolio.role_and_team")}:</span>
                          </div>
                          <p className="text-[#64748B]">
                            {proj.role_description} ({proj.team_name} · Team of {proj.team_size})
                          </p>
                        </div>

                        {/* Trainer Quote */}
                        {proj.trainer_feedback && (
                          <div className="bg-[#F0FDF4] border border-[#BBF7D0] rounded-xl p-3 text-[11px] text-[#166534] italic">
                            &ldquo;{proj.trainer_feedback}&rdquo;
                          </div>
                        )}
                      </div>

                      {/* Live Demo Action */}
                      <div className="pt-2">
                        {proj.live_demo_url ? (
                          <a
                            href={proj.live_demo_url}
                            target="_blank"
                            rel="noreferrer"
                            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-[#2BB3A0] hover:bg-[#239988] text-white text-xs font-bold rounded-xl shadow-sm transition"
                          >
                            <ExternalLink className="w-4 h-4" />
                            <span>{t("parent_portfolio.view_live_project")}</span>
                          </a>
                        ) : (
                          <div className="text-center py-2 text-xs font-semibold text-[#94A3B8] bg-[#F1F5F9] rounded-xl">
                            {language === "ta" ? "உள்நாட்டு சோதனை சூழலில் உள்ளது" : "In Staging Environment"}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Project Demo Day Invitation & RSVP Card */}
              <div className="bg-white rounded-2xl border-2 border-[#2B5CD0]/30 p-6 md:p-8 shadow-sm space-y-6 relative overflow-hidden">
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                  <div className="space-y-1.5">
                    <span className="text-[11px] font-black uppercase tracking-wider text-[#2B5CD0] bg-[#EFF6FF] px-2.5 py-1 rounded-md border border-[#BFDBFE]">
                      {t("parent_portfolio.demo_day_title")}
                    </span>
                    <h3 className="text-lg font-black text-[#0F1F3A]">
                      {data.demo_day_invitation.title}
                    </h3>
                    <p className="text-xs text-[#64748B] max-w-xl">
                      {data.demo_day_invitation.description}
                    </p>
                  </div>

                  <div className="flex-shrink-0">
                    {data.demo_day_invitation.rsvp_status === "attending" ? (
                      <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-[#DCFCE7] text-[#15803D] border border-[#86EFAC]">
                        <CheckCircle2 className="w-4 h-4" />
                        <span>{language === "ta" ? "பங்கேற்பது உறுதி செய்யப்பட்டது" : "Attending Confirmed"}</span>
                      </span>
                    ) : data.demo_day_invitation.rsvp_status === "declined" ? (
                      <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-[#FEE2E2] text-[#DC2626] border border-[#FCA5A5]">
                        <XCircle className="w-4 h-4" />
                        <span>{language === "ta" ? "கலந்துகொள்ள இயலாது" : "Declined"}</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-[#FEF3C7] text-[#B45309] border border-[#FDE68A]">
                        <Clock className="w-4 h-4" />
                        <span>{language === "ta" ? "பதில் நிலுவையில் உள்ளது" : "RSVP Pending"}</span>
                      </span>
                    )}
                  </div>
                </div>

                {/* Event Schedule Strip */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-4">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-[#EFF6FF] text-[#2B5CD0] flex items-center justify-center">
                      <Calendar className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-[11px] text-[#64748B] font-semibold">{language === "ta" ? "தேதி & நேரம்" : "Date & Time"}</div>
                      <div className="text-xs font-bold text-[#0F1F3A]">{data.demo_day_invitation.event_date}</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-[#F5F3FF] text-[#7C5CE0] flex items-center justify-center">
                      <MapPin className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-[11px] text-[#64748B] font-semibold">{language === "ta" ? "இடம்" : "Venue"}</div>
                      <div className="text-xs font-bold text-[#0F1F3A]">{data.demo_day_invitation.venue}</div>
                    </div>
                  </div>
                </div>

                {/* Interactive RSVP Action */}
                <div className="pt-2 border-t border-[#E2E8F0] space-y-3">
                  <div className="text-xs font-bold text-[#0F1F3A]">
                    {t("parent_portfolio.rsvp_heading")}
                  </div>

                  {rsvpFeedback && (
                    <div className="p-3 rounded-xl bg-[#F0FDF4] border border-[#BBF7D0] text-xs font-bold text-[#15803D] flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4" />
                      <span>{rsvpFeedback}</span>
                    </div>
                  )}

                  <div className="flex flex-col sm:flex-row items-center gap-3">
                    <button
                      onClick={() => handleRsvp("attending")}
                      disabled={rsvpLoading || data.demo_day_invitation.rsvp_status === "attending"}
                      className="w-full sm:w-auto px-5 py-2.5 bg-[#2BB3A0] hover:bg-[#239988] text-white text-xs font-bold rounded-xl shadow transition cursor-pointer disabled:opacity-60 flex items-center justify-center gap-2"
                    >
                      <ThumbsUp className="w-4 h-4" />
                      <span>{t("parent_portfolio.rsvp_attending")}</span>
                    </button>

                    <button
                      onClick={() => handleRsvp("declined")}
                      disabled={rsvpLoading || data.demo_day_invitation.rsvp_status === "declined"}
                      className="w-full sm:w-auto px-5 py-2.5 bg-[#F1F5F9] hover:bg-[#E2E8F0] text-[#475569] text-xs font-bold rounded-xl border border-[#CBD5E1] transition cursor-pointer disabled:opacity-60 flex items-center justify-center gap-2"
                    >
                      <XCircle className="w-4 h-4" />
                      <span>{t("parent_portfolio.rsvp_declined")}</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Mentor Remark Card */}
              <div className="bg-white rounded-2xl border border-[#E2E8F0] p-6 shadow-sm space-y-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-[#EFF6FF] text-[#2B5CD0] flex items-center justify-center font-bold text-sm">
                    AK
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-[#0F1F3A]">{data.mentor_evaluation.trainer_name}</h4>
                    <p className="text-[11px] text-[#64748B]">{data.mentor_evaluation.title}</p>
                  </div>
                </div>
                <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-4 text-xs text-[#334155] leading-relaxed italic">
                  &ldquo;{data.mentor_evaluation.remark}&rdquo;
                </div>
              </div>

              {/* Practical Skills Mastered */}
              <div className="bg-white rounded-2xl border border-[#E2E8F0] p-6 shadow-sm space-y-4">
                <h3 className="text-base font-bold text-[#0F1F3A] flex items-center gap-2">
                  <Award className="w-5 h-5 text-[#2B5CD0]" />
                  <span>{t("parent_portfolio.practical_skills_title")}</span>
                </h3>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  {data.practical_skills.map((s, idx) => (
                    <div
                      key={idx}
                      className="border border-[#E2E8F0] rounded-xl p-4 bg-[#F8FAFC] space-y-2 flex flex-col justify-between"
                    >
                      <div>
                        <div className="text-xs font-bold text-[#0F1F3A]">
                          {language === "ta" ? s.tamil_label : s.skill}
                        </div>
                        <p className="text-[11px] text-[#64748B] mt-1 leading-relaxed">
                          {s.description}
                        </p>
                      </div>
                      <div className="pt-2">
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#DCFCE7] text-[#15803D] border border-[#86EFAC]">
                          {s.level}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
