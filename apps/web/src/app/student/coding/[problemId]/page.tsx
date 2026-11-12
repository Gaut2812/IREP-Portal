"use client";

import React, { useState, useEffect } from "react";
import { AppShell } from "@/components/AppShell";
import { Play, Send, Bot, CheckCircle2, AlertCircle, Sparkles, MessageSquareQuote } from "lucide-react";

export default function CodingLabPage() {
  const [code, setCode] = useState(`class Solution:
    def countComponents(self, n: int, edges: list[list[int]]) -> int:
        parent = list(range(n))
        
        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x]) # Path compression
            return parent[x]
            
        def union(x, y):
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[rx] = ry
                return 1
            return 0
            
        return n - sum(union(u, v) for u, v in edges)`);

  const [isRunning, setIsRunning] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(true);
  const [hintCount, setHintCount] = useState(1);
  const [showExtraHint, setShowExtraHint] = useState(false);

  const handleRun = () => {
    setIsRunning(true);
    setTimeout(() => {
      setIsRunning(false);
    }, 400);
  };

  const handleSubmit = () => {
    setIsRunning(true);
    setTimeout(() => {
      setIsRunning(false);
      setIsSubmitted(true);
    }, 600);
  };

  return (
    <AppShell pageTitle="Coding Lab">
      {/* 3-Column Grid matching PDF 3 */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 h-[calc(100vh-120px)]">
        
        {/* LEFT COLUMN: Problem Statement (4 cols) */}
        <div className="lg:col-span-4 bg-white rounded-xl border border-[#E2E8F0] shadow-sm flex flex-col justify-between overflow-hidden">
          <div className="p-5 overflow-y-auto space-y-4">
            {/* Tag Chips */}
            <div className="flex flex-wrap gap-2">
              <span className="chip-amber">Medium</span>
              <span className="chip-blue">Union-Find</span>
              <span className="chip-purple">Asked: Product cos.</span>
            </div>

            {/* Title */}
            <h2 className="text-base font-bold text-[#0F1F3A]">
              Number of Connected Components in an Undirected Graph
            </h2>

            {/* Description */}
            <p className="text-xs text-[#334155] leading-relaxed">
              You have a graph of <code className="bg-[#F1F5F9] px-1 py-0.5 rounded text-[#2B5CD0] font-mono">n</code> nodes. You are given an integer <code className="bg-[#F1F5F9] px-1 py-0.5 rounded text-[#2B5CD0] font-mono">n</code> and an array <code className="bg-[#F1F5F9] px-1 py-0.5 rounded text-[#2B5CD0] font-mono">edges</code> where <code className="bg-[#F1F5F9] px-1 py-0.5 rounded text-[#2B5CD0] font-mono">edges[i] = [ai, bi]</code> indicates an edge between nodes <code className="bg-[#F1F5F9] px-1 py-0.5 rounded text-[#2B5CD0] font-mono">ai</code> and <code className="bg-[#F1F5F9] px-1 py-0.5 rounded text-[#2B5CD0] font-mono">bi</code> in the graph.
            </p>
            <p className="text-xs text-[#334155] leading-relaxed font-semibold">
              Return the total number of connected components in the graph.
            </p>

            {/* Example Box */}
            <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-3.5 space-y-2 text-xs">
              <div className="font-bold text-[#0F1F3A]">Example 1:</div>
              <div className="font-mono text-[11px] text-[#334155]">
                <div><span className="text-[#64748B]">Input:</span> n = 5, edges = [[0,1],[1,2],[3,4]]</div>
                <div><span className="text-[#64748B]">Output:</span> 2</div>
              </div>
            </div>

            {/* Constraints */}
            <div className="space-y-1.5 pt-2">
              <div className="text-xs font-bold text-[#0F1F3A]">Constraints:</div>
              <ul className="list-disc list-inside text-[11px] text-[#64748B] space-y-1 font-mono">
                <li>1 ≤ n ≤ 2000</li>
                <li>0 ≤ edges.length ≤ 5000</li>
                <li>edges[i].length == 2</li>
                <li>0 ≤ ai ≤ bi &lt; n</li>
                <li>No repeated edges</li>
              </ul>
            </div>
          </div>

          {/* Footer Status */}
          <div className="p-3 bg-[#F8FAFC] border-t border-[#E2E8F0] text-[11px] font-semibold text-[#64748B] text-center">
            Week 8 · Pattern drill · 3 of 6 solved
          </div>
        </div>

        {/* MIDDLE COLUMN: Code Editor + Test Results (5 cols) */}
        <div className="lg:col-span-5 flex flex-col gap-4 overflow-hidden">
          {/* Editor Container */}
          <div className="flex-1 bg-[#1B2236] rounded-xl border border-[#2D3748] shadow-sm flex flex-col overflow-hidden">
            {/* Editor Header Bar */}
            <div className="h-10 bg-[#141A29] px-4 flex items-center justify-between border-b border-[#2D3748] flex-shrink-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-[#CBD5E1] bg-[#1E293B] px-2.5 py-1 rounded">solution.py · Python 3.12</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleRun}
                  disabled={isRunning}
                  className="flex items-center gap-1.5 px-3 py-1 bg-transparent border border-[#475569] hover:bg-[#2D3748] text-white text-xs font-bold rounded-lg transition-all cursor-pointer"
                >
                  <Play className="w-3 h-3 text-[#2BB3A0]" />
                  <span>Run</span>
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={isRunning}
                  className="flex items-center gap-1.5 px-3.5 py-1 bg-[#2BB3A0] hover:bg-[#249B8A] text-white text-xs font-bold rounded-lg shadow transition-all cursor-pointer"
                >
                  <Send className="w-3 h-3" />
                  <span>Submit</span>
                </button>
              </div>
            </div>

            {/* Code Input Area */}
            <div className="flex-1 p-3 font-mono text-xs overflow-auto">
              <textarea
                value={code}
                onChange={(e) => setCode(e.target.value)}
                className="w-full h-full bg-transparent text-[#E2E8F0] resize-none focus:outline-none font-mono leading-relaxed selection:bg-[#2B5CD0]"
                spellCheck={false}
              />
            </div>
          </div>

          {/* Test Results Card (PDF 3) */}
          <div className="h-44 bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm flex flex-col justify-between flex-shrink-0">
            <div className="flex items-center justify-between text-xs border-b border-[#E2E8F0] pb-2">
              <span className="font-bold text-[#0F1F3A]">Test Results</span>
              <span className="text-[11px] font-mono text-[#64748B]">Runtime 42 ms · Memory 16.1 MB</span>
            </div>

            <div className="flex flex-wrap gap-2 py-2">
              <span className="chip-green"><CheckCircle2 className="w-3 h-3" /> Passed Sample case 1</span>
              <span className="chip-green"><CheckCircle2 className="w-3 h-3" /> Passed Sample case 2</span>
              <span className="chip-green"><CheckCircle2 className="w-3 h-3" /> Passed Edge: no edges</span>
              <span className="chip-green"><CheckCircle2 className="w-3 h-3" /> Passed Large graph (n=2000)</span>
            </div>

            <div className="text-xs font-extrabold text-[#15803D] flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4" />
              <span>18 / 18 hidden tests passed</span>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: AI Code Reviewer + Trainer Notes (3 cols) */}
        <div className="lg:col-span-3 bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-4 flex flex-col justify-between overflow-y-auto space-y-4">
          <div className="space-y-4">
            {/* AI Reviewer Header */}
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
              <div className="flex items-center gap-1.5">
                <Bot className="w-4 h-4 text-[#2B5CD0]" />
                <h3 className="font-bold text-xs text-[#0F1F3A]">AI Code Reviewer</h3>
              </div>
              <span className="chip-purple text-[10px]">Future Skills</span>
            </div>

            {/* Reviewer Note 1 (Good - Blue) */}
            <div className="p-3 rounded-xl bg-[#EFF6FF] border border-[#BFDBFE] text-xs space-y-1">
              <div className="font-bold text-[#1D4ED8] flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5" /> Good Practice
              </div>
              <p className="text-[#1E3A8A] text-[11px] leading-relaxed">
                Path compression flattens the tree during find(), keeping subsequent lookups near constant time.
              </p>
            </div>

            {/* Reviewer Note 2 (Try Next - Amber) */}
            <div className="p-3 rounded-xl bg-[#FEF3C7] border border-[#FDE68A] text-xs space-y-1">
              <div className="font-bold text-[#B45309]">Try next:</div>
              <p className="text-[#92400E] text-[11px] leading-relaxed">
                Add union by rank. Can you explain why it helps achieve the inverse Ackermann worst-case time?
              </p>
            </div>

            {/* Reviewer Note 3 (Interview Tip - Blue) */}
            <div className="p-3 rounded-xl bg-[#EFF6FF] border border-[#BFDBFE] text-xs space-y-1">
              <div className="font-bold text-[#1D4ED8]">Interview tip:</div>
              <p className="text-[#1E3A8A] text-[11px] leading-relaxed font-mono">
                State the complexity aloud: near O(E · α(n)), where α is the inverse Ackermann function.
              </p>
            </div>

            {/* Extra Hint Button */}
            {!showExtraHint ? (
              <button
                onClick={() => {
                  setShowExtraHint(true);
                  setHintCount(hintCount + 1);
                }}
                className="w-full py-2 bg-[#F1F5F9] hover:bg-[#E2E8F0] text-[#2B5CD0] text-xs font-bold rounded-lg border border-[#CBD5E1] transition-all cursor-pointer"
              >
                + Ask for another hint
              </button>
            ) : (
              <div className="p-2.5 rounded-lg bg-[#F8FAFC] border border-[#CBD5E1] text-[11px] text-[#0F1F3A]">
                <strong>Hint 2:</strong> Remember that if an edge connects two already connected nodes, the component count does not decrease.
              </div>
            )}

            {/* Policy note */}
            <div className="text-[10px] text-[#64748B] italic leading-tight">
              Hints only, no full solutions. AI help used in this problem: {hintCount} hint
            </div>

            {/* Trainer Notes Section */}
            <div className="pt-2 border-t border-[#E2E8F0] space-y-1.5">
              <div className="flex items-center gap-1.5 text-xs font-bold text-[#0F1F3A]">
                <MessageSquareQuote className="w-3.5 h-3.5 text-[#2BB3A0]" />
                <span>Trainer note</span>
              </div>
              <blockquote className="text-[11px] text-[#475569] italic bg-[#F8FAFC] p-2.5 rounded-lg border-l-2 border-[#2BB3A0]">
                "Notice how path compression in find() flattens the tree. For best worst-case complexity, add union-by-rank."
                <div className="text-right font-bold text-[10px] text-[#0F1F3A] not-italic mt-1">– Arun K.</div>
              </blockquote>
            </div>
          </div>
        </div>

      </div>
    </AppShell>
  );
}
