/**
 * Keycloak sign-in for the web app (AUTH_PROVIDER=keycloak on the API).
 *
 * Authorization-code flow with PKCE (S256) against the public client
 * "irep-web". The API publishes the issuer at GET /auth/config, so the web
 * build needs no Keycloak settings of its own. Parents never come here: they
 * keep the API's mobile OTP until Keycloak has SMS OTP.
 */
import { API_BASE } from "@/lib/api";

export interface AuthConfig {
  provider: "local" | "keycloak";
  issuer?: string;
  client_id?: string;
}

interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  id_token?: string;
  expires_in?: number;
}

const PENDING_KEY = "irep_oidc_pending";
export const REFRESH_KEY = "irep_refresh_token";
export const ID_TOKEN_KEY = "irep_id_token";
const CONFIG_KEY = "irep_auth_config";

let configPromise: Promise<AuthConfig> | null = null;

/** Sign-in settings from the API (cached for the tab). Falls back to local. */
export function getAuthConfig(): Promise<AuthConfig> {
  if (!configPromise) {
    configPromise = fetch(`${API_BASE}/auth/config`)
      .then((r) => (r.ok ? r.json() : { provider: "local" }))
      .then((cfg: AuthConfig) => {
        try {
          sessionStorage.setItem(CONFIG_KEY, JSON.stringify(cfg));
        } catch {
          /* storage blocked: still usable for this page */
        }
        return cfg;
      })
      .catch(() => ({ provider: "local" as const }));
  }
  return configPromise;
}

function cachedConfig(): AuthConfig | null {
  try {
    const raw = sessionStorage.getItem(CONFIG_KEY);
    return raw ? (JSON.parse(raw) as AuthConfig) : null;
  } catch {
    return null;
  }
}

function base64url(bytes: Uint8Array): string {
  let s = "";
  bytes.forEach((b) => (s += String.fromCharCode(b)));
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function randomString(len = 48): string {
  const bytes = new Uint8Array(len);
  crypto.getRandomValues(bytes);
  return base64url(bytes);
}

function redirectUri(): string {
  return `${window.location.origin}/auth/callback`;
}

function endpoint(cfg: AuthConfig, path: string): string {
  return `${cfg.issuer}/protocol/openid-connect/${path}`;
}

/** Leave for the Keycloak login page. */
export async function startKeycloakSignIn(cfg: AuthConfig, uiLocale: string): Promise<void> {
  const verifier = randomString(48);
  const state = randomString(16);
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  sessionStorage.setItem(PENDING_KEY, JSON.stringify({ verifier, state }));
  const params = new URLSearchParams({
    client_id: cfg.client_id || "irep-web",
    response_type: "code",
    scope: "openid",
    redirect_uri: redirectUri(),
    state,
    code_challenge: base64url(new Uint8Array(digest)),
    code_challenge_method: "S256",
    ui_locales: uiLocale,
  });
  window.location.assign(`${endpoint(cfg, "auth")}?${params.toString()}`);
}

function storeTokens(t: TokenResponse): void {
  if (t.refresh_token) sessionStorage.setItem(REFRESH_KEY, t.refresh_token);
  if (t.id_token) sessionStorage.setItem(ID_TOKEN_KEY, t.id_token);
}

/** Handle /auth/callback: check state, exchange the code. Returns the access token. */
export async function completeKeycloakSignIn(cfg: AuthConfig, search: string): Promise<string> {
  const params = new URLSearchParams(search);
  const pendingRaw = sessionStorage.getItem(PENDING_KEY);
  sessionStorage.removeItem(PENDING_KEY);
  if (params.get("error")) throw new Error(params.get("error_description") || params.get("error") || "sign-in failed");
  const code = params.get("code");
  const pending = pendingRaw ? (JSON.parse(pendingRaw) as { verifier: string; state: string }) : null;
  if (!code || !pending || params.get("state") !== pending.state) throw new Error("state_mismatch");

  const res = await fetch(endpoint(cfg, "token"), {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: cfg.client_id || "irep-web",
      code,
      redirect_uri: redirectUri(),
      code_verifier: pending.verifier,
    }),
  });
  if (!res.ok) throw new Error(`token_exchange_${res.status}`);
  const t = (await res.json()) as TokenResponse;
  storeTokens(t);
  return t.access_token;
}

/** Use the refresh token once; returns a new access token or null. */
export async function refreshKeycloakToken(): Promise<string | null> {
  const cfg = cachedConfig();
  const refresh = sessionStorage.getItem(REFRESH_KEY);
  if (!cfg || cfg.provider !== "keycloak" || !refresh) return null;
  try {
    const res = await fetch(endpoint(cfg, "token"), {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ grant_type: "refresh_token", client_id: cfg.client_id || "irep-web", refresh_token: refresh }),
    });
    if (!res.ok) return null;
    const t = (await res.json()) as TokenResponse;
    storeTokens(t);
    return t.access_token;
  } catch {
    return null;
  }
}

/** Where to send the browser on sign-out (ends the Keycloak session too). */
export function keycloakLogoutUrl(): string | null {
  const cfg = cachedConfig();
  if (!cfg || cfg.provider !== "keycloak") return null;
  const idToken = sessionStorage.getItem(ID_TOKEN_KEY);
  const params = new URLSearchParams({
    client_id: cfg.client_id || "irep-web",
    post_logout_redirect_uri: `${window.location.origin}/login`,
  });
  if (idToken) params.set("id_token_hint", idToken);
  return `${endpoint(cfg, "logout")}?${params.toString()}`;
}

export function clearKeycloakSession(): void {
  sessionStorage.removeItem(REFRESH_KEY);
  sessionStorage.removeItem(ID_TOKEN_KEY);
}
