import { test, expect, Page, APIRequestContext } from "@playwright/test";

const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8001/api/v1";
type Role = "student" | "trainer" | "college" | "parent";

const CREDS: Record<Role, any> = {
  student: { role: "student", identifier: "priya.r@demo.edu", password: "password123" },
  trainer: { role: "trainer", identifier: "arun.k@demo.edu", password: "password123" },
  college: { role: "college", identifier: "admin@demo.edu", password: "password123" },
  parent: { phone: "9876543210" },
};

const t0 = Date.now();
const log = (msg: string) => console.log(`[demo] t=${((Date.now() - t0) / 1000).toFixed(0)}s ${msg}`);

async function tokenFor(request: APIRequestContext, role: Role) {
  if (role === "parent") {
    const r = await (await request.post(`${API}/auth/parent/otp/request`, { data: { phone: CREDS.parent.phone } })).json();
    return (await request.post(`${API}/auth/parent/otp/verify`, { data: { phone: CREDS.parent.phone, otp: r.demo_otp || "123456" } })).json();
  }
  return (await request.post(`${API}/auth/login`, { data: CREDS[role] })).json();
}

/** Switch the single recorded browser session to another role (real JWT). */
async function signInAs(page: Page, role: Role, lang: "en" | "ta" = "en") {
  const data = await tokenFor(page.request, role);
  const user = { ...data.user, role: data.user.role === "college_admin" ? "college" : data.user.role };
  await page.evaluate(({ token, user, lang }) => {
    localStorage.setItem("irep_token", token);
    localStorage.setItem("irep_user", JSON.stringify(user));
    localStorage.setItem("irep_lang", lang);
  }, { token: data.access_token, user, lang });
  log(`signed in as ${role}`);
}

/** On-screen caption so the recording explains itself. */
async function caption(page: Page, title: string, sub = "") {
  await page.evaluate(({ title, sub }) => {
    let el = document.getElementById("demo-caption");
    if (!el) {
      el = document.createElement("div");
      el.id = "demo-caption";
      el.style.cssText = "position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:99999;background:rgba(15,31,58,.92);color:#fff;padding:10px 18px;border-radius:12px;font:600 15px Inter,Arial,sans-serif;box-shadow:0 8px 24px rgba(0,0,0,.3);max-width:80%;text-align:center;pointer-events:none";
      document.body.appendChild(el);
    }
    el.innerHTML = `${title}${sub ? `<div style="font-weight:400;font-size:12px;opacity:.85;margin-top:2px">${sub}</div>` : ""}`;
  }, { title, sub }).catch(() => undefined);
}

/** Run a step without letting a failure abort the recording. */
async function step(name: string, fn: () => Promise<void>) {
  const start = Date.now();
  try {
    await fn();
  } catch (e) {
    log(`${name} SKIPPED: ${(e as Error).message.split("\n")[0]}`);
  }
  log(`${name} ${((Date.now() - start) / 1000).toFixed(1)}s`);
}

async function visit(page: Page, path: string, title: string, sub: string, ready: () => Promise<unknown>, dwell = 2500) {
  await step(title, async () => {
    await page.goto(path, { waitUntil: "domcontentloaded", timeout: 30000 });
    await ready();
    await caption(page, title, sub);
    await page.waitForTimeout(dwell);
  });
}

const visible = (page: Page, testId: string, text?: string) =>
  text ? expect(page.getByTestId(testId)).toContainText(text, { timeout: 15000 }) : expect(page.getByTestId(testId)).toBeVisible({ timeout: 15000 });

const scrollMain = async (page: Page, y: number) => {
  await page.evaluate((y) => { const m = document.querySelector("main"); (m || window).scrollTo({ top: y, behavior: "smooth" } as any); }, y);
  await page.waitForTimeout(1400);
};

