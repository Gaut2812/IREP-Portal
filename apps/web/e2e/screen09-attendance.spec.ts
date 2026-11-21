import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** Screen 09 · Attendance (trainer) and student check-in. Spec: docs/screens/09-trainer-attendance.md */
const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000/api/v1";

function localIso(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:00`;
}

test.describe("Screen 09: Attendance (/trainer/attendance)", () => {
  test("the trainer shows the check-in code and a student checks in with it", async ({ page, browser }) => {
    const { token: trainerToken } = await loginAs(page, "trainer");
    const title = `Lab check-in ${Date.now().toString(36)}`;
    const start = new Date(Date.now() + 5 * 60000);
    const end = new Date(start.getTime() + 60 * 60000);
    const proposed = await (await page.request.post(`${API}/trainer/schedule/requests`, {
      headers: { Authorization: `Bearer ${trainerToken}` },
      data: { kind: "new", batch_id: "bat_aids_s5_aids", title, start: localIso(start), end: localIso(end), room: "Lab 2", reason: "In-lab practical with check-in" },
    })).json();
    const collegeCtx = await browser.newContext();
    const cp = await collegeCtx.newPage();
    const { token: collegeToken } = await loginAs(cp, "college");
    await cp.request.post(`${API}/college/schedule-requests/${proposed.id}/approve?override=true`, { headers: { Authorization: `Bearer ${collegeToken}` } });
    await collegeCtx.close();

    await page.goto("/trainer/attendance");
    await page.getByTestId("att-session").filter({ hasText: title }).click();
    await expect(page.getByTestId("att-title")).toHaveText(title);
    await page.getByTestId("checkin-show").click();
    const code = (await page.getByTestId("checkin-code").innerText()).trim();
    expect(code).toHaveLength(6);

    const studentCtx = await browser.newContext();
    const sp = await studentCtx.newPage();
    await loginAs(sp, "student");
    await sp.goto("/student/checkin");
    await sp.getByTestId("checkin-input").fill(code);
    await sp.getByTestId("checkin-submit").click();
    await expect(sp.getByTestId("checkin-result")).toContainText(title);
    await studentCtx.close();

    await page.reload();
    await page.getByTestId("att-session").filter({ hasText: title }).click();
    const priya = page.getByTestId("att-row").filter({ hasText: "Priya R" });
    await expect(priya.getByTestId("att-status")).toHaveText("Present");
    await expect(priya).toContainText("Check-in code");
  });

  test("the trainer overrides a past session's attendance with a reason", async ({ page }) => {
    await loginAs(page, "trainer");
    await page.goto("/trainer/attendance");
    const past = page.getByTestId("att-session").filter({ hasText: "DSA: Union-Find drill" }).first();
    await past.click();
    const row = page.getByTestId("att-row").filter({ hasText: "Sneha N" });
    await row.getByTestId("att-override").click();
    await page.getByTestId("override-status").selectOption("Present");
    await page.getByTestId("override-reason").fill("Was in the lab; network dropped");
    await page.getByTestId("override-save").click();
    await expect(page.getByTestId("att-row").filter({ hasText: "Sneha N" })).toContainText("Was in the lab; network dropped");
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "student", { lang: "ta" });
    await page.goto("/student/checkin");
    await expect(page.getByTestId("checkin-submit")).toHaveText("வருகையைப் பதிவு செய்");
  });

  test("blocks the student role from the trainer page", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/trainer/attendance");
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});
