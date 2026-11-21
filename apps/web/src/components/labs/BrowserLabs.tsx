"use client";

/** Browser labs (labs track): PostgreSQL via PGlite and Python via Pyodide, both running in the
 *  student's browser. Engines load from jsDelivr at pinned versions; nothing reaches IREP servers
 *  except the session's heartbeat beacons. */
import React, { useEffect, useRef, useState } from "react";
import { useLanguage } from "@/lib/LanguageContext";
import { Play } from "lucide-react";

export const PGLITE_URL = "https://cdn.jsdelivr.net/npm/@electric-sql/pglite@0.2.12/dist/index.js";
export const PYODIDE_BASE = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const loadModule = (url: string): Promise<any> => import(/* webpackIgnore: true */ /* turbopackIgnore: true */ url);

type Status = "loading" | "ready" | "error";

function Shell({ status, title, children }: { status: Status; title: string; children: React.ReactNode }) {
  const { t } = useLanguage();
  return (
    <div className="bg-[#1B2236] rounded-xl border border-[#2D3748] overflow-hidden" data-testid="browser-lab">
      <div className="px-4 py-2 border-b border-[#2D3748] text-xs text-[#CBD5E1] flex items-center justify-between">
        <span>{title}</span>
        <span data-testid="engine-status" className={status === "ready" ? "text-[#2BB3A0]" : status === "error" ? "text-[#F87171]" : "text-[#FBBF24]"}>
          {t(`labs.engine_${status}`)}
        </span>
      </div>
      {children}
    </div>
  );
}

export function SqlLab({ onActivity }: { onActivity: () => void }) {
  const { t } = useLanguage();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const db = useRef<any>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [sql, setSql] = useState("CREATE TABLE students (id serial PRIMARY KEY, name text, score int);\nINSERT INTO students (name, score) VALUES ('Asha', 82), ('Ravi', 74);\nSELECT name, score FROM students ORDER BY score DESC;");
  const [out, setOut] = useState<{ fields: string[]; rows: unknown[][] } | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    loadModule(PGLITE_URL)
      .then(async (mod) => {
        const pg = new mod.PGlite();
        await pg.waitReady;
        if (alive) { db.current = pg; setStatus("ready"); }
      })
      .catch(() => alive && setStatus("error"));
    return () => { alive = false; };
  }, []);

  const run = async () => {
    if (!db.current) return;
    setErr("");
    onActivity();
    try {
      const results = await db.current.exec(sql);
      const last = [...results].reverse().find((r: { fields: { name: string }[] }) => r.fields?.length) || results[results.length - 1];
      setOut(last ? { fields: (last.fields || []).map((f: { name: string }) => f.name), rows: (last.rows || []).map((r: Record<string, unknown>) => Object.values(r)) } : null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setOut(null);
    }
  };

  return (
    <Shell status={status} title={t("labs.sql_title")}>
      <textarea value={sql} onChange={(e) => setSql(e.target.value)} rows={7} spellCheck={false} aria-label={t("labs.sql_editor")} data-testid="sql-editor"
        className="w-full bg-transparent font-mono text-xs text-[#E2E8F0] p-4 focus:outline-none resize-y" />
      <div className="border-t border-[#2D3748] p-2 flex">
        <button type="button" onClick={run} disabled={status !== "ready"} data-testid="sql-run"
          className="px-3 py-1.5 bg-[#2BB3A0] text-white text-xs font-bold rounded-lg inline-flex items-center gap-1 disabled:opacity-40"><Play className="w-3.5 h-3.5" />{t("labs.run")}</button>
      </div>
      <div className="bg-white p-3 text-xs overflow-x-auto min-h-[60px]" data-testid="sql-output">
        {err && <pre className="text-red-600 whitespace-pre-wrap" data-testid="sql-error">{err}</pre>}
        {out && (
          <table className="min-w-full">
            <thead><tr>{out.fields.map((f) => <th key={f} className="text-left px-2 py-1 border-b border-[#E2E8F0] font-bold">{f}</th>)}</tr></thead>
            <tbody>{out.rows.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j} className="px-2 py-1 border-b border-[#F1F5F9] font-mono">{String(v)}</td>)}</tr>)}</tbody>
          </table>
        )}
        {status === "error" && <p className="text-red-600">{t("labs.engine_failed")}</p>}
      </div>
    </Shell>
  );
}

export function PythonLab({ onActivity }: { onActivity: () => void }) {
  const { t } = useLanguage();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const py = useRef<any>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [code, setCode] = useState("marks = [82, 74, 91]\nprint('Average:', sum(marks) / len(marks))");
  const [out, setOut] = useState("");

  useEffect(() => {
    let alive = true;
    loadModule(`${PYODIDE_BASE}pyodide.mjs`)
      .then(async (mod) => {
        const inst = await mod.loadPyodide({ indexURL: PYODIDE_BASE });
        if (alive) { py.current = inst; setStatus("ready"); }
      })
      .catch(() => alive && setStatus("error"));
    return () => { alive = false; };
  }, []);

  const run = async () => {
    if (!py.current) return;
    onActivity();
    const lines: string[] = [];
    py.current.setStdout({ batched: (s: string) => lines.push(s) });
    py.current.setStderr({ batched: (s: string) => lines.push(s) });
    try {
      await py.current.loadPackagesFromImports(code);
      await py.current.runPythonAsync(code);
    } catch (e) {
      lines.push(e instanceof Error ? e.message : String(e));
    }
    setOut(lines.join("\n"));
  };

  return (
    <Shell status={status} title={t("labs.python_title")}>
      <textarea value={code} onChange={(e) => setCode(e.target.value)} rows={8} spellCheck={false} aria-label={t("labs.python_editor")} data-testid="py-editor"
        className="w-full bg-transparent font-mono text-xs text-[#E2E8F0] p-4 focus:outline-none resize-y" />
      <div className="border-t border-[#2D3748] p-2 flex">
        <button type="button" onClick={run} disabled={status !== "ready"} data-testid="py-run"
          className="px-3 py-1.5 bg-[#2BB3A0] text-white text-xs font-bold rounded-lg inline-flex items-center gap-1 disabled:opacity-40"><Play className="w-3.5 h-3.5" />{t("labs.run")}</button>
      </div>
      <pre className="bg-[#0F172A] text-[#E2E8F0] p-3 text-xs min-h-[60px] whitespace-pre-wrap" data-testid="py-output">{out || (status === "error" ? t("labs.engine_failed") : "")}</pre>
    </Shell>
  );
}
