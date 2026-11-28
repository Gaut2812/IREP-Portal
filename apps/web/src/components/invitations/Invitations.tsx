"use client";

/** Phase 5 · Invitations. InviteLinkBox shows a one-time set-password link once, right after an account is created
 *  or an invitation is resent (development, when the portal does not send email itself). InvitationsPanel lists who
 *  was invited and whether they accepted, with Resend and Revoke. Used on /college/settings and /admin/colleges/[id]. */
import React, { useCallback, useEffect, useState } from "react";
import { Copy, RotateCw, Ban } from "lucide-react";
import { ApiError, fetchApi } from "@/lib/api";
import { useLanguage } from "@/lib/LanguageContext";

export interface InviteResult { email?: string; invite?: string; invite_link?: string; invite_expires_at?: string }
interface Invitation {
  id: string; email: string; name: string | null; role: string; provider: string; status: "pending" | "accepted" | "expired" | "revoked";
  invited_by: string | null; invited_at: string | null; last_sent_at: string | null; expires_at: string | null; accepted_at: string | null; resends: number;
}

export function InviteLinkBox({ result, testId = "invite-link-box" }: { result: InviteResult | null; testId?: string }) {
  const { t } = useLanguage();
  const [copied, setCopied] = useState(false);
  if (!result) return null;
  if (!result.invite_link) {
    return <p className="p-3 rounded-tile bg-success-faint border border-success-line text-xs text-success" role="status" data-testid={testId}>{result.invite || t("invitations.sent")}</p>;
  }
  return (
    <div className="p-3 rounded-tile bg-warning-soft border border-warning-line text-xs space-y-1.5" data-testid={testId}>
      <p className="font-semibold text-warning">{t("invitations.link_title")}{result.email ? ` · ${result.email}` : ""}</p>
      <div className="flex items-center gap-2">
        <input readOnly value={result.invite_link} onFocus={(e) => e.currentTarget.select()} aria-label={t("invitations.link_title")}
          className="flex-1 min-w-0 px-2 py-1 bg-white border border-line rounded-tile font-mono text-caption" data-testid="invite-link-value" />
        <button type="button" onClick={() => { navigator.clipboard?.writeText(result.invite_link!); setCopied(true); }}
          className="inline-flex items-center gap-1 text-brand font-semibold"><Copy className="w-3 h-3" />{copied ? t("invitations.copied") : t("invitations.copy")}</button>
      </div>
      <p className="text-warning">{t("invitations.link_note")}</p>
    </div>
  );
}

export function InvitationsPanel({ basePath, refreshKey = 0 }: { basePath: string; refreshKey?: number }) {
  const { t, language } = useLanguage();
  const [items, setItems] = useState<Invitation[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [asking, setAsking] = useState<Invitation | null>(null);
  const [result, setResult] = useState<InviteResult | null>(null);

  const load = useCallback(async () => {
    try {
      setItems((await fetchApi<{ items: Invitation[] }>(basePath)).items);
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : t("invitations.load_failed"));
    }
  }, [basePath, t]);
  useEffect(() => { load(); }, [load, refreshKey]);

  const act = async (inv: Invitation, what: "resend" | "revoke") => {
    setBusy(inv.id);
    setError("");
    try {
      const r = await fetchApi<InviteResult>(`${basePath}/${inv.id}/${what}`, { method: "POST" });
      setResult(what === "resend" ? { ...r, email: inv.email } : null);
      setAsking(null);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : t("invitations.action_failed"));
    } finally {
      setBusy(null);
    }
  };

  const when = (iso: string | null) => iso ? new Date(`${iso.replace(/Z$/, "")}Z`).toLocaleString(language === "ta" ? "ta-IN" : "en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : "";
  const chip: Record<string, string> = { pending: "bg-warning-soft text-warning", accepted: "bg-success-soft text-success", expired: "bg-line-soft text-ink-soft", revoked: "bg-danger-soft text-danger" };

  return (
    <section className="bg-white rounded-card border border-line p-4 space-y-3" data-testid="invitations">
      <div>
        <h2 className="text-sm font-semibold text-ink">{t("invitations.title")}</h2>
        <p className="text-caption text-muted">{t("invitations.help")}</p>
      </div>
      {error && <p className="text-xs text-danger" role="alert">{error}</p>}
      <InviteLinkBox result={result} testId="invite-resent-box" />
      {items?.length === 0 && <p className="text-xs text-muted" data-testid="invitations-empty">{t("invitations.none")}</p>}
      <ul className="divide-y divide-line-soft">
        {items?.map((i) => (
          <li key={i.id} className="py-2 flex flex-wrap items-center gap-2" data-testid="invitation-row" data-email={i.email}>
            <div className="min-w-0 flex-1">
              <div className="text-xs font-semibold text-ink truncate">{i.name || i.email} <span className="font-normal text-muted">· {i.email}</span></div>
              <div className="text-caption text-muted">
                {t(`invitations.role_${i.role}`)}{i.invited_by ? ` · ${t("invitations.by").replace("{name}", i.invited_by)}` : ""}
                {i.invited_at ? ` · ${when(i.invited_at)}` : ""}
                {i.status === "accepted" && i.accepted_at ? ` · ${t("invitations.accepted_on").replace("{d}", when(i.accepted_at))}` : ""}
                {i.status === "pending" && i.expires_at ? ` · ${t("invitations.expires").replace("{d}", when(i.expires_at))}` : ""}
                {i.resends > 0 ? ` · ${t("invitations.resent_n").replace("{n}", String(i.resends))}` : ""}
              </div>
            </div>
            <span className={`text-caption font-semibold px-2 py-0.5 rounded-full ${chip[i.status]}`} data-testid="invitation-status">{t(`invitations.status_${i.status}`)}</span>
            {i.status !== "accepted" && (
              <>
                <button type="button" disabled={busy === i.id} onClick={() => act(i, "resend")} data-testid="invitation-resend"
                  className="inline-flex items-center gap-1 px-2 py-1 border border-line-strong rounded-tile text-caption font-semibold disabled:opacity-50">
                  <RotateCw className="w-3 h-3" />{t("invitations.resend")}
                </button>
                {i.status !== "revoked" && (
                  <button type="button" disabled={busy === i.id} onClick={() => setAsking(i)} data-testid="invitation-revoke"
                    className="inline-flex items-center gap-1 px-2 py-1 border border-danger-line text-danger rounded-tile text-caption font-semibold disabled:opacity-50">
                    <Ban className="w-3 h-3" />{t("invitations.revoke")}
                  </button>
                )}
              </>
            )}
            {asking?.id === i.id && (
              <div role="alertdialog" aria-labelledby={`revoke-${i.id}`} className="basis-full p-2.5 rounded-tile bg-danger-soft border border-danger-line space-y-2" data-testid="revoke-confirm">
                <p id={`revoke-${i.id}`} className="text-xs text-danger font-semibold">{t("invitations.revoke_q").replace("{email}", i.email)}</p>
                <p className="text-caption text-ink-soft">{t("invitations.revoke_note")}</p>
                <div className="flex justify-end gap-2">
                  <button type="button" onClick={() => setAsking(null)} className="px-2.5 py-1 border border-line-strong bg-white rounded-tile text-caption font-semibold">{t("invitations.keep")}</button>
                  <button type="button" onClick={() => act(i, "revoke")} data-testid="revoke-confirm-ok" className="px-2.5 py-1 bg-danger text-white rounded-tile text-caption font-semibold">{t("invitations.revoke")}</button>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
