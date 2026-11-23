"use client";

/** Screen 04 · student profile for trainers: private notes and roster change requests. */
import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { ArrowLeft, Lock, Shuffle } from "lucide-react";

interface Profile {
  student: { id: string; name: string; register_no: string; branch: string; semester: number; batch: string; batch_id: string; readiness_score: number; readiness_band: string; attendance_pct: number; problems_solved: number };
  parents: { name: string; relationship: string }[];
  notes: { id: string; text: string; author: string; mine: boolean; at: string }[];
  open_roster_request: { id: string; kind: string; to_batch_id: string | null } | null;
  move_targets: { id: string; short_name: string }[];
}

export default function TrainerStudentPage() {
  const { t } = useLanguage();
  const { studentId } = useParams<{ studentId: string }>();
  const [p, setP] = useState<Profile | null>(null);
  const [note, setNote] = useState("");
  const [req, setReq] = useState({ kind: "move", to_batch_id: "", reason: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setP(await fetchApi<Profile>(`/trainer/students/${studentId}`));
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("trainer_batches.load_failed"));
    }
  }, [studentId, t]);

  useEffect(() => { load(); }, [load]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try { await fn(); await load(); } catch (e) { setError(e instanceof ApiError ? e.detail : t("trainer_batches.save_failed")); } finally { setBusy(false); }
  };

  const addNote = (e: React.FormEvent) => {
    e.preventDefault();
    if (!note.trim()) return;
    run(async () => { await fetchApi(`/trainer/students/${studentId}/notes`, { method: "POST", body: JSON.stringify({ text: note.trim() }) }); setNote(""); });
  };

  const requestChange = (e: React.FormEvent) => {
    e.preventDefault();
    if (req.reason.trim().length < 10) return setError(t("trainer_batches.err_reason"));
    const to = req.kind === "move" ? (req.to_batch_id || p?.move_targets[0]?.id || "") : null;
    if (req.kind === "move" && !to) return setError(t("trainer_batches.err_target"));
    run(async () => {
      await fetchApi("/trainer/roster-requests", { method: "POST", body: JSON.stringify({ student_id: studentId, kind: req.kind, to_batch_id: to, reason: req.reason.trim() }) });
      setReq({ kind: "move", to_batch_id: "", reason: "" });
    });
  };

  const s = p?.student;
  return (
    <RoleGuard allowedRoles={["trainer"]}>
      <AppShell pageTitle={t("trainer_batches.profile_title")}>
        <div className="p-4 md:p-6 space-y-4 max-w-5xl">
          <Link href="/trainer/batches" className="inline-flex items-center gap-1 text-xs text-[#2B5CD0] font-bold"><ArrowLeft className="w-3.5 h-3.5" />{t("trainer_batches.back")}</Link>
          {error && <p className="text-xs text-red-600" role="alert" data-testid="profile-error">{error}</p>}
          {s && p && (
            <>
              <div className="bg-white rounded-xl border border-[#E2E8F0] p-4">
                <h2 className="text-lg font-black text-[#0F1F3A]" data-testid="student-name">{s.name}</h2>
                <p className="text-xs text-[#64748B]">{s.register_no} · {s.branch} · {t("trainer_batches.sem")} {s.semester} · {s.batch}</p>
                <div className="grid grid-cols-3 gap-2 mt-3 text-xs">
                  <div><div className="text-[#64748B]">{t("trainer_batches.readiness")}</div><div className="font-black text-base">{s.readiness_score}</div><div>{s.readiness_band}</div></div>
                  <div><div className="text-[#64748B]">{t("trainer_batches.attendance")}</div><div className="font-black text-base">{s.attendance_pct}%</div></div>
                  <div><div className="text-[#64748B]">{t("trainer_batches.problems")}</div><div className="font-black text-base">{s.problems_solved}</div></div>
                </div>
                {p.parents.length > 0 && <p className="text-[11px] text-[#64748B] mt-2">{t("trainer_batches.parents")}: {p.parents.map((x) => `${x.name} (${x.relationship})`).join(", ")}</p>}
              </div>

              <section className="bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-2" data-testid="notes-section">
                <h3 className="text-sm font-black text-[#0F1F3A] flex items-center gap-2"><Lock className="w-4 h-4 text-[#2B5CD0]" />{t("trainer_batches.notes")}</h3>
                <p className="text-[11px] text-[#64748B]">{t("trainer_batches.notes_private")}</p>
                <form onSubmit={addNote} className="flex gap-2">
                  <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} placeholder={t("trainer_batches.note_placeholder")} data-testid="note-text"
                    className="flex-1 px-2.5 py-1.5 border border-[#E2E8F0] rounded-lg text-xs" />
                  <button type="submit" disabled={busy || !note.trim()} data-testid="note-save" className="px-3 py-1.5 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg disabled:opacity-50">{t("trainer_batches.add_note")}</button>
                </form>
                <ul className="space-y-1.5 text-xs">
                  {p.notes.map((n) => (
                    <li key={n.id} className="border border-[#F1F5F9] rounded-lg p-2 flex justify-between gap-2" data-testid="note-row">
                      <div><div>{n.text}</div><div className="text-[10px] text-[#64748B]">{n.author} · {n.at.slice(0, 16).replace("T", " ")}</div></div>
                      {n.mine && <button type="button" onClick={() => run(async () => { await fetchApi(`/trainer/notes/${n.id}`, { method: "DELETE" }); })}
                        className="text-[11px] text-[#DC2626] font-bold" data-testid="note-delete">{t("trainer_batches.delete")}</button>}
                    </li>
                  ))}
                </ul>
              </section>

              <section className="bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-2" data-testid="roster-request-section">
                <h3 className="text-sm font-black text-[#0F1F3A] flex items-center gap-2"><Shuffle className="w-4 h-4 text-[#2B5CD0]" />{t("trainer_batches.roster_change")}</h3>
                {p.open_roster_request ? (
                  <p className="text-xs text-[#92400E] font-bold" data-testid="request-pending">{t("trainer_batches.request_pending")}</p>
                ) : (
                  <form onSubmit={requestChange} className="grid grid-cols-1 md:grid-cols-4 gap-2" data-testid="roster-request-form">
                    <select value={req.kind} onChange={(e) => setReq({ ...req, kind: e.target.value })} data-testid="request-kind" aria-label={t("trainer_batches.change")}
                      className="px-2.5 py-1.5 border border-[#E2E8F0] rounded-lg text-xs bg-white">
                      <option value="move">{t("trainer_batches.kind_move")}</option>
                      <option value="remove">{t("trainer_batches.kind_remove")}</option>
                    </select>
                    {req.kind === "move" && (
                      <select value={req.to_batch_id} onChange={(e) => setReq({ ...req, to_batch_id: e.target.value })} data-testid="request-target" aria-label={t("trainer_batches.to_batch")}
                        className="px-2.5 py-1.5 border border-[#E2E8F0] rounded-lg text-xs bg-white">
                        {p.move_targets.map((b) => <option key={b.id} value={b.id}>{b.short_name}</option>)}
                      </select>
                    )}
                    <input value={req.reason} onChange={(e) => setReq({ ...req, reason: e.target.value })} placeholder={t("trainer_batches.reason")} data-testid="request-reason"
                      className="px-2.5 py-1.5 border border-[#E2E8F0] rounded-lg text-xs md:col-span-1" />
                    <button type="submit" disabled={busy} data-testid="request-send" className="px-3 py-1.5 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg disabled:opacity-50">{t("trainer_batches.send_request")}</button>
                  </form>
                )}
                <p className="text-[11px] text-[#64748B]">{t("trainer_batches.request_help")}</p>
              </section>
            </>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
