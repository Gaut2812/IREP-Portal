"use client";

/** Screen 14 · At-risk students (trainer): flags from the nightly readiness run (L34); notifying a parent reaches 18 and 15 (L31).
 *  Trainers also log real phone calls with their outcome, assign a mentor, and see their own mentees. */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { HowItWorks } from "@/components/ui/HowItWorks";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { AlertTriangle, CheckCircle2, Phone, PhoneCall, UserCheck } from "lucide-react";

interface Mentor { user_id: string; name: string | null; since?: string | null }
interface Flag {
  id: string; student_id: string; name: string; score: number | null; band: string | null; attendance_pct: number | null; batch: string | null;
  issue: string; severity: string; status: string; suggested_action: string; action_label: string; parent_notified: boolean; flagged_on: string | null;
  ai_calls_7d?: number; parent_notified_at?: string | null; mentor?: Mentor | null;
}
interface Detail {
  id: string; name: string | null; batch: string | null; status: string; issue: string; action_label: string; parent_notified: boolean;
  parent_notified_at: string | null; renotify_after_days: number; mentor: Mentor | null;
  actions: { type: string; note: string | null; by: string | null; at: string | null }[];
}
interface Mentee { flag_id: string; student_id: string; name: string; batch: string | null; issue: string; score: number | null; attendance_pct: number | null; since: string | null }
type Tab = "open" | "resolved" | "mentees";

const OUTCOME: Record<string, string> = { sent: "at_risk.call_sent", held: "at_risk.call_held", already: "at_risk.call_already", no_parent: "at_risk.call_no_parent" };
const CALL_OUTCOMES = ["reached", "no_answer", "call_back"] as const;
const DAY_MS = 86_400_000;

