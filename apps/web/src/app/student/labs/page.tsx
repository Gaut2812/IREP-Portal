"use client";

import React, { useState } from "react";
import { AppShell } from "@/components/AppShell";
import {
  Terminal, Container, Cloud, Cpu, ShieldAlert,
  Code, Play, StopCircle, ExternalLink, Lock
} from "lucide-react";

export default function VirtualLabsPage() {
  const [selectedFilter, setSelectedFilter] = useState("All labs");
  const [activeSession, setActiveSession] = useState<{
    labName: string;
    fileName: string;
    minutes: number;
  } | null>({
    labName: "AI Notebook Lab",
    fileName: "rag_notes_demo.ipynb",
    minutes: 38
  });
  const [approvalRequested, setApprovalRequested] = useState(false);

  const filters = [
    "All labs",
    "Software Engineering",
    "AI & Data Science",
    "Cybersecurity",
    "Cloud & DevOps"
  ];

  const labs = [
    {
      id: "linux",
      name: "Linux Sandbox",
      category: "Software Engineering",
      icon: Terminal,
      description: "Full Ubuntu terminal for commands, scripting and permissions practice.",
      chips: [
        { label: "Sem 2+", type: "blue" },
        { label: "Ready", type: "green" }
      ],
      footer: "Session: 2 hrs",
      requiresApproval: false
    },
    {
      id: "docker_k8s",
      name: "Docker & Kubernetes Lab",
      category: "Cloud & DevOps",
      icon: Container,
      description: "Build images, run containers and deploy to a practice cluster.",
      chips: [
        { label: "Sem 5+", type: "blue" },
        { label: "Ready", type: "green" }
      ],
      footer: "Last used: yesterday",
      requiresApproval: false
    },
    {
      id: "cloud",
      name: "Cloud Sandbox",
      category: "Cloud & DevOps",
      icon: Cloud,
      description: "Education-tier cloud account to launch VMs, storage and deploy apps.",
      chips: [
        { label: "Sem 5+", type: "blue" },
        { label: "Credits: 68%", type: "amber" }
      ],
      footer: "Auto-stops idle resources",
      requiresApproval: false
    },
    {
      id: "ai_notebook",
      name: "AI Notebook Lab",
      category: "AI & Data Science",
      icon: Cpu,
      description: "Notebooks with high-performance compute for ML, deep learning and RAG.",
      chips: [
        { label: "AI & DS", type: "purple" },
        { label: "Ready", type: "green" }
      ],
      footer: "Queue: none",
      requiresApproval: false
    },
    {
      id: "cyber_range",
      name: "Cyber Range",
      category: "Cybersecurity",
      icon: ShieldAlert,
      description: "Isolated network with vulnerable targets for legal, safe security practice.",
      chips: [
        { label: "Cybersecurity", type: "red" },
        { label: "Track access", type: "amber" }
      ],
      footer: "Trainer approval needed",
      requiresApproval: true
    },
    {
      id: "fullstack",
      name: "Full-Stack Workspace",
      category: "Software Engineering",
      icon: Code,
      description: "Browser IDE with Node, Java, Python and databases pre-configured.",
      chips: [
        { label: "Sem 3+", type: "blue" },
        { label: "Ready", type: "green" }
      ],
      footer: "Linked to your GitHub",
      requiresApproval: false
    }
  ];

  const filteredLabs = selectedFilter === "All labs"
    ? labs
    : labs.filter((l) => l.category === selectedFilter);

  const handleLaunch = (lab: any) => {
    if (lab.requiresApproval) {
      setApprovalRequested(true);
      return;
    }
    setActiveSession({
      labName: lab.name,
      fileName: "workspace_session.ipynb",
      minutes: 1
    });
  };

  return (
    <AppShell pageTitle="Virtual Labs">
      <div className="space-y-6 max-w-7xl mx-auto">
        {/* Filter Chips Bar */}
        <div className="flex flex-wrap gap-2">
          {filters.map((filter) => (
            <button
              key={filter}
              onClick={() => setSelectedFilter(filter)}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                selectedFilter === filter
                  ? "bg-[#2B5CD0] text-white shadow-sm"
                  : "bg-white text-[#64748B] border border-[#E2E8F0] hover:bg-[#F8FAFC]"
              }`}
            >
              {filter}
            </button>
          ))}
        </div>

        {/* 3 by 2 Card Grid matching PDF 5 */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredLabs.map((lab) => {
            const Icon = lab.icon;
            return (
              <div
                key={lab.id}
                className="bg-white rounded-xl border border-[#E2E8F0] p-5 shadow-sm flex flex-col justify-between space-y-4 hover:shadow-md transition-all"
              >
                <div className="space-y-3">
                  {/* Icon & Title */}
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="p-2.5 rounded-xl bg-[#EFF6FF] text-[#2B5CD0]">
                        <Icon className="w-5 h-5" />
                      </div>
                      <h3 className="font-bold text-sm text-[#0F1F3A]">{lab.name}</h3>
                    </div>
                  </div>

                  {/* Description */}
                  <p className="text-xs text-[#64748B] leading-relaxed">
                    {lab.description}
                  </p>

                  {/* Chips */}
                  <div className="flex gap-2">
                    {lab.chips.map((chip) => {
                      let chipClass = "chip-blue";
                      if (chip.type === "green") chipClass = "chip-green";
                      if (chip.type === "amber") chipClass = "chip-amber";
                      if (chip.type === "purple") chipClass = "chip-purple";
                      if (chip.type === "red") chipClass = "chip-red";
                      return (
                        <span key={chip.label} className={chipClass}>
                          {chip.label}
                        </span>
                      );
                    })}
                  </div>
                </div>

                {/* Footer and Launch Button */}
                <div className="flex items-center justify-between border-t border-[#E2E8F0] pt-3">
                  <span className="text-[11px] text-[#64748B] font-medium">{lab.footer}</span>
                  {lab.requiresApproval ? (
                    <button
                      onClick={() => handleLaunch(lab)}
                      className="px-3.5 py-1.5 border border-[#2B5CD0] text-[#2B5CD0] hover:bg-[#EFF6FF] text-xs font-bold rounded-lg transition-all flex items-center gap-1 cursor-pointer"
                    >
                      <Lock className="w-3 h-3" />
                      <span>{approvalRequested ? "Requested" : "Launch"}</span>
                    </button>
                  ) : (
                    <button
                      onClick={() => handleLaunch(lab)}
                      className="px-4 py-1.5 bg-[#2BB3A0] hover:bg-[#249B8A] text-white text-xs font-bold rounded-lg shadow-sm transition-all flex items-center gap-1 cursor-pointer"
                    >
                      <Play className="w-3 h-3" />
                      <span>Launch</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* ACTIVE SESSION CARD (PDF 5) */}
        {activeSession && (
          <div className="bg-white rounded-xl border border-[#2BB3A0] p-4 shadow-sm flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#2BB3A0] opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-[#2BB3A0]"></span>
              </span>
              <div>
                <div className="font-bold text-xs text-[#0F1F3A]">
                  {activeSession.labName} · <code className="font-mono text-[#2B5CD0]">{activeSession.fileName}</code>
                </div>
                <div className="text-[11px] text-[#64748B]">Running for {activeSession.minutes} min · Auto-idle stop in 22 min</div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <a
                href="/live/sess_thu_rag"
                className="flex items-center gap-1 px-3 py-1.5 border border-[#2B5CD0] text-[#2B5CD0] text-xs font-bold rounded-lg hover:bg-[#EFF6FF] transition-all"
              >
                <span>Open in Lab</span>
                <ExternalLink className="w-3 h-3" />
              </a>
              <button
                onClick={() => setActiveSession(null)}
                className="flex items-center gap-1 px-3 py-1.5 bg-[#D93636] hover:bg-[#B91C1C] text-white text-xs font-bold rounded-lg shadow transition-all cursor-pointer"
              >
                <StopCircle className="w-3.5 h-3.5" />
                <span>Stop</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}

