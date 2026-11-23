import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** S16 billing (screen 47 full). Spec: docs/screens/47-16-billing-and-dpdp.md. Re-seed before running
 *  (the demo college starts with no invoices and a ₹5,000 credit). */
test.describe("S16: billing (/admin/billing, /college/billing)", () => {
  test("the super admin generates, issues and settles; the college sees its invoice", async ({ page, browser }) => {
    await loginAs(page, "super");
    await page.goto("/admin/billing");
    await page.getByTestId("billing-generate").click();
    await expect(page.getByTestId("billing-msg")).toContainText("Drafts are ready");
    const demo = page.getByTestId("invoice-col_demo_001");
    await expect(demo.getByTestId("invoice-status")).toHaveText("Draft");
    await demo.locator("button").first().click();                                      // open the lines
    await expect(demo.getByTestId("line-seats")).toContainText("IREP programme seats");
    await expect(demo.getByTestId("line-credit")).toContainText("-₹5,000.00");
    page.once("dialog", (d) => d.accept());
    await demo.getByTestId("invoice-issue").click();
    await expect(page.getByTestId("billing-msg")).toContainText("Invoice issued");
    await expect(demo.getByTestId("invoice-status")).toHaveText("Issued");
    await expect(demo).toContainText("IREP/");

    const ctx = await browser.newContext();                                            // the college's view
    const college = await ctx.newPage();
    await loginAs(college, "college");
    await college.goto("/college/billing");
    await expect(college.getByTestId("billing-credit")).toHaveText("₹0.00");
    await expect(college.locator("[data-testid^='college-invoice-IREP']")).toHaveCount(1);
    await expect(college.getByTestId("college-invoice-pdf")).toBeVisible();
    const outstanding = await college.getByTestId("billing-outstanding").innerText();
    expect(outstanding).not.toBe("₹0.00");
    await ctx.close();

    page.once("dialog", (d) => d.accept("UTR20261122001"));
    await demo.getByTestId("invoice-pay").click();
    await expect(demo.getByTestId("invoice-status")).toHaveText("Paid");
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "college", { lang: "ta" });
    await page.goto("/college/billing");
    await expect(page.getByRole("heading", { level: 1, name: "பில்லிங்" })).toBeVisible();
    await expect(page.getByTestId("billing-summary")).toContainText("மீதமுள்ள வரவு");
  });

  test("IREP staff cannot open billing", async ({ page }) => {
    await loginAs(page, "admin");
    await page.goto("/admin/billing");
    await expect(page.getByTestId("billing-forbidden")).toBeVisible();
    await expect(page.getByTestId("billing-invoices")).toHaveCount(0);
  });

  test("a student cannot open the college's billing", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/college/billing");
    await expect(page.getByTestId("college-invoices")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});
