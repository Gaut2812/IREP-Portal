import { test, expect, Page, Locator, Frame } from "@playwright/test";

/**
 * IREP Portal tutorial video. One continuous recording:
 * every role signs in through the real login page and signs out from the
 * profile menu; the parent chapter runs inside a phone frame (390 px wide)
 * to show the mobile layout. Captions explain each step.
 */

const t0 = Date.now();
const log = (msg: string) => console.log(`[demo] t=${((Date.now() - t0) / 1000).toFixed(0)}s ${msg}`);
let stepNo = 0;

// ---------- on-screen helpers ----------
async function caption(page: Page, title: string, sub = "") {
  await page.evaluate(({ title, sub }) => {
    let el = document.getElementById("demo-caption");
    if (!el) {
      el = document.createElement("div");
      el.id = "demo-caption";
      el.style.cssText = "position:fixed;left:50%;bottom:20px;transform:translateX(-50%);z-index:2147483647;background:rgba(15,31,58,.94);color:#fff;padding:12px 22px;border-radius:14px;font:600 17px Inter,Segoe UI,Arial,sans-serif;box-shadow:0 10px 30px rgba(0,0,0,.35);max-width:78%;text-align:center;pointer-events:none;border:1px solid rgba(255,255,255,.15)";
      document.body.appendChild(el);
    }
    el.innerHTML = `${title}${sub ? `<div style="font-weight:400;font-size:14px;opacity:.88;margin-top:4px;line-height:1.35">${sub}</div>` : ""}`;
  }, { title, sub }).catch(() => undefined);
}

async function hideCaption(page: Page) {
  await page.evaluate(() => document.getElementById("demo-caption")?.remove()).catch(() => undefined);
}

/** Full-screen chapter card. */
async function chapter(page: Page, kicker: string, title: string, points: string[], ms = 5000) {
  await page.evaluate(({ kicker, title, points }) => {
    const el = document.createElement("div");
    el.id = "demo-chapter";
    el.style.cssText = "position:fixed;inset:0;z-index:2147483647;background:linear-gradient(135deg,#14284B,#1E3A6E 55%,#1E6B7B);color:#fff;display:flex;align-items:center;justify-content:center;font-family:Inter,Segoe UI,Arial,sans-serif";
    el.innerHTML = `<div style="max-width:900px;padding:40px">
      <div style="font-size:16px;letter-spacing:.18em;text-transform:uppercase;color:#2BB3A0;font-weight:700">${kicker}</div>
      <div style="font-size:46px;font-weight:800;margin:10px 0 26px;line-height:1.15">${title}</div>
      ${points.map((p) => `<div style="font-size:21px;margin:12px 0;display:flex;gap:14px;align-items:flex-start"><span style="color:#2BB3A0">●</span><span>${p}</span></div>`).join("")}
    </div>`;
    document.body.appendChild(el);
  }, { kicker, title, points }).catch(() => undefined);
  await page.waitForTimeout(ms);
  await page.evaluate(() => document.getElementById("demo-chapter")?.remove()).catch(() => undefined);
}

/** Draw a pulsing ring around the element the viewer should look at. */
async function ring(page: Page, target: Locator) {
  const box = await target.boundingBox().catch(() => null);
  if (!box) return;
  await page.evaluate((b) => {
    document.getElementById("demo-ring")?.remove();
    const r = document.createElement("div");
    r.id = "demo-ring";
    r.style.cssText = `position:fixed;left:${b.x - 6}px;top:${b.y - 6}px;width:${b.width + 12}px;height:${b.height + 12}px;border:3px solid #F59E0B;border-radius:12px;box-shadow:0 0 0 6px rgba(245,158,11,.25);z-index:2147483646;pointer-events:none;transition:all .2s`;
    document.body.appendChild(r);
  }, box).catch(() => undefined);
}
async function clearRing(page: Page) {
  await page.evaluate(() => document.getElementById("demo-ring")?.remove()).catch(() => undefined);
}

