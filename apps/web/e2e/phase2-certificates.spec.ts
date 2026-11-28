import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** Phase 2 · Certificates: an earned certificate downloads as a PDF for the student and the parent. */
test.describe("Certificate download", () => {
  test("the student downloads an earned certificate", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/student/certificates");
    const button = page.locator("[data-testid^='cert-download-']").first();
    await expect(button).toBeVisible();
    const download = page.waitForEvent("download");
    await button.click();
    expect((await download).suggestedFilename()).toMatch(/\.pdf$/);
  });

  test("the parent downloads the child's earned certificate", async ({ page }) => {
    await loginAs(page, "parent");
    await page.goto("/parent/certificates");
    const button = page.locator("[data-testid^='parent-cert-download-']").first();
    await expect(button).toBeVisible();
    const download = page.waitForEvent("download");
    await button.click();
    expect((await download).suggestedFilename()).toMatch(/\.pdf$/);
  });

  test("the download button in Tamil", async ({ page }) => {
    await loginAs(page, "student", { lang: "ta" });
    await page.goto("/student/certificates");
    await expect(page.locator("[data-testid^='cert-download-']").first()).toContainText("பதிவிறக்கு");
  });
});
