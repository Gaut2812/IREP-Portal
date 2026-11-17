import { test, expect, devices } from "@playwright/test";
import { loginAs } from "./helpers/auth";

test.describe("Screen 15: Parent View (/parent)", () => {
  test.use({ viewport: { width: 360, height: 780 }, isMobile: true, hasTouch: true });

  test("renders the child's card, monthly progress, portfolio, events and persists RSVP at 360px", async ({ page }) => {
    await loginAs(page, "parent");
    await page.goto("/parent");

    await expect(page.getByTestId("ward-name")).toContainText("Priya R · Sem 5 · AI & DS");
    const readiness = page.getByTestId("readiness-card");
    await expect(readiness).toContainText("74");
    await expect(readiness).toContainText("Nearly Ready");
    await expect(page.getByTestId("parent-kpis")).toContainText("92%");
    await expect(page.getByTestId("parent-kpis")).toContainText(/AWS exam on/);

    const card = page.getByTestId("monthly-card");
    await expect(card).toContainText("October");
    await expect(card).toContainText("Coding (problems solved)");
    await expect(card).toContainText("252");
    await expect(card).toContainText("286");
    await expect(card).toContainText("Needs practice");
    await expect(card).toContainText("How you can help");

    const demo = page.getByTestId("event-evt_demo_day");
    await expect(demo).toContainText("Project Demo Day");
    await demo.getByTestId("rsvp-yes").click();
    await expect(page.getByTestId("toast")).toContainText("RSVP saved");
    await expect(demo).toContainText("Attending");

    // RSVP survives a reload (persisted server-side)
    await page.reload();
    await expect(page.getByTestId("event-evt_demo_day")).toContainText("Attending");

    await expect(page.getByTestId("message-trainer")).toContainText("Replies within 24 hours");
    // no horizontal scroll at phone width
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "parent", { lang: "ta" });
    await page.goto("/parent");
    await expect(page.getByText("மாதாந்திர முன்னேற்ற அட்டை")).toBeVisible();
    await expect(page.getByTestId("monthly-card")).toContainText("அக்டோபர்");
    await expect(page.getByTestId("readiness-card")).toContainText("கிட்டத்தட்ட தயார்");
  });

  test("another parent sees only their own child", async ({ page }) => {
    await loginAs(page, "parent", { phone: "9876543214" });
    await page.goto("/parent");
    await expect(page.getByTestId("ward-name")).toContainText("Karthik S");
    await expect(page.getByTestId("readiness-card")).toContainText("52");
  });

  test("blocks the student role", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/parent");
    await expect(page.getByText(/Access Restricted/i).first()).toBeVisible();
  });
});
