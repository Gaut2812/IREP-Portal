"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { fetchApi } from "@/lib/api";
import { ArrowLeft, StopCircle, AlertCircle, Terminal, Info } from "lucide-react";

interface LabSession {
  id: string; lab_id: string; lab_name: string; status: string; workspace_file: string | null; running_minutes: number;
  expires_at: string; minutes_left: number; idle_limit_min: number; provider: string; stop_reason: string | null;
}

function fill(template: string, vars: Record<string, string | number>) {
  return Object.entries(vars).reduce((acc, [k, v]) => acc.replace(`{${k}}`, String(v)), template);
}

export default function LabWorkspacePage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { t } = useLanguage();
  const [s, setS] = useState<LabSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lines, setLines] = useState<string[]>([]);
  const [cmd, setCmd] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetchApi<LabSession>(`/student/lab-sessions/${sessionId}`);
      setS(res);
      setLines((prev) => prev.length ? prev : [`irep@${res.lab_id.replace("lab_", "")}:~$ # ${res.lab_name} ready`, `irep@${res.lab_id.replace("lab_", "")}:~$ ls`, res.workspace_file || ""]);
    } catch (err: any) {
      setError(err?.detail || err?.message || "error");
    }
  }, [sessionId]);

  useEffect(() => { load(); }, [load]);
  // heartbeat keeps the idle culler away while the tab is open
  useEffect(() => {
    if (!s || s.status !== "running") return;
    const id = setInterval(() => { fetchApi(`/student/lab-sessions/${sessionId}/heartbeat`, { method: "POST" }).catch(() => load()); }, 60000);
    return () => clearInterval(id);
  }, [s, sessionId, load]);
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [lines]);

  const run = (e: React.FormEvent) => {
    e.preventDefault();
    if (!cmd.trim() || !s) return;
    const prompt = `irep@${s.lab_id.replace("lab_", "")}:~$ ${cmd}`;
    const out = cmd.trim() === "pwd" ? "/home/irep" : cmd.trim() === "whoami" ? "irep" : cmd.trim().startsWith("echo ") ? cmd.trim().slice(5) : cmd.trim() === "clear" ? null : `${cmd.trim().split(" ")[0]}: available when LAB_ADAPTER=docker`;
    setLines((prev) => (out === null ? [] : [...prev, prompt, out]));
    setCmd("");
    fetchApi(`/student/lab-sessions/${sessionId}/heartbeat`, { method: "POST" }).catch(() => undefined);
  };

  const stop = async () => {
    try {
      await fetchApi(`/student/lab-sessions/${sessionId}/stop`, { method: "POST" });
      await load();
    } catch (err: any) {
      setError(err?.detail || "error");
    }
  };

  return (
    <RoleGuard allowedRoles={["student"]}>
      <AppShell pageTitle={s ? `${t("labs.workspace_title")} · ${s.lab_name}` : t("labs.workspace_title")}>
        <div className="max-w-5xl mx-auto space-y-4" data-testid="lab-workspace">
          <Link href="/student/labs" className="inline-flex items-center gap-1 text-xs font-semibold text-[#2B5CD0] hover:underline"><ArrowLeft className="w-3.5 h-3.5" /> {t("labs.workspace_back")}</Link>
          {error && <div className="bg-white rounded-xl border border-[#FECACA] p-4 text-xs text-[#D93636] flex items-center gap-2"><AlertCircle className="w-4 h-4" />{error}</div>}
          {!s && !error && <div className="h-80 bg-white rounded-xl border border-[#E2E8F0] animate-pulse" aria-busy="true" />}
          {s && (
            <>
              <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 flex flex-wrap items-center justify-between gap-3">
                <div className="text-xs space-y-1">
                  <div><span className="text-[#64748B]">{t("labs.workspace_status")}:</span> <span className={s.status === "running" ? "chip-green" : "chip-red"} data-testid="workspace-status">{s.status}</span></div>
                  {s.workspace_file && <div><span className="text-[#64748B]">{t("labs.workspace_file")}:</span> <code className="font-mono text-[#2B5CD0]">{s.workspace_file}</code></div>}
                  {s.status === "running" && <div className="text-[#64748B]">{fill(t("labs.workspace_expires"), { t: new Date(s.expires_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) })} · {fill(t("labs.minutes_left"), { n: s.minutes_left, i: s.idle_limit_min })}</div>}
                </div>
                {s.status === "running" && (
                  <button onClick={stop} className="flex items-center gap-1 px-3 py-1.5 bg-[#D93636] hover:bg-[#B91C1C] text-white text-xs font-bold rounded-lg" data-testid="workspace-stop"><StopCircle className="w-3.5 h-3.5" /> {t("labs.stop")}</button>
                )}
              </div>
              {s.status === "running" ? (
                <div className="bg-[#1B2236] rounded-xl border border-[#2D3748] overflow-hidden">
                  <div className="px-4 py-2 border-b border-[#2D3748] text-xs text-[#CBD5E1] flex items-center gap-2"><Terminal className="w-3.5 h-3.5 text-[#2BB3A0]" /> {t("labs.workspace_terminal")}</div>
                  <div className="p-4 font-mono text-xs text-[#E2E8F0] h-72 overflow-y-auto space-y-0.5" data-testid="terminal">
                    {lines.map((l, i) => <div key={i} className={l.startsWith("irep@") ? "text-[#2BB3A0]" : ""}>{l}</div>)}
                    <div ref={endRef} />
                  </div>
                  <form onSubmit={run} className="border-t border-[#2D3748] flex">
                    <span className="px-3 py-2 font-mono text-xs text-[#2BB3A0]">$</span>
                    <input value={cmd} onChange={(e) => setCmd(e.target.value)} aria-label={t("labs.workspace_terminal")} className="flex-1 bg-transparent font-mono text-xs text-white py-2 focus:outline-none" data-testid="terminal-input" />
                  </form>
                </div>
              ) : (
                <div className="bg-white rounded-xl border border-[#E2E8F0] p-6 text-center text-xs text-[#64748B]">{t("labs.workspace_ended")}</div>
              )}
              {s.provider === "fake" && <p className="text-[11px] text-[#64748B] flex items-start gap-1.5"><Info className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />{t("labs.workspace_hint")}</p>}
            </>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
