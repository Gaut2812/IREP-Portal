"use client";

/** Class check-in (screen 09): the student types the code the trainer shows. Used inside the live
 *  session and on /student/checkin (the deep link SMS reminders point to). */
import React, { useState } from "react";
import { CheckCircle2, KeyRound } from "lucide-react";
import { ApiError, fetchApi } from "@/lib/api";
import { cn } from "@/lib/cn";

export function CheckinBox({ t, dark = false, onDone }: { t: (k: string) => string; dark?: boolean; onDone?: () => void }) {
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
      const r = await fetchApi<{ title: string; checked_in: boolean; message?: string }>("/student/attendance/checkin", { method: "POST", body: JSON.stringify({ code: code.trim() }) });
      setDone(r);
      setCode("");
      if (r.checked_in) onDone?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : t("checkin.failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} noValidate className="space-y-2" data-testid="checkin-form">
      <p className={cn("text-caption", dark ? "text-subtle" : "text-muted")}>{t("checkin.help")}</p>
      <div className="flex gap-2">
        <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} maxLength={8} autoComplete="off" inputMode="text"
          placeholder="ABC234" data-testid="checkin-input" aria-label={t("checkin.code")}
          className={cn("flex-1 min-w-0 px-3 py-2 border rounded-tile text-center text-base font-semibold tracking-[0.3em]",
            dark ? "bg-[#0F172A] border-ink-soft text-white placeholder-muted focus:outline-none focus:border-brand" : "bg-white border-line")} />
        <button type="submit" disabled={busy} data-testid="checkin-submit"
          className="px-3 bg-brand hover:bg-brand-hover text-white text-xs font-semibold rounded-tile inline-flex items-center gap-1 disabled:opacity-50">
          <KeyRound className="w-3.5 h-3.5" />{t("checkin.submit")}
        </button>
      </div>
      {error && <p className="text-caption text-danger" role="alert" data-testid="checkin-error">{error}</p>}
      {done && (
        <p className={cn("text-caption font-semibold flex items-center gap-1.5", done.checked_in ? "text-success" : "text-warning")} role="status" data-testid="checkin-result">
          {done.checked_in && <CheckCircle2 className="w-4 h-4" />}{done.checked_in ? `${t("checkin.done")} ${done.title}` : done.message}
        </p>
      )}
    </form>
  );
}
