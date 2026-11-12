"use client";

import React, { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { useLanguage } from "@/lib/LanguageContext";
import {
  Heart, Calendar, Award, CheckCircle2,
  Sparkles, ExternalLink, MessageSquare, ArrowRight, Smartphone
} from "lucide-react";
import Link from "next/link";

export default function ParentViewPage() {
  const { language, toggleLanguage, t } = useLanguage();
  const [rsvpDone, setRsvpDone] = useState(false);
  const [isMobilePreview, setIsMobilePreview] = useState(false);

  const monthlyCards = [
    { area: language === "ta" ? "கோடிங் (தீர்க்கப்பட்டவை)" : "Coding (problems solved)", sep: "252", oct: "286", status: language === "ta" ? "சரியான பாதையில்" : "On track", isGreen: true },
    { area: language === "ta" ? "திறனறி தேர்வு" : "Aptitude test", sep: "64%", oct: "71%", status: language === "ta" ? "முன்னேற்றம்" : "Improving", isGreen: true },
    { area: language === "ta" ? "புராஜெக்ட்" : "Project", sep: language === "ta" ? "திட்டமிடல்" : "Planning", oct: "45% built", status: language === "ta" ? "சரியான பாதையில்" : "On track", isGreen: true },
    { area: language === "ta" ? "தொடர்புத் திறன்" : "Communication", sep: "3/5", oct: "3/5", status: language === "ta" ? "பயிற்சி தேவை" : "Needs practice", isGreen: false }
  ];

  return (
    <AppShell pageTitle="Parent View · Priya R (Sem 5, AI & DS)">
      <div className="space-y-6 max-w-5xl mx-auto">
        
        {/* Toggle between Web View & Mobile Frame View */}
        <div className="flex items-center justify-between bg-white p-3.5 rounded-xl border border-[#E2E8F0] shadow-sm">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-[#0F1F3A]">
              {language === "ta" ? "பிரியா R · AI & DS பருவம் 5" : "Ward: Priya R · Sem 5, AI & DS"}
            </span>
            <span className="chip-green text-[10px]">Active</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsMobilePreview(!isMobilePreview)}
              className="flex items-center gap-1.5 px-3 py-1 bg-[#F1F5F9] hover:bg-[#E2E8F0] text-xs font-semibold text-[#0F1F3A] rounded-lg transition-all"
            >
              <Smartphone className="w-3.5 h-3.5 text-[#2B5CD0]" />
              <span>{isMobilePreview ? "Switch to Desktop View" : "Preview Mobile Frame (360px)"}</span>
            </button>
          </div>
        </div>

        {/* MOBILE FRAME VIEW (360px) when toggled */}
        {isMobilePreview ? (
          <div className="flex justify-center pb-8">
            <div className="w-[360px] bg-white rounded-3xl border-4 border-[#1E3A6E] shadow-2xl overflow-hidden flex flex-col font-sans">
              {/* Blue Header */}
              <div className="bg-[#14284B] text-white p-4 flex items-center justify-between">
                <div>
                  <div className="text-sm font-bold">IREP Parent</div>
                  <div className="text-[10px] text-[#94A3B8]">Priya R · Sem 5 AI & DS</div>
                </div>
                <button
                  onClick={toggleLanguage}
                  className="text-[11px] font-bold px-2 py-0.5 rounded bg-white/20 text-white"
                >
                  {language === "en" ? "தமிழ்" : "EN"}
                </button>
              </div>

              {/* Mobile Content Scroll */}
              <div className="p-4 space-y-4 max-h-[580px] overflow-y-auto">
                {/* Readiness Score Card */}
                <div className="bg-[#EFF6FF] border border-[#BFDBFE] p-3.5 rounded-2xl text-center space-y-1">
                  <div className="text-xs text-[#1D4ED8] font-semibold">{t("student.readiness_score")}</div>
                  <div className="text-3xl font-black text-[#1E3A8A]">74 <span className="text-xs text-[#15803D]">▲ 6</span></div>
                  <span className="chip-amber text-[10px]">{t("student.nearly_ready")}</span>
                </div>

                {/* 2 Small Cards */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="bg-[#F8FAFC] border border-[#E2E8F0] p-2.5 rounded-xl text-center">
                    <div className="text-[10px] text-[#64748B]">Attendance</div>
                    <div className="text-lg font-bold text-[#0F1F3A]">92%</div>
                  </div>
                  <div className="bg-[#F8FAFC] border border-[#E2E8F0] p-2.5 rounded-xl text-center">
                    <div className="text-[10px] text-[#64748B]">Problems Solved</div>
                    <div className="text-lg font-bold text-[#0F1F3A]">286</div>
                  </div>
                </div>

                {/* Trainer Remark Card */}
                <div className="bg-white border border-[#E2E8F0] p-3 rounded-xl space-y-1 shadow-xs">
                  <div className="text-[10px] font-bold text-[#2B5CD0] uppercase tracking-wider">Trainer remark · October</div>
                  <p className="text-[11px] text-[#334155] leading-relaxed italic">
                    {language === "ta"
                      ? "இந்த மாதம் கோடிங் பயிற்சியில் பிரியா சிறப்பான முன்னேற்றம் அடைந்துள்ளார்."
                      : "Priya showed outstanding consistency in coding lab problems this month."}
                  </p>
                  <div className="text-[10px] text-right font-bold text-[#64748B]">– Arun Kumar</div>
                </div>

                {/* Project Demo Day Invitation Card */}
                <div className="bg-gradient-to-br from-[#F0FDF4] to-[#DCFCE7] border border-[#BBF7D0] p-3.5 rounded-xl space-y-2">
                  <div className="text-xs font-bold text-[#15803D]">Project Demo Day</div>
                  <p className="text-[11px] text-[#166534]">Sat, Nov 8 · 10:00 AM · You are invited</p>
                  <button
                    onClick={() => setRsvpDone(true)}
                    className="w-full py-2 bg-[#2BB3A0] hover:bg-[#249B8A] text-white font-bold text-xs rounded-lg shadow-sm"
                  >
                    {rsvpDone ? "RSVP Confirmed ✓" : "RSVP – Attend Event"}
                  </button>
                </div>

                {/* Message Trainer Button */}
                <Link
                  href="/trainer/messages"
                  className="w-full py-2.5 bg-[#2B5CD0] hover:bg-[#1E46B0] text-white font-bold text-xs rounded-xl shadow-sm flex items-center justify-center gap-1.5"
                >
                  <MessageSquare className="w-3.5 h-3.5" />
                  <span>Message the Trainer</span>
                </Link>
                <div className="text-[10px] text-center text-[#64748B]">Replies within 24 hours</div>
              </div>
            </div>
          </div>
        ) : (
          /* FULL DESKTOP WEB VIEW (PDF 10) */
          <>
            {/* Top 3 KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-white p-4 rounded-xl border border-[#E2E8F0] shadow-sm space-y-1.5">
                <div className="flex items-center justify-between text-xs text-[#64748B]">
                  <span>{t("student.readiness_score")}</span>
                  <span className="chip-amber">{t("student.nearly_ready")}</span>
                </div>
                <div className="text-3xl font-black text-[#0F1F3A]">74</div>
                <div className="text-[11px] text-[#15803D] font-bold">▲ +6 vs September</div>
              </div>

              <div className="bg-white p-4 rounded-xl border border-[#E2E8F0] shadow-sm space-y-1.5">
                <div className="flex items-center justify-between text-xs text-[#64748B]">
                  <span>{t("student.attendance")}</span>
                  <span className="chip-green">Excellent</span>
                </div>
                <div className="text-3xl font-black text-[#0F1F3A]">92%</div>
                <div className="text-[11px] text-[#64748B]">Above 85% recommended target</div>
              </div>

              <div className="bg-white p-4 rounded-xl border border-[#E2E8F0] shadow-sm space-y-1.5">
                <div className="flex items-center justify-between text-xs text-[#64748B]">
                  <span>Certifications</span>
                  <span className="chip-blue">Active</span>
                </div>
                <div className="text-3xl font-black text-[#0F1F3A]">1</div>
                <div className="text-[11px] text-[#64748B]">AWS exam scheduled Nov 22</div>
              </div>
            </div>

            {/* Monthly Progress Card Table (PDF 10) */}
            <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-4">
              <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
                <h3 className="font-bold text-xs text-[#0F1F3A]">{t("parent.monthly_progress_card")}</h3>
                <span className="text-[11px] font-semibold text-[#64748B]">October</span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead>
                    <tr className="border-b border-[#E2E8F0] text-[#64748B] text-[11px]">
                      <th className="pb-2 font-semibold">Area</th>
                      <th className="pb-2 font-semibold">September</th>
                      <th className="pb-2 font-semibold">October</th>
                      <th className="pb-2 font-semibold text-right">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E2E8F0]">
                    {monthlyCards.map((row) => (
                      <tr key={row.area} className="hover:bg-[#F8FAFC]">
                        <td className="py-3 font-bold text-[#0F1F3A]">{row.area}</td>
                        <td className="py-3 text-[#64748B]">{row.sep}</td>
                        <td className="py-3 font-semibold text-[#0F1F3A]">{row.oct}</td>
                        <td className="py-3 text-right">
                          <span className={row.isGreen ? "chip-green" : "chip-amber"}>
                            {row.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Light Blue "How You Can Help" Box (PDF 10) */}
            <div className="bg-[#EFF6FF] border border-[#BFDBFE] rounded-xl p-4 flex items-start gap-3">
              <Heart className="w-5 h-5 text-[#2B5CD0] flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="text-xs font-bold text-[#1D4ED8]">{t("parent.how_you_can_help")}</h4>
                <p className="text-xs text-[#1E3A8A] mt-1 leading-relaxed">
                  {language === "ta"
                    ? "தினமும் 10 நிமிடங்கள் வீட்டில் ஆங்கிலத்தில் பேச ஊக்குவிக்கவும், மேலும் பிரியாவிடம் அவரது புராஜெக்ட் பற்றி விளக்குமாறு கேட்கவும்."
                    : "Encourage 10 minutes of spoken English daily and ask Priya to explain her project to you at home."}
                </p>
              </div>
            </div>

            {/* Bottom Row: Portfolio & Upcoming Events */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Portfolio Links */}
              <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-3">
                <h3 className="font-bold text-xs text-[#0F1F3A] border-b border-[#E2E8F0] pb-2">Student Portfolio</h3>
                <div className="space-y-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-[#64748B]">GitHub:</span>
                    <span className="font-bold text-[#0F1F3A]">5 public repositories</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[#64748B]">Live Web Project:</span>
                    <span className="font-bold text-[#2B5CD0]">Crop Price Predictor</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[#64748B]">Demo video:</span>
                    <span className="font-semibold text-[#0F1F3A]">Sem 4 project available</span>
                  </div>
                </div>
              </div>

              {/* Upcoming Events & RSVP */}
              <div className="bg-white p-5 rounded-xl border border-[#E2E8F0] shadow-sm space-y-3 flex flex-col justify-between">
                <div>
                  <h3 className="font-bold text-xs text-[#0F1F3A] border-b border-[#E2E8F0] pb-2">Upcoming Events</h3>
                  <div className="space-y-2 text-xs pt-1">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-[#0F1F3A]">Project Demo Day · Nov 8</span>
                      <span className="chip-purple">Invited</span>
                    </div>
                    <div className="flex items-center justify-between text-[#64748B]">
                      <span>Parent review meeting · Nov 15</span>
                      <span>10:30 AM</span>
                    </div>
                  </div>
                </div>

                <div className="pt-2 flex gap-2">
                  <button
                    onClick={() => setRsvpDone(true)}
                    className="flex-1 py-2 bg-[#2BB3A0] hover:bg-[#249B8A] text-white font-bold text-xs rounded-lg shadow-sm"
                  >
                    {rsvpDone ? "RSVP Confirmed ✓" : "RSVP for Demo Day"}
                  </button>
                  <Link
                    href="/trainer/messages"
                    className="px-3 py-2 border border-[#2B5CD0] text-[#2B5CD0] font-bold text-xs rounded-lg hover:bg-[#EFF6FF] flex items-center gap-1"
                  >
                    <MessageSquare className="w-3.5 h-3.5" />
                    <span>Message Trainer</span>
                  </Link>
                </div>
              </div>
            </div>
          </>
        )}

      </div>
    </AppShell>
  );
}
