import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** S16 DPDP: a minor asks, the parent (fresh OTP sign-in) approves; notices in Tamil; role guards.
 *  Demo: Vinoth S (17, vinoth.s@demo.edu) and his mother Selvi S (mobile 9876543216). Re-seed before a re-run. */
const VINOTH = { identifier: "vinoth.s@demo.edu" };
const SELVI = { phone: "9876543216" };

test.describe.serial("S16 DPDP: consent for minors", () => {
  test("a minor asks; the parent approves and declines on the Consent page", async ({ page }) => {
    await loginAs(page, "student", VINOTH);
    await page.goto("/student/privacy");
    await expect(page.getByRole("heading", { level: 1, name: "My data & consent" })).toBeVisible();
    await expect(page.getByTestId("purpose-ai_hints").getByTestId("purpose-state")).toHaveText("Requested");
    await expect(page.getByTestId("ask-parent")).toContainText("under 18");
    await page.getByTestId("grant-recordings").click();
    await expect(page.getByTestId("consent-note")).toContainText("Request sent");
    await expect(page.getByTestId("purpose-recordings").getByTestId("purpose-state")).toHaveText("Requested");

    await page.context().clearCookies();
    await loginAs(page, "parent", SELVI);
    await page.goto("/parent/consent");
    const child = page.getByTestId("consent-child");
    await expect(child).toContainText("Vinoth S");
    await expect(page.getByTestId("reauth-note")).toHaveCount(0);                 // just signed in with the OTP
    await child.getByTestId("approve-ai_hints").click();
    await expect(child.getByTestId("purpose-ai_hints").getByTestId("purpose-state")).toHaveText("On");
    await child.getByTestId("decline-recordings").click();
    await expect(child.getByTestId("purpose-recordings").getByTestId("purpose-state")).toHaveText("Off");
    await expect(child.getByTestId("purpose-ai_hints")).toContainText("Anthropic");   // the notice says where questions go
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "parent", { ...SELVI, lang: "ta" });
    await page.goto("/parent/consent");
    await expect(page.getByRole("heading", { level: 1, name: "ஒப்புதல்" })).toBeVisible();
    await expect(page.getByTestId("purpose-ai_hints")).toContainText("AI படிப்பு நண்பர்");
    await expect(page.getByTestId("data-requests")).toContainText("உங்கள் தரவு");
  });

  test("an adult student decides alone and can ask for a copy", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/student/privacy");
    await expect(page.getByText("You are 18 or older")).toBeVisible();
    await expect(page.getByTestId("ask-parent")).toHaveCount(0);
    await expect(page.getByTestId("req-submit")).toBeVisible();
  });

  test("role guards: a student cannot open the parent's Consent page", async ({ page }) => {
    await loginAs(page, "student", VINOTH);
    await page.goto("/parent/consent");
    await expect(page.getByTestId("consent-child")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});