/** Tutorial step: caption + highlight, then the action. */
async function doStep(page: Page, target: Locator, title: string, sub: string, action: (l: Locator) => Promise<unknown>, after = 1600) {
  stepNo += 1;
  const label = `Step ${stepNo} · ${title}`;
  try {
    await target.scrollIntoViewIfNeeded({ timeout: 8000 });
    await caption(page, label, sub);
    await ring(page, target);
    await page.waitForTimeout(1500);
    await action(target);
    await clearRing(page);
    await page.waitForTimeout(after);
  } catch (e) {
    await clearRing(page);
    log(`${label} SKIPPED: ${(e as Error).message.split("\n")[0]}`);
  }
}

/** Show something without clicking it. */
async function show(page: Page, target: Locator, title: string, sub: string, ms = 3200) {
  stepNo += 1;
  try {
    await expect(target).toBeVisible({ timeout: 15000 });
    await target.scrollIntoViewIfNeeded({ timeout: 5000 });
    await caption(page, `Step ${stepNo} · ${title}`, sub);
    await ring(page, target);
    await page.waitForTimeout(ms);
    await clearRing(page);
  } catch (e) {
    await clearRing(page);
    log(`show ${title} SKIPPED: ${(e as Error).message.split("\n")[0]}`);
  }
}

async function guard(name: string, fn: () => Promise<void>) {
  try { await fn(); } catch (e) { log(`${name} SKIPPED: ${(e as Error).message.split("\n")[0]}`); }
}

async function go(page: Page, path: string, ready: Locator) {
  await page.goto(path, { waitUntil: "domcontentloaded", timeout: 30000 });
  await expect(ready).toBeVisible({ timeout: 20000 });
  await page.waitForTimeout(600);
}

async function scrollMain(page: Page | Frame, y: number) {
  await page.evaluate((y) => { const m = document.querySelector("main"); (m || window).scrollTo({ top: y, behavior: "smooth" } as any); }, y).catch(() => undefined);
  await (("waitForTimeout" in page) ? (page as Page).waitForTimeout(1300) : new Promise((r) => setTimeout(r, 1300)));
}

// ---------- sign in / out through the real UI ----------
async function signIn(page: Page, role: "student" | "trainer" | "college", who: string) {
  await guard(`sign in ${role}`, async () => {
    await page.goto("/login", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("login-submit")).toBeVisible({ timeout: 15000 });
    await doStep(page, page.getByTestId(`role-${role}`), `Choose the ${role === "college" ? "College" : role[0].toUpperCase() + role.slice(1)} role`, `Signing in as ${who}`, (l) => l.click(), 900);
    await doStep(page, page.getByTestId("login-password"), "Enter the password", "Demo password: password123", (l) => l.fill("password123"), 600);
    await doStep(page, page.getByTestId("login-submit"), "Sign in", "The API checks the password and returns a signed JWT for this user only", async (l) => {
      await l.click();
      await page.waitForURL(`**/${role}`, { timeout: 20000 });
    }, 1500);
  });
}

async function signOut(page: Page, title = "Sign out from the profile menu") {
  await guard("sign out", async () => {
    await doStep(page, page.getByTestId("profile-button"), "Open the profile menu", "Click your avatar: name, role, email, college and language", (l) => l.click(), 2200);
    await doStep(page, page.getByTestId("sign-out"), title, "The session is cleared and you return to the login page", async (l) => {
      await l.click();
      await page.waitForURL("**/login", { timeout: 15000 });
    }, 1200);
  });
}

