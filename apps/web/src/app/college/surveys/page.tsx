"use client";

/** Screen 02 (college settings) · Parent surveys: create in English and Tamil, publish, read results (L26). */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";

interface Q { kind: "rating" | "choice" | "text"; text_en: string; text_ta: string; options_en: string; options_ta: string }
interface SurveyRow { id: string; title: string; status: string; responses: number }
interface Results { responses: number; invited: number; hidden: boolean; min_responses?: number;
  questions: { id: string; kind: string; text: string; average?: number | null; counts?: Record<string, number>; comments?: string[] }[] }

const EMPTY_Q: Q = { kind: "rating", text_en: "", text_ta: "", options_en: "", options_ta: "" };

export default function SurveysPage() {
  const { t } = useLanguage();
  const [rows, setRows] = useState<SurveyRow[]>([]);
  const [title, setTitle] = useState({ en: "", ta: "" });
  const [qs, setQs] = useState<Q[]>([{ ...EMPTY_Q }]);
  const [results, setResults] = useState<Results | null>(null);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { setRows((await fetchApi<{ surveys: SurveyRow[] }>("/college/surveys")).surveys); }
    catch (e) { setError(e instanceof ApiError ? String(e.detail) : t("surveys.load_failed")); }
  }, [t]);
  useEffect(() => { load(); }, [load]);

  const run = async (fn: () => Promise<void>) => {
    setError("");
    setMsg("");
    try { await fn(); } catch (e) { setError(e instanceof ApiError ? String(e.detail) : t("surveys.save_failed")); }
  };
  const split = (v: string) => v.split(",").map((x) => x.trim()).filter(Boolean);
  const create = (e: React.FormEvent) => {
    e.preventDefault();
    run(async () => {
      if (title.en.trim().length < 3 || qs.some((q) => q.text_en.trim().length < 3)) throw new ApiError(422, t("surveys.err_fields"));
      await fetchApi("/college/surveys", { method: "POST", body: JSON.stringify({
        title_en: title.en, title_ta: title.ta || null,
        questions: qs.map((q) => ({ kind: q.kind, text_en: q.text_en, text_ta: q.text_ta || null, required: q.kind !== "text",
          options_en: q.kind === "choice" ? split(q.options_en) : null, options_ta: q.kind === "choice" && q.options_ta ? split(q.options_ta) : null })) }) });
      setTitle({ en: "", ta: "" });
      setQs([{ ...EMPTY_Q }]);
      setMsg(t("surveys.saved"));
      await load();
    });
  };
  const act = (s: SurveyRow, action: "publish" | "close") => run(async () => {
    const r = await fetchApi<{ notified?: number }>(`/college/surveys/${s.id}/${action}`, { method: "POST" });
    setMsg(action === "publish" ? `${t("surveys.published")} ${r.notified ?? 0}` : t("surveys.closed"));
    await load();
  });
  const showResults = (s: SurveyRow) => run(async () => setResults(await fetchApi<Results>(`/college/surveys/${s.id}/results`)));
  const setQ = (i: number, patch: Partial<Q>) => setQs(qs.map((q, j) => (j === i ? { ...q, ...patch } : q)));
  const cls = "w-full px-2.5 py-1.5 bg-surface-2 border border-line rounded-tile text-xs";

  return (
    <RoleGuard allowedRoles={["college"]}>
      <AppShell pageTitle={t("surveys.title")}>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 max-w-6xl">
          <form onSubmit={create} noValidate className="bg-white rounded-card border border-line p-3 space-y-2 h-fit" data-testid="survey-form">
            <p className="text-caption text-muted">{t("surveys.help")}</p>
            <input className={cls} placeholder={t("surveys.title_en")} value={title.en} onChange={(e) => setTitle({ ...title, en: e.target.value })} data-testid="survey-title" />
            <input className={cls} placeholder={t("surveys.title_ta")} value={title.ta} onChange={(e) => setTitle({ ...title, ta: e.target.value })} data-testid="survey-title-ta" />
            {qs.map((q, i) => (
              <fieldset key={i} className="border border-line rounded-tile p-2 space-y-1.5" data-testid="survey-q">
                <legend className="text-caption font-semibold px-1">{t("surveys.question")} {i + 1}</legend>
                <select className={cls} value={q.kind} onChange={(e) => setQ(i, { kind: e.target.value as Q["kind"] })} aria-label={t("surveys.kind")}>
                  {["rating", "choice", "text"].map((k) => <option key={k} value={k}>{t(`surveys.kind_${k}`)}</option>)}
                </select>
                <input className={cls} placeholder={t("surveys.q_en")} value={q.text_en} onChange={(e) => setQ(i, { text_en: e.target.value })} data-testid="q-en" />
                <input className={cls} placeholder={t("surveys.q_ta")} value={q.text_ta} onChange={(e) => setQ(i, { text_ta: e.target.value })} data-testid="q-ta" />
                {q.kind === "choice" && (
                  <>
                    <input className={cls} placeholder={t("surveys.options_en")} value={q.options_en} onChange={(e) => setQ(i, { options_en: e.target.value })} />
                    <input className={cls} placeholder={t("surveys.options_ta")} value={q.options_ta} onChange={(e) => setQ(i, { options_ta: e.target.value })} />
                  </>
                )}
              </fieldset>
            ))}
            <div className="flex gap-2">
              <button type="button" onClick={() => setQs([...qs, { ...EMPTY_Q }])} className="px-3 py-1.5 border border-line-strong text-xs font-semibold rounded-tile">{t("surveys.add_question")}</button>
              <button type="submit" className="px-3 py-1.5 bg-brand text-white text-xs font-semibold rounded-tile" data-testid="survey-save">{t("surveys.save_draft")}</button>
            </div>
          </form>
          <section className="space-y-2">
            {msg && <p className="text-xs text-success font-semibold" role="status" data-testid="survey-msg">{msg}</p>}
            {error && <p className="text-xs text-red-600" role="alert" data-testid="survey-error">{error}</p>}
            <ul className="space-y-2" data-testid="survey-list">
              {rows.map((s) => (
                <li key={s.id} className="bg-white rounded-card border border-line p-3 text-xs" data-testid="survey-row">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold">{s.title}</span>
                    <span className="text-muted" data-testid="survey-status">{t(`surveys.status_${s.status}`)} · {s.responses} {t("surveys.responses")}</span>
                  </div>
                  <div className="flex gap-2 mt-2">
                    {s.status === "draft" && <button type="button" onClick={() => act(s, "publish")} className="px-2.5 py-1 bg-success text-white font-semibold rounded-tile" data-testid="survey-publish">{t("surveys.publish")}</button>}
                    {s.status === "published" && <button type="button" onClick={() => act(s, "close")} className="px-2.5 py-1 border border-line-strong font-semibold rounded-tile">{t("surveys.close")}</button>}
                    {s.status !== "draft" && <button type="button" onClick={() => showResults(s)} className="px-2.5 py-1 border border-line-strong font-semibold rounded-tile" data-testid="survey-results">{t("surveys.results")}</button>}
                  </div>
                </li>
              ))}
            </ul>
            {results && (
              <div className="bg-white rounded-card border border-line p-3 text-xs space-y-2" data-testid="survey-results-panel">
                <div className="font-semibold">{results.responses}/{results.invited} {t("surveys.answered")}</div>
                {results.hidden ? <p className="text-muted">{t("surveys.hidden")} ({results.min_responses})</p> : results.questions.map((q) => (
                  <div key={q.id} className="border-t border-line-soft pt-1.5">
                    <div className="font-semibold">{q.text}</div>
                    {q.average !== undefined && <div>{t("surveys.average")}: {q.average ?? "—"} / 5</div>}
                    {q.counts && <div>{Object.entries(q.counts).map(([k, v]) => `${k}: ${v}`).join(" · ")}</div>}
                    {q.comments && <ul className="list-disc pl-4 text-ink-soft">{q.comments.map((c, i) => <li key={i}>{c}</li>)}</ul>}
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
