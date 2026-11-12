"use client";

import React from "react";
import { AppShell } from "@/components/AppShell";
import {
  Users, CheckCircle2, Award, Briefcase,
  TrendingUp, Download, Calendar, FileText
} from "lucide-react";
import {
  PieChart, Pie, Cell, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Tooltip
} from "recharts";

export default function CollegeDashboardPage() {
  const readinessDonut = [
    { name: "Placement Ready", value: 48, color: "#2BB3A0" },
    { name: "Nearly Ready", value: 36, color: "#F59E0B" },
    { name: "Needs Support", value: 16, color: "#D93636" }
  ];

  const branchData = [
    { branch: "CSE", students: 228, attendance: "91%", avgScore: 78, trend: "▲ 5" },
    { branch: "IT", students: 164, attendance: "88%", avgScore: 73, trend: "▲ 3" },
    { branch: "AI & DS", students: 142, attendance: "90%", avgScore: 77, trend: "▲ 6" },
    { branch: "Cybersecurity", students: 78, attendance: "86%", avgScore: 70, trend: "▲ 2" }
  ];

  const certData = [
    { month: "Jun", certs: 28 },
    { month: "Jul", certs: 54 },
    { month: "Aug", certs: 92 },
    { month: "Sep", certs: 143 },
    { month: "Oct", certs: 184 }
  ];

  const upcomingEvents = [
    { title: "Mock Drive 1 · Sem 7", date: "Oct 25" },
    { title: "Project Demo Day", date: "Nov 8" },
    { title: "Parent review meeting", date: "Nov 15" },
    { title: "Guest session: GCC leaders", date: "Nov 22" }
  ];

  const mouReports = [
    "September progress report",
    "Sem 4 performance report",
    "Placement readiness analysis"
  ];

  return (
    <AppShell pageTitle="Demo Engineering College · Program Overview">
      <div className="space-y-6 max-w-7xl mx-auto">
        
        {/* ROW 1: 4 Metric Cards (PDF 9) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white p-4 rounded-xl border border-[#E2E8F0] shadow-sm space-y-2">
            <div className="text-xs text-[#64748B] font-medium">Students Enrolled</div>
            <div className="text-3xl font-black text-[#0F1F3A]">612</div>
            <div className="text-[11px] text-[#64748B]">Sem 2 to 7 · 4 branches</div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-[#E2E8F0] shadow-sm space-y-2">
            <div className="text-xs text-[#64748B] font-medium">Average Attendance</div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-black text-[#0F1F3A]">89%</span>
              <span className="text-xs font-bold text-[#15803D]">Above 85% target</span>
            </div>
            <div className="text-[11px] text-[#64748B]">Across all weekday & Saturday labs</div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-[#E2E8F0] shadow-sm space-y-2">
            <div className="text-xs text-[#64748B] font-medium">Certifications Earned</div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-black text-[#0F1F3A]">184</span>
              <span className="text-xs font-bold text-[#15803D]">▲ 41 this semester</span>
            </div>
            <div className="text-[11px] text-[#64748B]">AWS, Cloud & AI verified badges</div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-[#E2E8F0] shadow-sm space-y-2">
            <div className="text-xs text-[#64748B] font-medium">Internships Secured</div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-black text-[#0F1F3A]">73</span>
              <span className="text-xs font-bold text-[#15803D]">Sem 6 batch · 64%</span>
            </div>
            <div className="text-[11px] text-[#64748B]">Target 80% before Sem 7</div>
          </div>
        </div>

        {/* ROW 2: Placement Readiness Donut + Branch Table (PDF 9) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Donut Chart (5 cols) */}
          <div className="lg:col-span-5 bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
              <h3 className="font-bold text-xs text-[#0F1F3A]">Placement readiness</h3>
              <span className="text-[11px] text-[#64748B]">All semesters</span>
            </div>

            <div className="relative h-48 w-full flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={readinessDonut}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={80}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {readinessDonut.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute text-center pointer-events-none">
                <div className="text-xl font-black text-[#0F1F3A]">612</div>
                <div className="text-[10px] text-[#64748B]">Students</div>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-center gap-3 text-xs pt-1">
              <span className="chip-green font-bold">Placement Ready 48%</span>
              <span className="chip-amber font-bold">Nearly Ready 36%</span>
              <span className="chip-red font-bold">Needs Support 16%</span>
            </div>
          </div>

          {/* Branch Readiness Table (7 cols) */}
          <div className="lg:col-span-7 bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
              <h3 className="font-bold text-xs text-[#0F1F3A]">Branch-wise readiness</h3>
              <span className="text-[11px] text-[#64748B]">4 Departments</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="border-b border-[#E2E8F0] text-[#64748B] text-[11px]">
                    <th className="pb-2 font-semibold">Branch</th>
                    <th className="pb-2 font-semibold">Students</th>
                    <th className="pb-2 font-semibold">Attendance</th>
                    <th className="pb-2 font-semibold">Avg Score</th>
                    <th className="pb-2 font-semibold text-right">Trend</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0]">
                  {branchData.map((b) => (
                    <tr key={b.branch} className="hover:bg-[#F8FAFC]">
                      <td className="py-2.5 font-bold text-[#0F1F3A]">{b.branch}</td>
                      <td className="py-2.5 text-[#64748B]">{b.students}</td>
                      <td className="py-2.5 text-[#64748B]">{b.attendance}</td>
                      <td className="py-2.5 font-bold text-[#0F1F3A]">{b.avgScore}</td>
                      <td className="py-2.5 text-right font-bold text-[#15803D]">{b.trend}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* ROW 3: Cumulative Certs Bar Chart + Events + MoU Reports (PDF 9) */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Cumulative Certifications Chart */}
          <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
              <h3 className="font-bold text-xs text-[#0F1F3A]">Cumulative certifications</h3>
              <span className="text-[11px] text-[#2BB3A0] font-semibold">June – Oct</span>
            </div>
            <div className="h-44 w-full pt-2">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={certData}>
                  <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="certs" fill="#2B5CD0" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Upcoming Events */}
          <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
              <h3 className="font-bold text-xs text-[#0F1F3A]">Upcoming events</h3>
              <Calendar className="w-3.5 h-3.5 text-[#64748B]" />
            </div>
            <div className="space-y-2.5">
              {upcomingEvents.map((evt) => (
                <div key={evt.title} className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-[#0F1F3A]">{evt.title}</span>
                  <span className="chip-purple text-[10px]">{evt.date}</span>
                </div>
              ))}
            </div>
          </div>

          {/* MoU Reports */}
          <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
              <h3 className="font-bold text-xs text-[#0F1F3A]">MoU reports</h3>
              <FileText className="w-3.5 h-3.5 text-[#64748B]" />
            </div>
            <div className="space-y-2">
              {mouReports.map((report) => (
                <div key={report} className="flex items-center justify-between p-2 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] text-xs">
                  <span className="font-medium text-[#0F1F3A] truncate pr-2">{report}</span>
                  <button className="flex items-center gap-1 px-2.5 py-1 bg-[#2BB3A0] hover:bg-[#249B8A] text-white font-bold text-[10px] rounded shadow-xs cursor-pointer flex-shrink-0">
                    <Download className="w-3 h-3" />
                    <span>PDF</span>
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

      </div>
    </AppShell>
  );
}