// ---------- phone frame for the parent chapter ----------
const PHONE_HOST = `<!doctype html><html><head><meta charset="utf-8"><title>IREP · Parent on mobile</title>
<style>
  html,body{margin:0;height:100%;font-family:Inter,Segoe UI,Arial,sans-serif;background:linear-gradient(135deg,#0F1F3A,#14284B 50%,#1E6B7B);color:#fff;overflow:hidden}
  .wrap{display:flex;height:100%;align-items:center;justify-content:center;gap:70px}
  .side{max-width:440px}
  .kick{color:#2BB3A0;font-weight:700;letter-spacing:.16em;text-transform:uppercase;font-size:14px}
  h1{font-size:38px;margin:10px 0 18px;line-height:1.15}
  .side p{font-size:17px;line-height:1.5;color:#CBD5E1;margin:8px 0}
  #notes li{font-size:16px;margin:10px 0;color:#E2E8F0}
  .phone{width:390px;border-radius:44px;background:#0B1324;padding:30px 12px 14px;box-shadow:0 30px 80px rgba(0,0,0,.55),inset 0 0 0 2px #334155;position:relative}
  .notch{position:absolute;top:11px;left:50%;transform:translateX(-50%);width:90px;height:8px;background:#1E293B;border-radius:6px}
  iframe{width:390px;height:812px;border:0;border-radius:26px;background:#fff;display:block}
  .size{margin-top:12px;font-size:13px;color:#94A3B8}
</style></head><body><div class="wrap">
  <div class="side"><div class="kick">Chapter 5 · Parent on mobile</div><h1>The parent portal on a phone</h1>
    <p>This is the real portal running at phone width (390 × 812). Parents sign in with their mobile number and an OTP.</p>
    <ul id="notes"></ul><div class="size">Live app inside a phone frame · same server, same data</div></div>
  <div class="phone"><div class="notch"></div><iframe id="phone" src="/login"></iframe></div>
</div></body></html>`;

async function note(page: Page, text: string) {
  await page.evaluate((text) => {
    const ul = document.getElementById("notes");
    if (!ul) return;
    const li = document.createElement("li");
    li.textContent = "✓ " + text;
    ul.appendChild(li);
    while (ul.children.length > 6) ul.removeChild(ul.firstChild!);
  }, text).catch(() => undefined);
}

