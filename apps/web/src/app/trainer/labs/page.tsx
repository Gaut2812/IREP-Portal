"use client";

/** Trainer lab board (labs track): live lab sessions in my batches; stop one with a note to the student. */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { StopCircle } from "lucide-react";

interface Row { id: string; student: string; batch: string | null; lab: string; runtime: string | null; status: string; running_minutes: number; idle_minutes: number; idle_warning: boolean; minutes_left: number }

export default function TrainerLabBoard() {
  const { t } = useLanguage();
  const [data, setData] = useState<{ sessions: Row[]; summary: { live: number; idle: number } } | null>(null);
  const [reason, setReason] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [progress, setProgress] = useState<{ students: number; exercises: { id: string; lab: string; title: string; passed: number; tried: number }[] } | null>(null);

  const load = useCallback(async () => {
    try { setData(await fetchApi("/trainer/labs")); } catch (e) { setError(e instanceof ApiError ? String(e.detail) : t("lab_board.load_failed")); }
  }, [t]);

  useEffect(() => {
    fetchApi<{ students: number; exercises: { id: string; lab: string; title: string; passed: number; tried: number }[] }>("/trainer/labs/exercises")
      .then(setProgress).catch(() => setProgress(null));
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [load]);

  const stop = async (r: Row) => {
    setError("");
    try {
      await fetchApi(`/trainer/lab-sessions/${r.id}/stop`, { method: "POST", body: JSON.stringify({ reason: reason || null }) });
      setMsg(`${t("lab_board.stopped")} ${r.student}`);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : t("lab_board.load_failed"));
    }
  };

  return (
    <RoleGuard allowedRoles={["trainer"]}>
      <AppShell pageTitle={t("lab_board.title")}>
        <div className="space-y-6 max-w-5xl">
          {data && (
            <p className="text-xs text-ink-soft" data-testid="lab-board-summary">{data.summary.live} {t("lab_board.live")} · {data.summary.idle} {t("lab_board.idle")}</p>
          )}
          <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t("lab_board.reason_ph")} aria-label={t("lab_board.reason_ph")}
            className="w-full max-w-md px-2.5 py-1.5 bg-surface-2 border border-line rounded-tile text-xs" data-testid="lab-board-reason" />
          {msg && <p className="text-xs text-success font-semibold" role="status" data-testid="lab-board-msg">{msg}</p>}
          {error && <p className="text-xs text-red-600" role="alert">{error}</p>}
          <div className="bg-white rounded-card border border-line overflow-x-auto">
            <table className="w-full text-xs" data-testid="lab-board">
              <thead><tr className="text-left text-muted border-b border-line">
                <th className="px-3 py-2">{t("lab_board.student")}</th><th>{t("lab_board.lab")}</th><th>{t("lab_board.running")}</th><th>{t("lab_board.idle_col")}</th><th>{t("lab_board.left")}</th><th />
              </tr></thead>
              <tbody>
                {data?.sessions.length === 0 && <tr><td colSpan={6} className="px-3 py-6 text-center text-muted">{t("lab_board.none")}</td></tr>}
                {data?.sessions.map((r) => (
                  <tr key={r.id} className="border-b border-line-soft" data-testid="lab-board-row">
                    <td className="px-3 py-2"><div className="font-semibold">{r.student}</div><div className="text-caption text-muted">{r.batch}</div></td>
                    <td>{r.lab}{r.status === "starting" ? ` · ${t("lab_board.starting")}` : ""}</td>
                    <td>{r.running_minutes} {t("lab_board.min")}</td>
                    <td className={r.idle_warning ? "text-warning font-semibold" : ""}>{r.idle_minutes} {t("lab_board.min")}</td>
                    <td>{r.minutes_left} {t("lab_board.min")}</td>
                    <td className="pr-3 text-right">
                      <button type="button" onClick={() => stop(r)} data-testid="lab-board-stop" className="px-2.5 py-1 bg-danger text-white text-caption font-semibold rounded-tile inline-flex items-center gap-1">
                        <StopCircle className="w-3.5 h-3.5" />{t("lab_board.stop")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {progress && progress.exercises.length > 0 && (
            <div className="bg-white rounded-card border border-line overflow-x-auto">
              <h2 className="px-3 pt-3 text-xs font-semibold text-ink">{t("lab_board.exercises")} · {progress.students} {t("lab_board.students")}</h2>
              <table className="w-full text-xs mt-2" data-testid="exercise-progress">
                <thead><tr className="text-left text-muted border-b border-line"><th className="px-3 py-1.5">{t("lab_board.lab")}</th><th>{t("lab_board.exercise")}</th><th>{t("lab_board.passed")}</th><th>{t("lab_board.tried")}</th></tr></thead>
                <tbody>
                  {progress.exercises.map((e) => (
                    <tr key={e.id} className="border-b border-line-soft"><td className="px-3 py-1.5">{e.lab}</td><td>{e.title}</td><td className="font-semibold text-success">{e.passed}</td><td>{e.tried}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
