"use client";

import React, { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { useLanguage } from "@/lib/LanguageContext";
import {
  TrendingUp, Award, Flame, CheckCircle2,
  Calendar, ArrowRight, Clock, FolderGit2, Sparkles, ExternalLink
} from "lucide-react";
import Link from "next/link";

export default function StudentDashboardPage() {
  const { t } = useLanguage();
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    fetch("http://localhost:8000/api/v1/student/dashboard")
      .then((res) => res.json())
      .then((d) => setData(d))
      .catch((err) => {
        console.warn("Using offline mock for student dashboard", err);
      });
  }, []);

  // Default values matching PDF 2 exactly
  const student = data?.student || {
    name: "Priya R",
    greeting: "Good morning, Priya 👋",
    readiness_score: 74,
    readiness_band: "Nearly Ready",
    readiness_delta: 6,
    problems_solved: 286,
    problems_delta: 34,
    attendance_pct: 92,
    attendance_target: 85,
    streak_days: 19,
    streak_best: 27
  };

  const skillProgress = data?.skill_progress || [
    { skill: "DSA patterns", percentage: 78, color: "#2BB3A0" },
    { skill: "Aptitude & reasoning", percentage: 71, color: "#2B5CD0" },
    { skill: "Cloud & DevOps", percentage: 64, color: "#7C5CE0" },
    { skill: "AI & Data Science track", percentage: 82, color: "#2BB3A0" },
    { skill: "Future Skills: AI engineering", percentage: 58, color: "#F59E0B" },
    { skill: "Communication", percentage: 69, color: "#2B5CD0" }
  ];

  const thisWeek = data?.this_week || [
    { day: "Mon", topic: "DSA: Pattern drill – Union-Find", duration: "1 hr", isPurple: false },
    { day: "Tue", topic: "Track: Model evaluation lab", duration: "1 hr", isPurple: false },
    { day: "Wed", topic: "Aptitude: Data interpretation", duration: "1 hr", isPurple: false },
    { day: "Thu", topic: "Future Skills: LLM APIs & RAG", duration: "1 hr", isPurple: false },
    { day: "Fri", topic: "GD + weekly quiz", duration: "1 hr", isPurple: false },
    { day: "Sat", topic: "Track project kick-off + RAG mini-lab", duration: "3 hrs", isPurple: true }
  ];

  return (
    <AppShell pageTitle="Student Dashboard">
      <div className="space-y-6 max-w-7xl mx-auto">
        {/* Welcome Greeting */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-[#0F1F3A]">{student.greeting}</h2>
            <p className="text-xs text-[#64748B] mt-0.5">Sem 5 · AI & Data Science · Week 8 of 12</p>
          </div>
          <Link
            href="/student/coding/prob_connected_components"
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#2B5CD0] hover:bg-[#1E46B0] text-white text-xs font-bold rounded-lg shadow-sm transition-all"
          >
            <span>Resume Daily Practice</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {/* ROW 1: 4 Metric Cards (PDF 2) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Card 1: Readiness Score */}
          <div className="bg-white p-4 rounded-xl border border-[#E2E8F0] shadow-sm space-y-2">
            <div className="flex items-center justify-between text-xs text-[#64748B] font-medium">
              <span>{t("student.readiness_score")}</span>
              <span className="chip-amber">{student.readiness_band}</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-black text-[#0F1F3A]">{student.readiness_score}/100</span>
              <span className="text-xs font-bold text-[#15803D]">+{student.readiness_delta} this month</span>
            </div>
            <div className="text-[11px] text-[#64748B] flex items-center gap-1">
              <TrendingUp className="w-3 h-3 text-[#2BB3A0]" />
              <span>Target: 80+ for Product Placement</span>
            </div>
          </div>

          {/* Card 2: Problems Solved */}
          <div className="bg-white p-4 rounded-xl border border-[#E2E8F0] shadow-sm space-y-2">
            <div className="text-xs text-[#64748B] font-medium">
              <span>{t("student.problems_solved")}</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-black text-[#0F1F3A]">{student.problems_solved}</span>
              <span className="text-xs font-bold text-[#15803D]">▲ {student.problems_delta} this month</span>
            </div>
            <div className="text-[11px] text-[#64748B] flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3 text-[#2B5CD0]" />
              <span>18 Graph patterns solved</span>
            </div>
          </div>

          {/* Card 3: Attendance */}
          <div className="bg-white p-4 rounded-xl border border-[#E2E8F0] shadow-sm space-y-2">
            <div className="flex items-center justify-between text-xs text-[#64748B] font-medium">
              <span>{t("student.attendance")}</span>
              <span className="chip-green">On track</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-black text-[#0F1F3A]">{student.attendance_pct}%</span>
              <span className="text-xs text-[#64748B]">Target {student.attendance_target}%</span>
            </div>
            <div className="text-[11px] text-[#64748B] flex items-center gap-1">
              <Calendar className="w-3 h-3 text-[#2BB3A0]" />
              <span>53 of 58 sessions attended</span>
            </div>
          </div>

          {/* Card 4: Practice Streak */}
          <div className="bg-white p-4 rounded-xl border border-[#E2E8F0] shadow-sm space-y-2">
            <div className="text-xs text-[#64748B] font-medium">
              <span>{t("student.practice_streak")}</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-black text-[#0F1F3A]">🔥 {student.streak_days} days</span>
            </div>
            <div className="text-[11px] text-[#64748B] flex items-center gap-1">
              <Flame className="w-3 h-3 text-[#F59E0B]" />
              <span>Personal Best: {student.streak_best} days</span>
            </div>
          </div>
        </div>

        {/* ROW 2: Skill Progress + This Week Plan */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Skill Progress */}
          <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
              <h3 className="font-bold text-sm text-[#0F1F3A]">{t("student.skill_progress")}</h3>
              <span className="text-[11px] font-semibold text-[#64748B]">Semester 5</span>
            </div>
            <div className="space-y-3.5">
              {skillProgress.map((item: any) => (
                <div key={item.skill} className="space-y-1">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-[#0F1F3A]">{item.skill}</span>
                    <span className="text-[#64748B]">{item.percentage}%</span>
                  </div>
                  <div className="w-full bg-[#F1F5F9] rounded-full h-2 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${item.percentage}%`, backgroundColor: item.color }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* This Week Plan (Mon to Sat) */}
          <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
              <h3 className="font-bold text-sm text-[#0F1F3A]">{t("student.this_week")}</h3>
              <span className="text-[11px] font-semibold text-[#64748B]">Week 8 of 12</span>
            </div>
            <div className="space-y-2.5">
              {thisWeek.map((row: any) => (
                <div
                  key={row.day}
                  className="flex items-center justify-between p-2.5 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] hover:bg-[#F1F5F9] transition-all"
                >
                  <div className="flex items-center gap-3">
                    <span className="w-10 text-center font-bold text-xs text-[#0F1F3A] bg-white py-1 rounded border border-[#E2E8F0]">
                      {row.day}
                    </span>
                    <span className="text-xs font-medium text-[#0F1F3A]">{row.topic}</span>
                  </div>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${row.isPurple ? "bg-[#EDE9FE] text-[#6D28D9]" : "bg-[#EFF6FF] text-[#1D4ED8]"}`}>
                    {row.duration}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ROW 3: 3 Cards (Current Project, Upcoming, Badges) */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1: Current Project */}
          <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-3 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-xs text-[#64748B] font-medium mb-1">
                <span>{t("student.current_project")}</span>
                <span className="chip-purple">Sprint 2</span>
              </div>
              <h4 className="font-bold text-sm text-[#0F1F3A]">Crop Price Predictor</h4>
              <p className="text-xs text-[#64748B] mt-0.5">End-to-end ML · Team of 3 · Due Week 12</p>

              <div className="mt-4 space-y-1.5">
                <div className="flex justify-between text-xs font-semibold">
                  <span className="text-[#0F1F3A]">Sprint Progress</span>
                  <span className="text-[#2BB3A0]">45% complete</span>
                </div>
                <div className="w-full bg-[#F1F5F9] rounded-full h-2">
                  <div className="h-full bg-[#2BB3A0] rounded-full" style={{ width: "45%" }} />
                </div>
                <div className="text-[11px] text-[#64748B] pt-1">3 tasks open · 1 pull request pending review</div>
              </div>
            </div>

            <Link
              href="/student/projects/board"
              className="text-xs font-bold text-[#2B5CD0] hover:underline flex items-center gap-1 pt-2"
            >
              <span>Open Sprint Board</span>
              <ExternalLink className="w-3 h-3" />
            </Link>
          </div>

          {/* Card 2: Upcoming Events & Tests */}
          <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-3">
            <div className="flex items-center justify-between text-xs text-[#64748B] font-medium border-b border-[#E2E8F0] pb-2">
              <span>{t("student.upcoming")}</span>
              <Clock className="w-3.5 h-3.5 text-[#64748B]" />
            </div>
            <div className="space-y-2.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-[#0F1F3A]">Mid-term DSA test</span>
                <span className="chip-amber">Sat</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-[#0F1F3A]">Mock interview</span>
                <span className="chip-blue">Wed 4:00 PM</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-[#0F1F3A]">AWS Cloud Practitioner</span>
                <span className="chip-purple">Nov 22</span>
              </div>
            </div>
          </div>

          {/* Card 3: Badges Earned */}
          <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-3">
            <div className="flex items-center justify-between text-xs text-[#64748B] font-medium border-b border-[#E2E8F0] pb-2">
              <span>{t("student.badges_earned")}</span>
              <Award className="w-3.5 h-3.5 text-[#2BB3A0]" />
            </div>
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-[#2BB3A0] to-[#2B5CD0] flex items-center justify-center text-white text-xl shadow-md">
                🚀
              </div>
              <div>
                <div className="text-xs font-bold text-[#0F1F3A]">Cloud Deployer</div>
                <div className="text-[11px] text-[#64748B]">Deployed first app on cloud</div>
              </div>
            </div>
            <div className="flex gap-2 pt-1">
              <span className="w-7 h-7 rounded-lg bg-[#EFF6FF] border border-[#BFDBFE] flex items-center justify-center text-xs" title="DSA Master">🧩</span>
              <span className="w-7 h-7 rounded-lg bg-[#FEF3C7] border border-[#FDE68A] flex items-center justify-center text-xs" title="15 Day Streak">🔥</span>
              <span className="w-7 h-7 rounded-lg bg-[#EDE9FE] border border-[#DDD6FE] flex items-center justify-center text-xs" title="Team Lead">👥</span>
              <span className="w-7 h-7 rounded-lg bg-[#DCFCE7] border border-[#BBF7D0] flex items-center justify-center text-xs" title="100% Attendance">⭐</span>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
