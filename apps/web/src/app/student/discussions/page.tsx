"use client";

import React, { useState } from "react";
import { AppShell } from "@/components/AppShell";
import {
  Users, Lock, Pin, Send, ThumbsUp, CheckCircle2,
  ShieldCheck, Code2, Paperclip, AlertCircle, Medal
} from "lucide-react";

export default function DiscussionGroupsPage() {
  const [selectedGroup, setSelectedGroup] = useState("grp_doubts");
  const [replyText, setReplyText] = useState("");
  const [reactions, setReactions] = useState(12);
  const [hasLiked, setHasLiked] = useState(false);

  const groups = [
    { id: "grp_batch", name: "AI & DS · Sem 5 Batch", badge: 3, locked: false },
    { id: "grp_doubts", name: "Track Doubts · ML", badge: 5, locked: false },
    { id: "grp_dsa", name: "DSA Daily Problem", badge: 0, locked: false },
    { id: "grp_team", name: "Team: Crop Price Predictor", badge: 2, locked: false },
    { id: "grp_placement", name: "Placement Updates", badge: 1, locked: true },
    { id: "grp_gd", name: "GD & Communication", badge: 0, locked: false }
  ];

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!replyText.trim()) return;
    setReplyText("");
  };

  const handleLike = () => {
    if (!hasLiked) {
      setReactions(reactions + 1);
      setHasLiked(true);
    } else {
      setReactions(reactions - 1);
      setHasLiked(false);
    }
  };

  return (
    <AppShell pageTitle="Discussion Groups">
      <div className="space-y-4 max-w-7xl mx-auto h-[calc(100vh-120px)] flex flex-col">
        
        {/* SAFE SPACE BANNER (Yellow) matching PDF 11 */}
        <div className="bg-[#FEF3C7] border border-[#FDE68A] p-3 rounded-xl flex items-center gap-2.5 text-xs text-[#92400E] flex-shrink-0">
          <ShieldCheck className="w-4 h-4 text-[#B45309] flex-shrink-0" />
          <span>
            <strong>Safe learning space:</strong> students chat in moderated groups only. One-to-one messaging between students is turned off. All groups are moderated by trainers.
          </span>
        </div>

        {/* 3-COLUMN LAYOUT */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 flex-1 min-h-0">
          
          {/* LEFT COLUMN: Groups List (3 cols) */}
          <div className="lg:col-span-3 bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-3 flex flex-col justify-between overflow-hidden">
            <div>
              <div className="text-[11px] font-bold text-[#64748B] uppercase tracking-wider px-2 py-1.5 border-b border-[#E2E8F0]">
                My Groups
              </div>
              <div className="mt-2 space-y-1 overflow-y-auto">
                {groups.map((g) => {
                  const isSelected = selectedGroup === g.id;
                  return (
                    <button
                      key={g.id}
                      onClick={() => setSelectedGroup(g.id)}
                      className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-left text-xs transition-all ${
                        isSelected
                          ? "bg-[#EFF6FF] text-[#1D4ED8] font-bold border border-[#BFDBFE]"
                          : "text-[#0F1F3A] hover:bg-[#F8FAFC]"
                      }`}
                    >
                      <div className="flex items-center gap-2 truncate">
                        {g.locked ? (
                          <Lock className="w-3.5 h-3.5 text-[#64748B] flex-shrink-0" />
                        ) : (
                          <Users className="w-3.5 h-3.5 text-[#2B5CD0] flex-shrink-0" />
                        )}
                        <span className="truncate">{g.name}</span>
                      </div>
                      {g.badge > 0 && (
                        <span className="w-5 h-5 rounded-full bg-[#2B5CD0] text-white text-[10px] font-bold flex items-center justify-center flex-shrink-0">
                          {g.badge}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="text-[10px] text-[#64748B] p-2 bg-[#F8FAFC] rounded-lg border border-[#E2E8F0] leading-tight">
              Lock icon marks announcement-only groups where students can read and react.
            </div>
          </div>

          {/* CENTRE COLUMN: Active Conversation (6 cols) */}
          <div className="lg:col-span-6 bg-white rounded-xl border border-[#E2E8F0] shadow-sm flex flex-col overflow-hidden">
            {/* Group Header */}
            <div className="p-4 border-b border-[#E2E8F0] flex items-center justify-between flex-shrink-0">
              <div>
                <h3 className="text-sm font-bold text-[#0F1F3A]">Track Doubts · ML</h3>
                <p className="text-[11px] text-[#64748B]">42 members · Moderated by Arun K. and Meena S.</p>
              </div>
              <span className="chip-green text-[10px]">18 online</span>
            </div>

            {/* Pinned Note */}
            <div className="bg-[#FFFBEB] border-b border-[#FEF3C7] px-4 py-2 flex items-center gap-2 text-[11px] text-[#B45309] flex-shrink-0">
              <Pin className="w-3.5 h-3.5 text-[#D97706] flex-shrink-0" />
              <span>Post code as snippets, never share answers to graded tests. Be respectful.</span>
            </div>

            {/* Message Thread (PDF 11) */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {/* Message 1: Sneha N */}
              <div className="space-y-1.5">
                <div className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-[#EDE9FE] text-[#6D28D9] font-bold text-[10px] flex items-center justify-center">SN</span>
                  <span className="text-xs font-bold text-[#0F1F3A]">Sneha N</span>
                  <span className="text-[10px] text-[#64748B]">10:24 AM</span>
                </div>
                <div className="pl-8 space-y-2">
                  <p className="text-xs text-[#334155] leading-relaxed">
                    I'm getting 0.97 cross-validation score on the training set, but test accuracy drops to 0.64. I standardized features before splitting. Could that cause it?
                  </p>
                  <div className="bg-[#1B2236] text-[#E2E8F0] p-2.5 rounded-lg text-xs font-mono">
                    <span className="text-[#94A3B8]">from</span> sklearn.preprocessing <span className="text-[#94A3B8]">import</span> StandardScaler<br />
                    scaler = StandardScaler()<br />
                    X_scaled = scaler.fit_transform(X) <span className="text-[#64748B]"># before train_test_split</span>
                  </div>
                </div>
              </div>

              {/* Message 2: Vikram R */}
              <div className="space-y-1.5">
                <div className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-[#EFF6FF] text-[#1D4ED8] font-bold text-[10px] flex items-center justify-center">VR</span>
                  <span className="text-xs font-bold text-[#0F1F3A]">Vikram R</span>
                  <span className="text-[10px] text-[#64748B]">10:28 AM</span>
                </div>
                <div className="pl-8">
                  <p className="text-xs text-[#334155] leading-relaxed">
                    Yes! That is classic data leakage. The scaler learned the mean and variance of your test set during fit_transform.
                  </p>
                </div>
              </div>

              {/* Message 3: Arun K (Trainer) - Marked as Answer */}
              <div className="space-y-1.5 bg-[#F0FDF4] border border-[#BBF7D0] p-3 rounded-xl">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-[#14284B] text-white font-bold text-[10px] flex items-center justify-center">AK</span>
                    <span className="text-xs font-bold text-[#0F1F3A]">Arun K.</span>
                    <span className="px-1.5 py-0.5 rounded bg-[#14284B] text-white text-[9px] font-bold">Trainer</span>
                    <span className="text-[10px] text-[#64748B]">10:35 AM</span>
                  </div>
                  <span className="chip-green text-[10px] font-bold flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Marked as answer
                  </span>
                </div>
                <div className="pt-1">
                  <p className="text-xs text-[#166534] leading-relaxed">
                    Spot on Vikram. Always fit the scaler only on the training fold, or wrap the model inside a scikit-learn Pipeline so it handles this automatically in cross-validation.
                  </p>
                </div>
                <div className="flex items-center gap-2 pt-2">
                  <button
                    onClick={handleLike}
                    className="flex items-center gap-1 px-2.5 py-1 bg-white border border-[#BBF7D0] rounded-md text-[11px] font-bold text-[#15803D] hover:bg-[#DCFCE7] transition-all cursor-pointer"
                  >
                    <ThumbsUp className="w-3 h-3" />
                    <span>{reactions}</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Message Input Box */}
            <form onSubmit={handleSend} className="p-3 border-t border-[#E2E8F0] flex items-center gap-2 flex-shrink-0">
              <input
                type="text"
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                placeholder="Ask a doubt or reply..."
                className="flex-1 px-3.5 py-2 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-xs text-[#0F1F3A] focus:outline-none focus:border-[#2B5CD0] focus:bg-white"
              />
              <button type="button" className="p-2 text-[#64748B] hover:text-[#0F1F3A]" title="Insert code">
                <Code2 className="w-4 h-4" />
              </button>
              <button type="button" className="p-2 text-[#64748B] hover:text-[#0F1F3A]" title="Attach file">
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

          {/* RIGHT COLUMN: Group Info & Top Helpers (3 cols) */}
          <div className="lg:col-span-3 space-y-4 flex flex-col justify-between overflow-y-auto">
            {/* Group Info Card */}
            <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm space-y-3">
              <h4 className="text-xs font-bold text-[#0F1F3A] border-b border-[#E2E8F0] pb-2">Group info</h4>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between text-[#64748B]">
                  <span>Students enrolled:</span>
                  <strong className="text-[#0F1F3A]">42</strong>
                </div>
                <div className="flex justify-between text-[#64748B]">
                  <span>Trainer moderators:</span>
                  <strong className="text-[#0F1F3A]">2</strong>
                </div>
                <div className="flex justify-between text-[#64748B]">
                  <span>Doubts answered:</span>
                  <strong className="text-[#2BB3A0]">128</strong>
                </div>
                <div className="flex justify-between text-[#64748B]">
                  <span>Avg trainer reply:</span>
                  <strong className="text-[#0F1F3A]">35 min</strong>
                </div>
              </div>
            </div>

            {/* Top Helpers Card (PDF 11) */}
            <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm space-y-3">
              <h4 className="text-xs font-bold text-[#0F1F3A] border-b border-[#E2E8F0] pb-2">Top helpers</h4>
              <div className="space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 font-bold text-[#0F1F3A]">
                    <span className="text-amber-500">🥇</span>
                    <span>Vikram R</span>
                  </div>
                  <span className="chip-green text-[10px]">24 answers</span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 font-bold text-[#0F1F3A]">
                    <span className="text-slate-400">🥈</span>
                    <span>Ananya P</span>
                  </div>
                  <span className="chip-blue text-[10px]">19 answers</span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 font-bold text-[#0F1F3A]">
                    <span className="text-amber-700">🥉</span>
                    <span>Sneha N</span>
                  </div>
                  <span className="chip-purple text-[10px]">15 answers</span>
                </div>
              </div>
            </div>

            {/* Safety & Moderation Note */}
            <div className="bg-[#F8FAFC] border border-[#E2E8F0] p-3 rounded-xl text-[11px] text-[#64748B] space-y-1">
              <div className="font-bold text-[#0F1F3A] flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5 text-[#2B5CD0]" /> Safety Guidelines
              </div>
              <p>One-tap reporting available on every message for inappropriate or test leak content.</p>
            </div>
          </div>

        </div>

      </div>
    </AppShell>
  );
}
