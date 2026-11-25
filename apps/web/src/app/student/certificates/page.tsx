"use client";

/** Screen 26 · Certificates (student): earned, scheduled and external ones. An external proof goes to the
 *  trainer (43, L10) and shows as verified only after approval. */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi, fetchBlob } from "@/lib/api";
import { Award, BadgeCheck, Clock, FileUp, XCircle } from "lucide-react";

interface Cert {
  id: string; title: string; issuer: string; type: string; status: string; status_label: string; verified: boolean;
  issued_on: string | null; exam_date: string | null; verify_code: string | null; credential_id: string | null;
  has_proof: boolean; decision_note: string | null; voucher: boolean;
}

const ICON: Record<string, React.ComponentType<{ className?: string }>> = { earned: BadgeCheck, scheduled: Clock, pending_proof: Clock, rejected: XCircle };
const CHIP: Record<string, string> = { earned: "bg-success-soft text-success", scheduled: "bg-info-soft text-info", pending_proof: "bg-warning-soft text-warning", rejected: "bg-danger-soft text-danger" };

export default function StudentCertificatesPage() {
  const { t, language } = useLanguage();
  const [certs, setCerts] = useState<Cert[]>([]);
  const [form, setForm] = useState({ title: "", issuer: "", issued_on: "", credential_id: "" });
  const [file, setFile] = useState<File | null>(null);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setCerts((await fetchApi<{ certificates: Cert[] }>(`/student/certificates?lang=${language}`)).certificates); }
    catch (e) { setError(e instanceof ApiError ? String(e.detail) : t("certs.load_failed")); }
  }, [language, t]);
  useEffect(() => { load(); }, [load]);

  const send = async (url: string, fd: FormData) => {
    setBusy(true);
    setError("");
    setMsg("");
    try {
      await fetchApi(url, { method: "POST", body: fd });
      setMsg(t("certs.sent"));
      await load();
      return true;
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : t("certs.save_failed"));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const addExternal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.title.trim().length < 3 || form.issuer.trim().length < 2 || !form.issued_on || !file) return setError(t("certs.err_fields"));
    const fd = new FormData();
    Object.entries(form).forEach(([k, v]) => v && fd.append(k, v));
    fd.append("file", file);
    if (await send("/student/certificates", fd)) {
      setForm({ title: "", issuer: "", issued_on: "", credential_id: "" });
      setFile(null);
      (e.target as HTMLFormElement).reset();
    }
  };

  const uploadProof = (c: Cert, f: File | undefined) => {
    if (!f) return;
    const fd = new FormData();
    fd.append("file", f);
    send(`/student/certificates/${c.id}/proof`, fd);
  };

  const viewProof = async (c: Cert) => {
    try { window.open(URL.createObjectURL(await fetchBlob(`/student/certificates/${c.id}/proof`)), "_blank", "noopener"); } catch { setError(t("certs.load_failed")); }
  };

  const cls = "w-full px-2.5 py-1.5 bg-surface-2 border border-line rounded-tile text-xs";
  return (
    <RoleGuard allowedRoles={["student"]}>
      <AppShell pageTitle={t("certs.title")}>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 max-w-6xl">
          <section className="lg:col-span-2 space-y-2">
            {msg && <p className="text-xs text-success font-semibold" role="status" data-testid="certs-msg">{msg}</p>}
            {error && <p className="text-xs text-red-600" role="alert" data-testid="certs-error">{error}</p>}
            <ul className="space-y-2" data-testid="cert-list">
              {certs.length === 0 && <li className="bg-white rounded-card border border-dashed border-line-strong p-6 text-center text-xs text-muted">{t("certs.none")}</li>}
              {certs.map((c) => {
                const Icon = ICON[c.status] || Award;
                return (
                  <li key={c.id} className="bg-white rounded-card border border-line p-3" data-testid="cert-row">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-start gap-2 min-w-0">
                        <Icon className="w-5 h-5 text-brand shrink-0 mt-0.5" />
                        <div className="min-w-0">
                          <div className="text-sm font-semibold text-ink">{c.title}</div>
                          <div className="text-caption text-muted">
                            {c.issuer}{c.issued_on ? ` · ${c.issued_on}` : ""}{c.exam_date && c.status === "scheduled" ? ` · ${t("certs.exam_on")} ${c.exam_date}` : ""}
                            {c.verify_code && c.verified ? ` · ${c.verify_code}` : ""}{c.voucher ? ` · ${t("certs.voucher")}` : ""}
                          </div>
                        </div>
                      </div>
                      <span className={`text-caption font-semibold px-2 py-0.5 rounded-full shrink-0 ${CHIP[c.status] || ""}`} data-testid="cert-status">{c.status_label}</span>
                    </div>
                    {c.status === "pending_proof" && <p className="text-caption text-warning mt-1">{t("certs.pending_note")}</p>}
                    {c.status === "rejected" && c.decision_note && <p className="text-caption text-danger mt-1" data-testid="cert-note">{t("certs.rejected_note")}: {c.decision_note}</p>}
                    <div className="flex gap-2 mt-2">
                      {(c.status === "scheduled" || c.status === "rejected") && (
                        <label className="px-2.5 py-1 border border-brand text-brand text-caption font-semibold rounded-tile inline-flex items-center gap-1 cursor-pointer">
                          <FileUp className="w-3.5 h-3.5" />{c.status === "scheduled" ? t("certs.upload_result") : t("certs.upload_again")}
                          <input type="file" accept="application/pdf,image/png,image/jpeg" className="sr-only" disabled={busy} data-testid="cert-proof-input"
                            onChange={(e) => uploadProof(c, e.target.files?.[0])} />
                        </label>
                      )}
                      {c.has_proof && <button type="button" onClick={() => viewProof(c)} className="px-2.5 py-1 border border-line-strong text-caption font-semibold rounded-tile">{t("certs.view_proof")}</button>}
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
          <form onSubmit={addExternal} noValidate className="bg-white rounded-card border border-line p-4 space-y-2 h-fit" data-testid="cert-form">
            <h2 className="text-sm font-semibold text-ink flex items-center gap-2"><FileUp className="w-4 h-4 text-brand" />{t("certs.add_external")}</h2>
            <p className="text-caption text-muted">{t("certs.add_help")}</p>
            <input className={cls} placeholder={t("certs.f_title")} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} data-testid="cert-title" />
            <input className={cls} placeholder={t("certs.f_issuer")} value={form.issuer} onChange={(e) => setForm({ ...form, issuer: e.target.value })} data-testid="cert-issuer" />
            <label className="block text-caption text-ink-soft">{t("certs.f_issued_on")}
              <input type="date" className={cls} value={form.issued_on} onChange={(e) => setForm({ ...form, issued_on: e.target.value })} data-testid="cert-date" />
            </label>
            <input className={cls} placeholder={t("certs.f_credential")} value={form.credential_id} onChange={(e) => setForm({ ...form, credential_id: e.target.value })} />
            <label className="block text-caption text-ink-soft">{t("certs.f_file")}
              <input type="file" accept="application/pdf,image/png,image/jpeg" className="block text-xs mt-1" onChange={(e) => setFile(e.target.files?.[0] || null)} data-testid="cert-file" />
            </label>
            <button type="submit" disabled={busy} className="w-full px-3 py-2 bg-brand text-white text-xs font-semibold rounded-tile disabled:opacity-50" data-testid="cert-submit">{t("certs.submit")}</button>
          </form>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
