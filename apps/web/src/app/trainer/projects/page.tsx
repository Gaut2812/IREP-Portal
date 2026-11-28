"use client";

/** Trainer · Projects: create project teams from my batches (title, client, description, goals, repo, sprints),
 *  edit them, start the next sprint, and open each team's Sprint Board (screen 30). */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { ConfirmDelete, DeleteButton, EmptyState } from "@/components/ui";
import { FolderKanban, Pencil, Plus, SkipForward, ExternalLink } from "lucide-react";

interface Member { student_id: string; name: string; initials: string; role: string; batch: string | null }
interface Project {
  id: string; name: string; project_title: string; client: string; description: string | null; goals: string | null; repo: string | null;
  members: Member[]; sprint: { id: string; number: number; total: number; goal: string | null } | null; progress_pct: number; tasks: number; has_history: boolean;
}
interface StudentRow { student_id: string; name: string; batch: string | null; team_id: string | null }

const EMPTY = { name: "", project_title: "", client_name: "Trainer", description: "", goals: "", repo_full_name: "", total_sprints: 3, sprint_goal: "",
  member_ids: [] as string[], lead_id: "" };

export default function TrainerProjectsPage() {
  const { t } = useLanguage();
  const [projects, setProjects] = useState<Project[]>([]);
  const [students, setStudents] = useState<StudentRow[]>([]);
  const [form, setForm] = useState<typeof EMPTY | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [del, setDel] = useState<Project | null>(null);
  const [nextFor, setNextFor] = useState<Project | null>(null);
  const [nextGoal, setNextGoal] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await fetchApi<{ projects: Project[]; students: StudentRow[] }>("/trainer/projects");
      setProjects(r.projects);
      setStudents(r.students);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("projects.load_failed"));
    }
  }, [t]);
  useEffect(() => { load(); }, [load]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setError(""); setMsg("");
    try { await fn(); } catch (e) { setError(e instanceof ApiError ? e.detail : t("projects.save_failed")); } finally { setBusy(false); }
  };

  const openNew = () => { setEditing(null); setForm({ ...EMPTY }); };
  const openEdit = (p: Project) => {
    setEditing(p.id);
    setForm({ name: p.name, project_title: p.project_title, client_name: p.client, description: p.description || "", goals: p.goals || "",
      repo_full_name: p.repo || "", total_sprints: p.sprint?.total || 3, sprint_goal: p.sprint?.goal || "",
      member_ids: p.members.map((m) => m.student_id), lead_id: p.members.find((m) => m.role === "lead")?.student_id || "" });
  };

  const save = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form) return;
    if (form.name.trim().length < 2 || form.project_title.trim().length < 3) return setError(t("projects.err_title"));
    if (!form.member_ids.length) return setError(t("projects.err_members"));
    run(async () => {
      const details = { name: form.name, project_title: form.project_title, client_name: form.client_name || "Trainer", description: form.description,
        goals: form.goals, repo_full_name: form.repo_full_name, sprint_goal: form.sprint_goal };
      if (editing) {
        await fetchApi(`/trainer/projects/${editing}`, { method: "PUT", body: JSON.stringify(details) });
        await fetchApi(`/trainer/projects/${editing}/members`, { method: "PUT", body: JSON.stringify({ member_ids: form.member_ids, lead_id: form.lead_id || null }) });
        setMsg(t("projects.saved"));
      } else {
        await fetchApi("/trainer/projects", { method: "POST", body: JSON.stringify({ ...details, repo_full_name: form.repo_full_name || null,
          total_sprints: form.total_sprints, member_ids: form.member_ids, lead_id: form.lead_id || null }) });
        setMsg(t("projects.created"));
      }
      setForm(null);
      setEditing(null);
      await load();
    });
  };

  const startNext = () => nextFor && run(async () => {
    await fetchApi(`/trainer/projects/${nextFor.id}/next-sprint`, { method: "POST", body: JSON.stringify({ goal: nextGoal }) });
    setMsg(t("projects.next_started"));
    setNextFor(null);
    setNextGoal("");
    await load();
  });

  // students free to join, plus the ones already in the team being edited, grouped by batch
  const pickable = useMemo(() => {
    const groups: Record<string, StudentRow[]> = {};
    for (const s of students) {
      if (s.team_id && s.team_id !== editing) continue;
      (groups[s.batch || "—"] ||= []).push(s);
    }
    return groups;
  }, [students, editing]);

  const toggleMember = (id: string) => form && setForm({
    ...form,
    member_ids: form.member_ids.includes(id) ? form.member_ids.filter((x) => x !== id) : [...form.member_ids, id],
    lead_id: form.lead_id === id && form.member_ids.includes(id) ? "" : form.lead_id,
  });

  const cls = "w-full px-2.5 py-1.5 bg-surface-2 border border-line rounded-tile text-xs";
  const nameOf = (id: string) => students.find((s) => s.student_id === id)?.name || id;

  return (
    <RoleGuard allowedRoles={["trainer"]}>
      <AppShell pageTitle={t("projects.title")} pageSubtitle={t("projects.subtitle")}
        pageActions={<button type="button" onClick={openNew} data-testid="project-new" className="px-3 py-1.5 bg-brand text-white text-xs font-semibold rounded-tile inline-flex items-center gap-1"><Plus className="w-3.5 h-3.5" />{t("projects.new")}</button>}>
        <div className="space-y-4 max-w-6xl">
          {msg && <p className="text-xs text-success font-semibold" role="status" data-testid="project-msg">{msg}</p>}
          {error && !form && <p className="text-xs text-danger" role="alert" data-testid="project-error">{error}</p>}

          {projects.length === 0 && <EmptyState title={t("projects.none")} />}
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-3" data-testid="project-list">
            {projects.map((p) => (
              <li key={p.id} className="bg-white rounded-card border border-line p-4 space-y-2" data-testid="project-card">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-ink flex items-center gap-1.5"><FolderKanban className="w-4 h-4 text-brand" />{p.project_title}</div>
                    <div className="text-caption text-muted">{p.name} · {t("projects.client")}: {p.client}</div>
                  </div>
                  {p.sprint && <span className="chip-purple shrink-0">{t("projects.sprint_of").replace("{n}", String(p.sprint.number)).replace("{t}", String(p.sprint.total))}</span>}
                </div>
                {p.description && <p className="text-xs text-ink-soft line-clamp-2">{p.description}</p>}
                <div className="flex flex-wrap gap-1">{p.members.map((m) => <span key={m.student_id} className={m.role === "lead" ? "chip-blue" : "chip-green"}>{m.name}</span>)}</div>
                <div className="h-1.5 bg-line-soft rounded-full overflow-hidden" aria-label={`${p.progress_pct}%`}><div className="h-full bg-teal" style={{ width: `${p.progress_pct}%` }} /></div>
                <div className="text-caption text-muted">{p.progress_pct}% · {p.tasks} {t("projects.cards")}</div>
                <div className="flex flex-wrap gap-2 pt-1">
                  <Link href={`/student/projects/${p.id}/board`} className="px-2.5 py-1 border border-brand text-brand text-xs font-semibold rounded-tile inline-flex items-center gap-1" data-testid="project-open-board">
                    <ExternalLink className="w-3.5 h-3.5" />{t("projects.open_board")}
                  </Link>
                  <button type="button" onClick={() => openEdit(p)} className="px-2.5 py-1 border border-line-strong text-xs font-semibold rounded-tile inline-flex items-center gap-1" data-testid="project-edit"><Pencil className="w-3.5 h-3.5" />{t("projects.edit")}</button>
                  {p.sprint && p.sprint.number < p.sprint.total && (
                    <button type="button" onClick={() => setNextFor(p)} className="px-2.5 py-1 border border-line-strong text-xs font-semibold rounded-tile inline-flex items-center gap-1" data-testid="project-next-sprint"><SkipForward className="w-3.5 h-3.5" />{t("projects.next_sprint")}</button>
                  )}
                  {!p.has_history && <DeleteButton onClick={() => setDel(p)} testId="project-delete" className="ml-auto" />}
                </div>
              </li>
            ))}
          </ul>
        </div>

        {form && (
          <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-labelledby="project-form-title">
            <button type="button" className="absolute inset-0 bg-ink/40" aria-label={t("projects.cancel")} onClick={() => setForm(null)} tabIndex={-1} />
            <form onSubmit={save} noValidate className="relative w-full max-w-lg h-full bg-white shadow-pop p-5 overflow-y-auto space-y-3" data-testid="project-form">
              <h2 id="project-form-title" className="text-heading font-semibold text-ink">{editing ? t("projects.edit_title") : t("projects.new")}</h2>
              <div className="grid grid-cols-2 gap-2">
                <label className="text-caption font-semibold text-ink-soft">{t("projects.team_name")}<input className={cls} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="project-name" /></label>
                <label className="text-caption font-semibold text-ink-soft">{t("projects.client")}<input className={cls} value={form.client_name} onChange={(e) => setForm({ ...form, client_name: e.target.value })} /></label>
              </div>
              <label className="block text-caption font-semibold text-ink-soft">{t("projects.project_title")}<input className={cls} value={form.project_title} onChange={(e) => setForm({ ...form, project_title: e.target.value })} data-testid="project-title" /></label>
              <label className="block text-caption font-semibold text-ink-soft">{t("projects.description")}<textarea className={cls} rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} data-testid="project-description-input" /></label>
              <label className="block text-caption font-semibold text-ink-soft">{t("projects.goals")}<textarea className={cls} rows={3} value={form.goals} placeholder={t("projects.goals_hint")} onChange={(e) => setForm({ ...form, goals: e.target.value })} data-testid="project-goals-input" /></label>
              <div className="grid grid-cols-2 gap-2">
                <label className="text-caption font-semibold text-ink-soft">{t("projects.repo")}<input className={cls} value={form.repo_full_name} placeholder="org/repo" onChange={(e) => setForm({ ...form, repo_full_name: e.target.value })} /></label>
                {!editing && (
                  <label className="text-caption font-semibold text-ink-soft">{t("projects.sprints")}
                    <select className={cls} value={form.total_sprints} onChange={(e) => setForm({ ...form, total_sprints: Number(e.target.value) })}>{[1, 2, 3, 4, 5, 6].map((n) => <option key={n} value={n}>{n}</option>)}</select>
                  </label>
                )}
              </div>
              <label className="block text-caption font-semibold text-ink-soft">{t("projects.sprint_goal")}<input className={cls} value={form.sprint_goal} onChange={(e) => setForm({ ...form, sprint_goal: e.target.value })} /></label>

              <fieldset className="space-y-2">
                <legend className="text-caption font-semibold text-ink-soft">{t("projects.members")} ({form.member_ids.length})</legend>
                <div className="max-h-56 overflow-y-auto border border-line rounded-tile p-2 space-y-2" data-testid="project-members">
                  {Object.entries(pickable).map(([batch, rows]) => (
                    <div key={batch}>
                      <div className="text-caption font-semibold text-muted">{batch}</div>
                      {rows.map((s) => (
                        <label key={s.student_id} className="flex items-center gap-2 text-xs py-0.5">
                          <input type="checkbox" checked={form.member_ids.includes(s.student_id)} onChange={() => toggleMember(s.student_id)} data-testid={`member-${s.student_id}`} />{s.name}
                        </label>
                      ))}
                    </div>
                  ))}
                </div>
                <label className="block text-caption font-semibold text-ink-soft">{t("projects.lead")}
                  <select className={cls} value={form.lead_id} onChange={(e) => setForm({ ...form, lead_id: e.target.value })} data-testid="project-lead">
                    <option value="">—</option>
                    {form.member_ids.map((id) => <option key={id} value={id}>{nameOf(id)}</option>)}
                  </select>
                </label>
              </fieldset>
              {error && <p className="text-xs text-danger" role="alert" data-testid="project-form-error">{error}</p>}
              <div className="flex gap-2 pt-1">
                <button type="button" onClick={() => { setForm(null); setError(""); }} className="flex-1 py-2 border border-line-strong text-xs font-semibold rounded-tile">{t("projects.cancel")}</button>
                <button type="submit" disabled={busy} className="flex-1 py-2 bg-brand text-white text-xs font-semibold rounded-tile disabled:opacity-50" data-testid="project-save">{editing ? t("projects.save") : t("projects.create")}</button>
              </div>
            </form>
          </div>
        )}

        {nextFor && (
          <div className="fixed inset-0 z-50 bg-ink/50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="next-sprint-title">
            <div className="bg-white rounded-card border border-line shadow-pop max-w-md w-full p-5 space-y-3">
              <h2 id="next-sprint-title" className="text-heading font-semibold text-ink">{t("projects.next_sprint")}: {nextFor.project_title}</h2>
              <p className="text-xs text-ink-soft">{t("projects.next_sprint_help")}</p>
              <label className="block text-caption font-semibold text-ink-soft">{t("projects.sprint_goal")}<input className={cls} value={nextGoal} onChange={(e) => setNextGoal(e.target.value)} data-testid="next-sprint-goal" /></label>
              <div className="flex gap-2">
                <button type="button" onClick={() => setNextFor(null)} className="flex-1 py-2 border border-line-strong text-xs font-semibold rounded-tile">{t("projects.cancel")}</button>
                <button type="button" onClick={startNext} disabled={busy} className="flex-1 py-2 bg-brand text-white text-xs font-semibold rounded-tile disabled:opacity-50" data-testid="next-sprint-start">{t("projects.start_sprint")}</button>
              </div>
            </div>
          </div>
        )}

        {del && (
          <ConfirmDelete itemName={del.project_title} note={t("projects.delete_note")}
            onConfirm={async () => { await fetchApi(`/trainer/projects/${del.id}`, { method: "DELETE" }); setMsg(t("projects.deleted")); await load(); }}
            onClose={() => setDel(null)} />
        )}
      </AppShell>
    </RoleGuard>
  );
}
