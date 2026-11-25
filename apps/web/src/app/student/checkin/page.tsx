"use client";

/** Screen 09 (student side): enter the class check-in code shown by the trainer. */
import React, { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { CheckCircle2 } from "lucide-react";

export default function StudentCheckinPage() {
  const { t } = useLanguage();
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ title: string; checked_in: boolean; message?: string } | null>(null);
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setDone(null);
    if (code.trim().length < 4) return setError(t("checkin.err_code"));
    setBusy(true);
    try {
      setDone(await fetchApi("/student/attendance/checkin", { method: "POST", body: JSON.stringify({ code: code.trim() }) }));
      setCode("");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : t("checkin.failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <RoleGuard allowedRoles={["student"]}>
      <AppShell pageTitle={t("checkin.title")}>
        <div className="max-w-md">
          <form onSubmit={submit} noValidate className="bg-white rounded-card border border-line p-5 space-y-3" data-testid="checkin-form">
            <p className="text-xs text-muted">{t("checkin.help")}</p>
            <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} maxLength={8} autoComplete="off" inputMode="text"
              placeholder="ABC234" data-testid="checkin-input" aria-label={t("checkin.code")}
              className="w-full px-3 py-3 border border-line rounded-card text-center text-2xl font-semibold tracking-[0.3em]" />
            {error && <p className="text-xs text-red-600" role="alert" data-testid="checkin-error">{error}</p>}
            {done && (
              <p className={`text-xs font-semibold flex items-center gap-1.5 ${done.checked_in ? "text-success" : "text-warning"}`} data-testid="checkin-result">
                {done.checked_in && <CheckCircle2 className="w-4 h-4" />}{done.checked_in ? `${t("checkin.done")} ${done.title}` : done.message}
              </p>
            )}
            <button type="submit" disabled={busy} data-testid="checkin-submit" className="w-full py-2.5 bg-brand text-white text-xs font-semibold rounded-card disabled:opacity-50">{t("checkin.submit")}</button>
          </form>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
