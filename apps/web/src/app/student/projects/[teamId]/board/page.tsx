"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  DndContext, DragEndEvent, KeyboardSensor, PointerSensor, useDraggable, useDroppable, useSensor, useSensors, closestCorners,
} from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { useAuth } from "@/lib/AuthContext";
import { fetchApi, WS_BASE } from "@/lib/api";
import { CheckCircle2, AlertCircle, RefreshCw, Users, GitPullRequest, Sparkles, X, XCircle, ExternalLink } from "lucide-react";

type ColKey = "todo" | "in_progress" | "code_review" | "done";
interface Task {
  id: string; title: string; tag: string; tag_type: string; assignee_initials: string; assignee_name: string;
  story_points: number; pr_number: string | null; pr_status: string | null; position: number;
}
interface Board {
  team: { id: string; name: string; project_title: string; client: string; repo: string | null; members: number };
  sprint: { id: string; number: number; total: number; ends_week: number; goal: string | null } | null;
  change_request: { id: string; code: string; title: string; description: string | null; status: string } | null;
  columns: { key: ColKey; label: string; tasks: Task[] }[];
  metrics: { progress_pct: number; points_done: number; points_total: number; velocity_last: number | null; tasks_done: number; tasks_total: number };
  build: { status: string; run_number: number; workflow: string; environment: string | null; url: string | null; finished_ago: string | null } | null;
  standups_today: number;
}

const TAG: Record<string, string> = { ai: "chip-purple", backend: "chip-blue", frontend: "chip-amber", qa: "chip-red", devops: "chip-green", feature: "chip-blue" };
const AVATAR: Record<ColKey, string> = { todo: "bg-navy", in_progress: "bg-teal", code_review: "bg-violet", done: "bg-muted" };
const COUNT: Record<ColKey, string> = {
  todo: "bg-white border-line text-muted", in_progress: "bg-brand-soft border-brand-line text-info",
  code_review: "bg-warning-soft border-warning-line text-warning", done: "bg-success-soft border-success-line text-success",
};
const COLS: ColKey[] = ["todo", "in_progress", "code_review", "done"];

function fill(template: string, vars: Record<string, string | number>) {
  return Object.entries(vars).reduce((acc, [k, v]) => acc.replace(`{${k}}`, String(v)), template);
}

function Card({ task, col, onMove, t }: { task: Task; col: ColKey; onMove: (id: string, to: ColKey) => void; t: (k: string) => string }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: task.id, data: { col } });
  const style = { transform: CSS.Translate.toString(transform), zIndex: isDragging ? 50 : undefined };
  const prLabel = task.pr_number ? (task.pr_status === "approved" ? "pr_approved" : task.pr_status === "changes_requested" ? "pr_changes" : "pr_pending") : null;
  return (
    <div ref={setNodeRef} style={style} data-testid={`card-${task.id}`}
      className={`bg-white p-3 rounded-card border border-line shadow-card space-y-2 ${isDragging ? "opacity-80 shadow-pop ring-2 ring-brand" : "hover:border-brand"}`}>
      <div {...listeners} {...attributes} className="cursor-grab active:cursor-grabbing focus:outline-none focus-visible:ring-2 focus-visible:ring-brand rounded" aria-roledescription="draggable card">
        <p className={`text-xs font-semibold leading-tight ${col === "done" ? "text-muted" : "text-ink"}`}>{task.title}</p>
      </div>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 flex-wrap min-w-0">
          {col === "done" ? <span className="chip-green text-caption">{t("board.col_done")}</span> : <span className={`${TAG[task.tag_type] || "chip-blue"} text-caption`}>{task.tag}</span>}
          {task.pr_number && (
            <span className={`text-caption font-mono flex items-center gap-0.5 ${task.pr_status === "approved" ? "text-success" : task.pr_status === "changes_requested" ? "text-danger" : "text-warning"}`} title={prLabel ? fill(t(`board.${prLabel}`), { n: task.pr_number }) : ""}>
              <GitPullRequest className="w-3 h-3" /> {task.pr_number}
            </span>
          )}
        </div>
        <span className={`w-6 h-6 rounded-full ${AVATAR[col]} text-white text-caption font-semibold flex items-center justify-center flex-shrink-0`} title={task.assignee_name}>{task.assignee_initials}</span>
      </div>
      <label className="sr-only" htmlFor={`move-${task.id}`}>{t("board.move_to")}</label>
      <select id={`move-${task.id}`} value={col} onChange={(e) => onMove(task.id, e.target.value as ColKey)}
        className="w-full text-caption text-muted bg-surface-2 border border-line rounded px-1 py-0.5 focus:outline-none focus:border-brand" data-testid={`move-${task.id}`}>
        {COLS.map((c) => <option key={c} value={c}>{t("board.move_to")}: {t(`board.col_${c}`)}</option>)}
      </select>
    </div>
  );
}

