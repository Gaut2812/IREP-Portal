"use client";

/** Lab exercises (labs track S13): pick one, solve it in the lab, then "Check my answer". The page
 *  sends the latest result; the expected answer stays on the server. Practice checks, not marks. */
import React from "react";
import { useLanguage } from "@/lib/LanguageContext";
import { CheckCircle2, Circle } from "lucide-react";

export interface Exercise { id: string; position: number; title: string; prompt: string; setup: string | null; points: number; passed: boolean; attempts: number }

export function ExercisePanel({ exercises, score, maxScore, selected, onSelect, onCheck, busy, verdict }: {
  exercises: Exercise[]; score: number; maxScore: number; selected: string | null; onSelect: (id: string) => void;
  onCheck: () => void; busy: boolean; verdict: "pass" | "fail" | null;
}) {
  const { t } = useLanguage();
  const current = exercises.find((e) => e.id === selected);
  return (
    <aside className="bg-white rounded-card border border-line p-3 space-y-2" data-testid="exercise-panel">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-semibold text-ink">{t("labs.exercises")}</h2>
        <span className="text-caption font-semibold text-brand" data-testid="exercise-score">{score}/{maxScore}</span>
      </div>
      <ol className="space-y-1">
        {exercises.map((e) => (
          <li key={e.id}>
            <button type="button" onClick={() => onSelect(e.id)} aria-pressed={selected === e.id} data-testid="exercise-item"
              className={`w-full text-left px-2 py-1.5 rounded-tile text-xs flex items-center gap-2 ${selected === e.id ? "bg-brand-soft" : "hover:bg-surface-2"}`}>
              {e.passed ? <CheckCircle2 className="w-3.5 h-3.5 text-success" /> : <Circle className="w-3.5 h-3.5 text-subtle" />}
              <span className="flex-1">{e.position}. {e.title}</span><span className="text-caption text-muted">{e.points}</span>
            </button>
          </li>
        ))}
      </ol>
      {current && (
        <div className="border-t border-line-soft pt-2 space-y-2">
          <p className="text-xs text-ink-soft" data-testid="exercise-prompt">{current.prompt}</p>
          <button type="button" onClick={onCheck} disabled={busy} data-testid="exercise-check"
            className="w-full px-3 py-1.5 bg-brand text-white text-xs font-semibold rounded-tile disabled:opacity-50">{t("labs.check_answer")}</button>
          {verdict && (
            <p role="status" data-testid="exercise-verdict" className={`text-xs font-semibold ${verdict === "pass" ? "text-success" : "text-warning"}`}>
              {verdict === "pass" ? t("labs.check_pass") : t("labs.check_fail")}
            </p>
          )}
          <p className="text-caption text-subtle">{t("labs.check_note")}</p>
        </div>
      )}
    </aside>
  );
}
