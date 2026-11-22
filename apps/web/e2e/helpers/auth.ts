import { Page } from "@playwright/test";

/** "super" is the super admin (API role super_admin, web role admin); "admin" is plain IREP staff. */
export type DemoRole = "student" | "trainer" | "college" | "parent" | "admin" | "super";

const API_BASE = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000/api/v1";

const CREDENTIALS: Record<DemoRole, { identifier: string; password: string; phone?: string }> = {
  student: { identifier: "priya.r@demo.edu", password: "password123" },
  trainer: { identifier: "arun.k@demo.edu", password: "password123" },
  college: { identifier: "admin@demo.edu", password: "password123" },
  parent: { identifier: "ramesh.k@example.com", password: "password123", phone: "9876543210" },
  admin: { identifier: "staff@irep.demo", password: "password123" },
  super: { identifier: "super@irep.demo", password: "password123" },
};

// OTP requests are rate limited (5 per 10 min per phone), so each worker logs a
// parent in once and reuses the token.
const parentLogins = new Map<string, any>();

function toWebRole(apiRole: string): DemoRole {
  if (apiRole === "college_admin") return "college";
  if (apiRole === "irep_admin" || apiRole === "super_admin") return "admin";
  return apiRole as DemoRole;
}

/**
 * Log in through the real API with the seeded demo account for `role`
 * and seed localStorage so the app starts authenticated with a real JWT.
 * Optionally pass `phone` (another seeded parent) or `identifier` (another seeded account of that role).
 */
export async function loginAs(
  page: Page,
  role: DemoRole,
  options: { lang?: "en" | "ta"; phone?: string; identifier?: string } = {}
): Promise<{ token: string; user: any }> {
  const creds = CREDENTIALS[role];
  let data: any;
  if (role === "parent") {
    const phone = (options.phone || creds.phone) as string;
    const cached = parentLogins.get(phone);
    if (cached) {
      data = cached;
    } else {
      const req = await page.request.post(`${API_BASE}/auth/parent/otp/request`, { data: { phone } });
      const reqData = await req.json();
      const res = await page.request.post(`${API_BASE}/auth/parent/otp/verify`, {
        data: { phone, otp: reqData.demo_otp || "123456" },
      });
      if (!res.ok()) throw new Error(`Parent OTP login failed: ${res.status()}`);
      data = await res.json();
      parentLogins.set(phone, data);
    }
  } else {
    const res = await page.request.post(`${API_BASE}/auth/login`, {
      data: { role: role === "super" ? "admin" : role, identifier: options.identifier || creds.identifier, password: creds.password },
    });
    if (!res.ok()) throw new Error(`Login failed for ${role}: ${res.status()}`);
    data = await res.json();
  }
  const user = { ...data.user, role: toWebRole(data.user.role), super_admin: data.user.role === "super_admin" };
  const token: string = data.access_token;
  const lang = options.lang || "en";

  await page.addInitScript(
    ({ token, user, lang }) => {
      localStorage.setItem("irep_user", JSON.stringify(user));
      localStorage.setItem("irep_token", token);
      localStorage.setItem("irep_lang", lang);
    },
    { token, user, lang }
  );
  return { token, user };
}

/** Authorization header for direct API calls in specs. */
export function bearer(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` };
}