function Column({ col, tasks, children, t }: { col: ColKey; tasks: Task[]; children: React.ReactNode; t: (k: string) => string }) {
  const { setNodeRef, isOver } = useDroppable({ id: `col-${col}`, data: { col } });
  return (
    <div ref={setNodeRef} data-testid={`col-${col}`} className={`rounded-card border p-3.5 space-y-3 min-h-[200px] transition-colors ${isOver ? "bg-brand-soft border-brand" : "bg-surface-2 border-line"}`}>
      <div className="flex items-center justify-between text-xs font-semibold text-ink border-b border-line pb-2">
        <span>{t(`board.col_${col}`)}</span>
        <span className={`w-5 h-5 rounded-full border text-caption font-semibold flex items-center justify-center ${COUNT[col]}`} data-testid={`count-${col}`}>{tasks.length}</span>
      </div>
      <div className="space-y-2.5">
        {children}
        {tasks.length === 0 && <p className="text-caption text-subtle text-center py-6">{t("board.empty_col")}</p>}
      </div>
    </div>
  );
}

export default function SprintBoardPage() {
  const { teamId } = useParams<{ teamId: string }>();
  const { t } = useLanguage();
  const { token } = useAuth();
  const [board, setBoard] = useState<Board | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ text: string; ok: boolean } | null>(null);
  const [standupOpen, setStandupOpen] = useState(false);
  const [crOpen, setCrOpen] = useState(false);
  const [form, setForm] = useState({ yesterday: "", today: "", blockers: "" });
  const [savingStandup, setSavingStandup] = useState(false);
  const [standupDone, setStandupDone] = useState(false);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }), useSensor(KeyboardSensor));

  const load = useCallback(async () => {
    try {
      setBoard(await fetchApi<Board>(`/teams/${teamId}/board`));
      setError(null);
    } catch (err: any) {
      setError(err?.detail || err?.message || "error");
    } finally {
      setLoading(false);
    }
  }, [teamId]);

  useEffect(() => { load(); }, [load]);

  // Teammates' moves arrive over WebSocket; 15 s polling is the fallback
  useEffect(() => {
    const id = setInterval(load, 15000);
    let ws: WebSocket | null = null;
    if (token && !token.startsWith("mock")) {
      try {
        ws = new WebSocket(`${WS_BASE}/ws/board/${teamId}?token=${encodeURIComponent(token)}`);
        ws.onmessage = () => load();
      } catch { /* polling only */ }
    }
    const ping = setInterval(() => { try { ws?.readyState === 1 && ws.send("ping"); } catch { /* ignore */ } }, 25000);
    return () => { clearInterval(id); clearInterval(ping); try { ws?.close(); } catch { /* ignore */ } };
  }, [load, teamId, token]);

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(id);
  }, [toast]);

  const move = useCallback(async (taskId: string, to: ColKey, position?: number) => {
    if (!board) return;
    const from = board.columns.find((c) => c.tasks.some((x) => x.id === taskId));
    if (!from) return;
    if (from.key === to && position === undefined) return;
    const snapshot = board;
    // optimistic update
    const task = from.tasks.find((x) => x.id === taskId)!;
    const next = {
      ...board,
      columns: board.columns.map((c) => {
        let tasks = c.tasks.filter((x) => x.id !== taskId);
        if (c.key === to) {
          const at = position === undefined ? tasks.length : Math.min(position, tasks.length);
          tasks = [...tasks.slice(0, at), task, ...tasks.slice(at)];
        }
        return { ...c, tasks };
      }),
    };
    setBoard(next);
    try {
      await fetchApi(`/tasks/${taskId}/move`, { method: "PATCH", body: JSON.stringify({ column: to, position }) });
      setToast({ text: fill(t("board.moved"), { c: t(`board.col_${to}`) }), ok: true });
      load();
    } catch (err: any) {
      setBoard(snapshot);
      setToast({ text: err?.detail || t("board.move_failed"), ok: false });
    }
  }, [board, load, t]);

  const onDragEnd = (e: DragEndEvent) => {
    if (!e.over || !board) return;
    const overId = String(e.over.id);
    if (overId.startsWith("col-")) {
      move(String(e.active.id), overId.slice(4) as ColKey);
    }
  };

  const submitStandup = async () => {
    if (!board?.sprint || form.yesterday.trim().length < 2 || form.today.trim().length < 2) return;
    setSavingStandup(true);
    try {
      await fetchApi(`/sprints/${board.sprint.id}/standups`, { method: "POST", body: JSON.stringify(form) });
      setStandupOpen(false);
      setStandupDone(true);
      setToast({ text: t("board.standup_saved"), ok: true });
    } catch (err: any) {
      setToast({ text: err?.detail || t("board.error_title"), ok: false });
    } finally {
      setSavingStandup(false);
    }
  };

  const m = board?.metrics;
  const build = board?.build;

  return (
    <RoleGuard allowedRoles={["student", "trainer"]}>
      <AppShell pageTitle={board ? fill(t("board.title"), { t: board.team.name }) : t("board.loading")}>
        <div className="space-y-6 max-w-7xl mx-auto" data-testid="sprint-board">
          {loading && (
            <div className="space-y-5 animate-pulse" aria-busy="true" aria-label={t("board.loading")}>
              <div className="h-14 bg-white rounded-card border border-line" />
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">{[1, 2, 3, 4].map((i) => <div key={i} className="h-72 bg-white rounded-card border border-line" />)}</div>
            </div>
          )}

          {!loading && error && (
            <div className="bg-white rounded-card border border-danger-line p-8 text-center space-y-3 max-w-md mx-auto">
              <AlertCircle className="w-8 h-8 text-danger mx-auto" />
              <h2 className="text-base font-semibold text-ink">{t("board.error_title")}</h2>
              <p className="text-xs text-muted">{error}</p>
              <button onClick={load} className="inline-flex items-center gap-1.5 px-4 py-2 bg-brand text-white text-xs font-semibold rounded-tile"><RefreshCw className="w-3.5 h-3.5" /> {t("board.retry")}</button>
            </div>
          )}

          {!loading && !error && board && (
            <>
              {/* Header strip (PDF 6) */}
              <div className="bg-white rounded-card border border-line p-4 shadow-card flex flex-wrap items-center justify-between gap-4" data-testid="board-header">
                <div className="flex flex-wrap items-center gap-3">
                  {board.sprint && <span className="chip-purple font-semibold">{fill(t("board.sprint_of"), { n: board.sprint.number, t: board.sprint.total })}</span>}
                  <span className="text-xs font-semibold text-ink">
                    {board.team.project_title} · {fill(t("board.client"), { c: board.team.client })}{board.sprint ? ` · ${fill(t("board.ends_week"), { w: board.sprint.ends_week })}` : ""}
                  </span>
                  {board.change_request && (
                    <button onClick={() => setCrOpen(true)} className="chip-amber font-semibold cursor-pointer hover:brightness-95" data-testid="change-request">
                      <Sparkles className="w-3 h-3" /> {fill(t("board.change_request"), { t: board.change_request.title })}
                    </button>
                  )}
                </div>
                <button onClick={() => setStandupOpen(true)} className="px-3.5 py-1.5 bg-brand hover:bg-brand-hover text-white text-xs font-semibold rounded-tile shadow-card flex items-center gap-1.5" data-testid="standup-button">
                  {standupDone ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Users className="w-3.5 h-3.5" />}
                  <span>{standupDone ? t("board.standup_done") : t("board.daily_standup")}</span>
                </button>
              </div>

              {/* Columns */}
              <DndContext sensors={sensors} collisionDetection={closestCorners} onDragEnd={onDragEnd}>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {board.columns.map((c) => (
                    <Column key={c.key} col={c.key} tasks={c.tasks} t={t}>
                      {c.tasks.map((task) => <Card key={task.id} task={task} col={c.key} onMove={(id, to) => move(id, to)} t={t} />)}
                    </Column>
                  ))}
                </div>
              </DndContext>

              {/* Metrics strip */}
              {m && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-5" data-testid="board-metrics">
                  <div className="bg-white p-4 rounded-card border border-line shadow-card space-y-2">
                    <div className="flex items-center justify-between text-xs font-semibold"><span className="text-ink">{t("board.sprint_progress")}</span><span className="text-teal font-semibold text-sm">{m.progress_pct}%</span></div>
                    <div className="w-full bg-line-soft rounded-full h-2 overflow-hidden" role="progressbar" aria-valuenow={m.progress_pct} aria-valuemin={0} aria-valuemax={100}><div className="bg-teal h-full rounded-full transition-all" style={{ width: `${m.progress_pct}%` }} /></div>
                    <div className="text-caption text-muted">{fill(t("board.tasks_done"), { a: m.tasks_done, b: m.tasks_total })}</div>
                  </div>
                  <div className="bg-white p-4 rounded-card border border-line shadow-card space-y-1.5">
                    <div className="text-xs font-semibold text-ink">{t("board.story_points")}</div>
                    <div className="text-xl font-semibold text-ink">{m.points_done} / {m.points_total}</div>
                    {m.velocity_last !== null && <div className="text-caption text-muted">{fill(t("board.velocity_last"), { v: m.velocity_last })}</div>}
                  </div>
                  <div className="bg-white p-4 rounded-card border border-line shadow-card space-y-1.5" data-testid="build-status">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-ink">{t("board.build_status")}</span>
                      {build && <span className={`${build.status === "passing" ? "chip-green" : build.status === "failing" ? "chip-red" : "chip-amber"} font-semibold`}>{build.status === "passing" ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />} {t(`board.${build.status}`)}</span>}
                    </div>
                    {build ? (
                      <>
                        {build.environment && build.finished_ago && <div className="text-xs font-semibold text-ink">{fill(t("board.deployed"), { e: build.environment, t: build.finished_ago })}</div>}
                        {build.url ? (
                          <a href={build.url} target="_blank" rel="noreferrer" className="text-caption text-brand hover:underline inline-flex items-center gap-1">{fill(t("board.run"), { n: build.run_number, w: build.workflow })} <ExternalLink className="w-3 h-3" /></a>
                        ) : <div className="text-caption text-muted">{fill(t("board.run"), { n: build.run_number, w: build.workflow })}</div>}
                      </>
                    ) : <div className="text-caption text-muted">{t("board.no_build")}</div>}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {standupOpen && board && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" role="dialog" aria-modal="true" aria-label={t("board.daily_standup")} data-testid="standup-dialog">
            <div className="bg-white rounded-card max-w-md w-full p-6 space-y-4 shadow-pop border border-line">
              <h3 className="text-base font-semibold text-ink">{fill(t("board.standup_title"), { t: board.team.name })}</h3>
              {(["yesterday", "today", "blockers"] as const).map((k) => (
                <label key={k} className="block text-xs font-semibold text-ink">{t(`board.${k}`)}
                  <input value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} className="mt-1 w-full px-3 py-2 border border-line rounded-tile bg-surface-2 font-normal focus:outline-none focus:border-brand" data-testid={`standup-${k}`} />
                </label>
              ))}
              <div className="flex gap-2 pt-1">
                <button onClick={() => setStandupOpen(false)} className="flex-1 py-2 bg-line-soft text-ink font-semibold text-xs rounded-card">{t("board.cancel")}</button>
                <button onClick={submitStandup} disabled={savingStandup || form.yesterday.trim().length < 2 || form.today.trim().length < 2} className="flex-1 py-2 bg-brand text-white font-semibold text-xs rounded-card disabled:opacity-50" data-testid="standup-submit">{t("board.share")}</button>
              </div>
            </div>
          </div>
        )}

        {crOpen && board?.change_request && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" role="dialog" aria-modal="true" aria-label={fill(t("board.cr_title"), { c: board.change_request.code })} data-testid="cr-dialog">
            <div className="bg-white rounded-card max-w-md w-full p-6 space-y-3 shadow-pop border border-line">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-semibold text-ink">{fill(t("board.cr_title"), { c: board.change_request.code })}</h3>
                <button onClick={() => setCrOpen(false)} className="p-1.5 rounded-tile hover:bg-line-soft" aria-label={t("board.close")}><X className="w-4 h-4 text-muted" /></button>
              </div>
              <div className="text-sm font-semibold text-ink">{board.change_request.title}</div>
              {board.change_request.description && <p className="text-xs text-ink-soft leading-relaxed">{board.change_request.description}</p>}
              <div className="text-caption text-muted">{fill(t("board.client"), { c: board.team.client })}</div>
            </div>
          </div>
        )}

        {toast && (
          <div role="status" className={`fixed bottom-6 right-6 z-50 text-white text-xs font-semibold px-4 py-3 rounded-card shadow-pop flex items-center gap-2 max-w-sm ${toast.ok ? "bg-ink" : "bg-danger"}`} data-testid="toast">
            {toast.ok ? <CheckCircle2 className="w-4 h-4 text-teal flex-shrink-0" /> : <AlertCircle className="w-4 h-4 flex-shrink-0" />} {toast.text}
          </div>
        )}
      </AppShell>
    </RoleGuard>
  );
}
