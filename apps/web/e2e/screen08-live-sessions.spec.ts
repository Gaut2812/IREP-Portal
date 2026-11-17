import { test, expect } from "@playwright/test";
import { loginAs, bearer } from "./helpers/auth";

const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000/api/v1";

test.describe("Screen 08: Live Sessions & Recordings (/student/live)", () => {
  test("renders hero, week table, attendance summary and library; sets a reminder and opens a recording", async ({ page }) => {
    const { token } = await loginAs(page, "student");
    const expected = await (await page.request.get(`${API}/student/live`, { headers: bearer(token) })).json();

    await page.goto("/student/live");

    const hero = page.getByTestId("hero-session");
    await expect(hero).toContainText(expected.hero_session.title);
    if (expected.hero_session.join_enabled) {
      await expect(page.getByTestId("join-session")).toBeVisible();
    } else {
      await expect(page.getByTestId("join-session-disabled")).toBeDisabled();
      await expect(hero).toContainText("Join opens 10 min before start");
    }

    const table = page.getByTestId("week-table");
    await expect(table).toContainText("DSA: Union-Find drill");
    await expect(table).toContainText("Track project kick-off + RAG mini-lab");
    await expect(table).toContainText("In-lab / Hybrid");

    const summary = page.getByTestId("attendance-summary");
    await expect(summary).toContainText(`${expected.attendance_summary.overall_pct}%`);
    await expect(summary).toContainText(`${expected.attendance_summary.sessions_attended} of ${expected.attendance_summary.sessions_total} sessions`);

    // Remind me on the first session that still offers it
    const remindable = expected.week_sessions.find((r: any) => r.action === "remind_me" && !r.reminder_set);
    if (remindable) {
      await page.getByTestId(`remind-${remindable.id}`).click();
      await expect(page.getByTestId("toast")).toContainText("remind you 15 minutes before");
      await expect(page.getByTestId(`row-${remindable.id}`)).toContainText("Reminder set");
    }

    // Library recording opens a player with a signed link
    const library = page.getByTestId("recording-library");
    await expect(library).toContainText("Cloud deploy walkthrough");
    await page.getByRole("button", { name: "Watch Cloud deploy walkthrough" }).click();
    const player = page.getByTestId("recording-player");
    await expect(player).toBeVisible();
    await expect(player).toContainText("Chapters");
    await expect(player.locator("video")).toHaveAttribute("src", /\/media\/recordings\/library\/cloud_deploy\.mp4\?exp=\d+&sig=[0-9a-f]+/);
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "student", { lang: "ta" });
    await page.goto("/student/live");
    await expect(page.getByText("இந்த வார அமர்வுகள்")).toBeVisible();
    await expect(page.getByText("பதிவு நூலகம்")).toBeVisible();
    await expect(page.getByText("என் வருகை")).toBeVisible();
  });

  test("blocks the parent role", async ({ page }) => {
    await loginAs(page, "parent");
    await page.goto("/student/live");
    await expect(page.getByText(/Access Restricted/i).first()).toBeVisible();
  });
});
