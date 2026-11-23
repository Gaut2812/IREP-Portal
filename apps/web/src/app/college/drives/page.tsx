"use client";

/** Screen 38 · Mock drives (college). A "drive" event on 42 creates its drive here (L29); rounds are a
 *  practice test or interview slots on the trainer's 37 (L17). Results show scores only, never trainer
 *  notes (5.4). Spec: docs/screens/37-38-39-interviews-drives-readiness.md */
import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";

interface DriveRow { id: string; event_id: string; title: string; starts_at: string; batch: string | null; status: string; rounds: number; company_pattern: string }
interface Round { id: string; round_no: number; kind: "test" | "interview"; label: string; test_title: string | null; trainer: string | null;
  starts_at: string | null; duration_min: number; slot_count: number; cutoff: number }
interface Detail extends DriveRow { round_list: Round[]; options: { tests: { id: string; title: string }[]; trainers: { id: string; name: string }[];
  round_types: { key: string; label: string }[]; rubric_max: number } }
interface Results { status: string; shortlisted: number; total: number; funnel: { round_no: number; attempted: number; cleared: number }[];
  students: { student_id: string; name: string; register_no: string; shortlisted: boolean; rounds: { round_id: string; score: number | null; cleared: boolean }[] }[] }

const STATUS: Record<string, string> = { draft: "bg-[#F1F5F9] text-[#475569]", published: "bg-[#DBEAFE] text-[#1E40AF]", results_published: "bg-[#DCFCE7] text-[#166534]" };
const EMPTY_ROUND = { kind: "test", test_id: "", round_type: "technical", trainer_id: "", starts_at: "", duration_min: "40", slot_count: "5", cutoff: "" };

