"use client";

/** Screen 46 · the IREP problem and question bank (platform tenant). Trainers import items on 22 (L37). */
import React, { useCallback, useEffect, useState } from "react";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { Library } from "lucide-react";

interface BankItem { kind: "problem" | "test"; id: string; title: string; difficulty?: string; topic?: string; questions?: number; imports: number }

const EMPTY = { title: "", statement: "", difficulty: "Easy", topic: "", sample_in: "", sample_out: "", hidden_in: "", hidden_out: "" };

export function BankPanel() {
  const { t } = useLanguage();
  const [bank, setBank] = useState<{ problems: BankItem[]; tests: BankItem[] } | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setBank(await fetchApi("/admin/content/bank")); } catch (e) { setError(e instanceof ApiError ? e.detail : t("content.load_failed")); }
  }, [t]);
  useEffect(() => { load(); }, [load]);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.title.trim().length < 3 || form.statement.trim().length < 10 || !form.sample_in || !form.sample_out) return setError(t("assess.err_problem"));
    setBusy(true);
    setError("");
    try {
      const cases = [{ name: "Sample", input_data: form.sample_in, expected_output: form.sample_out, is_hidden: false }];
      if (form.hidden_in && form.hidden_out) cases.push({ name: "Hidden", input_data: form.hidden_in, expected_output: form.hidden_out, is_hidden: true });
      await fetchApi("/admin/content/bank/problems", { method: "POST", body: JSON.stringify({
        title: form.title, statement: form.statement, difficulty: form.difficulty, topic: form.topic || "General",
        example_input: form.sample_in, example_output: form.sample_out, cases }) });
      setForm(EMPTY);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : t("content.save_failed"));
    } finally {
      setBusy(false);
    }
  };

  const cls = "w-full px-2.5 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg text-xs";
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <form onSubmit={add} noValidate className="bg-white rounded-xl border border-[#E2E8F0] p-3 space-y-2" data-testid="bank-form">
        <h2 className="text-sm font-black flex items-center gap-2"><Library className="w-4 h-4 text-[#2B5CD0]" />{t("content.bank_add_problem")}</h2>
        <p className="text-[11px] text-[#64748B]">{t("content.bank_help")}</p>
        {error && <p className="text-xs text-red-600" role="alert">{error}</p>}
        <input className={cls} placeholder={t("assess.p_title")} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} data-testid="bank-title" />
        <textarea className={cls} rows={3} placeholder={t("assess.p_statement")} value={form.statement} onChange={(e) => setForm({ ...form, statement: e.target.value })} data-testid="bank-statement" />
        <div className="grid grid-cols-2 gap-2">
          <select className={cls} value={form.difficulty} onChange={(e) => setForm({ ...form, difficulty: e.target.value })} aria-label={t("assess.difficulty")}>
            {["Easy", "Medium", "Hard"].map((d) => <option key={d}>{d}</option>)}
          </select>
          <input className={cls} placeholder={t("assess.topic")} value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })} />
          <textarea className={cls} rows={2} placeholder={t("assess.sample_in")} value={form.sample_in} onChange={(e) => setForm({ ...form, sample_in: e.target.value })} data-testid="bank-sample-in" />
          <textarea className={cls} rows={2} placeholder={t("assess.sample_out")} value={form.sample_out} onChange={(e) => setForm({ ...form, sample_out: e.target.value })} data-testid="bank-sample-out" />
          <textarea className={cls} rows={2} placeholder={t("assess.hidden_in")} value={form.hidden_in} onChange={(e) => setForm({ ...form, hidden_in: e.target.value })} />
          <textarea className={cls} rows={2} placeholder={t("assess.hidden_out")} value={form.hidden_out} onChange={(e) => setForm({ ...form, hidden_out: e.target.value })} />
        </div>
        <button type="submit" disabled={busy} className="px-3 py-1.5 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg disabled:opacity-50" data-testid="bank-save">{t("content.bank_publish")}</button>
      </form>
      <ul className="bg-white rounded-xl border border-[#E2E8F0] divide-y divide-[#F1F5F9] h-fit" data-testid="bank-list">
        {bank && [...bank.problems, ...bank.tests].map((it) => (
          <li key={it.id} className="px-3 py-2 text-xs" data-testid="bank-item">
            <div className="font-bold">{it.title}</div>
            <div className="text-[11px] text-[#64748B]">{t(`assess.kind_${it.kind}`)}{it.difficulty ? ` · ${it.difficulty}` : ""}{it.questions ? ` · ${it.questions} ${t("assess.questions")}` : ""} · {t("content.bank_imports")} {it.imports}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}
