import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** Screens 10 (parent attendance) and 43 (approvals). Spec: docs/screens/10-43-parent-attendance-and-approvals.md */
function isoDaysAhead(days: number): string {
  const d = new Date(Date.now() + days * 86400000);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

test.describe("Screens 10/43: parent leave request and trainer approval", () => {
  test("a parent requests leave and the trainer approves it", { tag: ["@L09", "@L07"] }, async ({ page, browser }) => {
    const offset = 10 + (new Date().getMinutes() % 40);           // future dates: no past attendance changes
    const start = isoDaysAhead(offset);
    await loginAs(page, "parent", { phone: "9876543214" });
    await page.goto("/parent/attendance");
    await expect(page.getByTestId("pa-summary")).toBeVisible();
    await page.getByTestId("leave-start").fill(start);
    await page.getByTestId("leave-end").fill(start);
    await page.getByTestId("leave-reason").fill("Family function in the village");
    await page.getByTestId("leave-send").click();
    await expect(page.getByTestId("leave-sent")).toBeVisible();
    await expect(page.getByTestId("leave-row").filter({ hasText: start }).getByTestId("leave-status")).toHaveText("Waiting for the trainer");

    const ctx = await browser.newContext();
    const tp = await ctx.newPage();
    await loginAs(tp, "trainer");
    await tp.goto("/trainer/approvals");
    const item = tp.getByTestId("approval-leave").filter({ hasText: start });
    await expect(item).toContainText("Karthik");
    await item.getByTestId("approve").click();
    await expect(tp.getByTestId("approval-leave").filter({ hasText: start })).toHaveCount(0);
    await ctx.close();

    await page.reload();
    await expect(page.getByTestId("leave-row").filter({ hasText: start }).getByTestId("leave-status")).toHaveText("Approved");
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "trainer", { lang: "ta" });
    await page.goto("/trainer/approvals");
    await expect(page.getByTestId("tab-pending")).toHaveText("காத்திருப்பவை");
  });

  test("blocks the parent role from approvals", async ({ page }) => {
    await loginAs(page, "parent");
    await page.goto("/trainer/approvals");
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});
