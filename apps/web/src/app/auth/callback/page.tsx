"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useAuth, UserProfile } from "@/lib/AuthContext";
import { useLanguage } from "@/lib/LanguageContext";
import { API_BASE } from "@/lib/api";
import { completeKeycloakSignIn, getAuthConfig } from "@/lib/oidc";

/** Keycloak redirects here with ?code&state; exchange it, load the profile, go home. */
export default function AuthCallbackPage() {
  const { login } = useAuth();
  const { t, setLanguage } = useLanguage();
  const [failed, setFailed] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;     // the code is single-use: never exchange twice
    started.current = true;
    (async () => {
      try {
        const cfg = await getAuthConfig();
        if (cfg.provider !== "keycloak") throw new Error("not_keycloak");
        const token = await completeKeycloakSignIn(cfg, window.location.search);
        const res = await fetch(`${API_BASE}/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
        if (res.status === 401 && res.headers.get("X-IREP-Reason") === "two_factor_required") {
          // e.g. the first sign-in, when the authenticator app was only being set up
          window.location.replace("/login?reauth=2fa");
          return;
        }
        if (!res.ok) throw new Error(`me_${res.status}`);
        const me = (await res.json()) as UserProfile & { language_pref?: string };
        window.history.replaceState(null, "", "/auth/callback");   // drop the code from history
        if (me.language_pref === "en" || me.language_pref === "ta") setLanguage(me.language_pref, false);
        login(token, me);
      } catch {
        setFailed(true);
      }
    })();
  }, [login, setLanguage]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-danger-soft p-6">
      <div className="w-full max-w-sm bg-white rounded-card shadow-pop border border-line p-8 text-center space-y-4" data-testid="auth-callback">
        {failed ? (
          <>
            <p className="text-sm font-semibold text-danger" role="alert">{t("auth.callback_failed")}</p>
            <Link href="/login" className="inline-block px-4 py-2.5 bg-brand text-white text-xs font-semibold rounded-card">
              {t("auth.back_to_login")}
            </Link>
          </>
        ) : (
          <p className="text-sm font-medium text-ink">{t("auth.signing_in")}</p>
        )}
      </div>
    </div>
  );
}
