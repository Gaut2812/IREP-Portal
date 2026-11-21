import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** Screens 21 and 16 monthly cards, 20 MoU reports, 49 Support desk. Spec: docs/screens/21-16-20-49-reports-and-support.md */
test.describe("Screens 21 and 16: monthly cards (/trainer/reports, /parent/reports)", () => {
  test("the trainer approves a card and the parent reads it", { tag: "@L22" }, async ({ page, browser }) => {
    await loginAs(page, "trainer");
    await page.goto("/trainer/reports");
    await page.getByTestId("generate-drafts").click();
    await expect(page.getByTestId("report-msg")).toContainText("Drafts created");
    await page.getByTestId("card-row").filter({ hasText: "Priya R" }).click();
    await page.getByTestId("field-trainer_remark_en").fill("A focused month with a clear project demo.");
    await page.getByTestId("card-approve").click();                                        // Tamil missing: refused
    await expect(page.getByTestId("report-error")).toContainText("Tamil");
    await page.getByTestId("field-trainer_remark_ta").fill("தெளிவான புராஜெக்ட் விளக்கத்துடன் கவனமான மாதம்.");
    await page.getByTestId("field-how_to_help_en").fill("Ask Priya to show you her project this weekend.");
    await page.getByTestId("field-how_to_help_ta").fill("இந்த வார இறுதியில் தன் புராஜெக்ட்டைக் காட்டச் சொல்லுங்கள்.");
    await page.getByTestId("card-approve").click();
    await expect(page.getByTestId("card-released")).toBeVisible();

    const ctx = await browser.newContext();
    const parent = await ctx.newPage();
    await loginAs(parent, "parent");
    await parent.goto("/parent/reports");
    await expect(parent.getByTestId("report-remark").first()).toContainText("A focused month with a clear project demo.");
    const download = parent.waitForEvent("download");
    await parent.getByTestId("report-pdf").first().click();
    expect((await download).suggestedFilename()).toMatch(/^progress-.*\.pdf$/);
    await ctx.close();
  });

  test("parent reports support the Tamil toggle", async ({ page }) => {
    await loginAs(page, "parent", { lang: "ta" });
    await page.goto("/parent/reports");
    await expect(page.getByRole("heading", { level: 1, name: "முன்னேற்ற அறிக்கைகள்" })).toBeVisible();
    await expect(page.getByTestId("report-card").first()).toBeVisible();
  });

  test("students cannot open the trainer reports", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/trainer/reports");
    await expect(page.getByTestId("generate-drafts")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});

test.describe("Screen 20: MoU reports (/college/reports)", () => {
  test("the college generates and downloads a report", async ({ page }) => {
    await loginAs(page, "college");
    await page.goto("/college/reports");
    await expect(page.getByTestId("mou-row").first()).toBeVisible();                   // seeded runs (screen 19) are listed
    const before = await page.getByTestId("mou-row").count();
    await page.getByTestId("mou-generate").click();
    await expect(page.getByTestId("mou-row")).toHaveCount(before + 1);
    const download = page.waitForEvent("download");
    await page.getByTestId("mou-download").first().click();
    expect((await download).suggestedFilename()).toMatch(/\.pdf$/);
  });
});

test.describe("Screen 49: support desk (/support, /admin/support)", () => {
  test("a student reports a problem from a screen and staff reply", { tag: ["@L39", "@L28"] }, async ({ page, browser }) => {
    const subject = `Hint button spins ${Date.now().toString(36).slice(-5)}`;
    await loginAs(page, "student");
    await page.goto("/student");
    await page.getByTestId("profile-button").click();
    await page.getByTestId("report-problem").click();
    await page.waitForURL("**/support?from=%2Fstudent");
    await expect(page.getByTestId("ticket-from")).toContainText("/student");
    await page.getByTestId("ticket-subject").fill(subject);
    await page.getByTestId("ticket-body").fill("The hint button on problem 3 keeps spinning.");
    await page.getByTestId("ticket-submit").click();
    await expect(page.getByTestId("ticket-subject-heading")).toHaveText(subject);

    const ctx = await browser.newContext();
    const staff = await ctx.newPage();
    await loginAs(staff, "admin");
    await staff.goto("/admin/support");
    await staff.getByTestId("ticket-row").filter({ hasText: subject }).click();
    await expect(staff.getByTestId("ticket-detail")).toContainText("/student");
    await staff.getByTestId("ticket-reply").fill("Thanks: fixed, please reload the page.");
    await staff.getByTestId("ticket-send").click();
    await expect(staff.getByTestId("ticket-status")).toHaveText("Answered");
    await ctx.close();

    await page.goto("/notifications");                                                          // 44 Notification centre
    await expect(page.getByTestId("notification-item").filter({ hasText: `IREP support replied: ${subject}` })).toBeVisible();
    await page.goto("/support");
    await page.getByTestId("ticket-row").filter({ hasText: subject }).click();
    await expect(page.getByTestId("staff-message")).toContainText("fixed, please reload");
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "parent", { lang: "ta" });
    await page.goto("/support");
    await expect(page.getByRole("heading", { level: 1, name: "சிக்கலைத் தெரிவிக்கவும்" })).toBeVisible();
  });

  test("only IREP staff open the support desk", async ({ page }) => {
    await loginAs(page, "college");
    await page.goto("/admin/support");
    await expect(page.getByTestId("ticket-list")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});
