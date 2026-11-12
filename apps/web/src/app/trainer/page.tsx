"use client";

import React from "react";
import { AppShell } from "@/components/AppShell";
import {
  Users, ClipboardCheck, Code2, AlertTriangle,
  Calendar, CheckCircle2, Clock, ArrowRight, FileText
} from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import Link from "next/link";

export default function TrainerDashboardPage() {
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

  return (
    <AppShell pageTitle="Trainer Dashboard">
      <div className="space-y-6 max-w-7xl mx-auto">
        
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

        {/* ROW 3: Students Needing Support + Quick Actions (PDF 8) */}
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

