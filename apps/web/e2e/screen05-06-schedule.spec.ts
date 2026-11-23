import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** Screens 05 (trainer schedule) and 06 (college timetable). Spec: docs/screens/05-06-schedule-and-timetable.md */
test.describe("Screens 05/06: schedule and timetable", () => {
  test("a trainer proposes a session and the college approves it on the timetable", { tag: "@L11" }, async ({ page, browser }) => {
    const title = `Mock drive prep ${Date.now().toString(36)}`;
    await loginAs(page, "trainer");
    await page.goto("/trainer/schedule");
    await expect(page.getByTestId("week-view")).toBeVisible();
    await page.getByTestId("proposal-kind").selectOption("new");
    await page.getByTestId("proposal-title").fill(title);
    await page.getByTestId("proposal-time").fill("06:30");
    await page.getByTestId("proposal-room").fill("Seminar Hall");
    await page.getByTestId("proposal-reason").fill("Extra practice before the mock drive");
    await page.getByTestId("proposal-send").click();
    await expect(page.getByTestId("my-request").filter({ hasText: title })).toContainText("Pending");

    const ctx = await browser.newContext();
    const cp = await ctx.newPage();
    await loginAs(cp, "college");
    await cp.goto("/college/timetable");
    const req = cp.getByTestId("pending-request").filter({ hasText: title });
    await expect(req).toBeVisible();
    await req.getByTestId("request-approve").click();
    await expect(cp.getByTestId("pending-request").filter({ hasText: title })).toHaveCount(0);
    await ctx.close();

    await page.reload();
    await expect(page.getByTestId("my-request").filter({ hasText: title })).toContainText("Approved");
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "college", { lang: "ta" });
    await page.goto("/college/timetable");
    await expect(page.getByTestId("pending-requests")).toContainText("ஒப்புதலுக்கான மாற்றங்கள்");
  });

  test("blocks the student role from both screens", async ({ page }) => {
    await loginAs(page, "student");
    for (const path of ["/trainer/schedule", "/college/timetable"]) {
      await page.goto(path);
      await expect(page.getByText(/Access restricted/i)).toBeVisible();
    }
  });
});
