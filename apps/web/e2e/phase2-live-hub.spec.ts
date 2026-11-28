import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** Phase 2 · Trainer live classroom hub (the sidebar used to open one fixed class). */
test.describe("Trainer live classroom hub", () => {
  test("the sidebar opens the hub, which lists upcoming and recent classes", async ({ page }) => {
    await loginAs(page, "trainer");
    await page.goto("/trainer");
    const link = page.getByTestId("desktop-sidebar").getByRole("link", { name: "Live Classroom" });
    await expect(link).toHaveAttribute("href", "/trainer/live");
    await link.click();
    await expect(page.getByTestId("live-hub")).toBeVisible();
    await expect(page.getByTestId("live-hub")).toContainText("Today and coming up");
    await expect(page.getByTestId("live-hub")).toContainText("Recent classes");
  });

  test("the hub in Tamil, and students cannot open it", async ({ page, browser }) => {
    await loginAs(page, "trainer", { lang: "ta" });
    await page.goto("/trainer/live");
    await expect(page.getByTestId("live-hub")).toContainText("சமீபத்திய வகுப்புகள்");
    const ctx = await browser.newContext();
    const sp = await ctx.newPage();
    await loginAs(sp, "student");
    await sp.goto("/trainer/live");
    await expect(sp.getByText(/Access Restricted/i).first()).toBeVisible();
    await ctx.close();
  });
});
