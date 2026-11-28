"use client";

/** S16 DPDP · Parent consent: each linked child, every purpose with its notice, requests waiting for the
 *  parent, and self-service data requests. Granting for a minor needs an OTP sign-in in the last 15 minutes. */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useAuth } from "@/lib/AuthContext";
import { useLanguage } from "@/lib/LanguageContext";
import { fetchApi } from "@/lib/api";
import { Btn, DataRequests, errText, PURPOSES, PurposeRow, PurposeView } from "@/components/privacy/PrivacyParts";

interface Child { student_id: string; name: string; is_minor: boolean; purposes: Record<string, PurposeView> }

export default function ParentConsentPage() {
  const { t, language } = useLanguage();
  const { logout } = useAuth();
  const [data, setData] = useState<{ identity_fresh: boolean; children: Child[] } | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { setData(await fetchApi(`/parent/consent?lang=${language}`)); }
    catch (e) { setError(errText(e, t("privacy.load_failed"))); }
  }, [language, t]);
  useEffect(() => { load(); }, [load]);

  const decide = async (c: Child, purpose: string, status: "granted" | "withdrawn") => {
    setError("");
    try {
      await fetchApi("/consent", { method: "POST", body: JSON.stringify({ purpose, status, student_id: c.student_id }) });
      await load();
    } catch (e) { setError(errText(e, t("privacy.save_failed"))); }
  };

  return (
    <RoleGuard allowedRoles={["parent"]}>
      <AppShell pageTitle={t("privacy.parent_title")}>
        <div className="max-w-2xl mx-auto space-y-6">
          <p className="text-xs text-ink-soft">{t("privacy.parent_intro")}</p>
          {data && !data.identity_fresh && (
            <div className="bg-brand-soft border border-brand-line rounded-card p-3 text-xs text-info space-y-2" data-testid="reauth-note">
              <p>{t("privacy.reauth")}</p>
              <Btn onClick={logout} kind="ghost" testId="reauth">{t("privacy.reauth_button")}</Btn>
            </div>
          )}
          {error && <p className="text-xs text-red-600" role="alert" data-testid="consent-error">{error}</p>}
          {data?.children.map((c) => (
            <section key={c.student_id} className="bg-white rounded-card border border-line p-4" data-testid="consent-child">
              <h2 className="text-sm font-semibold text-ink">{c.name}</h2>
              <p className="text-caption text-muted">{c.is_minor ? t("privacy.child_minor") : t("privacy.child_adult")}</p>
              <ul className="divide-y divide-line-soft">
                {PURPOSES.map((p) => {
                  const v = c.purposes[p];
                  if (!v) return null;
                  const parentDecides = p === "parent_data_processing" || c.is_minor;
                  return (
                    <PurposeRow key={p} purpose={p} view={v}>
                      {parentDecides && !v.effective && <Btn onClick={() => decide(c, p, "granted")} testId={`approve-${p}`}>{v.status === "requested" ? t("privacy.approve") : t("privacy.agree")}</Btn>}
                      {parentDecides && (v.effective || v.status === "requested") && <Btn kind="ghost" onClick={() => decide(c, p, "withdrawn")} testId={`decline-${p}`}>{v.status === "requested" ? t("privacy.decline") : t("privacy.withdraw")}</Btn>}
                      {!parentDecides && <span className="text-caption text-muted">{t("privacy.adult_decides")}</span>}
                    </PurposeRow>
                  );
                })}
              </ul>
            </section>
          ))}
          {data && <DataRequests kids={data.children.map((c) => ({ id: c.student_id, name: c.name }))} />}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