export default function AtRiskPage() {
  const { t, language } = useLanguage();
  const [tab, setTab] = useState<Tab>("open");
  const [data, setData] = useState<{ flags: Flag[]; summary: { open: number; high: number; parents_alerted: number } } | null>(null);
  const [mentees, setMentees] = useState<Mentee[] | null>(null);
  const [mentors, setMentors] = useState<{ user_id: string; name: string; is_me: boolean }[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [note, setNote] = useState("");
  const [callOutcome, setCallOutcome] = useState<string>("");
  const [mentorPick, setMentorPick] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const fmt = (iso: string | null | undefined) =>
    iso ? new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`).toLocaleDateString(language === "ta" ? "ta-IN" : "en-IN", { day: "numeric", month: "short" }) : "";

  const load = useCallback(async () => {
    try {
      if (tab === "mentees") setMentees((await fetchApi<{ mentees: Mentee[] }>(`/trainer/mentees?lang=${language}`)).mentees);
      else setData(await fetchApi(`/trainer/at-risk?status=${tab}&lang=${language}`));
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("at_risk.load_failed"));
    }
  }, [tab, language, t]);

  const loadDetail = useCallback(async (id: string) => {
    try {
      setDetail(await fetchApi<Detail>(`/trainer/flags/${id}?lang=${language}`));
    } catch {
      setDetail(null);
    }
  }, [language]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    fetchApi<{ mentors: { user_id: string; name: string; is_me: boolean }[] }>("/trainer/mentors").then((r) => setMentors(r.mentors)).catch(() => setMentors([]));
  }, []);
  useEffect(() => {
    if (!selectedId) return setDetail(null);
    loadDetail(selectedId);
  }, [selectedId, loadDetail]);
  useEffect(() => { setMentorPick(detail?.mentor?.user_id || ""); }, [detail?.mentor?.user_id]);

  const run = async (fn: () => Promise<string | void>) => {
    setBusy(true);
    setError("");
    setMsg("");
    try {
      const done = await fn();
      if (done) setMsg(done);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("at_risk.save_failed"));
    } finally {
      setBusy(false);
    }
  };

  const act = (type: "parent_call" | "extra_saturday" | "note" | "resolve") => {
    if (!selectedId) return;
    if ((type === "resolve" || type === "note") && !note.trim()) return setError(t("at_risk.err_note"));
    return run(async () => {
      if (type === "resolve") {
        await fetchApi(`/trainer/flags/${selectedId}/resolve`, { method: "POST", body: JSON.stringify({ note }) });
        setNote("");
        setSelectedId(null);
        return t("at_risk.resolved");
      }
      const r = await fetchApi<{ parent_call: string | null }>(`/trainer/flags/${selectedId}/actions`, { method: "POST", body: JSON.stringify({ action_type: type, note: note || null }) });
      setNote("");
      await loadDetail(selectedId);
      return r.parent_call ? t(OUTCOME[r.parent_call]) : t("at_risk.action_saved");
    });
  };

  const logCall = () => {
    if (!selectedId) return;
    if (!callOutcome) return setError(t("at_risk.err_outcome"));
    return run(async () => {
      await fetchApi(`/trainer/flags/${selectedId}/actions`, { method: "POST", body: JSON.stringify({ action_type: "phone_call", outcome: callOutcome, note: note || null }) });
      setNote("");
      setCallOutcome("");
      await loadDetail(selectedId);
      return t("at_risk.call_logged");
    });
  };

  const setMentor = (userId: string | null) => {
    if (!selectedId) return;
    return run(async () => {
      await fetchApi(`/trainer/flags/${selectedId}/mentor`, { method: "POST", body: JSON.stringify({ user_id: userId }) });
      await loadDetail(selectedId);
      return userId ? t("at_risk.mentor_saved") : t("at_risk.mentor_removed");
    });
  };

  const sev: Record<string, string> = { high: "bg-danger-soft text-danger", medium: "bg-warning-soft text-warning", low: "bg-line-soft text-ink-soft" };
  const renotifyAt = detail?.parent_notified_at ? new Date(new Date(`${detail.parent_notified_at.replace(/Z$/, "")}Z`).getTime() + detail.renotify_after_days * DAY_MS) : null;

  return (
    <RoleGuard allowedRoles={["trainer"]}>
      <AppShell pageTitle={t("at_risk.title")}>
        <HowItWorks topic="at_risk" steps={5} className="mb-4 max-w-6xl" />
        <div className="space-y-6 max-w-6xl">
          {data && (
            <div className="grid grid-cols-3 gap-3" data-testid="risk-summary">
              {([["open", data.summary.open], ["high", data.summary.high], ["parents_alerted", data.summary.parents_alerted]] as const).map(([k, v]) => (
                <div key={k} className="bg-white rounded-card border border-line p-3">
                  <div className="text-2xl font-semibold text-ink">{v}</div>
                  <div className="text-caption text-muted">{t(`at_risk.sum_${k}`)}</div>
                </div>
              ))}
            </div>
          )}
          <div className="flex gap-2" role="tablist">
            {(["open", "resolved", "mentees"] as const).map((s) => (
              <button key={s} type="button" role="tab" aria-selected={tab === s} onClick={() => { setTab(s); setSelectedId(null); }} data-testid={`risk-tab-${s}`}
                className={`px-3 py-1.5 rounded-tile text-xs font-semibold ${tab === s ? "bg-brand text-white" : "border border-line-strong"}`}>{t(`at_risk.tab_${s}`)}</button>
            ))}
          </div>
          {msg && <p className="text-xs text-success font-semibold" role="status" data-testid="risk-msg">{msg}</p>}
          {error && <p className="text-xs text-red-600" role="alert" data-testid="risk-error">{error}</p>}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
            {tab === "mentees" ? (
              <ul className="lg:col-span-3 bg-white rounded-card border border-line divide-y divide-line-soft" data-testid="mentee-list">
                {mentees?.length === 0 && <li className="p-6 text-center text-xs text-muted">{t("at_risk.mentees_none")}</li>}
                {mentees?.map((m) => (
                  <li key={m.flag_id}>
                    <button type="button" onClick={() => setSelectedId(m.flag_id)} aria-pressed={selectedId === m.flag_id} data-testid="mentee-row"
                      className={`w-full text-left px-3 py-2.5 flex items-center gap-3 ${selectedId === m.flag_id ? "bg-brand-soft" : "hover:bg-surface-2"}`}>
                      <UserCheck className="w-4 h-4 shrink-0 text-teal" />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-semibold text-ink truncate">{m.name}</div>
                        <div className="text-caption text-muted">{m.issue} · {t("at_risk.score")} {m.score ?? "—"} · {t("at_risk.attendance")} {m.attendance_pct ?? "—"}%{m.batch ? ` · ${m.batch}` : ""}</div>
                      </div>
                      {m.since && <span className="text-caption text-muted">{t("at_risk.mentor_since").replace("{d}", fmt(m.since))}</span>}
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <ul className="lg:col-span-3 bg-white rounded-card border border-line divide-y divide-line-soft" data-testid="risk-list">
                {data?.flags.length === 0 && <li className="p-6 text-center text-xs text-muted">{t("at_risk.none")}</li>}
                {data?.flags.map((f) => (
                  <li key={f.id}>
                    <button type="button" onClick={() => setSelectedId(f.id)} aria-pressed={selectedId === f.id} data-testid="risk-row"
                      className={`w-full text-left px-3 py-2.5 flex items-center gap-3 ${selectedId === f.id ? "bg-brand-soft" : "hover:bg-surface-2"}`}>
                      <AlertTriangle className={`w-4 h-4 shrink-0 ${f.severity === "high" ? "text-danger" : "text-warning"}`} />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-semibold text-ink truncate">{f.name}</div>
                        <div className="text-caption text-muted">
                          {f.issue} · {t("at_risk.score")} {f.score ?? "—"} · {t("at_risk.attendance")} {f.attendance_pct ?? "—"}%{f.batch ? ` · ${f.batch}` : ""}{` · ${t("at_risk.ai_calls")} ${f.ai_calls_7d ?? 0}`}
                          {f.mentor?.name ? ` · ${t("at_risk.mentor_title")}: ${f.mentor.name}` : ""}
                        </div>
                      </div>
                      <span className={`text-caption font-semibold px-2 py-0.5 rounded-full ${sev[f.severity] || sev.low}`}>{t(`at_risk.sev_${f.severity}`)}</span>
                      {f.parent_notified && <Phone className="w-3.5 h-3.5 text-teal" aria-label={t("at_risk.parent_alerted")} />}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {selectedId && detail && (
              <section className="lg:col-span-2 bg-white rounded-card border border-line p-4 space-y-3 h-fit" data-testid="risk-detail">
                <div>
                  <h2 className="text-sm font-semibold text-ink">{detail.name}</h2>
                  <p className="text-xs text-ink-soft">{detail.issue} · {t("at_risk.suggested")}: <span className="font-semibold">{detail.action_label}</span></p>
                  {detail.parent_notified_at && (
                    <p className="text-caption text-teal font-semibold mt-1" data-testid="parent-notified-at">
                      {t("at_risk.notified_on").replace("{d}", fmt(detail.parent_notified_at))}{" "}
                      {renotifyAt && renotifyAt.getTime() > Date.now()
                        ? t("at_risk.renotify_from").replace("{d}", fmt(renotifyAt.toISOString()))
                        : t("at_risk.renotify_now")}
                    </p>
                  )}
                </div>
                {detail.status !== "resolved" && (
                  <>
                    <div className="grid grid-cols-3 gap-2">
                      <button type="button" disabled={busy} onClick={() => act("parent_call")} data-testid="act-parent-call" className="px-2 py-2 bg-brand text-white text-xs font-semibold rounded-tile inline-flex items-center justify-center gap-1 disabled:opacity-50">
                        <Phone className="w-3.5 h-3.5" />{t("at_risk.parent_call")}
                      </button>
                      <button type="button" disabled={busy} onClick={() => act("extra_saturday")} className="px-2 py-2 border border-line-strong text-xs font-semibold rounded-tile disabled:opacity-50">{t("at_risk.extra_saturday")}</button>
                      <button type="button" disabled={busy} onClick={() => act("note")} className="px-2 py-2 border border-line-strong text-xs font-semibold rounded-tile disabled:opacity-50">{t("at_risk.add_note")}</button>
                    </div>
                    <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("at_risk.note_ph")} data-testid="risk-note"
                      className="w-full px-2.5 py-1.5 bg-surface-2 border border-line rounded-tile text-xs" />

                    <fieldset className="border border-line-soft rounded-tile p-2.5 space-y-2" data-testid="log-call">
                      <legend className="px-1 text-caption font-semibold text-muted">{t("at_risk.call_outcome")}</legend>
                      <div className="flex flex-wrap gap-1.5">
                        {CALL_OUTCOMES.map((o) => (
                          <button key={o} type="button" aria-pressed={callOutcome === o} onClick={() => setCallOutcome(o)} data-testid={`call-outcome-${o}`}
                            className={`px-2 py-1 rounded-full text-caption font-semibold ${callOutcome === o ? "bg-brand text-white" : "border border-line-strong text-ink-soft"}`}>
                            {t(`at_risk.out_${o}`)}
                          </button>
                        ))}
                      </div>
                      <button type="button" disabled={busy} onClick={logCall} data-testid="act-log-call" className="w-full px-2 py-1.5 border border-line-strong text-xs font-semibold rounded-tile inline-flex items-center justify-center gap-1 disabled:opacity-50">
                        <PhoneCall className="w-3.5 h-3.5" />{t("at_risk.log_call")}
                      </button>
                    </fieldset>

                    <div className="border border-line-soft rounded-tile p-2.5 space-y-2" data-testid="mentor-box">
                      <div className="text-caption font-semibold text-muted">{t("at_risk.mentor_title")}</div>
                      <p className="text-xs text-ink" data-testid="mentor-current">
                        {detail.mentor ? `${detail.mentor.name ?? ""}${detail.mentor.since ? ` · ${t("at_risk.mentor_since").replace("{d}", fmt(detail.mentor.since))}` : ""}` : t("at_risk.mentor_none")}
                      </p>
                      <div className="flex gap-2">
                        <select value={mentorPick} onChange={(e) => setMentorPick(e.target.value)} data-testid="mentor-select" aria-label={t("at_risk.mentor_pick")}
                          className="flex-1 min-w-0 px-2 py-1.5 bg-surface-2 border border-line rounded-tile text-xs">
                          <option value="">{t("at_risk.mentor_pick")}</option>
                          {mentors.map((m) => <option key={m.user_id} value={m.user_id}>{m.name}{m.is_me ? ` ${t("at_risk.mentor_me")}` : ""}</option>)}
                        </select>
                        <button type="button" disabled={busy || !mentorPick || mentorPick === detail.mentor?.user_id} onClick={() => setMentor(mentorPick)} data-testid="act-mentor"
                          className="px-2.5 py-1.5 bg-brand text-white text-xs font-semibold rounded-tile disabled:opacity-50">{t("at_risk.mentor_assign")}</button>
                        {detail.mentor && (
                          <button type="button" disabled={busy} onClick={() => setMentor(null)} data-testid="act-mentor-remove"
                            className="px-2.5 py-1.5 border border-line-strong text-xs font-semibold rounded-tile disabled:opacity-50">{t("at_risk.mentor_remove")}</button>
                        )}
                      </div>
                    </div>

                    <button type="button" disabled={busy} onClick={() => act("resolve")} data-testid="act-resolve" className="w-full px-2 py-2 bg-success text-white text-xs font-semibold rounded-tile inline-flex items-center justify-center gap-1 disabled:opacity-50">
                      <CheckCircle2 className="w-3.5 h-3.5" />{t("at_risk.resolve")}
                    </button>
                  </>
                )}
                <div>
                  <h3 className="text-caption font-semibold text-muted">{t("at_risk.history")}</h3>
                  <ol className="mt-1 space-y-1" data-testid="risk-history">
                    {detail.actions.length === 0 && <li className="text-caption text-subtle">{t("at_risk.no_history")}</li>}
                    {detail.actions.map((a, i) => (
                      <li key={i} className="text-caption text-ink-soft">
                        <span className="font-semibold">{t(`at_risk.act_${a.type}`)}</span>{a.by ? ` · ${a.by}` : ""}{a.at ? ` · ${fmt(a.at)}` : ""}{a.note ? `: ${a.note}` : ""}
                      </li>
                    ))}
                  </ol>
                </div>
              </section>
            )}
          </div>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