export default function DrivesPage() {
  const { t, language } = useLanguage();
  const [drives, setDrives] = useState<DriveRow[]>([]);
  const [d, setD] = useState<Detail | null>(null);
  const [res, setRes] = useState<Results | null>(null);
  const [round, setRound] = useState({ ...EMPTY_ROUND });
  const [pattern, setPattern] = useState("");
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const loadList = useCallback(async () => {
    try { setDrives((await fetchApi<{ drives: DriveRow[] }>(`/college/drives?lang=${language}`)).drives); }
    catch (e) { setError(e instanceof ApiError ? String(e.detail) : t("drives.load_failed")); }
  }, [language, t]);
  useEffect(() => { loadList(); }, [loadList]);

  const open = useCallback(async (id: string) => {
    setError(""); setMsg("");
    try {
      const det = await fetchApi<Detail>(`/college/drives/${id}?lang=${language}`);
      setD(det); setPattern(det.company_pattern); setRound({ ...EMPTY_ROUND });
      setRes(det.status === "draft" ? null : await fetchApi<Results>(`/college/drives/${id}/results`));
    } catch (e) { setError(e instanceof ApiError ? String(e.detail) : t("drives.load_failed")); }
  }, [language, t]);

  const run = async (fn: () => Promise<unknown>, done: string) => {
    if (!d) return;
    setBusy(true); setError(""); setMsg("");
    try { await fn(); await open(d.id); await loadList(); setMsg(done); }    // open() clears old messages first
    catch (e) { setError(e instanceof ApiError ? String(e.detail) : t("drives.action_failed")); }
    finally { setBusy(false); }
  };

  const addRound = (e: React.FormEvent) => {
    e.preventDefault();
    if (!d) return;
    const cutoff = Number(round.cutoff || 0);
    const body = round.kind === "test"
      ? { kind: "test", test_id: round.test_id, cutoff }
      : { kind: "interview", round_type: round.round_type, trainer_id: round.trainer_id, starts_at: round.starts_at,
          duration_min: Number(round.duration_min), slot_count: Number(round.slot_count), cutoff };
    if (round.kind === "test" && !round.test_id) { setError(t("drives.err_test")); return; }
    if (round.kind === "interview" && (!round.trainer_id || !round.starts_at)) { setError(t("drives.err_interview")); return; }
    run(() => fetchApi(`/college/drives/${d.id}/rounds`, { method: "POST", body: JSON.stringify(body) }), t("drives.round_added"));
  };

  const card = "bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-3";
  const field = "px-2.5 py-1.5 border border-[#CBD5E1] rounded-lg text-xs";
  const fmt = (iso: string) => new Date(iso).toLocaleString(language === "ta" ? "ta-IN" : "en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

  return (
    <RoleGuard allowedRoles={["college"]}>
      <AppShell pageTitle={t("drives.title")}>
        <div className="p-4 md:p-6 space-y-4 max-w-6xl">
          <p className="text-xs text-[#64748B]">{t("drives.help")} <Link href="/college/events" className="text-[#2B5CD0] font-bold underline">{t("drives.go_events")}</Link></p>
          {error && <p className="text-xs text-red-600" role="alert" data-testid="drives-error">{error}</p>}
          {msg && <p className="text-xs text-[#166534]" role="status" data-testid="drives-msg">{msg}</p>}

          <section className={card} data-testid="drive-list">
            {drives.length === 0 && <p className="text-xs text-[#64748B]">{t("drives.none")}</p>}
            <ul className="space-y-2">
              {drives.map((x) => (
                <li key={x.id}>
                  <button type="button" onClick={() => open(x.id)} data-testid={`drive-${x.id}`}
                    className={`w-full text-left border rounded-lg p-2.5 text-xs flex flex-wrap items-center justify-between gap-2 ${d?.id === x.id ? "border-[#2B5CD0] bg-[#EFF6FF]" : "border-[#F1F5F9]"}`}>
                    <span><b className="text-[#0F1F3A]">{x.title}</b> · {fmt(x.starts_at)} · {x.batch || t("drives.no_batch")} · {x.rounds} {t("drives.rounds")}</span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${STATUS[x.status]}`}>{t(`drives.status_${x.status}`)}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>

          {d && (
            <section className={card} data-testid="drive-detail">
              <h2 className="text-sm font-black text-[#0F1F3A]">{d.title}</h2>
              {d.status === "draft" ? (
                <div className="flex gap-2 items-center">
                  <input value={pattern} onChange={(e) => setPattern(e.target.value)} placeholder={t("drives.pattern_ph")} aria-label={t("drives.pattern")}
                    data-testid="drive-pattern" className={`${field} flex-1`} />
                  <button type="button" disabled={busy} data-testid="drive-pattern-save" className="px-3 py-1.5 border border-[#CBD5E1] rounded-lg text-xs font-bold"
                    onClick={() => run(() => fetchApi(`/college/drives/${d.id}`, { method: "PUT", body: JSON.stringify({ company_pattern: pattern }) }), t("drives.saved"))}>{t("drives.save")}</button>
                </div>
              ) : <p className="text-xs text-[#475569]">{d.company_pattern}</p>}

              <ol className="space-y-2" data-testid="round-list">
                {d.round_list.map((r) => (
                  <li key={r.id} className="border border-[#F1F5F9] rounded-lg p-2.5 text-xs flex flex-wrap items-center justify-between gap-2" data-testid="round-row">
                    <span><b>{t("drives.round")} {r.round_no}: {r.label}</b> · {r.kind === "test" ? r.test_title
                      : `${r.trainer} · ${r.starts_at ? fmt(r.starts_at) : ""} · ${r.slot_count} × ${r.duration_min} ${t("drives.min")}`} · {t("drives.cutoff")} {r.cutoff}{r.kind === "test" ? "%" : ` / ${d.options.rubric_max}`}</span>
                    {d.status === "draft" && <button type="button" disabled={busy} data-testid="round-remove" className="text-[#DC2626] font-bold"
                      onClick={() => run(() => fetchApi(`/college/drives/${d.id}/rounds/${r.id}`, { method: "DELETE" }), t("drives.round_removed"))}>{t("drives.remove")}</button>}
                  </li>
                ))}
              </ol>

              {d.status === "draft" && (
                <>
                  <form onSubmit={addRound} noValidate className="flex flex-wrap gap-2 items-end border-t border-[#F1F5F9] pt-3" data-testid="round-form">
                    <select value={round.kind} onChange={(e) => setRound({ ...round, kind: e.target.value })} aria-label={t("drives.kind")} data-testid="round-kind" className={field}>
                      <option value="test">{t("drives.kind_test")}</option>
                      <option value="interview">{t("drives.kind_interview")}</option>
                    </select>
                    {round.kind === "test" ? (
                      <select value={round.test_id} onChange={(e) => setRound({ ...round, test_id: e.target.value })} aria-label={t("drives.test")} data-testid="round-test" className={field}>
                        <option value="">{t("drives.choose_test")}</option>
                        {d.options.tests.map((x) => <option key={x.id} value={x.id}>{x.title}</option>)}
                      </select>
                    ) : (
                      <>
                        <select value={round.round_type} onChange={(e) => setRound({ ...round, round_type: e.target.value })} aria-label={t("drives.round_type")} data-testid="round-type" className={field}>
                          {d.options.round_types.map((x) => <option key={x.key} value={x.key}>{x.label}</option>)}
                        </select>
                        <select value={round.trainer_id} onChange={(e) => setRound({ ...round, trainer_id: e.target.value })} aria-label={t("drives.trainer")} data-testid="round-trainer" className={field}>
                          <option value="">{t("drives.choose_trainer")}</option>
                          {d.options.trainers.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
                        </select>
                        <input type="datetime-local" value={round.starts_at} onChange={(e) => setRound({ ...round, starts_at: e.target.value })}
                          aria-label={t("drives.starts_at")} data-testid="round-start" className={field} />
                        <input type="number" min={1} max={60} value={round.slot_count} onChange={(e) => setRound({ ...round, slot_count: e.target.value })}
                          aria-label={t("drives.slots")} data-testid="round-slots" className={`${field} w-20`} />
                        <select value={round.duration_min} onChange={(e) => setRound({ ...round, duration_min: e.target.value })} aria-label={t("drives.length")} data-testid="round-length" className={field}>
                          {["20", "30", "40", "60"].map((m) => <option key={m} value={m}>{m} {t("drives.min")}</option>)}
                        </select>
                      </>
                    )}
                    <input type="number" min={0} step="0.1" value={round.cutoff} onChange={(e) => setRound({ ...round, cutoff: e.target.value })}
                      placeholder={round.kind === "test" ? t("drives.cutoff_pct") : `${t("drives.cutoff_score")} / ${d.options.rubric_max}`}
                      aria-label={t("drives.cutoff")} data-testid="round-cutoff" className={`${field} w-32`} />
                    <button type="submit" disabled={busy} data-testid="round-add" className="px-3.5 py-1.5 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg disabled:opacity-50">{t("drives.add_round")}</button>
                  </form>
                  <div className="flex justify-end">
                    <button type="button" disabled={busy || d.round_list.length === 0} data-testid="drive-publish" className="px-3.5 py-1.5 bg-[#166534] text-white text-xs font-bold rounded-lg disabled:opacity-50"
                      onClick={() => run(() => fetchApi(`/college/drives/${d.id}/publish`, { method: "POST" }), t("drives.published"))}>{t("drives.publish")}</button>
                  </div>
                  <p className="text-[11px] text-[#64748B]">{t("drives.publish_note")}</p>
                </>
              )}

              {res && (
                <div className="space-y-2 border-t border-[#F1F5F9] pt-3" data-testid="drive-results">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-xs font-black text-[#0F1F3A]" data-testid="results-summary">{t("drives.shortlisted")}: {res.shortlisted} / {res.total}
                      {res.funnel.map((f) => ` · ${t("drives.round")} ${f.round_no}: ${f.cleared}/${f.attempted}`).join("")}</h3>
                    {d.status === "published" && <button type="button" disabled={busy} data-testid="shortlist-publish" className="px-3 py-1.5 bg-[#166534] text-white text-xs font-bold rounded-lg disabled:opacity-50"
                      onClick={() => { if (window.confirm(t("drives.confirm_shortlist"))) run(() => fetchApi(`/college/drives/${d.id}/shortlist`, { method: "POST" }), t("drives.shortlist_done")); }}>{t("drives.publish_shortlist")}</button>}
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead><tr className="text-left text-[#64748B] border-b border-[#E2E8F0]">
                        <th className="py-1.5 pr-2">{t("drives.student")}</th>
                        {d.round_list.map((r) => <th key={r.id} className="pr-2">{t("drives.round")} {r.round_no}</th>)}
                        <th>{t("drives.result")}</th>
                      </tr></thead>
                      <tbody>
                        {res.students.filter((s) => s.rounds.some((c) => c.score !== null)).map((s) => (
                          <tr key={s.student_id} className="border-b border-[#F1F5F9]" data-testid="result-row">
                            <td className="py-1.5 pr-2">{s.name} <span className="text-[#94A3B8]">{s.register_no}</span></td>
                            {s.rounds.map((c) => <td key={c.round_id} className={`pr-2 ${c.cleared ? "text-[#166534] font-bold" : "text-[#64748B]"}`}>{c.score ?? "–"}</td>)}
                            <td>{s.shortlisted ? <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#DCFCE7] text-[#166534]">{t("drives.shortlisted_yes")}</span> : "–"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="text-[11px] text-[#64748B]">{t("drives.scores_only")}</p>
                </div>
              )}
            </section>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
