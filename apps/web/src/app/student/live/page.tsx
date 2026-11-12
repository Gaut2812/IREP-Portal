"use client";

import React from "react";
import { AppShell } from "@/components/AppShell";
import {
  Radio, Play, CheckCircle2, Clock, Calendar,
  Bell, Video, ArrowRight, ShieldCheck, Sparkles
} from "lucide-react";
import Link from "next/link";

export default function LiveSessionsPage() {
  const weekSessions = [
    { when: "Mon 9:00–10:00 AM", session: "DSA: Union-Find drill", type: "Live", status: "Attended", action: "Recording" },
    { when: "Tue 9:00–10:00 AM", session: "Model evaluation lab", type: "Live", status: "Attended", action: "Recording" },
    { when: "Wed 9:00–10:00 AM", session: "Aptitude: Data interpretation", type: "Live", status: "Missed", action: "Watch now" },
    { when: "Thu 11:00–12:00 PM", session: "Future Skills: LLM APIs & RAG", type: "Live", status: "Upcoming", action: "Join" },
    { when: "Fri 9:00–10:00 AM", session: "GD + weekly quiz", type: "Live", status: "Scheduled", action: "Remind me" },
    { when: "Sat 10:00–1:00 PM", session: "Track project + RAG mini-lab", type: "In-lab / Hybrid", status: "Scheduled", action: "Remind me" }
  ];

  const recordings = [
    { title: "Cloud deploy walkthrough", duration: "58 min", date: "Sep 28" },
    { title: "Docker Compose lab", duration: "2 hr 51 min", date: "Sep 21" },
    { title: "Mock interview tips", duration: "42 min", date: "Sep 15" }
  ];

  return (
    <AppShell pageTitle="Live Sessions & Recordings">
      <div className="space-y-6 max-w-7xl mx-auto">
        
        {/* HERO CARD (Navy Gradient) matching PDF 14 */}
        <div className="bg-gradient-to-r from-[#14284B] via-[#1E3A6E] to-[#2B5CD0] rounded-2xl p-6 text-white shadow-lg flex flex-wrap items-center justify-between gap-6">
          <div className="space-y-2 max-w-xl">
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full bg-red-500 text-white font-extrabold text-[10px] animate-pulse">
                Starting in 4 min
              </span>
              <span className="text-xs text-[#CBD5E1]">Session 4 of 6 this week</span>
            </div>
            <h2 className="text-xl lg:text-2xl font-black text-white tracking-tight">
              Future Skills: LLM APIs & RAG
            </h2>
            <p className="text-xs text-[#CBD5E1]">
              Thu, Oct 9 · 11:00 AM to 12:00 PM · Arun K. · <span className="text-[#2BB3A0] font-semibold">Lab: AI Notebook pre-loaded</span>
            </p>
          </div>

          <div className="flex flex-col items-end gap-2">
            <Link
              href="/live/sess_thu_rag"
              className="px-6 py-3 bg-[#2BB3A0] hover:bg-[#249B8A] text-white font-bold text-xs rounded-xl shadow-md transition-all flex items-center gap-2 cursor-pointer"
            >
              <Radio className="w-4 h-4 animate-ping" />
              <span>Join session</span>
            </Link>
            <div className="flex items-center gap-1.5 text-[11px] text-[#A7F3D0]">
              <CheckCircle2 className="w-3.5 h-3.5 text-[#2BB3A0]" />
              <span>Mic & camera check passed</span>
            </div>
          </div>
        </div>

        {/* 2-COLUMN LAYOUT: This Week's Sessions (Left) + Attendance & Library (Right) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          
          {/* LEFT: This Week's Sessions Table (PDF 14) (7 cols) */}
          <div className="lg:col-span-7 bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
              <div>
                <h3 className="font-bold text-xs text-[#0F1F3A]">This week's sessions</h3>
                <p className="text-[11px] text-[#64748B]">Week 8 · join from the portal, no separate app</p>
              </div>
              <span className="chip-blue">Week 8 of 12</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="border-b border-[#E2E8F0] text-[#64748B] text-[11px]">
                    <th className="pb-2 font-semibold">When</th>
                    <th className="pb-2 font-semibold">Session</th>
                    <th className="pb-2 font-semibold">Type</th>
                    <th className="pb-2 font-semibold">Status</th>
                    <th className="pb-2 font-semibold text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0]">
                  {weekSessions.map((s) => (
                    <tr key={s.session} className="hover:bg-[#F8FAFC]">
                      <td className="py-3 text-[#64748B] whitespace-nowrap">{s.when}</td>
                      <td className="py-3 font-bold text-[#0F1F3A]">{s.session}</td>
                      <td className="py-3">
                        <span className={s.type === "Live" ? "chip-blue text-[10px]" : "chip-purple text-[10px]"}>
                          {s.type}
                        </span>
                      </td>
                      <td className="py-3">
                        {s.status === "Attended" && <span className="chip-green text-[10px]">Attended</span>}
                        {s.status === "Missed" && <span className="chip-red text-[10px]">Missed</span>}
                        {s.status === "Upcoming" && <span className="chip-amber text-[10px]">Upcoming</span>}
                        {s.status === "Scheduled" && <span className="text-[10px] text-[#64748B] font-semibold">Scheduled</span>}
                      </td>
                      <td className="py-3 text-right">
                        {s.action === "Join" ? (
                          <Link
                            href="/live/sess_thu_rag"
                            className="px-3 py-1 bg-[#2BB3A0] hover:bg-[#249B8A] text-white font-bold text-[11px] rounded-lg shadow-xs"
                          >
                            Join
                          </Link>
                        ) : s.action === "Watch now" ? (
                          <button className="px-2.5 py-1 border border-red-300 text-red-600 hover:bg-red-50 font-bold text-[11px] rounded-lg">
                            Watch now
                          </button>
                        ) : s.action === "Recording" ? (
                          <button className="px-2.5 py-1 border border-[#CBD5E1] text-[#2B5CD0] hover:bg-[#EFF6FF] font-bold text-[11px] rounded-lg">
                            Recording
                          </button>
                        ) : (
                          <button className="text-[11px] font-semibold text-[#64748B] hover:text-[#0F1F3A]">
                            Remind me
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* RIGHT: Attendance & Recording Library (5 cols) */}
          <div className="lg:col-span-5 space-y-5">
            
            {/* My Attendance Card (PDF 14) */}
            <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm space-y-3">
              <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
                <h4 className="text-xs font-bold text-[#0F1F3A]">My attendance (Semester 5)</h4>
                <span className="text-sm font-black text-[#15803D]">92%</span>
              </div>
              <div className="text-xs text-[#64748B] font-semibold">53 of 58 sessions attended</div>
              
              <div className="space-y-2 text-xs pt-1">
                <div className="flex justify-between">
                  <span className="text-[#64748B]">Weekday sessions (1 hr):</span>
                  <strong className="text-[#0F1F3A]">93%</strong>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#64748B]">Saturday labs (3 hrs):</span>
                  <strong className="text-[#0F1F3A]">89%</strong>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#64748B]">Recordings watched for missed:</span>
                  <strong className="text-[#2BB3A0]">4 of 5</strong>
                </div>
              </div>
            </div>

            {/* Recording Library */}
            <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm space-y-3">
              <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
                <h4 className="text-xs font-bold text-[#0F1F3A]">Recording library</h4>
                <span className="text-[10px] text-[#2BB3A0] font-semibold">AI Summaries</span>
              </div>

              <div className="space-y-2">
                {recordings.map((rec) => (
                  <div key={rec.title} className="flex items-center justify-between p-2.5 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0]">
                    <div className="flex items-center gap-2.5">
                      <div className="w-7 h-7 rounded-lg bg-[#EFF6FF] text-[#2B5CD0] flex items-center justify-center">
                        <Play className="w-3.5 h-3.5 ml-0.5" />
                      </div>
                      <div>
                        <div className="text-xs font-bold text-[#0F1F3A]">{rec.title}</div>
                        <div className="text-[10px] text-[#64748B]">{rec.duration} · {rec.date}</div>
                      </div>
                    </div>
                    <button className="text-[11px] font-bold text-[#2B5CD0] hover:underline">
                      Watch
                    </button>
                  </div>
                ))}
              </div>

              <p className="text-[10px] text-[#64748B] italic pt-1 leading-tight text-center">
                Chapters, transcripts and AI summaries for quick revision
              </p>
            </div>

            {/* How Attendance Works Card (PDF 14) */}
            <div className="bg-[#EFF6FF] border border-[#BFDBFE] p-3.5 rounded-xl space-y-1.5 text-xs text-[#1E3A8A]">
              <div className="font-bold flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-[#2B5CD0]" />
                <span>How attendance works</span>
              </div>
              <p className="text-[11px] leading-relaxed text-[#1D4ED8]">
                Present status is automatically recorded once you remain in the live session for 75% of scheduled time (45 mins). Saturday lab attendance requires scanning the rotating QR code in person. Attendance directly feeds your monthly parent card.
              </p>
            </div>

          </div>

        </div>

      </div>
    </AppShell>
  );
}
