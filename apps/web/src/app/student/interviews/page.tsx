"use client";

import React, { useState } from "react";
import { AppShell } from "@/components/AppShell";
import {
  Video, Play, Calendar, CheckCircle2, TrendingUp,
  Clock, Sparkles, MessageSquareQuote, Check
} from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";

export default function MockInterviewsPage() {
  const [bookedSlots, setBookedSlots] = useState<string[]>([]);

  const rubrics = [
    { label: "Problem solving", score: 4 },
    { label: "Coding & correctness", score: 4 },
    { label: "Thinking aloud", score: 3 },
    { label: "Core CS knowledge", score: 4 },
    { label: "Project explanation", score: 4 },
    { label: "Communication & confidence", score: 3 }
  ];

  const trendData = [
    { round: "Round #1", score: 3.0 },
    { round: "Round #2", score: 3.8 }
  ];

  const availableSlots = [
    { id: "s1", time: "Wed, Oct 15 · 4:00 PM", type: "Technical", color: "chip-blue" },
    { id: "s2", time: "Sat, Oct 18 · 10:30 AM", type: "HR round", color: "chip-green" },
    { id: "s3", time: "Sat, Oct 18 · 12:00 PM", type: "AI-allowed coding", color: "chip-purple" }
  ];

  const handleBook = (id: string) => {
    setBookedSlots([...bookedSlots, id]);
  };

  return (
    <AppShell pageTitle="Mock Interviews & Feedback">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 max-w-7xl mx-auto">
        
        {/* LEFT COLUMN: Latest Interview Card & Rubric (7 cols) */}
        <div className="lg:col-span-7 bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6 space-y-5">
          {/* Header */}
          <div className="border-b border-[#E2E8F0] pb-4 space-y-2">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-[#0F1F3A]">Mock Interview #2 – Technical</h2>
              <span className="text-xs text-[#64748B] font-medium">Oct 8 · 40 min</span>
            </div>
            <div className="text-xs text-[#64748B]">
              Interviewer: <strong className="text-[#0F1F3A]">Arun K. (Senior Technical Trainer)</strong>
            </div>

            {/* Overall score & chips */}
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <div className="text-3xl font-black text-[#0F1F3A]">3.8 / 5</div>
              <span className="chip-green font-bold">Hire-ready for service roles</span>
              <span className="chip-amber font-bold">Improve for product roles</span>
            </div>
          </div>

          {/* 6 Rubric Rows with 5-segment bars (PDF 7) */}
          <div className="space-y-3.5">
            <h3 className="text-xs font-bold text-[#0F1F3A] uppercase tracking-wider text-[#64748B]">Evaluation Rubric</h3>
            {rubrics.map((r) => (
              <div key={r.label} className="space-y-1">
                <div className="flex justify-between text-xs font-medium">
                  <span className="text-[#0F1F3A]">{r.label}</span>
                  <span className="font-bold text-[#2BB3A0]">{r.score} / 5</span>
                </div>
                {/* 5-segment bar */}
                <div className="grid grid-cols-5 gap-1.5 h-2">
                  {[1, 2, 3, 4, 5].map((seg) => (
                    <div
                      key={seg}
                      className={`rounded-full transition-all ${
                        seg <= r.score ? "bg-[#2BB3A0]" : "bg-[#F1F5F9]"
                      }`}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Written Trainer Feedback */}
          <div className="pt-3 border-t border-[#E2E8F0] space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-bold text-[#0F1F3A]">
              <MessageSquareQuote className="w-4 h-4 text-[#2B5CD0]" />
              <span>Trainer feedback</span>
            </div>
            <p className="text-xs text-[#334155] leading-relaxed bg-[#F8FAFC] p-3.5 rounded-xl border border-[#E2E8F0]">
              "Priya displayed very clear problem-solving intuition for Union-Find and graph edge conditions. She wrote the code cleanly with path compression. However, when asked to explain worst-case time complexity, she hesitated and spent time computing instead of vocalizing her thought process. Recommend practicing thinking aloud and expressing Big-O notation with confidence."
            </p>
          </div>
        </div>

        {/* RIGHT COLUMN: Progress Chart + Book Slot + Recording (5 cols) */}
        <div className="lg:col-span-5 space-y-5">
          
          {/* Progress Across Interviews Line Chart (PDF 7) */}
          <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm space-y-2">
            <div className="flex items-center justify-between text-xs font-bold text-[#0F1F3A] border-b border-[#E2E8F0] pb-2">
              <span>Progress across interviews</span>
              <span className="text-[11px] text-[#2BB3A0] font-semibold">Target: 4.2</span>
            </div>

            <div className="h-40 w-full pt-2">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendData}>
                  <XAxis dataKey="round" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 5]} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <ReferenceLine y={4.2} stroke="#F59E0B" strokeDasharray="3 3" label={{ value: "Target 4.2", fill: "#B45309", fontSize: 10 }} />
                  <Line type="monotone" dataKey="score" stroke="#2BB3A0" strokeWidth={3} dot={{ r: 5, fill: "#2BB3A0" }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="text-[11px] text-[#64748B] text-center pt-1">
              Round #1: 3.0 → Round #2: 3.8 (+0.8 improvement)
            </div>
          </div>

          {/* Book Next Slot List */}
          <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm space-y-3">
            <div className="flex items-center justify-between text-xs font-bold text-[#0F1F3A] border-b border-[#E2E8F0] pb-2">
              <span>Book next slot</span>
              <Calendar className="w-3.5 h-3.5 text-[#64748B]" />
            </div>

            <div className="space-y-2">
              {availableSlots.map((slot) => {
                const isBooked = bookedSlots.includes(slot.id);
                return (
                  <div
                    key={slot.id}
                    className="flex items-center justify-between p-2.5 rounded-lg border border-[#E2E8F0] bg-[#F8FAFC]"
                  >
                    <div>
                      <div className="text-xs font-bold text-[#0F1F3A]">{slot.time}</div>
                      <span className={`${slot.color} text-[10px] mt-0.5 inline-block`}>{slot.type}</span>
                    </div>

                    <button
                      onClick={() => handleBook(slot.id)}
                      disabled={isBooked}
                      className={`px-3 py-1 rounded-lg text-xs font-bold transition-all ${
                        isBooked
                          ? "bg-[#DCFCE7] text-[#15803D] border border-[#BBF7D0]"
                          : "bg-[#2BB3A0] hover:bg-[#249B8A] text-white shadow-xs cursor-pointer"
                      }`}
                    >
                      {isBooked ? "Booked ✓" : "Book"}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Recording Player Card (PDF 7) */}
          <div className="bg-[#1B2236] rounded-xl border border-[#2D3748] p-4 text-white shadow-sm space-y-3">
            <div className="text-xs font-bold text-[#CBD5E1] flex items-center justify-between">
              <span>Interview Recording</span>
              <span className="text-[10px] text-[#94A3B8]">40:15</span>
            </div>
            <div className="h-28 bg-[#141A29] rounded-lg flex items-center justify-center border border-[#2D3748] cursor-pointer group">
              <div className="w-12 h-12 rounded-full bg-[#2BB3A0] group-hover:scale-110 flex items-center justify-center shadow-lg transition-transform">
                <Play className="w-5 h-5 text-white ml-0.5" />
              </div>
            </div>
            <p className="text-[11px] text-[#94A3B8] text-center leading-tight">
              Watch your interview with timestamped trainer comments
            </p>
          </div>

        </div>

      </div>
    </AppShell>
  );
}
