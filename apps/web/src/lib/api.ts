import { refreshKeycloakToken } from "@/lib/oidc";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
export const WS_BASE = API_BASE.replace(/^http/, "ws");

/** Error raised for non-2xx responses; carries the HTTP status and the API `detail`. */
export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(`API Error ${status}: ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
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
    window.location.href = "/login?expired=1";
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body && typeof body.detail === "string") detail = body.detail;
      else if (body && body.detail) detail = JSON.stringify(body.detail);
    } catch {
      /* body was not JSON */
    }
    throw new ApiError(res.status, detail);
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
