"use client";

import React, { useState } from "react";
import { AppShell } from "@/components/AppShell";
import {
  Search, Send, Languages, Paperclip, MessageSquare,
  ShieldCheck, AlertTriangle, Radio, Check, X, ExternalLink
} from "lucide-react";
import Link from "next/link";

export default function TrainerMessageHubPage() {
  const [selectedFilter, setSelectedFilter] = useState("All");
  const [selectedThread, setSelectedThread] = useState("th_ramesh");
  const [replyText, setReplyText] = useState("");
  const [showTamil, setShowTamil] = useState(false);
  const [broadcastModal, setBroadcastModal] = useState(false);
  const [moderationItems, setModerationItems] = useState([
    { id: "1", text: "External test answers leak link shared", author: "Student in CSE-A" },
    { id: "2", text: "Inappropriate comment flag in General", author: "Student in AI & DS" }
  ]);

  const filterChips = ["All", "Parents", "College", "Groups"];

  const threads = [
    { id: "th_ramesh", name: "Mr. Ramesh K", role: "Parent · Priya R", initials: "RK", time: "10:45 AM", preview: "Vanakkam sir, Priya's mock interview feedback received.", badge: 0, category: "Parents" },
    { id: "th_lakshmi", name: "Mrs. Lakshmi S", role: "Parent · Karthik S", initials: "LS", time: "Yesterday", preview: "Will Karthik have extra coaching this Saturday?", badge: 2, category: "Parents" },
    { id: "th_kavitha", name: "Dr. Kavitha (Coordinator)", role: "College", initials: "DK", time: "Yesterday", preview: "MoU progress report due for governing council review.", badge: 1, category: "College" },
    { id: "th_placement", name: "Placement Cell", role: "College", initials: "PC", time: "Oct 7", preview: "Shortlisted candidates for Mock Drive 1 ready.", badge: 0, category: "College" },
    { id: "th_group_ai", name: "AI & DS · Sem 5 Batch", role: "Group · 42", initials: "AI", time: "Oct 6", preview: "Next project standup on Monday.", badge: 0, category: "Groups" },
    { id: "th_group_cyber", name: "Cyber · Sem 5 Batch", role: "Group · 31", initials: "CY", time: "Oct 5", preview: "OWASP lab walkthrough uploaded.", badge: 0, category: "Groups" }
  ];

  const filteredThreads = selectedFilter === "All"
    ? threads
    : threads.filter((t) => t.category === selectedFilter);

  const [conversation, setConversation] = useState([
    {
      id: "m1",
      sender: "Mr. Ramesh K",
      isIncoming: true,
      text_en: "Hello Arun sir, I reviewed Priya's October progress card. Her coding score improved nicely.",
      text_ta: "வணக்கம் அருண் சார், பிரியாவின் அக்டோபர் மாத முன்னேற்ற அட்டையைப் பார்த்தேன். கோடிங் மதிப்பெண்கள் நன்றாக உயர்ந்துள்ளது.",
      time: "10:30 AM"
    },
    {
      id: "m2",
      sender: "Arun Kumar (You)",
      isIncoming: false,
      text_en: "Hello Mr. Ramesh! Yes, Priya solved 34 problems this month. If she practices spoken English for 10 minutes daily at home, she will easily reach the Placement Ready band.",
      text_ta: "வணக்கம் ரமேஷ் சார்! ஆம், பிரியா இந்த மாதம் 34 கணக்குகளைத் தீர்த்துள்ளார். வீட்டில் தினமும் 10 நிமிடங்கள் ஆங்கிலத்தில் பேச பயிற்சி செய்தால் பிளேஸ்மென்ட் தயார் நிலையை எளிதில் எட்டிவிடுவார்.",
      time: "10:38 AM"
    },
    {
      id: "m3",
      sender: "Mr. Ramesh K",
      isIncoming: true,
      text_en: "Sure sir, we will definitely encourage her. Thank you for your guidance.",
      text_ta: "நிச்சயமாக சார், நாங்கள் அவளை ஊக்குவிக்கிறோம். உங்கள் வழிகாட்டுதலுக்கு நன்றி.",
      time: "10:45 AM"
    }
  ]);

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!replyText.trim()) return;

    setConversation([
      ...conversation,
      {
        id: `m_${Date.now()}`,
        sender: "Arun Kumar (You)",
        isIncoming: false,
        text_en: replyText,
        text_ta: `[தமிழ்] ${replyText}`,
        time: "Just now"
      }
    ]);
    setReplyText("");
  };

  const handleModerationAction = (id: string) => {
    setModerationItems(moderationItems.filter((item) => item.id !== id));
  };

  return (
    <AppShell pageTitle="Trainer Message Hub">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 h-[calc(100vh-120px)] max-w-7xl mx-auto">
        
        {/* LEFT COLUMN: Filter & Threads List (3 cols) */}
        <div className="lg:col-span-3 bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-3 flex flex-col overflow-hidden">
          {/* Filter Chips */}
          <div className="flex gap-1.5 pb-3 border-b border-[#E2E8F0] overflow-x-auto scrollbar-none flex-shrink-0">
            {filterChips.map((fc) => (
              <button
                key={fc}
                onClick={() => setSelectedFilter(fc)}
                className={`px-2.5 py-1 rounded-full text-xs font-semibold cursor-pointer transition-all ${
                  selectedFilter === fc
                    ? "bg-[#2B5CD0] text-white shadow-xs"
                    : "bg-[#F1F5F9] text-[#64748B] hover:bg-[#E2E8F0]"
                }`}
              >
                {fc}
              </button>
            ))}
          </div>

          {/* Threads Scroll */}
          <div className="flex-1 overflow-y-auto space-y-1 pt-2">
            {filteredThreads.map((th) => {
              const isSelected = selectedThread === th.id;
              return (
                <button
                  key={th.id}
                  onClick={() => setSelectedThread(th.id)}
                  className={`w-full p-2.5 rounded-xl text-left transition-all flex items-start gap-2.5 cursor-pointer ${
                    isSelected
                      ? "bg-[#EFF6FF] border border-[#BFDBFE]"
                      : "hover:bg-[#F8FAFC] border border-transparent"
                  }`}
                >
                  <div className="w-8 h-8 rounded-full bg-[#14284B] text-white font-bold text-xs flex items-center justify-center flex-shrink-0">
                    {th.initials}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-xs text-[#0F1F3A] truncate">{th.name}</span>
                      <span className="text-[10px] text-[#94A3B8]">{th.time}</span>
                    </div>
                    <div className="text-[10px] font-semibold text-[#2B5CD0]">{th.role}</div>
                    <p className="text-[11px] text-[#64748B] truncate mt-0.5">{th.preview}</p>
                  </div>
                  {th.badge > 0 && (
                    <span className="w-4 h-4 rounded-full bg-[#D93636] text-white text-[9px] font-bold flex items-center justify-center flex-shrink-0 mt-1">
                      {th.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* CENTRE COLUMN: Active Conversation & Translation (6 cols) */}
        <div className="lg:col-span-6 bg-white rounded-xl border border-[#E2E8F0] shadow-sm flex flex-col overflow-hidden">
          {/* Header */}
          <div className="p-3.5 border-b border-[#E2E8F0] flex items-center justify-between flex-shrink-0">
            <div>
              <h3 className="text-sm font-bold text-[#0F1F3A]">Mr. Ramesh K</h3>
              <p className="text-[11px] text-[#64748B]">Parent of Priya R · Sem 5 AI & DS · <span className="text-[#2B5CD0] font-semibold">Prefers Tamil</span></p>
            </div>
            <Link
              href="/parent"
              className="px-3 py-1 bg-[#F1F5F9] hover:bg-[#E2E8F0] text-[#2B5CD0] text-xs font-bold rounded-lg border border-[#CBD5E1] transition-all"
            >
              View progress card
            </Link>
          </div>

          {/* Translation Toggle Pill */}
          <div className="bg-[#EFF6FF] border-b border-[#BFDBFE] px-4 py-1.5 flex items-center justify-between text-xs text-[#1D4ED8] flex-shrink-0">
            <span className="flex items-center gap-1.5 font-medium">
              <Languages className="w-3.5 h-3.5 text-[#2B5CD0]" />
              <span>Auto-translate available: தமிழ் ⇄ English</span>
            </span>
            <button
              onClick={() => setShowTamil(!showTamil)}
              className="text-[11px] font-bold underline cursor-pointer hover:text-[#1E3A8A]"
            >
              {showTamil ? "Show Original (English)" : "Show in Tamil (தமிழ்)"}
            </button>
          </div>

          {/* Messages Body */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3.5">
            {conversation.map((msg) => (
              <div
                key={msg.id}
                className={`flex flex-col ${msg.isIncoming ? "items-start" : "items-end"}`}
              >
                <div
                  className={`max-w-[80%] p-3.5 rounded-2xl text-xs space-y-1 ${
                    msg.isIncoming
                      ? "bg-[#F1F5F9] text-[#0F1F3A] rounded-tl-xs"
                      : "bg-[#2B5CD0] text-white rounded-tr-xs"
                  }`}
                >
                  <p className="leading-relaxed">
                    {showTamil ? (msg.text_ta || msg.text_en) : msg.text_en}
                  </p>
                  <div
                    className={`text-[9px] text-right ${
                      msg.isIncoming ? "text-[#94A3B8]" : "text-white/70"
                    }`}
                  >
                    {msg.time}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Message Input Box */}
          <form onSubmit={handleSend} className="p-3 border-t border-[#E2E8F0] flex items-center gap-2 flex-shrink-0">
            <input
              type="text"
              value={replyText}
              onChange={(e) => setReplyText(e.target.value)}
              placeholder="Type a message..."
              className="flex-1 px-3.5 py-2 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-xs text-[#0F1F3A] focus:outline-none focus:border-[#2B5CD0] focus:bg-white"
            />
            <button type="button" className="p-2 text-[#64748B] hover:text-[#0F1F3A]" title="Attach">
              <Paperclip className="w-4 h-4" />
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-[#2B5CD0] hover:bg-[#1E46B0] text-white font-bold text-xs rounded-xl shadow-xs flex items-center gap-1.5 cursor-pointer"
            >
              <span>Send</span>
              <Send className="w-3.5 h-3.5" />
            </button>
          </form>
        </div>

        {/* RIGHT COLUMN: Permission Matrix + Moderation Queue + Broadcast (3 cols) */}
        <div className="lg:col-span-3 space-y-4 flex flex-col justify-between overflow-y-auto">
          {/* Who Can Message Whom (PDF 12) */}
          <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm space-y-3">
            <h4 className="text-xs font-bold text-[#0F1F3A] border-b border-[#E2E8F0] pb-2">
              Who can message whom
            </h4>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#64748B]">Student ⇄ Student 1-1</span>
                <span className="chip-red">Off</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#64748B]">Student groups</span>
                <span className="chip-green">Moderated</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#64748B]">Trainer ⇄ Parent 1-1</span>
                <span className="chip-green">Allowed</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#64748B]">Trainer ⇄ College 1-1</span>
                <span className="chip-green">Allowed</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#64748B]">Announcements</span>
                <span className="chip-blue">Broadcast</span>
              </div>
            </div>
          </div>

          {/* Moderation Queue */}
          <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
              <h4 className="text-xs font-bold text-[#0F1F3A]">Moderation queue</h4>
              {moderationItems.length > 0 && (
                <span className="w-4 h-4 rounded-full bg-[#D93636] text-white text-[10px] font-bold flex items-center justify-center">
                  {moderationItems.length}
                </span>
              )}
            </div>

            {moderationItems.length === 0 ? (
              <div className="text-xs text-[#64748B] italic py-2 text-center">Queue empty ✓</div>
            ) : (
              <div className="space-y-2">
                {moderationItems.map((item) => (
                  <div key={item.id} className="p-2.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg space-y-2 text-xs">
                    <div>
                      <div className="text-[10px] text-[#64748B]">{item.author}</div>
                      <div className="font-medium text-[#0F1F3A]">{item.text}</div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleModerationAction(item.id)}
                        className="px-2.5 py-1 bg-red-100 hover:bg-red-200 text-red-700 font-bold text-[10px] rounded"
                      >
                        Remove
                      </button>
                      <button
                        onClick={() => handleModerationAction(item.id)}
                        className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-[#0F1F3A] font-bold text-[10px] rounded"
                      >
                        Keep
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Broadcast Card */}
          <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm space-y-2">
            <h4 className="text-xs font-bold text-[#0F1F3A]">Broadcast</h4>
            <p className="text-[11px] text-[#64748B]">Send announcements to batches, parents, or both simultaneously.</p>
            <button
              onClick={() => setBroadcastModal(true)}
              className="w-full py-2 bg-[#2BB3A0] hover:bg-[#249B8A] text-white font-bold text-xs rounded-xl shadow-xs flex items-center justify-center gap-1.5 cursor-pointer"
            >
              <Radio className="w-3.5 h-3.5" />
              <span>New announcement</span>
            </button>
          </div>
        </div>

      </div>

      {/* Broadcast Modal */}
      {broadcastModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl border border-[#E2E8F0]">
            <h3 className="text-base font-bold text-[#0F1F3A]">Send Broadcast Announcement</h3>
            <div className="space-y-3 text-xs">
              <div>
                <label className="font-bold text-[#0F1F3A] block mb-1">Target Audience</label>
                <select className="w-full p-2 border rounded-lg bg-[#F8FAFC]">
                  <option>All Students (Batches)</option>
                  <option>All Parents</option>
                  <option>Both Students and Parents</option>
                </select>
              </div>
              <div>
                <label className="font-bold text-[#0F1F3A] block mb-1">Announcement Title</label>
                <input type="text" placeholder="e.g. Saturday Lab Timing Update" className="w-full p-2 border rounded-lg bg-[#F8FAFC]" />
              </div>
              <div>
                <label className="font-bold text-[#0F1F3A] block mb-1">Message Content</label>
                <textarea rows={3} placeholder="Type announcement message..." className="w-full p-2 border rounded-lg bg-[#F8FAFC]" />
              </div>
            </div>
            <div className="flex gap-2 pt-2">
              <button
                onClick={() => setBroadcastModal(false)}
                className="flex-1 py-2 bg-[#F1F5F9] text-[#0F1F3A] font-bold text-xs rounded-xl"
              >
                Cancel
              </button>
              <button
                onClick={() => setBroadcastModal(false)}
                className="flex-1 py-2 bg-[#2BB3A0] text-white font-bold text-xs rounded-xl"
              >
                Send Broadcast
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}

