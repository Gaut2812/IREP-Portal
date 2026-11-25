"use client";

/** S16 DPDP · My data & consent (student): every purpose with its notice. An adult decides; a minor asks
 *  a parent (the request waits on the parent's Consent page). Adults also ask for a copy or deletion here. */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { fetchApi } from "@/lib/api";
import { Btn, DataRequests, errText, PURPOSES, PurposeRow, PurposeView } from "@/components/privacy/PrivacyParts";

interface Mine { student_id: string; is_minor: boolean; dob_known: boolean; purposes: Record<string, PurposeView> }

export default function StudentPrivacyPage() {
  const { t, language } = useLanguage();
  const [data, setData] = useState<Mine | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    try { setData(await fetchApi(`/consent?lang=${language}`)); }
    catch (e) { setError(errText(e, t("privacy.load_failed"))); }
  }, [language, t]);
  useEffect(() => { load(); }, [load]);

  const decide = async (purpose: string, status: "granted" | "withdrawn") => {
    setError(""); setNote("");
    try {
      const r = await fetchApi<{ status: string }>("/consent", { method: "POST", body: JSON.stringify({ purpose, status }) });
      if (r.status === "requested") setNote(t("privacy.asked_parent"));
      await load();
    } catch (e) { setError(errText(e, t("privacy.save_failed"))); }
  };

  return (
    <RoleGuard allowedRoles={["student"]}>
      <AppShell pageTitle={t("privacy.student_title")}>
        <div className="max-w-2xl mx-auto space-y-6">
          <p className="text-xs text-ink-soft">{data?.is_minor ? t("privacy.student_intro_minor") : t("privacy.student_intro")}</p>
          {data && !data.dob_known && <p className="text-caption text-warning" data-testid="dob-unknown">{t("privacy.dob_unknown")}</p>}
          {note && <p className="text-xs text-success font-semibold" data-testid="consent-note">{note}</p>}
          {error && <p className="text-xs text-red-600" role="alert" data-testid="consent-error">{error}</p>}
          {data && (
            <section className="bg-white rounded-card border border-line p-4">
              <ul className="divide-y divide-line-soft">
                {PURPOSES.filter((p) => p !== "parent_data_processing").map((p) => {
                  const v = data.purposes[p];
                  if (!v) return null;
                  return (
                    <PurposeRow key={p} purpose={p} view={v}>
                      {!v.effective && v.status !== "requested" && (
                        <Btn onClick={() => decide(p, "granted")} testId={`grant-${p}`}>{v.needs_parent ? t("privacy.ask_parent") : t("privacy.agree")}</Btn>
                      )}
                      {v.status === "requested" && <span className="text-caption text-warning">{t("privacy.waiting_parent")}</span>}
                      {(v.effective || v.status === "requested") && <Btn kind="ghost" onClick={() => decide(p, "withdrawn")} testId={`withdraw-${p}`}>{t("privacy.withdraw")}</Btn>}
                    </PurposeRow>
                  );
                })}
              </ul>
              {data.purposes.parent_data_processing && (
                <p className="text-caption text-muted pt-2 border-t border-line-soft" data-testid="parent-view-state">
                  {data.purposes.parent_data_processing.effective ? t("privacy.parent_view_on") : t("privacy.parent_view_off")}
                </p>
              )}
            </section>
          )}
          {data && <DataRequests blocked={data.is_minor} />}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
