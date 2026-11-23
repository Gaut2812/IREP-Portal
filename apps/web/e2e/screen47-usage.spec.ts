import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** Screen 47 · Usage and quotas (S12). Spec: docs/screens/47-usage-quotas.md */
test.describe("Screen 47: usage and quotas (/admin/usage)", () => {
  test("staff see each college's use against its MoU", async ({ page }) => {
    await loginAs(page, "admin");
    await page.goto("/admin/usage");
    const demo = page.getByTestId("usage-row").filter({ hasText: "Demo Engineering College" });
    await expect(demo).toContainText("students");
    await expect(demo.getByTestId("usage-lab_minutes")).toContainText("/");
    await expect(page.getByTestId("usage-summary")).toContainText("colleges");
    await page.getByTestId("usage-flagged").check();
    await expect(page.getByTestId("usage-table")).toBeVisible();
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "admin", { lang: "ta" });
    await page.goto("/admin/usage");
    await expect(page.getByRole("heading", { level: 1, name: "பயன்பாடு மற்றும் ஒதுக்கீடுகள்" })).toBeVisible();
  });

  test("college admins cannot open it", async ({ page }) => {
    await loginAs(page, "college");
    await page.goto("/admin/usage");
    await expect(page.getByTestId("usage-table")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});
