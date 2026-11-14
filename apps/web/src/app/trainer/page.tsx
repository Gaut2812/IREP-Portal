"use client";

import React, { useState, useEffect } from "react";
import { AppShell } from "@/components/AppShell";
import {
  Users, ClipboardCheck, Code2, AlertTriangle,
  Calendar, CheckCircle2, Clock, ArrowRight, FileText,
  BookOpen, ExternalLink, Filter, PlusCircle
} from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import Link from "next/link";
import { fetchApi } from "@/lib/api";

interface CodingProblemSummary {
  id: string;
  slug: string;
  title: string;
  difficulty: string;
  topic: string;
  week_info: string;
  total_submissions: number;
  accepted_submissions: number;
  solved_percentage: number;
}

export default function TrainerDashboardPage() {
  const [codingProblems, setCodingProblems] = useState<CodingProblemSummary[]>([]);
  const [loadingProblems, setLoadingProblems] = useState<boolean>(true);
  const [selectedWeek, setSelectedWeek] = useState<string>("All");

  const readinessData = [
    { batch: "CSE-A", score: 82 },
    { batch: "CSE-B", score: 76 },
    { batch: "IT-A", score: 71 },
    { batch: "AI & DS", score: 79 },
    { batch: "Cyber", score: 68 }
  ];

  const todaySchedule = [
    { time: "9:00 AM", batch: "CSE-A · Sem 5", topic: "System design basics", status: "Done", statusColor: "chip-green" },
    { time: "11:00 AM", batch: "AI & DS · Sem 5", topic: "Future Skills: LLM APIs & RAG", status: "Next", statusColor: "chip-blue" },
    { time: "2:00 PM", batch: "IT-A · Sem 4", topic: "SQL window functions", status: "Later", statusColor: "bg-slate-100 text-slate-600" },
    { time: "3:30 PM", batch: "Cyber · Sem 5", topic: "OWASP lab: XSS", status: "Later", statusColor: "bg-slate-100 text-slate-600" }
  ];

  const studentsNeedingSupport = [
    { name: "Karthik S.", batch: "CSE-B", score: 52, issue: "Attendance 71%", action: "Parent call", actionClass: "chip-red" },
    { name: "Divya M.", batch: "IT-A", score: 56, issue: "DSA tests", action: "Extra Sat", actionClass: "chip-amber" },
    { name: "Rahul V.", batch: "Cyber", score: 58, issue: "Project delay", action: "Mentor", actionClass: "chip-blue" }
  ];

  useEffect(() => {
    async function loadProblems() {
      try {
        const res = await fetchApi<CodingProblemSummary[]>("/trainer/coding-problems");
        if (Array.isArray(res) && res.length > 0) {
          setCodingProblems(res);
        } else {
          setCodingProblems(getFallbackProblems());
        }
      } catch (err) {
        setCodingProblems(getFallbackProblems());
      } finally {
        setLoadingProblems(false);
      }
    }
    loadProblems();
  }, []);

  const filteredProblems = selectedWeek === "All"
    ? codingProblems
    : codingProblems.filter(p => p.week_info?.includes(`Week ${selectedWeek}`));

  return (
    <AppShell pageTitle="Trainer Dashboard">
      <div className="space-y-6 max-w-7xl mx-auto pb-10">
        
        {/* ROW 1: 4 Metric Cards (PDF 8) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Card 1: Active Batches */}
          <div className="bg-white p-4 rounded-xl border border-[#E2E8F0] shadow-sm space-y-2">
            <div className="text-xs text-[#64748B] font-medium">Active Batches</div>
            <div className="text-3xl font-black text-[#0F1F3A]">5</div>
            <div className="text-[11px] text-[#64748B]">248 students · 2 colleges</div>
          </div>

          {/* Card 2: Today's Attendance */}
          <div className="bg-white p-4 rounded-xl border border-[#E2E8F0] shadow-sm space-y-2">
            <div className="text-xs text-[#64748B] font-medium">Today's Attendance</div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-black text-[#0F1F3A]">91%</span>
              <span className="text-xs font-bold text-[#15803D]">▲ 3% vs last week</span>
            </div>
            <div className="text-[11px] text-[#64748B]">4 of 5 sessions completed</div>
          </div>

          {/* Card 3: Pending Code Reviews */}
          <div className="bg-white p-4 rounded-xl border border-[#E2E8F0] shadow-sm space-y-2">
            <div className="text-xs text-[#64748B] font-medium">Pending Code Reviews</div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-black text-[#0F1F3A]">17</span>
              <span className="text-xs font-bold text-[#D93636]">6 older than 2 days</span>
            </div>
            <div className="text-[11px] text-[#64748B]">Pull requests from Team Phoenix</div>
          </div>

          {/* Card 4: At-Risk Students */}
          <div className="bg-white p-4 rounded-xl border border-[#E2E8F0] shadow-sm space-y-2">
            <div className="text-xs text-[#64748B] font-medium">At-Risk Students</div>
            <div className="text-3xl font-black text-[#D93636]">12</div>
            <div className="text-[11px] text-[#64748B]">Parents notified: 9</div>
          </div>
        </div>

        {/* ROW 2: Batch Readiness Bar Chart + Today's Schedule (PDF 8) */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Chart */}
          <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
              <h3 className="font-bold text-xs text-[#0F1F3A]">Batch readiness score</h3>
              <span className="text-[11px] text-[#64748B]">Average · this semester</span>
            </div>
            <div className="h-56 w-full pt-2">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={readinessData}>
                  <XAxis dataKey="batch" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="score" radius={[6, 6, 0, 0]}>
                    {readinessData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.score >= 75 ? "#2BB3A0" : "#2B5CD0"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="flex items-center justify-center gap-4 text-[11px] text-[#64748B] pt-1">
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#2BB3A0]" /> 75+ Placement Ready</span>
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#2B5CD0]" /> Below 75</span>
            </div>
          </div>

          {/* Today's Schedule */}
          <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
              <h3 className="font-bold text-xs text-[#0F1F3A]">Today's schedule</h3>
              <span className="text-[11px] text-[#64748B] font-semibold">Thu, Oct 9</span>
            </div>
            <div className="space-y-2.5">
              {todaySchedule.map((item) => (
                <div
                  key={item.time}
                  className="flex items-center justify-between p-3 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]"
                >
                  <div className="flex items-center gap-3">
                    <span className="w-16 text-xs font-bold text-[#0F1F3A]">{item.time}</span>
                    <div>
                      <div className="text-xs font-bold text-[#0F1F3A]">{item.topic}</div>
                      <div className="text-[10px] text-[#64748B]">{item.batch}</div>
                    </div>
                  </div>
                  {item.status === "Next" ? (
                    <Link
                      href="/live/sess_thu_rag"
                      className="px-3 py-1 bg-[#2B5CD0] hover:bg-[#1E46B0] text-white text-xs font-bold rounded-lg shadow-sm"
                    >
                      Enter Room
                    </Link>
                  ) : (
                    <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full ${item.statusColor}`}>
                      {item.status}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ROW 3: Weekly DSA Curriculum & Coding Lab Widget (Screen 24 Integration) */}
        <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-4" data-testid="trainer-dsa-widget">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-[#E2E8F0] pb-3">
            <div>
              <div className="flex items-center gap-2">
                <Code2 className="w-5 h-5 text-[#2B5CD0]" />
                <h3 className="font-bold text-sm text-[#0F1F3A]">Weekly DSA Curriculum · Coding Lab</h3>
                <span className="chip-purple text-[10px]">Trainer: Arun Kumar</span>
              </div>
              <p className="text-xs text-[#64748B] mt-0.5">
                20 Structured Problems across Weeks 1-8 · Solved on weekly basis by placement students
              </p>
            </div>

            {/* Filter by Week */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-[#64748B] font-medium flex items-center gap-1">
                <Filter className="w-3.5 h-3.5" /> Week:
              </span>
              <select
                value={selectedWeek}
                onChange={(e) => setSelectedWeek(e.target.value)}
                className="bg-[#F8FAFC] border border-[#CBD5E1] text-xs font-semibold text-[#0F1F3A] rounded-lg px-2.5 py-1 focus:outline-none cursor-pointer"
              >
                <option value="All">All Weeks (1-8)</option>
                <option value="1">Week 1 (Arrays & Pointers)</option>
                <option value="2">Week 2 (Sliding Window)</option>
                <option value="3">Week 3 (Stacks & Queues)</option>
                <option value="4">Week 4 (Linked Lists)</option>
                <option value="5">Week 5 (Binary Search)</option>
                <option value="6">Week 6 (Trees & BST)</option>
                <option value="7">Week 7 (Dynamic Programming)</option>
                <option value="8">Week 8 (Graphs & DSU)</option>
              </select>
            </div>
          </div>

          {/* Table of DSA Problems */}
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-[#E2E8F0] text-[#64748B] text-[11px]">
                  <th className="pb-2.5 font-semibold">Problem Title</th>
                  <th className="pb-2.5 font-semibold">Curriculum Schedule</th>
                  <th className="pb-2.5 font-semibold">Topic</th>
                  <th className="pb-2.5 font-semibold">Difficulty</th>
                  <th className="pb-2.5 font-semibold text-center">Submissions</th>
                  <th className="pb-2.5 font-semibold text-center">Solved %</th>
                  <th className="pb-2.5 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E8F0]">
                {loadingProblems ? (
                  <tr>
                    <td colSpan={7} className="py-6 text-center text-xs text-[#64748B]">
                      Loading weekly curriculum problems...
                    </td>
                  </tr>
                ) : filteredProblems.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-6 text-center text-xs text-[#64748B]">
                      No problems found for Week {selectedWeek}.
                    </td>
                  </tr>
                ) : (
                  filteredProblems.map((prob) => (
                    <tr key={prob.id} className="hover:bg-[#F8FAFC] transition-colors">
                      <td className="py-2.5 font-bold text-[#0F1F3A]">
                        {prob.title}
                      </td>
                      <td className="py-2.5 text-[#64748B] font-medium">
                        {prob.week_info}
                      </td>
                      <td className="py-2.5">
                        <span className="chip-blue text-[10px]">{prob.topic}</span>
                      </td>
                      <td className="py-2.5">
                        <span className={
                          prob.difficulty === "Easy"
                            ? "chip-green text-[10px]"
                            : prob.difficulty === "Medium"
                              ? "chip-amber text-[10px]"
                              : "chip-red text-[10px]"
                        }>
                          {prob.difficulty}
                        </span>
                      </td>
                      <td className="py-2.5 text-center font-mono text-[#0F1F3A]">
                        {prob.total_submissions}
                      </td>
                      <td className="py-2.5 text-center">
                        <span className="font-bold text-[#15803D] text-[11px]">
                          {prob.solved_percentage}%
                        </span>
                      </td>
                      <td className="py-2.5 text-right">
                        <Link
                          href={`/student/coding/${prob.id}`}
                          className="inline-flex items-center gap-1 px-2.5 py-1 bg-[#2B5CD0] hover:bg-[#1E46B0] text-white font-bold text-[11px] rounded-lg shadow-sm transition-all"
                        >
                          <span>Solve</span>
                          <ExternalLink className="w-2.5 h-2.5" />
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* ROW 4: Students Needing Support + Quick Actions (PDF 8) */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Table (2 cols) */}
          <div className="lg:col-span-2 bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
              <h3 className="font-bold text-xs text-[#0F1F3A]">Students needing support</h3>
              <span className="text-[11px] text-[#D93636] font-semibold">Score below 60</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="border-b border-[#E2E8F0] text-[#64748B] text-[11px]">
                    <th className="pb-2 font-semibold">Student</th>
                    <th className="pb-2 font-semibold">Batch</th>
                    <th className="pb-2 font-semibold">Score</th>
                    <th className="pb-2 font-semibold">Issue</th>
                    <th className="pb-2 font-semibold text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0]">
                  {studentsNeedingSupport.map((st) => (
                    <tr key={st.name} className="hover:bg-[#F8FAFC]">
                      <td className="py-2.5 font-bold text-[#0F1F3A]">{st.name}</td>
                      <td className="py-2.5 text-[#64748B]">{st.batch}</td>
                      <td className="py-2.5">
                        <span className="px-2 py-0.5 rounded-md bg-red-100 text-red-700 font-bold text-[11px]">
                          {st.score}
                        </span>
                      </td>
                      <td className="py-2.5 text-[#64748B]">{st.issue}</td>
                      <td className="py-2.5 text-right">
                        <span className={`${st.actionClass} cursor-pointer`}>{st.action}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Quick Actions (1 col) */}
          <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-3 flex flex-col justify-between">
            <div>
              <h3 className="font-bold text-xs text-[#0F1F3A] border-b border-[#E2E8F0] pb-2">Quick actions</h3>
              <div className="grid grid-cols-2 gap-2.5 pt-3">
                <button className="py-2.5 px-3 bg-[#2B5CD0] hover:bg-[#1E46B0] text-white font-bold text-xs rounded-xl shadow cursor-pointer">
                  Mark attendance
                </button>
                <button className="py-2.5 px-3 border border-[#CBD5E1] hover:bg-[#F8FAFC] text-[#0F1F3A] font-bold text-xs rounded-xl cursor-pointer">
                  Create test
                </button>
                <button className="py-2.5 px-3 border border-[#CBD5E1] hover:bg-[#F8FAFC] text-[#0F1F3A] font-bold text-xs rounded-xl cursor-pointer">
                  Review PRs
                </button>
                <button className="py-2.5 px-3 border border-[#CBD5E1] hover:bg-[#F8FAFC] text-[#0F1F3A] font-bold text-xs rounded-xl cursor-pointer">
                  Send parent update
                </button>
                <button className="py-2.5 px-3 border border-[#CBD5E1] hover:bg-[#F8FAFC] text-[#0F1F3A] font-bold text-xs rounded-xl cursor-pointer">
                  Schedule mock
                </button>
                <button className="py-2.5 px-3 bg-[#2BB3A0] hover:bg-[#249B8A] text-white font-bold text-xs rounded-xl shadow cursor-pointer">
                  Monthly report
                </button>
              </div>
            </div>
            <div className="text-[11px] text-[#64748B] pt-2 text-center">
              Next batch review scheduled for Monday
            </div>
          </div>
        </div>

      </div>
    </AppShell>
  );
}

function getFallbackProblems(): CodingProblemSummary[] {
  return [
    { id: "prob_connected_components", slug: "connected-components", title: "Number of Connected Components in an Undirected Graph", difficulty: "Medium", topic: "Union-Find", week_info: "Week 8 · Pattern drill · 3 of 6 solved", total_submissions: 18, accepted_submissions: 16, solved_percentage: 88 },
    { id: "prob_two_sum", slug: "two-sum", title: "Two Sum", difficulty: "Easy", topic: "Arrays & Hash Map", week_info: "Week 1 · Foundation · 1 of 3", total_submissions: 42, accepted_submissions: 38, solved_percentage: 90 },
    { id: "prob_container_water", slug: "container-with-most-water", title: "Container With Most Water", difficulty: "Medium", topic: "Two Pointers", week_info: "Week 1 · Pattern drill · 2 of 3", total_submissions: 35, accepted_submissions: 28, solved_percentage: 80 },
    { id: "prob_3sum", slug: "3sum", title: "3Sum", difficulty: "Medium", topic: "Two Pointers", week_info: "Week 1 · Advanced drill · 3 of 3", total_submissions: 29, accepted_submissions: 21, solved_percentage: 72 },
    { id: "prob_longest_substring", slug: "longest-substring", title: "Longest Substring Without Repeating Characters", difficulty: "Medium", topic: "Sliding Window", week_info: "Week 2 · Pattern drill · 1 of 2", total_submissions: 31, accepted_submissions: 25, solved_percentage: 81 },
    { id: "prob_valid_parentheses", slug: "valid-parentheses", title: "Valid Parentheses", difficulty: "Easy", topic: "Stack", week_info: "Week 3 · Foundation · 1 of 3", total_submissions: 45, accepted_submissions: 42, solved_percentage: 93 },
    { id: "prob_climbing_stairs", slug: "climbing-stairs", title: "Climbing Stairs", difficulty: "Easy", topic: "Dynamic Programming", week_info: "Week 7 · Foundation · 1 of 3", total_submissions: 38, accepted_submissions: 35, solved_percentage: 92 },
    { id: "prob_course_schedule", slug: "course-schedule", title: "Course Schedule", difficulty: "Medium", topic: "Graph Topological Sort", week_info: "Week 8 · Advanced drill · 2 of 2", total_submissions: 22, accepted_submissions: 17, solved_percentage: 77 }
  ];
}
