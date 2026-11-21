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
    <aside className="bg-white rounded-xl border border-[#E2E8F0] p-3 space-y-2" data-testid="exercise-panel">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-black text-[#0F1F3A]">{t("labs.exercises")}</h2>
        <span className="text-[11px] font-bold text-[#2B5CD0]" data-testid="exercise-score">{score}/{maxScore}</span>
      </div>
      <ol className="space-y-1">
        {exercises.map((e) => (
          <li key={e.id}>
            <button type="button" onClick={() => onSelect(e.id)} aria-pressed={selected === e.id} data-testid="exercise-item"
              className={`w-full text-left px-2 py-1.5 rounded-lg text-xs flex items-center gap-2 ${selected === e.id ? "bg-[#EFF6FF]" : "hover:bg-[#F8FAFC]"}`}>
              {e.passed ? <CheckCircle2 className="w-3.5 h-3.5 text-[#166534]" /> : <Circle className="w-3.5 h-3.5 text-[#94A3B8]" />}
              <span className="flex-1">{e.position}. {e.title}</span><span className="text-[10px] text-[#64748B]">{e.points}</span>
            </button>
          </li>
        ))}
      </ol>
      {current && (
        <div className="border-t border-[#F1F5F9] pt-2 space-y-2">
          <p className="text-xs text-[#334155]" data-testid="exercise-prompt">{current.prompt}</p>
          <button type="button" onClick={onCheck} disabled={busy} data-testid="exercise-check"
            className="w-full px-3 py-1.5 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg disabled:opacity-50">{t("labs.check_answer")}</button>
          {verdict && (
            <p role="status" data-testid="exercise-verdict" className={`text-xs font-bold ${verdict === "pass" ? "text-[#166534]" : "text-[#B45309]"}`}>
              {verdict === "pass" ? t("labs.check_pass") : t("labs.check_fail")}
            </p>
          )}
          <p className="text-[10px] text-[#94A3B8]">{t("labs.check_note")}</p>
        </div>
      )}
    </aside>
  );
}
