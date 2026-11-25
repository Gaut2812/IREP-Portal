"use client";

/** Lab workspace (screen 29 and the labs track). Browser labs run here and send signed beacons;
 *  server labs (JupyterHub) and external sandboxes open in a new tab through a short-lived link. */
import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { API_BASE, ApiError, fetchApi } from "@/lib/api";
import { PythonLab, SqlLab } from "@/components/labs/BrowserLabs";
import { Exercise, ExercisePanel } from "@/components/labs/ExercisePanel";
import { ArrowLeft, StopCircle, AlertCircle, Terminal, Info, ExternalLink, Loader2 } from "lucide-react";

interface LabSession {
  id: string; lab_id: string; lab_name: string; status: string; workspace_file: string | null; running_minutes: number;
  expires_at: string; minutes_left: number; idle_limit_min: number; provider: string; stop_reason: string | null;
  runtime: "server" | "browser" | "external"; browser_kit: "sql" | "python" | null; beacon_token: string | null; can_connect: boolean;
}

function fill(template: string, vars: Record<string, string | number>) {
  return Object.entries(vars).reduce((acc, [k, v]) => acc.replace(`{${k}}`, String(v)), template);
}

export default function LabWorkspacePage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { t, language } = useLanguage();
  const [s, setS] = useState<LabSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lines, setLines] = useState<string[]>([]);
  const [cmd, setCmd] = useState("");
  const [opening, setOpening] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const lastBeacon = useRef(0);
  // S13 exercises (browser labs): the latest result is what "Check my answer" sends
  const [exercises, setExercises] = useState<{ exercises: Exercise[]; score: number; max_score: number } | null>(null);
  const [selectedEx, setSelectedEx] = useState<string | null>(null);
  const [verdict, setVerdict] = useState<"pass" | "fail" | null>(null);
  const [checking, setChecking] = useState(false);
  const [exercisesLoaded, setExercisesLoaded] = useState(false);   // mount the SQL engine once, with its setup
  const lastRows = useRef<string[][] | null>(null);
  const lastOutput = useRef<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetchApi<LabSession>(`/student/lab-sessions/${sessionId}`);
      setS(res);
      setLines((prev) => prev.length ? prev : [`irep@${res.lab_id.replace("lab_", "")}:~$ # ${res.lab_name} ready`, `irep@${res.lab_id.replace("lab_", "")}:~$ ls`, res.workspace_file || ""]);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "error");
    }
  }, [sessionId]);

  useEffect(() => { load(); }, [load]);

  const loadExercises = useCallback(async (labId: string) => {
    try {
      const r = await fetchApi<{ exercises: Exercise[]; score: number; max_score: number }>(`/student/labs/${labId}/exercises?lang=${language}`);
      setExercises(r);
      setSelectedEx((cur) => cur ?? r.exercises.find((e) => !e.passed)?.id ?? r.exercises[0]?.id ?? null);
    } catch { setExercises(null); }
    setExercisesLoaded(true);
  }, [language]);
  useEffect(() => { if (s?.runtime === "browser") loadExercises(s.lab_id); }, [s?.runtime, s?.lab_id, loadExercises]);

  const checkAnswer = async () => {
    if (!selectedEx || !s) return;
    setChecking(true);
    setVerdict(null);
    try {
      const body = s.browser_kit === "sql" ? { rows: lastRows.current ?? [] } : { output: lastOutput.current ?? "" };
      const r = await fetchApi<{ passed: boolean }>(`/student/lab-exercises/${selectedEx}/check`, { method: "POST", body: JSON.stringify(body) });
      setVerdict(r.passed ? "pass" : "fail");
      await loadExercises(s.lab_id);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "error");
    } finally {
      setChecking(false);
    }
  };
  const sqlSetup = exercises ? Array.from(new Set(exercises.exercises.map((e) => e.setup).filter(Boolean))).join(";\n") || null : null;
  const starter = exercises?.exercises.find((e) => e.id === selectedEx)?.setup ?? null;

  // a server that is still starting: poll until the outbox has started it
  useEffect(() => {
    if (s?.status !== "starting") return;
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, [s?.status, load]);

  // browser labs: signed beacons (also on tab close); other labs: the authenticated heartbeat
  const beacon = useCallback(() => {
    if (!s || s.status !== "running") return;
    lastBeacon.current = Date.now();
    if (s.beacon_token) {
      fetch(`${API_BASE}/labs/beacon`, { method: "POST", headers: { "Content-Type": "text/plain" }, body: JSON.stringify({ token: s.beacon_token }), keepalive: true })
        .then((r) => r.json()).then((r) => { if (r.status !== "running") load(); }).catch(() => undefined);
    } else {
      fetchApi(`/student/lab-sessions/${sessionId}/heartbeat`, { method: "POST" }).catch(() => load());
    }
  }, [s, sessionId, load]);

  useEffect(() => {
    if (!s || s.status !== "running") return;
    const id = setInterval(beacon, 60000);
    const onHide = () => {
      if (s.beacon_token && navigator.sendBeacon) navigator.sendBeacon(`${API_BASE}/labs/beacon`, JSON.stringify({ token: s.beacon_token }));
    };
    window.addEventListener("pagehide", onHide);
    return () => { clearInterval(id); window.removeEventListener("pagehide", onHide); };
  }, [s, beacon]);

  const activity = useCallback(() => { if (Date.now() - lastBeacon.current > 20000) beacon(); }, [beacon]);

  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [lines]);

  const run = (e: React.FormEvent) => {
    e.preventDefault();
    if (!cmd.trim() || !s) return;
    const prompt = `irep@${s.lab_id.replace("lab_", "")}:~$ ${cmd}`;
    const out = cmd.trim() === "pwd" ? "/home/irep" : cmd.trim() === "whoami" ? "irep" : cmd.trim().startsWith("echo ") ? cmd.trim().slice(5) : cmd.trim() === "clear" ? null : `${cmd.trim().split(" ")[0]}: ${t("labs.fake_terminal")}`;
    setLines((prev) => (out === null ? [] : [...prev, prompt, out]));
    setCmd("");
    activity();
  };

  const open = async () => {
    setOpening(true);
    setError(null);
    try {
      const r = await fetchApi<{ url: string }>(`/student/lab-sessions/${sessionId}/connect`);
      window.open(r.url, "_blank", "noopener,noreferrer");
    } catch (err) {
      const d = err instanceof ApiError ? err.detail : null;
      setError(typeof d === "object" && d && "message" in (d as object) ? String((d as { message: string }).message) : t("labs.open_failed"));
    } finally {
      setOpening(false);
    }
  };

  const stop = async () => {
    try {
      await fetchApi(`/student/lab-sessions/${sessionId}/stop`, { method: "POST" });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "error");
    }
  };

  const live = s && (s.status === "running" || s.status === "starting");

  return (
    <RoleGuard allowedRoles={["student"]}>
      <AppShell pageTitle={s ? `${t("labs.workspace_title")} · ${s.lab_name}` : t("labs.workspace_title")}>
        <div className="max-w-5xl mx-auto space-y-6" data-testid="lab-workspace">
          <Link href="/student/labs" className="inline-flex items-center gap-1 text-xs font-semibold text-brand hover:underline"><ArrowLeft className="w-3.5 h-3.5" /> {t("labs.workspace_back")}</Link>
          {error && <div className="bg-white rounded-card border border-danger-line p-4 text-xs text-danger flex items-center gap-2" role="alert"><AlertCircle className="w-4 h-4" />{error}</div>}
          {!s && !error && <div className="h-80 bg-white rounded-card border border-line animate-pulse" aria-busy="true" />}
          {s && (
            <>
              <div className="bg-white rounded-card border border-line p-4 flex flex-wrap items-center justify-between gap-3">
                <div className="text-xs space-y-1">
                  <div><span className="text-muted">{t("labs.workspace_status")}:</span> <span className={live ? "chip-green" : "chip-red"} data-testid="workspace-status">{s.status}</span></div>
                  {s.workspace_file && <div><span className="text-muted">{t("labs.workspace_file")}:</span> <code className="font-mono text-brand">{s.workspace_file}</code></div>}
                  {s.status === "running" && <div className="text-muted">{fill(t("labs.workspace_expires"), { t: new Date(s.expires_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) })} · {fill(t("labs.minutes_left"), { n: s.minutes_left, i: s.idle_limit_min })}</div>}
                </div>
                <div className="flex gap-2">
                  {s.can_connect && (
                    <button onClick={open} disabled={opening} className="flex items-center gap-1 px-3 py-1.5 bg-brand text-white text-xs font-semibold rounded-tile disabled:opacity-50" data-testid="workspace-open">
                      <ExternalLink className="w-3.5 h-3.5" /> {s.runtime === "external" ? t("labs.open_sandbox") : t("labs.open_workspace")}
                    </button>
                  )}
                  {live && (
                    <button onClick={stop} className="flex items-center gap-1 px-3 py-1.5 bg-danger hover:bg-danger text-white text-xs font-semibold rounded-tile" data-testid="workspace-stop"><StopCircle className="w-3.5 h-3.5" /> {t("labs.stop")}</button>
                  )}
                </div>
              </div>

              {s.status === "starting" && (
                <div className="bg-white rounded-card border border-line p-6 text-center text-xs text-ink-soft flex items-center justify-center gap-2" data-testid="workspace-starting">
                  <Loader2 className="w-4 h-4 animate-spin" />{t("labs.starting")}
                </div>
              )}

              {s.status === "running" && s.runtime === "browser" && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                  <div className="lg:col-span-2">
                    {s.browser_kit === "sql" && exercisesLoaded && (
                      <SqlLab onActivity={activity} setup={sqlSetup} onResult={(rows) => { lastRows.current = rows; setVerdict(null); }} />
                    )}
                    {s.browser_kit === "python" && <PythonLab onActivity={activity} starter={starter} onOutput={(o) => { lastOutput.current = o; setVerdict(null); }} />}
                  </div>
                  {exercises && exercises.exercises.length > 0 && (
                    <ExercisePanel exercises={exercises.exercises} score={exercises.score} maxScore={exercises.max_score} selected={selectedEx}
                      onSelect={(id) => { setSelectedEx(id); setVerdict(null); }} onCheck={checkAnswer} busy={checking} verdict={verdict} />
                  )}
                </div>
              )}

              {s.status === "running" && s.runtime !== "browser" && s.provider === "fake" && (
                <div className="bg-[#1B2236] rounded-card border border-[#2D3748] overflow-hidden">
                  <div className="px-4 py-2 border-b border-[#2D3748] text-xs text-line-strong flex items-center gap-2"><Terminal className="w-3.5 h-3.5 text-teal" /> {t("labs.workspace_terminal")}</div>
                  <div className="p-4 font-mono text-xs text-line h-72 overflow-y-auto space-y-0.5" data-testid="terminal">
                    {lines.map((l, i) => <div key={i} className={l.startsWith("irep@") ? "text-teal" : ""}>{l}</div>)}
                    <div ref={endRef} />
                  </div>
                  <form onSubmit={run} className="border-t border-[#2D3748] flex">
                    <span className="px-3 py-2 font-mono text-xs text-teal">$</span>
                    <input value={cmd} onChange={(e) => setCmd(e.target.value)} aria-label={t("labs.workspace_terminal")} className="flex-1 bg-transparent font-mono text-xs text-white py-2 focus:outline-none" data-testid="terminal-input" />
                  </form>
                </div>
              )}
              {s.status === "running" && s.runtime !== "browser" && s.provider !== "fake" && (
                <div className="bg-white rounded-card border border-line p-6 text-center text-xs text-ink-soft" data-testid="workspace-remote">
                  {s.runtime === "external" ? t("labs.external_hint") : t("labs.server_hint")}
                </div>
              )}

              {!live && <div className="bg-white rounded-card border border-line p-6 text-center text-xs text-muted">{t("labs.workspace_ended")}</div>}
              {s.provider === "fake" && s.runtime === "server" && <p className="text-caption text-muted flex items-start gap-1.5"><Info className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />{t("labs.workspace_hint")}</p>}
              {s.runtime === "browser" && <p className="text-caption text-muted flex items-start gap-1.5"><Info className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />{t("labs.browser_hint")}</p>}
            </>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