test("IREP Portal progress demo", async ({ page }) => {
  // ---- Title + Screen 01 ----
  await step("login", async () => {
    await page.goto("/login", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Welcome back").first()).toBeVisible({ timeout: 15000 });
    await caption(page, "IREP Portal · progress demo", "Next.js + FastAPI · real logins (JWT) · Tamil & English · data from the database");
    await page.waitForTimeout(3000);
    await caption(page, "Screen 01 · Sign-in & roles", "Four role views; parents sign in with mobile + OTP");
    await page.getByRole("button", { name: /Parent/ }).first().click({ timeout: 8000 });
    await page.waitForTimeout(1500);
    await page.getByRole("button", { name: /Student/ }).first().click({ timeout: 8000 });
    await page.waitForTimeout(1200);
  });

  // ---- Student ----
  await signInAs(page, "student");
  await visit(page, "/student", "Screen 12 · Student Dashboard", "Readiness 74 from nightly snapshot · skills, week plan, project, badges",
    () => visible(page, "readiness-card", "74"));
  await step("why-score", async () => {
    await page.getByTestId("readiness-card").click({ timeout: 8000 });
    await caption(page, "Screen 12 · \"Why this score\"", "Weighted breakdown computed by the readiness engine");
    await page.waitForTimeout(2800);
    await page.getByRole("button", { name: "Close" }).last().click({ timeout: 8000 });
    await scrollMain(page, 600);
  });

  await visit(page, "/student/live", "Screen 08 · Live Sessions & Recordings", "Join opens 10 min before start · attendance computed from 9 weeks of rows",
    () => visible(page, "week-table"));
  await step("recording", async () => {
    await page.getByRole("button", { name: "Watch Cloud deploy walkthrough" }).click({ timeout: 8000 });
    await caption(page, "Screen 08 · Recording player", "Short-lived signed link + chapters");
    await page.waitForTimeout(2500);
    await page.getByRole("button", { name: "Close" }).click({ timeout: 8000 });
  });

  await visit(page, "/student/coding/prob_connected_components", "Screen 24 · Coding Lab", "Monaco editor · sample & hidden tests · AI reviewer (hints only)",
    () => expect(page.getByText("Number of Connected Components").first()).toBeVisible({ timeout: 15000 }), 2000);
  await step("coding-submit", async () => {
    await page.getByRole("button", { name: /Submit/i }).first().click({ timeout: 8000 });
    await expect(page.getByText(/hidden tests passed/i).first()).toBeVisible({ timeout: 20000 });
    await caption(page, "Screen 24 · Submitted", "18 / 18 hidden tests passed");
    await page.waitForTimeout(2500);
  });

  await visit(page, "/student/labs", "Screen 29 · Virtual Labs", "Entitlement by semester/track · quotas · idle culler · Cyber Range approval",
    () => visible(page, "active-session", "AI Notebook Lab"));
  await step("labs", async () => {
    await page.getByTestId("launch-lab_cyber_range").click({ timeout: 8000 });
    await caption(page, "Screen 29 · Cyber Range", "Acceptable-use agreement, then trainer approval");
    await page.waitForTimeout(2500);
    await page.getByTestId("aup-dialog").getByRole("button", { name: "Cancel" }).last().click({ timeout: 8000 });
    await page.getByTestId("open-session").click({ timeout: 8000 });
    await visible(page, "lab-workspace");
    await page.getByTestId("terminal-input").fill("echo hello from the IREP lab", { timeout: 8000 });
    await page.getByTestId("terminal-input").press("Enter");
    await caption(page, "Screen 29 · Lab workspace", "Heartbeat keeps the session alive; docker adapter in production");
    await page.waitForTimeout(2500);
  });

  await visit(page, "/student/portfolio", "Screen 32 · Student Portfolio", "Verified projects and skills", () => page.waitForTimeout(2000), 3000);

  // ---- Trainer ----
  await signInAs(page, "trainer");
  await visit(page, "/trainer", "Screen 13 · Trainer Dashboard", "5 batches · 248 students · at-risk rule engine · live schedule",
    () => visible(page, "trainer-kpis"));
  await step("support-action", async () => {
    await scrollMain(page, 900);
    await page.getByTestId("support-action").first().click({ timeout: 8000 });
    await caption(page, "Screen 13 · Support action", "Logged on the flag, parent alerted once (respects quiet hours)");
    await page.waitForTimeout(2500);
  });

  await visit(page, "/live/sess_thu_rag", "Screen 07 · Live Classroom", "Trainer starts the class from the waiting room",
    () => visible(page, "start-class"), 1800);
  await step("live-class", async () => {
    await page.getByTestId("start-class").click({ timeout: 8000 });
    await visible(page, "stage-code");
    await caption(page, "Screen 07 · Live Classroom", "Stage, live poll, moderated Q&A, presence → auto attendance at 75%");
    await page.waitForTimeout(3500);
    await page.getByTestId("end-class").click({ timeout: 8000 });
    await visible(page, "live-lobby", "This class has ended");
    await caption(page, "Screen 07 · Class ended", "Attendance finalized for the whole batch");
    await page.waitForTimeout(2200);
  });

  await visit(page, "/trainer/reviews", "Screen 31 · Trainer Code Reviews", "PR queue · diff viewer · rubric · approve moves the sprint card",
    () => page.waitForTimeout(2000), 3000);

  // ---- College ----
  await signInAs(page, "college");
  await visit(page, "/college", "Screen 19 · College Dashboard", "612 students aggregated live · readiness donut · branch table",
    () => visible(page, "college-kpis", "612"));
  await step("college-filter", async () => {
    await scrollMain(page, 600);
    await page.getByTestId("semester-filter").selectOption("6", { timeout: 8000 });
    await caption(page, "Screen 19 · Semester filter", "MoU report PDFs with generated & data-as-of dates");
    await page.waitForTimeout(2500);
  });

  // ---- Parent ----
  await signInAs(page, "parent");
  await page.setViewportSize({ width: 420, height: 860 });
  await visit(page, "/parent", "Screen 15 · Parent View", "Mobile-first PWA · released monthly card · RSVP",
    () => visible(page, "monthly-card", "October"));
  await step("parent", async () => {
    await page.getByTestId("rsvp-yes").first().click({ timeout: 8000 });
    await page.waitForTimeout(1500);
    await page.getByRole("button", { name: "Toggle Tamil / English" }).first().click({ timeout: 8000 });
    await caption(page, "Screen 15 · Tamil", "Whole screen switches language without reload");
    await page.waitForTimeout(2800);
    await page.getByRole("button", { name: "Toggle Tamil / English" }).first().click({ timeout: 8000 });
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await visit(page, "/parent/portfolio", "Screen 33 · Parent Projects & Portfolio", "Plain-English project cards and Demo Day RSVP",
    () => page.waitForTimeout(2000), 3000);

  await caption(page, "Done so far: 12 screens full-stack (9 PDF mockups)", "Next: 30 Sprint Board (in progress), then 36, 34, 35 and 01 polish");
  await page.waitForTimeout(3500);
  log("finished");
});
