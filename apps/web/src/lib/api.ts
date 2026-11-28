import { refreshKeycloakToken } from "@/lib/oidc";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
export const WS_BASE = API_BASE.replace(/^http/, "ws");

/** Error raised for non-2xx responses; carries the HTTP status and the API `detail`. */
export class ApiError extends Error {
  status: number;
  detail: string;
  /** Set when the API answers with a structured error, e.g. "virus_found" or "scanner_unavailable". */
  code?: string;
  constructor(status: number, detail: string, code?: string) {
    super(`API Error ${status}: ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.code = code;
  }
}

/** Structured API errors carry {code, message, message_ta}: show the user's language. */
function structuredDetail(d: { code?: string; message?: string; message_ta?: string }): { text: string; code?: string } {
  let lang = "en";
  try { lang = localStorage.getItem("irep_lang") || "en"; } catch { /* storage blocked */ }
  return { text: (lang === "ta" && d.message_ta) || d.message || "", code: d.code };
}

const MOCK_TOKENS = new Set(["mock_jwt_token_demo", "mock_token"]);

function readStoredRole(): string | null {
  try {
    const raw = localStorage.getItem("irep_user");
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return typeof parsed?.role === "string" ? parsed.role : null;
  } catch {
    return null;
  }
}

/** Authorization headers for the current session (token first, dev demo-role header as fallback). */
export function authHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("irep_token");
  if (token && !MOCK_TOKENS.has(token)) {
    return { Authorization: `Bearer ${token}` };
  }
  const role = readStoredRole();
  return role ? { "X-Demo-Role": role } : {};
}

export async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const isForm = typeof FormData !== "undefined" && options.body instanceof FormData;   // multipart: the browser sets the boundary
  const headers: Record<string, string> = {
    ...(isForm ? {} : { "Content-Type": "application/json" }),
    ...authHeaders(),
    ...((options.headers as Record<string, string>) || {}),
  };

  let res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });

  // Keycloak access tokens are short-lived: refresh once and retry before signing out.
  if (res.status === 401 && !endpoint.startsWith("/auth/") && typeof window !== "undefined") {
    const fresh = await refreshKeycloakToken();
    if (fresh) {
      localStorage.setItem("irep_token", fresh);
      res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers: { ...headers, Authorization: `Bearer ${fresh}` } });
    }
  }

  if (res.status === 401 && !endpoint.startsWith("/auth/") && typeof window !== "undefined" && localStorage.getItem("irep_token")) {
    localStorage.removeItem("irep_token");
    localStorage.removeItem("irep_user");
    // IREP staff whose token does not show a two-factor sign-in: sign in again with the authenticator code
    window.location.href = res.headers.get("X-IREP-Reason") === "two_factor_required" ? "/login?reauth=2fa" : "/login?expired=1";
  }

  if (!res.ok) {
    let detail = res.statusText;
    let code: string | undefined;
    try {
      const body = await res.json();
      if (body && typeof body.detail === "string") detail = body.detail;
      else if (body && body.detail && typeof body.detail.message === "string") ({ text: detail, code } = structuredDetail(body.detail));
      else if (body && body.detail) detail = JSON.stringify(body.detail);
    } catch {
      /* body was not JSON */
    }
    throw new ApiError(res.status, detail, code);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Download helper for file endpoints (PDF, CSV). */
export async function fetchBlob(endpoint: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}${endpoint}`, { headers: authHeaders() });
  if (!res.ok) throw new ApiError(res.status, res.statusText);
  return await res.blob();
}

/** A signed media link from the API (`/media/...?exp=&sig=`) as a full URL on the API host. */
export const mediaSrc = (url: string) => `${API_BASE.replace(/\/api\/v1$/, "")}${url}`;
