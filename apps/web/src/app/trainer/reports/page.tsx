"use client";

/** Screen 21 · Reports (trainer): monthly cards; approval releases a card to the parent (L22, release rule §5.1.1). */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { CheckCircle2, FilePlus2 } from "lucide-react";

interface Row { student_id: string; name: string; batch: string | null; card_id: string | null; status: string; ready: boolean }
interface Card {
  id: string; name: string | null; month_label: string; status: string; missing: string[];
  rows: { area: string; prev: string; curr: string; status: string; color: string }[];
  trainer_remark_en: string | null; trainer_remark_ta: string | null; how_to_help_en: string | null; how_to_help_ta: string | null;
}
// English only: the API translates both into Tamil for parents (no separate Tamil boxes)
const FIELDS = ["trainer_remark_en", "how_to_help_en"] as const;

function thisMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function TrainerReportsPage() {
  const { t, language } = useLanguage();
  const [month, setMonth] = useState(thisMonth());
  const [data, setData] = useState<{ month_label: string; students: Row[]; counts: Record<string, number> } | null>(null);
  const [card, setCard] = useState<Card | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await fetchApi(`/trainer/reports?month=${month}&lang=${language}`));
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("reports.load_failed"));
    }
  }, [month, language, t]);

  useEffect(() => { load(); }, [load]);

  const openCard = async (id: string) => {
    const c = await fetchApi<Card>(`/trainer/reports/${id}?lang=${language}`);
    setCard(c);
    setForm(Object.fromEntries(FIELDS.map((f) => [f, c[f] || ""])));
    setMsg("");
    setError("");
  };

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setMsg("");
    try { await fn(); } catch (e) { setError(e instanceof ApiError ? e.detail : t("reports.save_failed")); } finally { setBusy(false); }
  };

  const generate = () => run(async () => {
    const r = await fetchApi<{ created: number }>("/trainer/reports/generate", { method: "POST", body: JSON.stringify({ month }) });
    setMsg(`${t("reports.drafts_made")} ${r.created}`);
    await load();
  });

  const save = (approve: boolean) => card && run(async () => {
    await fetchApi(`/trainer/reports/${card.id}`, { method: "PUT", body: JSON.stringify(form) });
    if (approve) {
      await fetchApi(`/trainer/reports/${card.id}/approve`, { method: "POST" });
      setMsg(t("reports.released"));
    } else {
      setMsg(t("reports.saved"));
    }
    await Promise.all([openCard(card.id), load()]);
  });

  const approveReady = () => data && run(async () => {
    const ids = data.students.filter((s) => s.ready && s.card_id).map((s) => s.card_id as string);
    if (!ids.length) return setMsg(t("reports.none_ready"));
    const r = await fetchApi<{ released: string[] }>("/trainer/reports/approve", { method: "POST", body: JSON.stringify({ card_ids: ids }) });
    setMsg(`${t("reports.released_n")} ${r.released.length}`);
    await load();
  });

  const chip: Record<string, string> = { none: "bg-line-soft text-muted", draft: "bg-warning-soft text-warning", approved: "bg-success-soft text-success", sent: "bg-success-soft text-success" };
  const cls = "w-full px-2.5 py-1.5 bg-surface-2 border border-line rounded-tile text-xs";

  return (
    <RoleGuard allowedRoles={["trainer"]}>
      <AppShell pageTitle={t("reports.trainer_title")}>
        <div className="space-y-6 max-w-6xl">
          <div className="flex flex-wrap items-center gap-2">
            <input type="month" value={month} onChange={(e) => { setMonth(e.target.value); setCard(null); }} aria-label={t("reports.month")} data-testid="report-month"
              className="px-2.5 py-1.5 border border-line-strong rounded-tile text-xs" />
            <button type="button" disabled={busy} onClick={generate} data-testid="generate-drafts" className="px-3 py-1.5 bg-brand text-white text-xs font-semibold rounded-tile inline-flex items-center gap-1 disabled:opacity-50">
              <FilePlus2 className="w-3.5 h-3.5" />{t("reports.generate")}
            </button>
            <button type="button" disabled={busy} onClick={approveReady} data-testid="approve-ready" className="px-3 py-1.5 border border-success-line text-success text-xs font-semibold rounded-tile disabled:opacity-50">{t("reports.approve_ready")}</button>
            {data && <span className="text-caption text-muted">{data.month_label} · {t("reports.drafts")} {data.counts.draft} · {t("reports.released_count")} {data.counts.approved + data.counts.sent}</span>}
          </div>
          {msg && <p className="text-xs text-success font-semibold" role="status" data-testid="report-msg">{msg}</p>}
          {error && <p className="text-xs text-red-600" role="alert" data-testid="report-error">{error}</p>}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
            <ul className="lg:col-span-2 bg-white rounded-card border border-line divide-y divide-line-soft max-h-[70vh] overflow-y-auto" data-testid="card-list">
              {data?.students.map((s) => (
                <li key={s.student_id}>
                  <button type="button" disabled={!s.card_id} onClick={() => s.card_id && openCard(s.card_id)} data-testid="card-row" aria-pressed={card?.id === s.card_id}
                    className={`w-full text-left px-3 py-2 flex items-center justify-between gap-2 ${card?.id === s.card_id ? "bg-brand-soft" : "hover:bg-surface-2"} disabled:cursor-default`}>
                    <span className="min-w-0"><span className="block text-xs font-semibold truncate">{s.name}</span><span className="block text-caption text-muted">{s.batch}</span></span>
                    <span className={`text-caption font-semibold px-2 py-0.5 rounded-full ${chip[s.status]}`}>{t(`reports.status_${s.status}`)}</span>
                  </button>
                </li>
              ))}
            </ul>
            {card && (
              <section className="lg:col-span-3 bg-white rounded-card border border-line p-4 space-y-3 h-fit" data-testid="card-editor">
                <h2 className="text-sm font-semibold text-ink">{card.name} · {card.month_label}</h2>
                <table className="w-full text-xs">
                  <thead><tr className="text-left text-muted"><th className="py-1">{t("reports.area")}</th><th>{t("reports.last_month")}</th><th>{t("reports.this_month")}</th><th>{t("reports.status")}</th></tr></thead>
                  <tbody>
                    {card.rows.map((r) => (
                      <tr key={r.area} className="border-t border-line-soft"><td className="py-1 font-semibold">{r.area}</td><td>{r.prev}</td><td>{r.curr}</td>
                        <td className={r.color === "green" ? "text-success" : "text-warning"}>{r.status}</td></tr>
                    ))}
                  </tbody>
                </table>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {FIELDS.map((f) => (
                    <label key={f} className="text-caption text-ink-soft">{t(`reports.${f}`)}
                      <textarea rows={3} className={cls} value={form[f] || ""} disabled={card.status !== "draft"} data-testid={`field-${f}`}
                        onChange={(e) => setForm({ ...form, [f]: e.target.value })} />
                    </label>
                  ))}
                </div>
                <p className="text-caption text-muted" data-testid="tamil-auto-note">{t("reports.tamil_auto")}</p>
                {card.status === "draft" ? (
                  <div className="flex gap-2">
                    <button type="button" disabled={busy} onClick={() => save(false)} data-testid="card-save" className="px-3 py-1.5 border border-line-strong text-xs font-semibold rounded-tile disabled:opacity-50">{t("reports.save_draft")}</button>
                    <button type="button" disabled={busy} onClick={() => save(true)} data-testid="card-approve" className="px-3 py-1.5 bg-success text-white text-xs font-semibold rounded-tile inline-flex items-center gap-1 disabled:opacity-50">
                      <CheckCircle2 className="w-3.5 h-3.5" />{t("reports.approve")}
                    </button>
                  </div>
                ) : <p className="text-caption text-success font-semibold" data-testid="card-released">{t("reports.released_note")}</p>}
              </section>
            )}
          </div>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
