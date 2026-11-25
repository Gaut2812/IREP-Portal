"use client";

/** S16 DPDP: the consent rows (with the notice for each purpose) and the self-service data requests,
 *  shared by /parent/consent and /student/privacy. */
import React, { useCallback, useEffect, useState } from "react";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi, fetchBlob } from "@/lib/api";

export interface PurposeView {
  status: "granted" | "withdrawn" | "requested" | null;
  effective: boolean;
  by_parent: boolean;
  needs_parent: boolean;
  notice: string | null;
  notice_version: string | null;
  recorded_at: string | null;
}

export const PURPOSES = ["parent_data_processing", "ai_hints", "public_portfolio", "recordings", "sms_alerts"] as const;

export function errText(e: unknown, fallback: string): string {
  return e instanceof ApiError && e.detail ? String(e.detail) : fallback;
}

/** One purpose: its notice, its state and the buttons the caller allows. */
export function PurposeRow({ purpose, view, children }: { purpose: string; view: PurposeView; children?: React.ReactNode }) {
  const { t } = useLanguage();
  const state = view.effective ? "on" : view.status === "requested" ? "requested" : "off";
  const style = state === "on" ? "bg-success-soft text-success" : state === "requested" ? "bg-warning-soft text-warning" : "bg-line-soft text-ink-soft";
  return (
    <li className="py-3 space-y-1.5" data-testid={`purpose-${purpose}`}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-semibold text-ink">{t(`privacy.purpose.${purpose}`)}</p>
        <span className={`shrink-0 px-2 py-0.5 rounded-full text-caption font-semibold ${style}`} data-testid="purpose-state">{t(`privacy.state.${state}`)}</span>
      </div>
      {view.notice && <p className="text-caption text-ink-soft leading-relaxed">{view.notice}</p>}
      {view.notice_version && <p className="text-caption text-subtle">{t("privacy.notice_version")} {view.notice_version}</p>}
      {children && <div className="flex flex-wrap gap-2 pt-1">{children}</div>}
    </li>
  );
}

export function Btn({ onClick, kind = "primary", children, testId }: { onClick: () => void; kind?: "primary" | "ghost"; children: React.ReactNode; testId?: string }) {
  return (
    <button type="button" onClick={onClick} data-testid={testId}
      className={kind === "primary" ? "px-3 py-1.5 bg-brand text-white text-xs font-semibold rounded-tile" : "px-3 py-1.5 border border-line-strong text-ink-soft text-xs font-semibold rounded-tile"}>
      {children}
    </button>
  );
}

interface Req { id: string; kind: string; student_id: string; status: string; due_on: string; has_export: boolean; decision_note: string | null }

/** Ask for a copy or deletion. A parent picks the child; a minor student sees "ask your parent" instead. */
export function DataRequests({ kids, blocked }: { kids?: { id: string; name: string }[]; blocked?: boolean }) {
  const { t } = useLanguage();
  const [items, setItems] = useState<Req[]>([]);
  const [kind, setKind] = useState<"export" | "deletion">("export");
  const [reason, setReason] = useState("");
  const [child, setChild] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try { setItems((await fetchApi<{ items: Req[] }>("/me/data-requests")).items); } catch { /* the list is optional */ }
  }, []);
  useEffect(() => { load(); }, [load]);

  const submit = async () => {
    setErr(""); setMsg("");
    try {
      const body: Record<string, string> = { kind, reason };
      if (kids?.length) body.student_id = child || kids[0].id;
      await fetchApi("/me/data-requests", { method: "POST", body: JSON.stringify(body) });
      setReason(""); setMsg(t("privacy.req_sent")); await load();
    } catch (e) { setErr(errText(e, t("privacy.req_failed"))); }
  };
  const download = async (r: Req) => {
    try {
      const url = URL.createObjectURL(await fetchBlob(`/me/data-requests/${r.id}/export`));
      const a = document.createElement("a"); a.href = url; a.download = `irep-export-${r.student_id}.json`; a.click(); URL.revokeObjectURL(url);
    } catch (e) { setErr(errText(e, t("privacy.req_failed"))); }
  };

  return (
    <section className="bg-white rounded-card border border-line p-4 space-y-3" data-testid="data-requests">
      <h2 className="text-sm font-semibold text-ink">{t("privacy.req_title")}</h2>
      <p className="text-caption text-muted">{t("privacy.req_intro")}</p>
      {blocked ? <p className="text-xs text-warning bg-warning-soft rounded-tile p-2" data-testid="ask-parent">{t("privacy.req_minor")}</p> : (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            {kids && kids.length > 1 && (
              <select aria-label={t("privacy.req_child")} value={child} onChange={(e) => setChild(e.target.value)} className="px-2 py-1.5 border border-line-strong rounded-tile text-xs">
                {kids.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
              </select>
            )}
            <select aria-label={t("privacy.req_kind")} value={kind} onChange={(e) => setKind(e.target.value as "export" | "deletion")} className="px-2 py-1.5 border border-line-strong rounded-tile text-xs" data-testid="req-kind">
              <option value="export">{t("privacy.kind.export")}</option>
              <option value="deletion">{t("privacy.kind.deletion")}</option>
            </select>
          </div>
          <textarea rows={2} aria-label={t("privacy.req_reason")} placeholder={t("privacy.req_reason")} value={reason} onChange={(e) => setReason(e.target.value)}
            className="w-full px-2.5 py-1.5 bg-surface-2 border border-line rounded-tile text-xs" data-testid="req-reason" />
          <Btn onClick={submit} testId="req-submit">{t("privacy.req_submit")}</Btn>
        </div>
      )}
      {msg && <p className="text-xs text-success font-semibold" data-testid="req-ok">{msg}</p>}
      {err && <p className="text-xs text-red-600" role="alert" data-testid="req-error">{err}</p>}
      {items.length > 0 && (
        <ul className="divide-y divide-line-soft">
          {items.map((r) => (
            <li key={r.id} className="py-2 flex items-center justify-between gap-2 text-xs" data-testid="req-row">
              <span>{t(`privacy.kind.${r.kind}`)} · {t(`privacy.req_status.${r.status}`)} · {t("privacy.req_due")} {r.due_on}</span>
              {r.has_export && <Btn kind="ghost" onClick={() => download(r)}>{t("privacy.req_download")}</Btn>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
