"use client";

/** Coding lab terminal: run the editor's code as a program on your own input (stdin), like VS Code's Run, and see
 *  stdout, stderr and compiler output. Any of the four languages; nothing is graded or saved. */
import React, { useState } from "react";
import { Play, RefreshCw, Clock, Cpu } from "lucide-react";
import { ApiError, fetchApi } from "@/lib/api";

interface RunOut {
  status: string; stdout: string; stderr: string; compile_output: string; runtime_ms: number; memory_mb: number;
  message: string | null; driver: boolean;
}

const STATUS_TONE: Record<string, string> = {
  Finished: "text-success-fill", "Compile Error": "text-danger", "Runtime Error": "text-danger",
  "Time Limit Exceeded": "text-warning-fill", Unavailable: "text-warning-fill",
};

export function TerminalPanel({ problemId, code, language, t }: {
  problemId: string; code: string; language: string; t: (k: string) => string;
}) {
  const [stdin, setStdin] = useState("");
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState<RunOut | null>(null);
  const [error, setError] = useState("");

  const run = async () => {
    if (!code.trim()) return;
    setBusy(true);
    setError("");
    try {
      setOut(await fetchApi<RunOut>(`/student/coding/${problemId}/execute`, { method: "POST", body: JSON.stringify({ code, language, stdin }) }));
    } catch (e) {
      setOut(null);
      setError(e instanceof ApiError ? e.detail : t("coding.request_failed"));
    } finally {
      setBusy(false);
    }
  };

  const statusLabel = (s: string) => t(`coding.term_status_${s.toLowerCase().replace(/\s+/g, "_")}`);

  return (
    <div className="h-full grid grid-cols-1 md:grid-cols-5 gap-0 bg-[#0B0F19] text-xs" data-testid="terminal-output">
      <div className="md:col-span-2 flex flex-col border-b md:border-b-0 md:border-r border-[#1E293B] p-2 gap-2 min-h-0">
        <label htmlFor="term-stdin" className="text-caption font-semibold text-subtle">{t("coding.term_input")}</label>
        <textarea id="term-stdin" value={stdin} onChange={(e) => setStdin(e.target.value)} spellCheck={false} data-testid="terminal-stdin"
          placeholder={t("coding.term_input_hint")}
          className="flex-1 min-h-[56px] resize-none bg-[#0F172A] border border-[#1E293B] rounded-tile p-2 font-mono text-caption text-line placeholder-muted focus:outline-none focus:border-brand" />
        <button type="button" onClick={run} disabled={busy || !code.trim()} data-testid="terminal-run"
          className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 bg-teal hover:bg-teal-hover text-white text-caption font-semibold rounded-tile disabled:opacity-50">
          {busy ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
          {busy ? t("coding.running_code") : t("coding.term_run")}
        </button>
      </div>
      <div className="md:col-span-3 p-2 overflow-y-auto font-mono text-caption min-h-0" aria-live="polite">
        {!out && !error && <p className="text-ink-soft italic">{t("coding.term_empty")}</p>}
        {error && <p className="text-danger" role="alert">{error}</p>}
        {out && (
          <div className="space-y-2" data-testid="terminal-result">
            <div className="flex flex-wrap items-center gap-3">
              <span className={`font-semibold ${STATUS_TONE[out.status] || "text-line"}`} data-testid="terminal-status">{statusLabel(out.status)}</span>
              {out.status !== "Unavailable" && <>
                <span className="text-subtle inline-flex items-center gap-1"><Clock className="w-3 h-3" />{out.runtime_ms} ms</span>
                <span className="text-subtle inline-flex items-center gap-1"><Cpu className="w-3 h-3" />{out.memory_mb} MB</span>
              </>}
            </div>
            {out.status === "Unavailable" && <p className="text-warning-fill" data-testid="terminal-unavailable">{t("coding.term_unavailable")}</p>}
            {out.message && out.status !== "Unavailable" && <p className="text-subtle">{out.message}</p>}
            {out.driver && <p className="text-subtle">{t("coding.term_driver_note")}</p>}
            {out.compile_output && <Block label={t("coding.term_compile")} text={out.compile_output} tone="text-danger" />}
            {out.stdout && <Block label={t("coding.term_stdout")} text={out.stdout} tone="text-success-fill" testId="terminal-stdout" />}
            {out.stderr && <Block label={t("coding.term_stderr")} text={out.stderr} tone="text-danger" />}
            {out.status === "Finished" && !out.stdout && !out.stderr && <p className="text-ink-soft italic">{t("coding.term_no_output")}</p>}
          </div>
        )}
      </div>
    </div>
  );
}

function Block({ label, text, tone, testId }: { label: string; text: string; tone: string; testId?: string }) {
  return (
    <div>
      <div className="text-subtle mb-0.5">{label}</div>
      <pre className={`whitespace-pre-wrap break-words leading-relaxed ${tone}`} data-testid={testId}>{text}</pre>
    </div>
  );
}
