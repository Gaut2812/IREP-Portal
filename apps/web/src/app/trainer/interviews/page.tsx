"use client";

/** Screen 37 · Mock interviews (trainer): open slots, score booked interviews with the rubric, attach the
 *  recording. Scores, feedback, notes and the recording reach the student's 36 (L16); slots made by a
 *  mock drive (38) carry the drive's name (L17). Spec: docs/screens/37-38-39-interviews-drives-readiness.md */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";

interface Slot { id: string; starts_at: string; duration_min: number; round_type: string; round_label: string; batch_id: string | null;
  booked_by: string | null; drive: string | null; can_cancel: boolean }
interface Iv { id: string; student: string; round_number: number; round_type: string; round_label: string; scheduled_at: string;
  duration_min: number; overall: number | null; has_recording: boolean; drive: string | null }
interface View { rubric: { max: number; criteria: { key: string; label: string }[] }; batches: { id: string; name: string }[];
  slots: Slot[]; to_score: Iv[]; upcoming: Iv[]; submitted: Iv[] }
interface Note { at: string; text: string }

const when = (iso: string, lang: string) =>
  new Date(iso).toLocaleString(lang === "ta" ? "ta-IN" : "en-IN", { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

function toSeconds(mmss: string): number | null {
  const m = /^(\d{1,3}):([0-5]\d)$/.exec(mmss.trim());
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

export default function TrainerInterviewsPage() {
  const { t, language } = useLanguage();
  const [v, setV] = useState<View | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [slot, setSlot] = useState({ starts_at: "", round_type: "technical", duration_min: "40", batch_id: "" });
  const [scoring, setScoring] = useState<Iv | null>(null);
  const [scores, setScores] = useState<Record<string, number>>({});
  const [fb, setFb] = useState({ en: "", ta: "" });
  const [notes, setNotes] = useState<Note[]>([]);

  const load = useCallback(async () => {
    try { setV(await fetchApi<View>(`/trainer/interviews?lang=${language}`)); }
    catch (e) { setError(e instanceof ApiError ? String(e.detail) : t("trainer_interviews.load_failed")); }
  }, [language, t]);
  useEffect(() => { load(); }, [load]);

  const run = async (fn: () => Promise<void>, done?: string) => {
    setBusy(true); setError(""); setMsg("");
    try { await fn(); if (done) setMsg(done); await load(); }
    catch (e) { setError(e instanceof ApiError ? String(e.detail) : t("trainer_interviews.action_failed")); }
    finally { setBusy(false); }
  };

  const addSlot = (e: React.FormEvent) => {
    e.preventDefault();
    if (!slot.starts_at) { setError(t("trainer_interviews.err_start")); return; }
    run(() => fetchApi("/trainer/interview-slots", { method: "POST", body: JSON.stringify({
      starts_at: slot.starts_at, round_type: slot.round_type, duration_min: Number(slot.duration_min), batch_id: slot.batch_id || null }) })
      .then(() => setSlot({ ...slot, starts_at: "" })), t("trainer_interviews.slot_added"));
  };

  const openScoring = (iv: Iv) => { setScoring(iv); setScores({}); setFb({ en: "", ta: "" }); setNotes([]); setError(""); };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!scoring || !v) return;
    if (v.rubric.criteria.some((c) => !scores[c.key])) { setError(t("trainer_interviews.err_scores")); return; }
    if (fb.en.trim().length < 5) { setError(t("trainer_interviews.err_feedback")); return; }
    const comments: { at_seconds: number; text: string }[] = [];
    for (const n of notes.filter((n) => n.text.trim())) {
      const s = toSeconds(n.at);
      if (s === null) { setError(t("trainer_interviews.err_note_time")); return; }
      comments.push({ at_seconds: s, text: n.text.trim() });
    }
    run(() => fetchApi(`/trainer/interviews/${scoring.id}/submit`, { method: "POST", body: JSON.stringify({
      scores, feedback_en: fb.en.trim(), feedback_ta: fb.ta.trim() || null, comments }) }).then(() => setScoring(null)),
      t("trainer_interviews.submitted"));
  };

  const upload = (iv: Iv, file: File | undefined) => {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    run(() => fetchApi(`/trainer/interviews/${iv.id}/recording`, { method: "POST", body: form }), t("trainer_interviews.recording_added"));
  };

  const card = "bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-3";
  const field = "px-2.5 py-1.5 border border-[#CBD5E1] rounded-lg text-xs";
  const badge = (text: string) => <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#EEF2FF] text-[#3730A3]" data-testid="drive-badge">{text}</span>;

  const ivRow = (iv: Iv, action?: React.ReactNode) => (
    <li key={iv.id} className="border border-[#F1F5F9] rounded-lg p-2.5 text-xs flex flex-wrap items-center justify-between gap-2" data-testid={`iv-${iv.id}`}>
      <div className="space-y-0.5">
        <div className="font-bold text-[#0F1F3A]">{iv.student} · #{iv.round_number} {iv.round_label} {iv.drive && badge(iv.drive)}</div>
        <div className="text-[#64748B]">{when(iv.scheduled_at, language)} · {iv.duration_min} {t("trainer_interviews.min")}
          {iv.overall !== null && <> · {t("trainer_interviews.overall")} <b data-testid="iv-overall">{iv.overall.toFixed(1)}</b> / {v?.rubric.max}</>}</div>
      </div>
      <div className="flex items-center gap-2">
        <label className="px-2.5 py-1 border border-[#CBD5E1] rounded-lg font-bold cursor-pointer">
          {iv.has_recording ? t("trainer_interviews.replace_recording") : t("trainer_interviews.add_recording")}
          <input type="file" accept="video/mp4,video/webm,audio/mpeg,audio/mp4" className="hidden" data-testid="iv-recording"
            onChange={(e) => upload(iv, e.target.files?.[0])} />
        </label>
        {action}
      </div>
    </li>
  );

  return (
    <RoleGuard allowedRoles={["trainer"]}>
      <AppShell pageTitle={t("trainer_interviews.title")}>
        <div className="space-y-4 max-w-5xl">
          <p className="text-xs text-[#64748B]">{t("trainer_interviews.help")}</p>
          {error && <p className="text-xs text-red-600" role="alert" data-testid="ti-error">{error}</p>}
          {msg && <p className="text-xs text-[#166534]" role="status" data-testid="ti-msg">{msg}</p>}

          {scoring && v && (
            <form onSubmit={submit} noValidate className={`${card} border-[#2B5CD0]`} data-testid="score-form">
              <h2 className="text-sm font-black text-[#0F1F3A]">{t("trainer_interviews.score_title")} · {scoring.student} · #{scoring.round_number} {scoring.round_label}</h2>
              <div className="grid sm:grid-cols-2 gap-2">
                {v.rubric.criteria.map((c) => (
                  <label key={c.key} className="text-xs flex items-center justify-between gap-2 border border-[#F1F5F9] rounded-lg px-2.5 py-1.5">
                    <span>{c.label}</span>
                    <select value={scores[c.key] || ""} onChange={(e) => setScores({ ...scores, [c.key]: Number(e.target.value) })}
                      className={field} data-testid={`score-${c.key}`} aria-label={c.label}>
                      <option value="">–</option>
                      {Array.from({ length: v.rubric.max }, (_, i) => i + 1).map((n) => <option key={n} value={n}>{n}</option>)}
                    </select>
                  </label>
                ))}
              </div>
              <textarea value={fb.en} onChange={(e) => setFb({ ...fb, en: e.target.value })} rows={3} placeholder={t("trainer_interviews.feedback_en")}
                aria-label={t("trainer_interviews.feedback_en")} data-testid="feedback-en" className={`${field} w-full`} />
              <textarea value={fb.ta} onChange={(e) => setFb({ ...fb, ta: e.target.value })} rows={2} placeholder={t("trainer_interviews.feedback_ta")}
                aria-label={t("trainer_interviews.feedback_ta")} data-testid="feedback-ta" className={`${field} w-full`} />
              <div className="space-y-1.5">
                <div className="text-xs font-bold text-[#0F1F3A]">{t("trainer_interviews.notes")}</div>
                {notes.map((n, i) => (
                  <div key={i} className="flex gap-2">
                    <input value={n.at} onChange={(e) => setNotes(notes.map((x, j) => j === i ? { ...x, at: e.target.value } : x))} placeholder="12:30"
                      aria-label={t("trainer_interviews.note_time")} data-testid={`note-at-${i}`} className={`${field} w-20`} />
                    <input value={n.text} onChange={(e) => setNotes(notes.map((x, j) => j === i ? { ...x, text: e.target.value } : x))}
                      aria-label={t("trainer_interviews.note_text")} data-testid={`note-text-${i}`} className={`${field} flex-1`} />
                  </div>
                ))}
                <button type="button" onClick={() => setNotes([...notes, { at: "", text: "" }])} className="text-xs text-[#2B5CD0] font-bold" data-testid="note-add">
                  + {t("trainer_interviews.add_note")}
                </button>
              </div>
              <div className="flex gap-2 justify-end">
                <button type="button" onClick={() => setScoring(null)} className="px-3 py-1.5 border border-[#CBD5E1] rounded-lg text-xs font-bold">{t("trainer_interviews.cancel")}</button>
                <button type="submit" disabled={busy} data-testid="score-submit" className="px-3.5 py-1.5 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg disabled:opacity-50">{t("trainer_interviews.submit")}</button>
              </div>
              <p className="text-[11px] text-[#64748B]">{t("trainer_interviews.submit_note")}</p>
            </form>
          )}

          <section className={card} data-testid="to-score">
            <h2 className="text-sm font-black text-[#0F1F3A]">{t("trainer_interviews.to_score")}</h2>
            {v && v.to_score.length === 0 && <p className="text-xs text-[#64748B]">{t("trainer_interviews.none_to_score")}</p>}
            <ul className="space-y-2">{v?.to_score.map((iv) => ivRow(iv,
              <button type="button" onClick={() => openScoring(iv)} data-testid="iv-score" className="px-2.5 py-1 bg-[#2B5CD0] text-white rounded-lg font-bold">{t("trainer_interviews.score")}</button>))}</ul>
          </section>

          <section className={card} data-testid="slots">
            <h2 className="text-sm font-black text-[#0F1F3A]">{t("trainer_interviews.slots")}</h2>
            <form onSubmit={addSlot} noValidate className="flex flex-wrap gap-2 items-end" data-testid="slot-form">
              <input type="datetime-local" value={slot.starts_at} onChange={(e) => setSlot({ ...slot, starts_at: e.target.value })}
                aria-label={t("trainer_interviews.starts_at")} data-testid="slot-start" className={field} />
              <select value={slot.round_type} onChange={(e) => setSlot({ ...slot, round_type: e.target.value })} aria-label={t("trainer_interviews.round")} data-testid="slot-type" className={field}>
                {["technical", "hr", "ai_coding"].map((k) => <option key={k} value={k}>{t(`trainer_interviews.round_${k}`)}</option>)}
              </select>
              <select value={slot.duration_min} onChange={(e) => setSlot({ ...slot, duration_min: e.target.value })} aria-label={t("trainer_interviews.length")} data-testid="slot-length" className={field}>
                {["20", "30", "40", "60"].map((m) => <option key={m} value={m}>{m} {t("trainer_interviews.min")}</option>)}
              </select>
              <select value={slot.batch_id} onChange={(e) => setSlot({ ...slot, batch_id: e.target.value })} aria-label={t("trainer_interviews.batch")} data-testid="slot-batch" className={field}>
                <option value="">{t("trainer_interviews.all_batches")}</option>
                {v?.batches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
              <button type="submit" disabled={busy} data-testid="slot-add" className="px-3.5 py-1.5 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg disabled:opacity-50">{t("trainer_interviews.add_slot")}</button>
            </form>
            <ul className="space-y-2">
              {v?.slots.map((s) => (
                <li key={s.id} className="border border-[#F1F5F9] rounded-lg p-2.5 text-xs flex flex-wrap items-center justify-between gap-2" data-testid={`slot-${s.id}`}>
                  <div>
                    <div className="font-bold text-[#0F1F3A]">{when(s.starts_at, language)} · {s.round_label} · {s.duration_min} {t("trainer_interviews.min")} {s.drive && badge(s.drive)}</div>
                    <div className="text-[#64748B]" data-testid="slot-booked">{s.booked_by ? `${t("trainer_interviews.booked_by")} ${s.booked_by}` : t("trainer_interviews.open")}</div>
                  </div>
                  {s.can_cancel && <button type="button" disabled={busy} data-testid="slot-cancel" className="px-2.5 py-1 border border-[#CBD5E1] rounded-lg font-bold"
                    onClick={() => { if (window.confirm(s.booked_by ? t("trainer_interviews.confirm_cancel_booked") : t("trainer_interviews.confirm_cancel"))) run(() => fetchApi(`/trainer/interview-slots/${s.id}`, { method: "DELETE" }), t("trainer_interviews.slot_cancelled")); }}>
                    {t("trainer_interviews.cancel_slot")}</button>}
                </li>
              ))}
            </ul>
          </section>

          {v && v.upcoming.length > 0 && (
            <section className={card} data-testid="upcoming">
              <h2 className="text-sm font-black text-[#0F1F3A]">{t("trainer_interviews.upcoming")}</h2>
              <ul className="space-y-2">{v.upcoming.map((iv) => ivRow(iv))}</ul>
            </section>
          )}

          <section className={card} data-testid="submitted">
            <h2 className="text-sm font-black text-[#0F1F3A]">{t("trainer_interviews.submitted_title")}</h2>
            {v && v.submitted.length === 0 && <p className="text-xs text-[#64748B]">{t("trainer_interviews.none_submitted")}</p>}
            <ul className="space-y-2">{v?.submitted.map((iv) => ivRow(iv))}</ul>
          </section>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
