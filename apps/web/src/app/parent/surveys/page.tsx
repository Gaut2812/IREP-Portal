"use client";

/** Screen 40 · Feedback survey (parent): answer the college's surveys once each (L26). */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { Star } from "lucide-react";

interface Q { id: string; kind: "rating" | "choice" | "text"; text: string; options: string[]; required: boolean }
interface S { id: string; title: string; closes_on: string | null; answered: boolean; open: boolean; questions: Q[] }

export default function ParentSurveysPage() {
  const { t, language } = useLanguage();
  const [surveys, setSurveys] = useState<S[] | null>(null);
  const [answers, setAnswers] = useState<Record<string, Record<string, string | number>>>({});
  const [error, setError] = useState("");
  const [done, setDone] = useState("");

  const load = useCallback(async () => {
    try { setSurveys((await fetchApi<{ surveys: S[] }>(`/parent/surveys?lang=${language}`)).surveys); }
    catch (e) { setError(e instanceof ApiError ? String(e.detail) : t("psurvey.load_failed")); }
  }, [language, t]);
  useEffect(() => { load(); }, [load]);

  const set = (sid: string, qid: string, v: string | number) => setAnswers({ ...answers, [sid]: { ...(answers[sid] || {}), [qid]: v } });
  const submit = async (s: S) => {
    setError("");
    try {
      await fetchApi(`/parent/surveys/${s.id}/responses`, { method: "POST", body: JSON.stringify({ answers: answers[s.id] || {} }) });
      setDone(s.id);
      await load();
    } catch (e) { setError(e instanceof ApiError ? String(e.detail) : t("psurvey.save_failed")); }
  };

  return (
    <RoleGuard allowedRoles={["parent"]}>
      <AppShell pageTitle={t("psurvey.title")}>
        <div className="max-w-2xl mx-auto space-y-3">
          {error && <p className="text-xs text-red-600" role="alert" data-testid="psurvey-error">{error}</p>}
          {surveys?.length === 0 && <p className="text-xs text-[#64748B] bg-white rounded-2xl border border-dashed border-[#CBD5E1] p-6 text-center">{t("psurvey.none")}</p>}
          {surveys?.map((s) => (
            <section key={s.id} className="bg-white rounded-2xl border border-[#E2E8F0] p-4 space-y-3" data-testid="psurvey">
              <h2 className="text-sm font-black text-[#0F1F3A]">{s.title}</h2>
              {s.answered ? (
                <p className="text-xs text-[#166534] font-bold" data-testid="psurvey-thanks">{done === s.id ? t("psurvey.thanks") : t("psurvey.already")}</p>
              ) : !s.open ? <p className="text-xs text-[#64748B]">{t("psurvey.closed")}</p> : (
                <>
                  {s.questions.map((q) => (
                    <div key={q.id} className="space-y-1.5">
                      <p className="text-xs font-semibold text-[#334155]">{q.text}{q.required ? " *" : ""}</p>
                      {q.kind === "rating" && (
                        <div className="flex gap-1" role="radiogroup" aria-label={q.text}>
                          {[1, 2, 3, 4, 5].map((n) => (
                            <button key={n} type="button" role="radio" aria-checked={answers[s.id]?.[q.id] === n} aria-label={`${n}`} onClick={() => set(s.id, q.id, n)} data-testid={`rate-${n}`}>
                              <Star className={`w-6 h-6 ${Number(answers[s.id]?.[q.id] || 0) >= n ? "fill-[#F59E0B] text-[#F59E0B]" : "text-[#CBD5E1]"}`} />
                            </button>
                          ))}
                        </div>
                      )}
                      {q.kind === "choice" && (
                        <div className="flex flex-wrap gap-2">
                          {q.options.map((o) => (
                            <button key={o} type="button" aria-pressed={answers[s.id]?.[q.id] === o} onClick={() => set(s.id, q.id, o)} data-testid="choice"
                              className={`px-3 py-1.5 rounded-lg text-xs border ${answers[s.id]?.[q.id] === o ? "bg-[#2B5CD0] text-white border-[#2B5CD0]" : "border-[#CBD5E1]"}`}>{o}</button>
                          ))}
                        </div>
                      )}
                      {q.kind === "text" && (
                        <textarea rows={2} className="w-full px-2.5 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg text-xs" aria-label={q.text}
                          value={String(answers[s.id]?.[q.id] || "")} onChange={(e) => set(s.id, q.id, e.target.value)} data-testid="comment" />
                      )}
                    </div>
                  ))}
                  <button type="button" onClick={() => submit(s)} className="w-full py-2 bg-[#2BB3A0] text-white text-xs font-bold rounded-lg" data-testid="psurvey-submit">{t("psurvey.submit")}</button>
                  <p className="text-[10px] text-[#94A3B8]">{t("psurvey.privacy")}</p>
                </>
              )}
            </section>
          ))}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
