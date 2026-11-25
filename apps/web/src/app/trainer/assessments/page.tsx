"use client";

/** Screen 22 · Assessments (trainer): publish problems (24) and tests (23) to batches, read results back (L13);
 *  import from the IREP bank (46, L37). */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { Download, Plus, Send, Undo2 } from "lucide-react";

type Kind = "problem" | "test";
interface Item {
  kind: Kind; id: string; title: string; status: string; batch_ids: string[] | null; batches: "all" | string[]; due_at: string | null;
  source_id: string | null; difficulty?: string; topic?: string; trainer_notes?: string | null; questions?: number; imported?: boolean;
}
interface Results { students: { student_id: string; name: string; batch: string | null; attempts: number; result: string | null; score: string | null; done: boolean }[]; summary: { students: number; attempted: number; done: number } }
interface Q { question_text: string; option_a: string; option_b: string; option_c: string; option_d: string; correct_option: string }

const EMPTY_P = { title: "", statement: "", constraints: "", difficulty: "Easy", topic: "", trainer_notes: "", sample_in: "", sample_out: "", hidden_in: "", hidden_out: "" };
const EMPTY_Q: Q = { question_text: "", option_a: "", option_b: "", option_c: "", option_d: "", correct_option: "A" };

export default function AssessmentsPage() {
  const { t } = useLanguage();
  const [tab, setTab] = useState<"problems" | "tests" | "bank">("problems");
  const [data, setData] = useState<{ batches: { id: string; name: string }[]; problems: Item[]; tests: Item[] } | null>(null);
  const [bank, setBank] = useState<{ problems: Item[]; tests: Item[] } | null>(null);
  const [sel, setSel] = useState<Item | null>(null);
  const [results, setResults] = useState<Results | null>(null);
  const [chosen, setChosen] = useState<string[]>([]);
  const [due, setDue] = useState("");
  const [notes, setNotes] = useState("");
  const [creating, setCreating] = useState(false);
  const [pf, setPf] = useState(EMPTY_P);
  const [tf, setTf] = useState({ title: "", duration_min: "15", questions: [{ ...EMPTY_Q }] });
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await fetchApi("/trainer/assessments"));
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("assess.load_failed"));
    }
  }, [t]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (tab === "bank") fetchApi<{ problems: Item[]; tests: Item[] }>("/trainer/bank").then(setBank).catch(() => setError(t("assess.load_failed"))); }, [tab, t]);

  const pick = async (it: Item) => {
    setSel(it);
    setCreating(false);
    setMsg("");
    setChosen(it.batch_ids === null ? [] : it.batch_ids.filter((b) => data?.batches.some((x) => x.id === b)));
    setNotes(it.trainer_notes || "");
    setDue(it.due_at ? it.due_at.slice(0, 16) : "");
    setResults(await fetchApi<Results>(`/trainer/assessments/${it.kind}/${it.id}/results`).catch(() => null));
  };

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setMsg("");
    try { await fn(); } catch (e) { setError(e instanceof ApiError ? e.detail : t("assess.save_failed")); } finally { setBusy(false); }
  };

  const refreshSel = async (kind: Kind, id: string) => {
    const d = await fetchApi<{ batches: { id: string; name: string }[]; problems: Item[]; tests: Item[] }>("/trainer/assessments");
    setData(d);
    const it = (kind === "problem" ? d.problems : d.tests).find((x) => x.id === id);
    if (it) await pick(it);
  };

  const publish = () => sel && run(async () => {
    if (!chosen.length) throw new ApiError(422, t("assess.err_batches"));
    const r = await fetchApi<{ notified: number }>(`/trainer/assessments/${sel.kind}/${sel.id}/publish`, {
      method: "POST", body: JSON.stringify({ batch_ids: chosen, due_at: due ? `${due}:00` : null }) });
    await refreshSel(sel.kind, sel.id);
    setMsg(`${t("assess.published")} ${r.notified}`);
  });

  const unpublish = () => sel && run(async () => {
    await fetchApi(`/trainer/assessments/${sel.kind}/${sel.id}/unpublish`, { method: "POST" });
    await refreshSel(sel.kind, sel.id);
    setMsg(t("assess.unpublished"));
  });

  const saveNotes = () => sel && run(async () => {
    await fetchApi(`/trainer/assessments/problem/${sel.id}/notes`, { method: "PUT", body: JSON.stringify({ trainer_notes: notes }) });
    await refreshSel(sel.kind, sel.id);
    setMsg(t("assess.notes_saved"));
  });

  const createProblem = (e: React.FormEvent) => {
    e.preventDefault();
    run(async () => {
      if (pf.title.trim().length < 3 || pf.statement.trim().length < 10 || !pf.sample_in || !pf.sample_out) throw new ApiError(422, t("assess.err_problem"));
      const cases = [{ name: "Sample", input_data: pf.sample_in, expected_output: pf.sample_out, is_hidden: false }];
      if (pf.hidden_in && pf.hidden_out) cases.push({ name: "Hidden", input_data: pf.hidden_in, expected_output: pf.hidden_out, is_hidden: true });
      const it = await fetchApi<Item>("/trainer/assessments/problems", { method: "POST", body: JSON.stringify({
        title: pf.title, statement: pf.statement, constraints: pf.constraints, difficulty: pf.difficulty, topic: pf.topic || "General",
        trainer_notes: pf.trainer_notes || null, example_input: pf.sample_in, example_output: pf.sample_out, cases }) });
      setPf(EMPTY_P);
      await refreshSel("problem", it.id);
      setMsg(t("assess.created"));
    });
  };

  const createTest = (e: React.FormEvent) => {
    e.preventDefault();
    run(async () => {
      if (tf.title.trim().length < 3 || tf.questions.some((q) => q.question_text.trim().length < 5 || !q.option_a || !q.option_b || !q.option_c || !q.option_d))
        throw new ApiError(422, t("assess.err_test"));
      const it = await fetchApi<Item>("/trainer/assessments/tests", { method: "POST", body: JSON.stringify({ title: tf.title, duration_min: Number(tf.duration_min), questions: tf.questions }) });
      setTf({ title: "", duration_min: "15", questions: [{ ...EMPTY_Q }] });
      setTab("tests");
      await refreshSel("test", it.id);
      setMsg(t("assess.created"));
    });
  };

  const importItem = (it: Item) => run(async () => {
    const made = await fetchApi<Item>(`/trainer/bank/${it.kind}/${it.id}/import`, { method: "POST" });
    setBank(await fetchApi("/trainer/bank"));
    setTab(it.kind === "problem" ? "problems" : "tests");
    await refreshSel(it.kind, made.id);
    setMsg(t("assess.imported"));
  });

  const cls = "w-full px-2.5 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg text-xs";
  const chip = (s: string) => s === "published" ? "bg-[#DCFCE7] text-[#166534]" : "bg-[#F1F5F9] text-[#475569]";
  const list = tab === "problems" ? data?.problems : tab === "tests" ? data?.tests : null;
  const setQ = (i: number, patch: Partial<Q>) => setTf({ ...tf, questions: tf.questions.map((q, j) => (j === i ? { ...q, ...patch } : q)) });

  return (
    <RoleGuard allowedRoles={["trainer"]}>
      <AppShell pageTitle={t("assess.title")}>
        <div className="space-y-4 max-w-6xl">
          <div className="flex flex-wrap gap-2 items-center" role="tablist">
            {(["problems", "tests", "bank"] as const).map((k) => (
              <button key={k} type="button" role="tab" aria-selected={tab === k} onClick={() => { setTab(k); setSel(null); setCreating(false); }} data-testid={`assess-tab-${k}`}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold ${tab === k ? "bg-[#2B5CD0] text-white" : "border border-[#CBD5E1]"}`}>{t(`assess.tab_${k}`)}</button>
            ))}
            {tab !== "bank" && (
              <button type="button" onClick={() => { setCreating(true); setSel(null); }} data-testid="assess-new" className="ml-auto px-3 py-1.5 border border-[#2B5CD0] text-[#2B5CD0] text-xs font-bold rounded-lg inline-flex items-center gap-1">
                <Plus className="w-3.5 h-3.5" />{tab === "problems" ? t("assess.new_problem") : t("assess.new_test")}
              </button>
            )}
          </div>
          {msg && <p className="text-xs text-[#166534] font-bold" role="status" data-testid="assess-msg">{msg}</p>}
          {error && <p className="text-xs text-red-600" role="alert" data-testid="assess-error">{error}</p>}

          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
            <ul className="lg:col-span-2 bg-white rounded-xl border border-[#E2E8F0] divide-y divide-[#F1F5F9] max-h-[70vh] overflow-y-auto" data-testid="assess-list">
              {tab === "bank" && bank && [...bank.problems, ...bank.tests].map((it) => (
                <li key={it.id} className="px-3 py-2 flex items-center justify-between gap-2" data-testid="bank-row">
                  <div className="min-w-0"><div className="text-xs font-bold truncate">{it.title}</div><div className="text-[11px] text-[#64748B]">{t(`assess.kind_${it.kind}`)}{it.difficulty ? ` · ${it.difficulty}` : ""}{it.questions ? ` · ${it.questions} ${t("assess.questions")}` : ""}</div></div>
                  {it.imported ? <span className="text-[11px] text-[#64748B]">{t("assess.already")}</span> : (
                    <button type="button" disabled={busy} onClick={() => importItem(it)} data-testid="bank-import" className="px-2.5 py-1 border border-[#CBD5E1] text-[11px] font-bold rounded-lg inline-flex items-center gap-1 shrink-0">
                      <Download className="w-3.5 h-3.5" />{t("assess.import")}
                    </button>
                  )}
                </li>
              ))}
              {list?.map((it) => (
                <li key={it.id}>
                  <button type="button" onClick={() => pick(it)} aria-pressed={sel?.id === it.id} data-testid="assess-row"
                    className={`w-full text-left px-3 py-2 ${sel?.id === it.id ? "bg-[#EFF6FF]" : "hover:bg-[#F8FAFC]"}`}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-bold truncate">{it.title}</span>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${chip(it.status)}`}>{t(`assess.status_${it.status}`)}</span>
                    </div>
                    <div className="text-[11px] text-[#64748B] truncate">{it.batches === "all" ? t("assess.all_batches") : it.batches.join(", ") || "—"}</div>
                  </button>
                </li>
              ))}
            </ul>

            <section className="lg:col-span-3 space-y-3">
              {creating && tab === "problems" && (
                <form onSubmit={createProblem} noValidate className="bg-white rounded-xl border border-[#E2E8F0] p-4 grid grid-cols-1 md:grid-cols-2 gap-2" data-testid="problem-form">
                  <input className={`${cls} md:col-span-2`} placeholder={t("assess.p_title")} value={pf.title} onChange={(e) => setPf({ ...pf, title: e.target.value })} data-testid="p-title" />
                  <textarea className={`${cls} md:col-span-2`} rows={4} placeholder={t("assess.p_statement")} value={pf.statement} onChange={(e) => setPf({ ...pf, statement: e.target.value })} data-testid="p-statement" />
                  <select className={cls} value={pf.difficulty} onChange={(e) => setPf({ ...pf, difficulty: e.target.value })} aria-label={t("assess.difficulty")}>
                    {["Easy", "Medium", "Hard"].map((d) => <option key={d}>{d}</option>)}
                  </select>
                  <input className={cls} placeholder={t("assess.topic")} value={pf.topic} onChange={(e) => setPf({ ...pf, topic: e.target.value })} />
                  <textarea className={cls} rows={2} placeholder={t("assess.sample_in")} value={pf.sample_in} onChange={(e) => setPf({ ...pf, sample_in: e.target.value })} data-testid="p-sample-in" />
                  <textarea className={cls} rows={2} placeholder={t("assess.sample_out")} value={pf.sample_out} onChange={(e) => setPf({ ...pf, sample_out: e.target.value })} data-testid="p-sample-out" />
                  <textarea className={cls} rows={2} placeholder={t("assess.hidden_in")} value={pf.hidden_in} onChange={(e) => setPf({ ...pf, hidden_in: e.target.value })} />
                  <textarea className={cls} rows={2} placeholder={t("assess.hidden_out")} value={pf.hidden_out} onChange={(e) => setPf({ ...pf, hidden_out: e.target.value })} />
                  <textarea className={`${cls} md:col-span-2`} rows={2} placeholder={t("assess.notes_ph")} value={pf.trainer_notes} onChange={(e) => setPf({ ...pf, trainer_notes: e.target.value })} />
                  <button type="submit" disabled={busy} className="md:col-span-2 px-3 py-2 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg disabled:opacity-50" data-testid="p-save">{t("assess.save_draft")}</button>
                </form>
              )}
              {creating && tab === "tests" && (
                <form onSubmit={createTest} noValidate className="bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-2" data-testid="test-form">
                  <div className="grid grid-cols-3 gap-2">
                    <input className={`${cls} col-span-2`} placeholder={t("assess.t_title")} value={tf.title} onChange={(e) => setTf({ ...tf, title: e.target.value })} data-testid="t-title" />
                    <input className={cls} type="number" min={5} max={180} value={tf.duration_min} onChange={(e) => setTf({ ...tf, duration_min: e.target.value })} aria-label={t("assess.minutes")} />
                  </div>
                  {tf.questions.map((q, i) => (
                    <fieldset key={i} className="border border-[#E2E8F0] rounded-lg p-2 space-y-1.5" data-testid="t-question">
                      <legend className="text-[11px] font-bold px-1">{t("assess.question")} {i + 1}</legend>
                      <input className={cls} placeholder={t("assess.q_text")} value={q.question_text} onChange={(e) => setQ(i, { question_text: e.target.value })} data-testid="q-text" />
                      <div className="grid grid-cols-2 gap-1.5">
                        {(["a", "b", "c", "d"] as const).map((o) => (
                          <input key={o} className={cls} placeholder={`${t("assess.option")} ${o.toUpperCase()}`} value={q[`option_${o}`]} onChange={(e) => setQ(i, { [`option_${o}`]: e.target.value } as Partial<Q>)} data-testid={`q-opt-${o}`} />
                        ))}
                      </div>
                      <label className="text-[11px] text-[#475569] flex items-center gap-2">{t("assess.correct")}
                        <select value={q.correct_option} onChange={(e) => setQ(i, { correct_option: e.target.value })} className="px-2 py-1 border border-[#CBD5E1] rounded text-xs" data-testid="q-correct">
                          {["A", "B", "C", "D"].map((o) => <option key={o}>{o}</option>)}
                        </select>
                      </label>
                    </fieldset>
                  ))}
                  <div className="flex gap-2">
                    <button type="button" onClick={() => setTf({ ...tf, questions: [...tf.questions, { ...EMPTY_Q }] })} className="px-3 py-1.5 border border-[#CBD5E1] text-xs font-bold rounded-lg">{t("assess.add_question")}</button>
                    <button type="submit" disabled={busy} className="px-3 py-1.5 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg disabled:opacity-50" data-testid="t-save">{t("assess.save_draft")}</button>
                  </div>
                </form>
              )}

              {sel && !creating && (
                <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-3" data-testid="assess-detail">
                  <div className="flex items-start justify-between gap-2">
                    <h2 className="text-sm font-black text-[#0F1F3A]" data-testid="assess-heading">{sel.title}</h2>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${chip(sel.status)}`} data-testid="assess-status">{t(`assess.status_${sel.status}`)}</span>
                  </div>
                  <div>
                    <div className="text-[11px] font-bold text-[#64748B] mb-1">{t("assess.publish_to")}</div>
                    <div className="flex flex-wrap gap-2">
                      {data?.batches.map((b) => (
                        <label key={b.id} className="text-xs inline-flex items-center gap-1 border border-[#E2E8F0] rounded-lg px-2 py-1">
                          <input type="checkbox" checked={sel.batch_ids === null || chosen.includes(b.id)} disabled={sel.batch_ids === null}
                            onChange={(e) => setChosen(e.target.checked ? [...chosen, b.id] : chosen.filter((x) => x !== b.id))} data-testid={`batch-${b.id}`} />{b.name}
                        </label>
                      ))}
                    </div>
                    {sel.batch_ids === null && <p className="text-[11px] text-[#64748B] mt-1">{t("assess.college_wide")}</p>}
                  </div>
                  <label className="text-[11px] text-[#475569] block">{t("assess.due")}
                    <input type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} className={cls} data-testid="assess-due" />
                  </label>
                  <div className="flex gap-2">
                    <button type="button" disabled={busy} onClick={publish} data-testid="assess-publish" className="px-3 py-1.5 bg-[#166534] text-white text-xs font-bold rounded-lg inline-flex items-center gap-1 disabled:opacity-50"><Send className="w-3.5 h-3.5" />{t("assess.publish")}</button>
                    {sel.status === "published" && <button type="button" disabled={busy} onClick={unpublish} data-testid="assess-unpublish" className="px-3 py-1.5 border border-[#CBD5E1] text-xs font-bold rounded-lg inline-flex items-center gap-1 disabled:opacity-50"><Undo2 className="w-3.5 h-3.5" />{t("assess.unpublish")}</button>}
                  </div>
                  {sel.kind === "problem" && (
                    <div className="space-y-1">
                      <label className="text-[11px] font-bold text-[#64748B]">{t("assess.notes")}</label>
                      <textarea rows={2} className={cls} value={notes} onChange={(e) => setNotes(e.target.value)} data-testid="assess-notes" />
                      <button type="button" disabled={busy} onClick={saveNotes} data-testid="assess-notes-save" className="px-3 py-1 border border-[#CBD5E1] text-[11px] font-bold rounded-lg">{t("assess.save_notes")}</button>
                    </div>
                  )}
                  {results && (
                    <div>
                      <div className="text-[11px] font-bold text-[#64748B]">{t("assess.results")}: {results.summary.attempted}/{results.summary.students} {t("assess.attempted")} · {results.summary.done} {t("assess.done")}</div>
                      <table className="w-full text-xs mt-1" data-testid="assess-results">
                        <thead><tr className="text-left text-[#64748B]"><th className="py-1">{t("assess.student")}</th><th>{t("assess.attempts")}</th><th>{t("assess.result")}</th><th>{t("assess.score")}</th></tr></thead>
                        <tbody>
                          {results.students.filter((r) => r.attempts > 0).slice(0, 50).map((r) => (
                            <tr key={r.student_id} className="border-t border-[#F1F5F9]" data-testid="result-row"><td className="py-1">{r.name}</td><td>{r.attempts}</td><td>{r.result}</td><td>{r.score}</td></tr>
                          ))}
                        </tbody>
                      </table>
                      {results.summary.attempted === 0 && <p className="text-[11px] text-[#94A3B8] mt-1">{t("assess.no_attempts")}</p>}
                    </div>
                  )}
                </div>
              )}
            </section>
          </div>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