// =====================================================================
test("IREP Portal tutorial", async ({ page }) => {
  // ---------------- Intro ----------------
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("login-submit")).toBeVisible({ timeout: 20000 });
  await chapter(page, "IREP Portal · Tutorial", "Industry-Ready Engineer Program",
    ["One portal for students, trainers, colleges and parents", "Every number comes from the database (612-student demo cohort)",
     "English and Tamil on every screen", "This video walks through each role step by step"], 6500);

  // ---------------- Chapter 1: Sign-in ----------------
  await chapter(page, "Chapter 1", "Signing in", ["Four roles on one sign-in card", "Students, trainers and college staff use a password", "Parents use their mobile number and an OTP", "Five wrong passwords lock an account for 15 minutes"]);
  await guard("login tour", async () => {
    await doStep(page, page.getByTestId("login-lang"), "Switch the sign-in card to Tamil", "Every label is translated; the choice is saved to the account after sign-in", (l) => l.click(), 2200);
    await doStep(page, page.getByTestId("login-lang"), "Back to English", "", (l) => l.click(), 800);
    await doStep(page, page.getByTestId("login-password"), "Try a wrong password", "The server never logs anyone in on failure", (l) => l.fill("wrong-password"), 400);
    await doStep(page, page.getByTestId("login-submit"), "Sign in with the wrong password", "The error shows how many attempts are left before the account locks", (l) => l.click(), 2600);
  });

  // ---------------- Chapter 2: Student ----------------
  await chapter(page, "Chapter 2", "Student · Priya R (Sem 5, AI & DS)", ["Dashboard and readiness score", "Live classes, coding lab and practice tests", "Virtual labs, sprint board, mock interviews and discussion groups"]);
  await signIn(page, "student", "Priya R");

  await guard("student dashboard", async () => {
    await expect(page.getByTestId("readiness-card")).toBeVisible({ timeout: 20000 });
    await show(page, page.getByTestId("readiness-card"), "Student dashboard · Readiness score", "74 / 100 from the nightly readiness job; tap it to see why");
    await doStep(page, page.getByTestId("readiness-card"), "Open \"Why this score\"", "Weighted breakdown: coding, aptitude, projects, communication, attendance", (l) => l.click(), 3000);
    await guard("close why", async () => { await page.getByRole("button", { name: "Close" }).last().click({ timeout: 5000 }); });
    await caption(page, "Student dashboard", "This week's classes, current project, upcoming events and badges");
    await scrollMain(page, 650);
    await page.waitForTimeout(2200);
  });

  await guard("notifications", async () => {
    await doStep(page, page.getByTestId("notification-bell"), "Notifications", "Each user sees only their own notifications (interview booked, lab approved, feedback ready)", (l) => l.click(), 3200);
    await page.keyboard.press("Escape");
    await page.mouse.click(700, 120);
  });

  await guard("live sessions", async () => {
    await go(page, "/student/live", page.getByTestId("week-table"));
    await show(page, page.getByTestId("week-table"), "Live sessions this week", "Join opens 10 minutes before start; status comes from attendance records");
    await doStep(page, page.getByRole("button", { name: "Watch Cloud deploy walkthrough" }), "Watch a recording", "Recordings play from short-lived signed links with chapters", (l) => l.click(), 2800);
    await guard("close rec", async () => { await page.getByRole("button", { name: "Close" }).click({ timeout: 5000 }); });
  });

  await guard("coding", async () => {
    await go(page, "/student/coding/prob_connected_components", page.getByText("Number of Connected Components").first());
    await caption(page, "Coding lab", "Problem statement, code editor, sample tests and an AI reviewer that gives hints only");
    await page.waitForTimeout(2500);
    await doStep(page, page.getByRole("button", { name: /Submit/i }).first(), "Submit the solution", "The code runs against hidden test cases", async (l) => {
      await l.click();
      await expect(page.getByText(/hidden tests passed/i).first()).toBeVisible({ timeout: 25000 });
    }, 2800);
  });

  await guard("practice test", async () => {
    await go(page, "/student/tests/test_service_aptitude", page.getByText(/Question 12 of/));
    await caption(page, "Practice test", "Timer, question palette, autosave every 10 s; copy/paste and tab switches are logged");
    await page.waitForTimeout(2600);
    await doStep(page, page.getByRole("button", { name: /^B\b/ }).first(), "Choose an answer", "", (l) => l.click(), 700);
    await doStep(page, page.getByRole("button", { name: "Save & Next" }), "Save & Next", "Moves to question 13", (l) => l.click(), 900);
    await doStep(page, page.getByRole("button", { name: "Mark for review" }), "Mark for review", "Shown in amber in the palette", (l) => l.click(), 1200);
    await doStep(page, page.getByRole("button", { name: "Submit Test" }).first(), "Submit the test", "A summary shows answered, review and unanswered counts", (l) => l.click(), 1600);
    await doStep(page, page.getByRole("button", { name: "Confirm Submit" }), "Confirm", "Scored on the server", async (l) => {
      await l.click();
      await expect(page.getByText("Test Submitted Successfully!")).toBeVisible({ timeout: 15000 });
    }, 1500);
    await caption(page, "Practice test · Result", "Score, accuracy, section analysis and explanations for every question");
    await page.waitForTimeout(2500);
    await scrollMain(page, 600);
    await page.waitForTimeout(1500);
  });

  await guard("labs", async () => {
    await go(page, "/student/labs", page.getByTestId("active-session"));
    await show(page, page.getByTestId("active-session"), "Virtual labs · active session", "AI Notebook running; minutes and credits are metered");
    await doStep(page, page.getByTestId("open-session"), "Open the lab workspace", "Browser terminal connected to the lab session", (l) => l.click(), 1500);
    await expect(page.getByTestId("lab-workspace")).toBeVisible({ timeout: 15000 });
    await doStep(page, page.getByTestId("terminal-input"), "Run a command", "", async (l) => { await l.fill("echo hello from the IREP lab"); await l.press("Enter"); }, 2200);
    await go(page, "/student/labs", page.getByTestId("active-session"));
    await doStep(page, page.getByTestId("launch-lab_cyber_range"), "Request the Cyber Range", "Restricted lab: needs the acceptable-use agreement and trainer approval", (l) => l.click(), 1500);
    await doStep(page, page.getByTestId("aup-accept"), "Accept the acceptable-use agreement", "", (l) => l.check(), 800);
    await doStep(page, page.getByTestId("aup-submit"), "Send the request to the trainer", "The trainer is notified; we approve it in Chapter 3", (l) => l.click(), 2600);
  });

  await guard("sprint board", async () => {
    await go(page, "/student/projects/board", page.getByTestId("board-header"));
    await show(page, page.getByTestId("board-header"), "Sprint board", "Team project: To Do → In Progress → Code Review → Done; progress and velocity computed");
    await doStep(page, page.getByTestId("standup-button"), "Post today's stand-up", "", (l) => l.click(), 900);
    await guard("standup", async () => {
      await page.getByTestId("standup-yesterday").fill("Finished the booking API tests");
      await page.getByTestId("standup-today").fill("Slot reminders via SMS");
      await doStep(page, page.getByTestId("standup-submit"), "Share the stand-up", "Teammates and the trainer see it on the board", (l) => l.click(), 2000);
    });
  });

  await guard("interviews", async () => {
    await go(page, "/student/interviews", page.getByTestId("latest-interview"));
    await show(page, page.getByTestId("latest-interview"), "Mock interviews · latest feedback", "Rubric scores, trend across interviews, recording with time-stamped comments");
    await doStep(page, page.getByTestId("book-slot_demo_hr"), "Book an open slot", "Each slot can be booked once; the trainer is notified", (l) => l.click(), 2600);
  });

  await guard("discussions", async () => {
    await go(page, "/student/discussions", page.getByTestId("conversation"));
    await caption(page, "Discussion groups", "Moderated by trainers; one-to-one chat between students is turned off");
    await page.waitForTimeout(2800);
    await doStep(page, page.getByTestId("message-input"), "Ask a doubt", "", (l) => l.fill("How do I choose k for k-fold cross validation?"), 500);
    await doStep(page, page.getByTestId("send"), "Send", "Posted to the group instantly (WebSocket push)", (l) => l.click(), 2200);
  });

  await signOut(page);

  // ---------------- Chapter 3: Trainer ----------------
  await chapter(page, "Chapter 3", "Trainer · Arun Kumar", ["Approve Priya's Cyber Range request", "Batches, at-risk students and today's schedule", "Message hub with Tamil translation, moderation and broadcasts", "Run a live class"]);
  await signIn(page, "trainer", "Arun Kumar");

  await guard("trainer dashboard", async () => {
    await expect(page.getByTestId("lab-approvals")).toBeVisible({ timeout: 20000 });
    const row = page.getByTestId("lab-approvals").locator("[data-testid^='approval-']", { hasText: "Priya R" });
    await show(page, row, "Lab access requests", "Priya's Cyber Range request from Chapter 2 is waiting here");
    await doStep(page, row.getByTestId("approve"), "Approve the request", "Priya is notified and can now launch the Cyber Range", (l) => l.click(), 2600);
    await scrollMain(page, 380);
    await show(page, page.getByTestId("trainer-kpis"), "Trainer dashboard", "5 batches · 248 students · attendance, pending reviews and at-risk count from live data");
    await scrollMain(page, 1100);
    await doStep(page, page.getByTestId("support-action").first(), "Act on an at-risk student", "The action is logged and the parent is alerted once", (l) => l.click(), 2600);
  });

  await guard("message hub", async () => {
    await go(page, "/trainer/messages", page.getByTestId("thread-list"));
    await caption(page, "Message hub", "Parents, college staff and moderated groups in one place");
    await page.waitForTimeout(2600);
    await doStep(page, page.getByTestId("toggle-tamil"), "Translate the conversation to Tamil", "Mr. Ramesh prefers Tamil; the original stays one tap away", (l) => l.click(), 2800);
    await doStep(page, page.getByTestId("toggle-tamil"), "Back to the original", "", (l) => l.click(), 900);
    await doStep(page, page.getByTestId("thread-th_lakshmi"), "Open Mrs. Lakshmi's thread", "2 unread messages", (l) => l.click(), 1600);
    await doStep(page, page.getByTestId("reply-input"), "Type a reply", "", (l) => l.fill("Yes, extra coaching is at 10 AM on Saturday in Lab 3."), 400);
    await doStep(page, page.getByTestId("send"), "Send the reply", "The parent gets an in-app notification and an SMS", (l) => l.click(), 2000);
    await doStep(page, page.getByTestId("reason-rep_seed_01"), "Moderation queue: give a reason", "Removing a reported message always needs a reason", (l) => l.fill("Shares graded test answers"), 500);
    await doStep(page, page.getByTestId("remove-rep_seed_01"), "Remove the reported message", "Recorded in the moderation log and audit trail", (l) => l.click(), 2000);
    await doStep(page, page.getByTestId("new-broadcast"), "New announcement", "", (l) => l.click(), 900);
    await guard("broadcast form", async () => {
      await page.getByTestId("bc-batch").selectOption("bat_aids_s5_aids");
      await page.getByTestId("bc-title").fill("Saturday lab timing");
      await page.getByTestId("bc-body").fill("Lab starts at 10:00 in Lab 3. Bring your laptop charger.");
      await doStep(page, page.getByTestId("bc-send"), "Send the broadcast", "Delivery report: students in-app, parents in-app + SMS", (l) => l.click(), 3200);
    });
  });

  await guard("live class", async () => {
    await go(page, "/live/sess_thu_rag", page.getByTestId("start-class"));
    await doStep(page, page.getByTestId("start-class"), "Start the live class", "Students in the batch can now join", (l) => l.click(), 1500);
    await expect(page.getByTestId("stage-code")).toBeVisible({ timeout: 15000 });
    await caption(page, "Live classroom", "Shared stage, live poll, moderated Q&A; attendance is marked automatically at 75% presence");
    await page.waitForTimeout(3500);
    await doStep(page, page.getByTestId("end-class"), "End the class", "Attendance is finalised for the whole batch", (l) => l.click(), 2400);
  });

  await guard("reviews", async () => {
    await go(page, "/trainer/reviews", page.getByText(/Pull Request|PR/).first());
    await caption(page, "Code reviews", "Pull-request queue, diff viewer and rubric; approving moves the sprint card to Done");
    await page.waitForTimeout(3200);
  });

  await signOut(page);

  // ---------------- Chapter 4: College ----------------
  await chapter(page, "Chapter 4", "College admin · Dr. Kavitha", ["612 students across 4 branches", "Readiness distribution, certifications and branch comparison", "MoU progress reports as PDF"]);
  await signIn(page, "college", "Dr. Kavitha");
  await guard("college", async () => {
    await expect(page.getByTestId("college-kpis")).toBeVisible({ timeout: 20000 });
    await show(page, page.getByTestId("college-kpis"), "College dashboard", "Totals aggregated live from the student records");
    await show(page, page.getByTestId("readiness-donut"), "Placement readiness", "Placement ready / nearly ready / needs support");
    await doStep(page, page.getByTestId("semester-filter"), "Filter by semester", "Every chart and table updates", (l) => l.selectOption("6"), 2600);
    await guard("reset filter", async () => { await page.getByTestId("semester-filter").selectOption({ index: 0 }); });
    await show(page, page.getByTestId("branch-table"), "Branch comparison", "Students, attendance and readiness per branch");
    await show(page, page.getByTestId("mou-reports"), "MoU reports", "Download PDF reports with generated and data-as-of dates");
  });
  await signOut(page);

  // ---------------- Chapter 5: Parent on mobile ----------------
  await chapter(page, "Chapter 5", "Parent · Mr. Ramesh K (on a phone)", ["Mobile-first layout", "Sign in with mobile number + OTP", "Monthly progress card, events RSVP, message the trainer", "Tamil with one tap"]);
  await page.route("**/__phone-preview", (route) => route.fulfill({ status: 200, contentType: "text/html", body: PHONE_HOST }));
  await page.goto("/__phone-preview", { waitUntil: "domcontentloaded" });
  const phone = page.frameLocator("#phone");
  const frame = () => page.frames().find((f) => f !== page.mainFrame())!;

  await guard("parent otp", async () => {
    await expect(phone.getByTestId("role-parent")).toBeVisible({ timeout: 20000 });
    await page.waitForTimeout(1500);
    await doStep(page, phone.getByTestId("role-parent"), "Choose Parent", "Parents sign in with their mobile number", (l) => l.click(), 900);
    await doStep(page, phone.getByTestId("login-phone"), "Enter the mobile number", "9876543210 · Mr. Ramesh K", (l) => l.fill("9876543210"), 400);
    await doStep(page, phone.getByTestId("login-submit"), "Get OTP", "A 6-digit OTP is sent by SMS (shown on screen in the demo)", (l) => l.click(), 1500);
    const otp = ((await phone.getByTestId("demo-otp").innerText()).match(/\d{6}/) || [""])[0];
    await doStep(page, phone.getByTestId("login-otp"), "Enter the OTP", "Valid for 5 minutes · 5 tries", (l) => l.fill(otp), 400);
    await doStep(page, phone.getByTestId("login-submit"), "Verify & enter", "", async (l) => {
      await l.click();
      await expect(phone.getByTestId("ward-name")).toBeVisible({ timeout: 20000 });
    }, 1500);
    await note(page, "Signed in with mobile + OTP");
  });

  await guard("parent overview", async () => {
    await show(page, phone.getByTestId("parent-kpis"), "Child's progress at a glance", "Readiness, attendance, problems solved, certifications");
    await note(page, "Readiness, attendance and certifications");
    await doStep(page, phone.getByTestId("monthly-card"), "Monthly progress card", "Released by the trainer; includes how parents can help at home", async () => {
      await phone.getByTestId("monthly-card").scrollIntoViewIfNeeded();
    }, 3000);
    await note(page, "Monthly progress card");
    await doStep(page, phone.getByTestId("rsvp-yes").first(), "RSVP to an event", "Saved for the college; works on a slow phone connection", (l) => l.click(), 2000);
    await note(page, "Event RSVP");
    await scrollMain(frame(), 0);
    await doStep(page, phone.getByRole("button", { name: "Toggle Tamil / English" }).first(), "Switch to Tamil", "The whole screen changes language", (l) => l.click(), 3000);
    await note(page, "Tamil with one tap");
    await doStep(page, phone.getByRole("button", { name: "Toggle Tamil / English" }).first(), "Back to English", "", (l) => l.click(), 900);
    // make sure the phone is in English before continuing
    const header = phone.getByTestId("lang-toggle");
    if ((await header.innerText()).includes("English")) await header.click();
    await page.waitForTimeout(800);
  });

  await guard("parent menu + messages", async () => {
    await doStep(page, phone.getByTestId("open-nav"), "Open the menu", "On phones the sidebar slides in from the left", (l) => l.click(), 1600);
    await doStep(page, phone.getByTestId("mobile-nav").locator('a[href="/parent/messages"]'), "Message Trainer", "", (l) => l.click(), 1800);
    await expect(phone.getByTestId("parent-input")).toBeVisible({ timeout: 15000 });
    await doStep(page, phone.getByTestId("parent-input"), "Write to the trainer", "Tamil or English; the trainer can translate", (l) => l.fill("Thank you sir, we will make sure she practises daily."), 400);
    await doStep(page, phone.getByTestId("parent-send"), "Send", "Trainers usually reply within 24 hours", (l) => l.click(), 2400);
    await note(page, "Message the trainer");
  });

  await guard("close drawer", async () => { if (await phone.getByTestId("mobile-nav").count()) await frame().press("body", "Escape"); });
  await guard("parent portfolio", async () => {
    await doStep(page, phone.getByTestId("open-nav"), "Open the menu", "", (l) => l.click(), 1000);
    await doStep(page, phone.getByTestId("mobile-nav").locator('a[href="/parent/portfolio"]'), "Projects & Portfolio", "Plain-language project cards and Demo Day invitation", async (l) => {
      await l.click();
      await expect(phone.getByText("Engineering Project Portfolio")).toBeVisible({ timeout: 20000 });
    }, 2500);
    await scrollMain(frame(), 700);
    await page.waitForTimeout(1500);
    await note(page, "Projects and portfolio");
    await doStep(page, phone.getByTestId("profile-button"), "Profile menu", "Name, role and Sign out — same as on desktop", (l) => l.click(), 2500);
    await doStep(page, phone.getByTestId("sign-out"), "Sign out", "", (l) => l.click(), 1500);
  });

  // ---------------- Outro ----------------
  await hideCaption(page);
  await chapter(page, "Summary", "All 14 mockup screens are built", [
    "Real sign-in for every role; each user sees only their own data and notifications",
    "Student: dashboard, live classes, coding lab, practice tests, labs, sprint board, interviews, discussions",
    "Trainer: dashboard, lab approvals, code reviews, message hub, live classroom",
    "College dashboard and the mobile parent portal · English and Tamil throughout",
  ], 8000);
  log(`finished, ${stepNo} steps`);
});
