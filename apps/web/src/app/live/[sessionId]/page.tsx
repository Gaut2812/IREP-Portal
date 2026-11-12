"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  Mic, MicOff, Video, VideoOff, Hand, MessageSquare,
  BarChart2, Cpu, LogOut, ArrowDown, ThumbsUp, CheckCircle2, Circle
} from "lucide-react";

export default function LiveClassroomPage() {
  const [micOn, setMicOn] = useState(false);
  const [camOn, setCamOn] = useState(false);
  const [handRaised, setHandRaised] = useState(false);
  const [pollVoted, setPollVoted] = useState(false);
  const [qaUpvotes, setQaUpvotes] = useState(14);

  return (
    <div className="h-screen w-screen bg-[#1B2236] text-white flex flex-col font-sans overflow-hidden">
      
      {/* TOP BAR (PDF 13) */}
      <header className="h-12 bg-[#141A29] border-b border-[#2D3748] px-4 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded-md bg-[#2BB3A0] flex items-center justify-center font-bold text-xs text-white">IR</span>
            <span className="font-extrabold text-sm tracking-wide text-white">IREP Live</span>
          </div>
          <span className="text-[#475569]">|</span>
          <span className="font-bold text-xs text-[#E2E8F0]">Future Skills: LLM APIs & RAG</span>
          <span className="text-[11px] text-[#94A3B8]">AI & DS · Sem 5 · Week 8 · Thu</span>
        </div>

        <div className="flex items-center gap-3 text-xs">
          {/* Red REC Pill */}
          <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-red-950/80 border border-red-800 text-red-400 font-bold text-[10px]">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            REC
          </span>

          {/* Timer */}
          <span className="font-mono text-[#CBD5E1] text-xs">00:38:12 / 01:00:00</span>

          {/* Attendance Status */}
          <span className="chip-green text-[10px] font-bold">
            Attendance on track
          </span>
        </div>
      </header>

      {/* STAGE & RIGHT COLUMN */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* STAGE AREA (Left ~75%) */}
        <div className="flex-1 flex flex-col justify-between p-4 space-y-3 overflow-hidden">
          
          {/* Main Stage: Screen Share & RAG Flow (PDF 13) */}
          <div className="flex-1 bg-[#141A29] rounded-2xl border border-[#2D3748] p-4 flex flex-col justify-between overflow-hidden relative">
            {/* Screen Share Header */}
            <div className="flex items-center justify-between pb-3 border-b border-[#2D3748]">
              <div className="flex items-center gap-2 text-xs">
                <span className="w-2.5 h-2.5 rounded-full bg-[#2BB3A0]" />
                <span className="font-bold text-[#E2E8F0]">Arun K is sharing screen · <code className="font-mono text-[#2BB3A0]">rag_demo.ipynb</code></span>
              </div>
              <span className="text-[10px] text-[#94A3B8] bg-[#1E293B] px-2 py-0.5 rounded">Shared via Virtual Labs</span>
            </div>

            {/* Split Stage: Code Editor (Left) + RAG Flow Diagram (Right) */}
            <div className="flex-1 grid grid-cols-1 md:grid-cols-12 gap-4 py-3 overflow-hidden">
              {/* Code Editor */}
              <div className="md:col-span-8 bg-[#0F172A] rounded-xl p-3.5 font-mono text-xs overflow-auto border border-[#1E293B] text-[#E2E8F0] space-y-2 leading-relaxed">
                <div className="text-[#64748B]"># Step 1: Create retriever with similarity top_k = 3</div>
                <div><span className="text-[#F472B6]">from</span> langchain_community.vectorstores <span className="text-[#F472B6]">import</span> Chroma</div>
                <div>retriever = vectorstore.as_retriever(search_kwargs=&#123;<span className="text-[#38BDF8]">"k"</span>: <span className="text-[#FBBF24]">3</span>&#125;)</div>
                <div className="pt-2 text-[#64748B]"># Step 2: Augment prompt with context</div>
                <div>prompt = f<span className="text-[#38BDF8]">"""Use the following notes to answer:</span></div>
                <div><span className="text-[#38BDF8]">&#123;context&#125;</span></div>
                <div><span className="text-[#38BDF8]">Question: &#123;question&#125;"""</span></div>
                <div className="pt-2 text-[#64748B]"># Step 3: Stream generated response</div>
                <div>response = model.invoke(prompt)</div>
                <div><span className="text-[#38BDF8]">print</span>(response.content)</div>
              </div>

              {/* White "RAG Flow" Panel with 4 Stacked Steps (PDF 13) */}
              <div className="md:col-span-4 bg-white rounded-xl p-4 text-[#0F1F3A] flex flex-col justify-between shadow-lg">
                <div className="text-xs font-bold text-[#0F1F3A] border-b border-[#E2E8F0] pb-2 text-center uppercase tracking-wider">
                  RAG Architecture Flow
                </div>

                <div className="space-y-2 py-2">
                  <div className="p-2 rounded-lg bg-[#EFF6FF] border border-[#BFDBFE] text-center text-xs font-bold text-[#1D4ED8]">
                    1. Question
                  </div>
                  <div className="flex justify-center text-[#94A3B8]"><ArrowDown className="w-3.5 h-3.5" /></div>
                  <div className="p-2 rounded-lg bg-[#DCFCE7] border border-[#BBF7D0] text-center text-xs font-bold text-[#15803D]">
                    2. Search vector DB
                  </div>
                  <div className="flex justify-center text-[#94A3B8]"><ArrowDown className="w-3.5 h-3.5" /></div>
                  <div className="p-2 rounded-lg bg-[#FEF3C7] border border-[#FDE68A] text-center text-xs font-bold text-[#B45309]">
                    3. Add context to prompt
                  </div>
                  <div className="flex justify-center text-[#94A3B8]"><ArrowDown className="w-3.5 h-3.5" /></div>
                  <div className="p-2 rounded-lg bg-[#EDE9FE] border border-[#DDD6FE] text-center text-xs font-bold text-[#6D28D9]">
                    4. LLM answers
                  </div>
                </div>

                <div className="text-[10px] text-[#64748B] text-center italic">
                  Live demo synchronized across participants
                </div>
              </div>
            </div>

            {/* Bottom Strip: Participant Avatars (PDF 13) */}
            <div className="flex items-center gap-2 pt-2 border-t border-[#2D3748] overflow-x-auto">
              {[
                { name: "AK Arun K (Trainer)", color: "bg-[#2B5CD0]" },
                { name: "PR Priya R (You)", color: "bg-[#2BB3A0]" },
                { name: "SN Sneha N", color: "bg-[#7C5CE0]" },
                { name: "VR Vikram R", color: "bg-[#F59E0B]" },
                { name: "AP Ananya P", color: "bg-pink-600" }
              ].map((p) => (
                <div key={p.name} className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#1E293B] border border-[#334155] text-xs">
                  <span className={`w-5 h-5 rounded-full ${p.color} text-white font-bold text-[10px] flex items-center justify-center`}>
                    {p.name.substring(0, 2)}
                  </span>
                  <span className="text-[11px] text-[#E2E8F0] whitespace-nowrap">{p.name}</span>
                </div>
              ))}
              <span className="text-[11px] text-[#94A3B8] px-2">+ 36 more</span>
            </div>
          </div>

          {/* CONTROL BAR (Bottom) */}
          <div className="h-12 bg-[#141A29] rounded-xl border border-[#2D3748] px-4 flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setMicOn(!micOn)}
                className={`p-2 rounded-lg transition-all ${micOn ? "bg-[#2BB3A0] text-white" : "bg-[#1E293B] text-[#94A3B8] hover:text-white"}`}
                title="Mute / Unmute"
              >
                {micOn ? <Mic className="w-4 h-4" /> : <MicOff className="w-4 h-4" />}
              </button>

              <button
                onClick={() => setCamOn(!camOn)}
                className={`p-2 rounded-lg transition-all ${camOn ? "bg-[#2BB3A0] text-white" : "bg-[#1E293B] text-[#94A3B8] hover:text-white"}`}
                title="Camera"
              >
                {camOn ? <Video className="w-4 h-4" /> : <VideoOff className="w-4 h-4" />}
              </button>

              <button
                onClick={() => setHandRaised(!handRaised)}
                className={`p-2 rounded-lg transition-all ${handRaised ? "bg-[#F59E0B] text-white" : "bg-[#1E293B] text-[#94A3B8] hover:text-white"}`}
                title="Raise Hand"
              >
                <Hand className="w-4 h-4" />
              </button>
            </div>

            {/* Middle Quick Tools */}
            <div className="flex items-center gap-2 text-xs">
              <span className="text-[#94A3B8] flex items-center gap-1.5"><Cpu className="w-4 h-4 text-[#2BB3A0]" /> Lab: Connected</span>
            </div>

            {/* Leave Room Button */}
            <Link
              href="/student/live"
              className="flex items-center gap-1.5 px-4 py-1.5 bg-[#D93636] hover:bg-[#B91C1C] text-white text-xs font-bold rounded-lg shadow transition-all"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Leave</span>
            </Link>
          </div>
        </div>

        {/* RIGHT COLUMN (PDF 13: Polls, Q&A, Auto-attendance) (~25%) */}
        <div className="w-80 bg-[#141A29] border-l border-[#2D3748] p-4 flex flex-col justify-between space-y-4 overflow-y-auto">
          
          <div className="space-y-4">
            {/* Live Poll (31 votes) */}
            <div className="bg-[#1E293B] border border-[#334155] rounded-xl p-3.5 space-y-2.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-[#E2E8F0]">Live poll</span>
                <span className="text-[10px] text-[#2BB3A0]">31 votes</span>
              </div>
              <p className="text-[11px] text-[#CBD5E1] leading-tight font-medium">
                If the answer is not in the notes, the model should...
              </p>

              <div className="space-y-2 pt-1 text-xs">
                <div className="space-y-1">
                  <div className="flex justify-between text-[11px] text-[#94A3B8]">
                    <span>Make up an answer</span>
                    <span className="text-red-400 font-bold">6%</span>
                  </div>
                  <div className="w-full bg-[#0F172A] h-1.5 rounded-full overflow-hidden">
                    <div className="bg-red-500 h-full" style={{ width: "6%" }} />
                  </div>
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between text-[11px] text-[#E2E8F0] font-bold">
                    <span>Say it doesn't know</span>
                    <span className="text-[#2BB3A0] font-bold">87%</span>
                  </div>
                  <div className="w-full bg-[#0F172A] h-2 rounded-full overflow-hidden">
                    <div className="bg-[#2BB3A0] h-full" style={{ width: "87%" }} />
                  </div>
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between text-[11px] text-[#94A3B8]">
                    <span>Search the web</span>
                    <span className="text-blue-400 font-bold">7%</span>
                  </div>
                  <div className="w-full bg-[#0F172A] h-1.5 rounded-full overflow-hidden">
                    <div className="bg-blue-500 h-full" style={{ width: "7%" }} />
                  </div>
                </div>
              </div>
            </div>

            {/* Moderated Q&A */}
            <div className="bg-[#1E293B] border border-[#334155] rounded-xl p-3.5 space-y-2.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-[#E2E8F0]">Q&A</span>
                <span className="text-[10px] text-[#94A3B8]">Session chat · moderated</span>
              </div>

              <div className="p-2.5 rounded-lg bg-[#0F172A] border border-[#334155] space-y-1.5 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-[#2BB3A0]">Sneha N</span>
                  <button
                    onClick={() => setQaUpvotes(qaUpvotes + 1)}
                    className="flex items-center gap-1 text-[10px] font-bold text-[#38BDF8] hover:text-white"
                  >
                    <ThumbsUp className="w-3 h-3" />
                    <span>{qaUpvotes}</span>
                  </button>
                </div>
                <p className="text-[11px] text-[#E2E8F0]">How do we choose top_k for similarity search?</p>
                <div className="text-[10px] text-[#2BB3A0] font-semibold flex items-center gap-1 pt-0.5">
                  <CheckCircle2 className="w-3 h-3" /> Answered live at 31:40
                </div>
              </div>
            </div>
          </div>

          {/* Auto Attendance Card (PDF 13) */}
          <div className="bg-[#0F172A] border border-[#334155] rounded-xl p-3.5 space-y-2 text-xs">
            <div className="flex items-center justify-between font-bold text-[#E2E8F0]">
              <span>Auto attendance</span>
              <span className="text-[#2BB3A0]">38 / 60 min</span>
            </div>
            <div className="w-full bg-[#1E293B] h-2 rounded-full overflow-hidden">
              <div className="bg-[#2BB3A0] h-full rounded-full" style={{ width: `${(38 / 60) * 100}%` }} />
            </div>
            <p className="text-[11px] text-[#94A3B8] leading-tight">
              Joined 10:58 AM · present 38 of 60 min so far. Marked present automatically at 45 min (75% of the session).
            </p>
          </div>

        </div>

      </div>

    </div>
  );
}
