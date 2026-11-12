"use client";

import React, { useState } from "react";
import { AppShell } from "@/components/AppShell";
import {
  CheckCircle2, AlertCircle, Plus, Users, GitPullRequest,
  Check, ArrowRight, ShieldAlert, Sparkles
} from "lucide-react";

interface TaskItem {
  id: string;
  title: string;
  tag: string;
  tagType: "feature" | "ai" | "backend" | "frontend" | "qa" | "devops";
  assignee: string;
  pr?: string;
}

export default function SprintBoardPage() {
  const [standupOpen, setStandupOpen] = useState(false);
  const [standupDone, setStandupDone] = useState(false);

  // 4 columns matching PDF 6
  const [tasks, setTasks] = useState<{
    todo: TaskItem[];
    in_progress: TaskItem[];
    code_review: TaskItem[];
    done: TaskItem[];
  }>({
    todo: [
      { id: "1", title: "SMS reminder for appointments (CR-04)", tag: "Feature", tagType: "feature", assignee: "KS" },
      { id: "2", title: "Doctor availability calendar", tag: "Feature", tagType: "feature", assignee: "MV" },
      { id: "3", title: "Accessibility review", tag: "QA", tagType: "qa", assignee: "AN" }
    ],
    in_progress: [
      { id: "4", title: "AI symptom triage (LLM API)", tag: "AI feature", tagType: "ai", assignee: "PR" },
      { id: "5", title: "Patient history API", tag: "Backend", tagType: "backend", assignee: "RD" },
      { id: "6", title: "Booking UI – mobile layout", tag: "Frontend", tagType: "frontend", assignee: "KS" }
    ],
    code_review: [
      { id: "7", title: "JWT refresh tokens", tag: "Backend", tagType: "backend", assignee: "RD", pr: "#41" },
      { id: "8", title: "Unit tests – booking service", tag: "QA", tagType: "qa", assignee: "PR", pr: "#39" }
    ],
    done: [
      { id: "9", title: "Login & roles", tag: "Feature", tagType: "feature", assignee: "PR" },
      { id: "10", title: "Appointment CRUD", tag: "Backend", tagType: "backend", assignee: "RD" },
      { id: "11", title: "CI/CD pipeline", tag: "DevOps", tagType: "devops", assignee: "MV" },
      { id: "12", title: "Database migrations & schema", tag: "Backend", tagType: "backend", assignee: "AN" }
    ]
  });

  const getTagClass = (type: string) => {
    switch (type) {
      case "ai": return "chip-purple";
      case "backend": return "chip-blue";
      case "frontend": return "chip-amber";
      case "qa": return "chip-red";
      case "devops": return "chip-green";
      default: return "chip-blue";
    }
  };

  const moveTask = (taskId: string, fromCol: keyof typeof tasks, toCol: keyof typeof tasks) => {
    const task = tasks[fromCol].find((t) => t.id === taskId);
    if (!task) return;
    setTasks({
      ...tasks,
      [fromCol]: tasks[fromCol].filter((t) => t.id !== taskId),
      [toCol]: [...tasks[toCol], task]
    });
  };

  return (
    <AppShell pageTitle="Company Simulation · Team Phoenix">
      <div className="space-y-5 max-w-7xl mx-auto">
        
        {/* HEADER STRIP matching PDF 6 */}
        <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <span className="chip-purple font-bold">Sprint 2 of 3</span>
            <span className="text-xs font-bold text-[#0F1F3A]">
              Clinic Appointment System · Client: Trainer (Arun K.) · Ends Week 8
            </span>
            <span className="chip-amber flex items-center gap-1 font-bold">
              <Sparkles className="w-3 h-3" /> Change request: SMS reminders
            </span>
          </div>

          <button
            onClick={() => setStandupOpen(true)}
            className="px-3.5 py-1.5 bg-[#2B5CD0] hover:bg-[#1E46B0] text-white text-xs font-bold rounded-lg shadow-sm transition-all flex items-center gap-1.5 cursor-pointer"
          >
            <Users className="w-3.5 h-3.5" />
            <span>Daily stand-up</span>
          </button>
        </div>

        {/* 4 KANBAN COLUMNS */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          
          {/* Column: To Do */}
          <div className="bg-[#F8FAFC] rounded-xl border border-[#E2E8F0] p-3.5 space-y-3">
            <div className="flex items-center justify-between text-xs font-bold text-[#0F1F3A] border-b border-[#E2E8F0] pb-2">
              <span>To Do</span>
              <span className="w-5 h-5 rounded-full bg-white border border-[#E2E8F0] flex items-center justify-center text-[10px] text-[#64748B]">
                {tasks.todo.length}
              </span>
            </div>
            <div className="space-y-2.5">
              {tasks.todo.map((task) => (
                <div
                  key={task.id}
                  className="bg-white p-3 rounded-xl border border-[#E2E8F0] shadow-sm space-y-2 hover:border-[#2B5CD0] transition-all cursor-pointer group"
                  onClick={() => moveTask(task.id, "todo", "in_progress")}
                >
                  <p className="text-xs font-bold text-[#0F1F3A] leading-tight">{task.title}</p>
                  <div className="flex items-center justify-between pt-1">
                    <span className={getTagClass(task.tagType)}>{task.tag}</span>
                    <span className="w-6 h-6 rounded-full bg-[#14284B] text-white text-[10px] font-bold flex items-center justify-center shadow-xs">
                      {task.assignee}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Column: In Progress */}
          <div className="bg-[#F8FAFC] rounded-xl border border-[#E2E8F0] p-3.5 space-y-3">
            <div className="flex items-center justify-between text-xs font-bold text-[#0F1F3A] border-b border-[#E2E8F0] pb-2">
              <span>In Progress</span>
              <span className="w-5 h-5 rounded-full bg-[#EFF6FF] border border-[#BFDBFE] text-[10px] text-[#1D4ED8] font-bold flex items-center justify-center">
                {tasks.in_progress.length}
              </span>
            </div>
            <div className="space-y-2.5">
              {tasks.in_progress.map((task) => (
                <div
                  key={task.id}
                  className="bg-white p-3 rounded-xl border border-[#E2E8F0] shadow-sm space-y-2 hover:border-[#2B5CD0] transition-all cursor-pointer"
                  onClick={() => moveTask(task.id, "in_progress", "code_review")}
                >
                  <p className="text-xs font-bold text-[#0F1F3A] leading-tight">{task.title}</p>
                  <div className="flex items-center justify-between pt-1">
                    <span className={getTagClass(task.tagType)}>{task.tag}</span>
                    <span className="w-6 h-6 rounded-full bg-[#2BB3A0] text-white text-[10px] font-bold flex items-center justify-center shadow-xs">
                      {task.assignee}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Column: Code Review */}
          <div className="bg-[#F8FAFC] rounded-xl border border-[#E2E8F0] p-3.5 space-y-3">
            <div className="flex items-center justify-between text-xs font-bold text-[#0F1F3A] border-b border-[#E2E8F0] pb-2">
              <span>Code Review</span>
              <span className="w-5 h-5 rounded-full bg-[#FEF3C7] border border-[#FDE68A] text-[10px] text-[#B45309] font-bold flex items-center justify-center">
                {tasks.code_review.length}
              </span>
            </div>
            <div className="space-y-2.5">
              {tasks.code_review.map((task) => (
                <div
                  key={task.id}
                  className="bg-white p-3 rounded-xl border border-[#E2E8F0] shadow-sm space-y-2 hover:border-[#2B5CD0] transition-all cursor-pointer"
                  onClick={() => moveTask(task.id, "code_review", "done")}
                >
                  <p className="text-xs font-bold text-[#0F1F3A] leading-tight">{task.title}</p>
                  <div className="flex items-center justify-between pt-1">
                    <div className="flex items-center gap-1.5">
                      <span className={getTagClass(task.tagType)}>{task.tag}</span>
                      {task.pr && (
                        <span className="text-[10px] text-[#2B5CD0] font-mono flex items-center gap-0.5">
                          <GitPullRequest className="w-3 h-3" /> {task.pr}
                        </span>
                      )}
                    </div>
                    <span className="w-6 h-6 rounded-full bg-[#7C5CE0] text-white text-[10px] font-bold flex items-center justify-center shadow-xs">
                      {task.assignee}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Column: Done */}
          <div className="bg-[#F8FAFC] rounded-xl border border-[#E2E8F0] p-3.5 space-y-3">
            <div className="flex items-center justify-between text-xs font-bold text-[#0F1F3A] border-b border-[#E2E8F0] pb-2">
              <span>Done</span>
              <span className="w-5 h-5 rounded-full bg-[#DCFCE7] border border-[#BBF7D0] text-[10px] text-[#15803D] font-bold flex items-center justify-center">
                {tasks.done.length}
              </span>
            </div>
            <div className="space-y-2.5">
              {tasks.done.map((task) => (
                <div
                  key={task.id}
                  className="bg-white p-3 rounded-xl border border-[#E2E8F0] shadow-sm space-y-2 opacity-90"
                >
                  <p className="text-xs font-bold text-[#0F1F3A] line-through decoration-[#94A3B8] text-[#64748B] leading-tight">
                    {task.title}
                  </p>
                  <div className="flex items-center justify-between pt-1">
                    <span className="chip-green text-[10px]">Completed</span>
                    <span className="w-6 h-6 rounded-full bg-[#64748B] text-white text-[10px] font-bold flex items-center justify-center">
                      {task.assignee}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

        </div>

        {/* BOTTOM METRICS STRIP matching PDF 6 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Metric 1: Sprint Progress */}
          <div className="bg-white p-4 rounded-xl border border-[#E2E8F0] shadow-sm space-y-2">
            <div className="flex items-center justify-between text-xs font-semibold">
              <span className="text-[#0F1F3A]">Sprint progress</span>
              <span className="text-[#2BB3A0] font-bold text-sm">58%</span>
            </div>
            <div className="w-full bg-[#F1F5F9] rounded-full h-2 overflow-hidden">
              <div className="bg-[#2BB3A0] h-full rounded-full" style={{ width: "58%" }} />
            </div>
            <div className="text-[11px] text-[#64748B]">8 of 12 tasks completed</div>
          </div>

          {/* Metric 2: Story Points */}
          <div className="bg-white p-4 rounded-xl border border-[#E2E8F0] shadow-sm space-y-1.5">
            <div className="text-xs font-semibold text-[#0F1F3A]">Story points</div>
            <div className="text-xl font-black text-[#0F1F3A]">21 / 36</div>
            <div className="text-[11px] text-[#64748B]">Velocity last sprint: 30</div>
          </div>

          {/* Metric 3: Build Status */}
          <div className="bg-white p-4 rounded-xl border border-[#E2E8F0] shadow-sm space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-[#0F1F3A]">Build status</span>
              <span className="chip-green font-bold">Passing</span>
            </div>
            <div className="text-xs font-bold text-[#0F1F3A] flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-[#15803D]" />
              <span>Deployed to staging 2 hrs ago</span>
            </div>
            <div className="text-[11px] text-[#64748B]">GitHub Actions workflow #448 passing</div>
          </div>
        </div>

      </div>

      {/* Daily Stand-up Modal */}
      {standupOpen && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl border border-[#E2E8F0]">
            <h3 className="text-base font-bold text-[#0F1F3A]">Team Phoenix · Daily Stand-up</h3>
            <div className="space-y-3 text-xs">
              <div>
                <label className="font-bold text-[#0F1F3A] block mb-1">What did you complete yesterday?</label>
                <input
                  type="text"
                  defaultValue="Completed AI symptom triage LLM API prompt chaining"
                  className="w-full px-3 py-2 border rounded-lg bg-[#F8FAFC]"
                />
              </div>
              <div>
                <label className="font-bold text-[#0F1F3A] block mb-1">What are you working on today?</label>
                <input
                  type="text"
                  defaultValue="Unit tests for booking service and PR review"
                  className="w-full px-3 py-2 border rounded-lg bg-[#F8FAFC]"
                />
              </div>
              <div>
                <label className="font-bold text-[#0F1F3A] block mb-1">Any blockers?</label>
                <input
                  type="text"
                  defaultValue="None. Waiting for Trainer review on PR #39."
                  className="w-full px-3 py-2 border rounded-lg bg-[#F8FAFC]"
                />
              </div>
            </div>
            <div className="flex gap-2 pt-2">
              <button
                onClick={() => setStandupOpen(false)}
                className="flex-1 py-2 bg-[#F1F5F9] text-[#0F1F3A] font-bold text-xs rounded-xl"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setStandupOpen(false);
                  setStandupDone(true);
                }}
                className="flex-1 py-2 bg-[#2B5CD0] text-white font-bold text-xs rounded-xl"
              >
                Share with Team
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
