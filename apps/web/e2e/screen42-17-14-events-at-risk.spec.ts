import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** Screens 42 and 17 Events, 14 At-risk students. Spec: docs/screens/42-17-14-events-and-at-risk.md */

function inDays(days: number): string {
  const d = new Date(Date.now() + days * 86_400_000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T10:00`;
}

test.describe("Screens 42 and 17: events (/college/events, /parent/events)", () => {
  test("the college invites parents and their RSVPs come back as counts", { tag: "@L05" }, async ({ page, browser }) => {
    const title = `Parents' open day ${Date.now().toString(36).slice(-5)}`;
    await loginAs(page, "college");
    await page.goto("/college/events");
    await page.getByTestId("event-save").click();                                    // empty form: inline error, no request
    await expect(page.getByTestId("event-error")).toHaveText("Enter a title (at least 3 characters).");
    await page.getByTestId("event-title-en").fill(title);
    await page.getByTestId("event-title-ta").fill("பெற்றோர் திறந்த நாள்");
    await page.getByTestId("event-audience").selectOption("parents");
    await page.getByTestId("event-start").fill(inDays(3));
    await page.getByTestId("event-save").click();
    const row = page.getByTestId("event-row").filter({ hasText: title });
    await expect(row.getByTestId("event-status")).toHaveText("Draft");
    await row.getByTestId("event-publish").click();
    await expect(row.getByTestId("event-status")).toHaveText("Published");
    await expect(page.getByTestId("event-toast")).toContainText("Invited");

    const ctx = await browser.newContext();
    const parent = await ctx.newPage();
    await loginAs(parent, "parent");
    await parent.goto("/parent/events");
    const card = parent.getByTestId("event-card").filter({ hasText: title });
    await card.getByTestId("guest-count").selectOption("2");
    await card.getByTestId("rsvp-yes").click();
    await expect(card.getByTestId("rsvp-saved")).toBeVisible();
    await expect(card.getByTestId("rsvp-answer")).toHaveText("Attending · 2 people");
    await expect(card.getByTestId("rsvp-yes")).toHaveCount(0);                     // a confirmation card, not the buttons
    await expect(card.getByTestId("rsvp-change-until")).toBeVisible();

    await page.reload();
    await expect(row.getByTestId("rsvp-counts")).toContainText("Yes 1");
    await expect(row.getByTestId("rsvp-counts")).toContainText("Guests 2");

    // change the reply to "Can't come": it asks first, takes an optional reason, and the counts move
    await card.getByTestId("rsvp-change").click();
    await card.getByTestId("rsvp-no").click();
    await expect(card.getByTestId("rsvp-no-dialog")).toBeVisible();
    await card.getByTestId("rsvp-no-reason").fill("Travelling that week");
    await card.getByTestId("rsvp-no-confirm").click();
    await expect(card.getByTestId("rsvp-answer")).toHaveText("Can't come");
    await ctx.close();

    await page.reload();
    await expect(row.getByTestId("rsvp-counts")).toContainText("Yes 0");
    await expect(row.getByTestId("rsvp-counts")).toContainText("No 1");
    await row.getByTestId("decline-reasons-toggle").click();
    await expect(row.getByTestId("decline-reasons")).toContainText("Travelling that week");
    await row.getByTestId("event-cancel").click();                                   // tidy: parents are told it is off
    await expect(row.getByTestId("event-status")).toHaveText("Cancelled");
  });

  test("parent events support the Tamil toggle", async ({ page }) => {
    await loginAs(page, "parent", { lang: "ta" });
    await page.goto("/parent/events");
    await expect(page.getByRole("heading", { level: 1, name: "நிகழ்வுகள்" })).toBeVisible();
  });

  test("students cannot open the college events screen", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/college/events");
    await expect(page.getByTestId("event-form")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});

test.describe("Screen 14: at-risk students (/trainer/at-risk)", () => {
  test("a parent call reaches the parent's overview", { tag: "@L31" }, async ({ page, browser }) => {
    await loginAs(page, "trainer");
    await page.goto("/trainer/at-risk");
    await expect(page.getByTestId("risk-summary")).toBeVisible();
    await page.getByTestId("risk-row").filter({ hasText: "Karthik S" }).filter({ hasText: "4 sessions missed" }).click();
    await page.getByTestId("act-parent-call").click();
    const msg = page.getByTestId("risk-msg");
    await expect(msg).toHaveText(/Parent alerted|Quiet hours|already been alerted/);
    await expect(page.getByTestId("risk-history")).toContainText("Parent notified");
    const outcome = await msg.innerText();
    test.skip(/Quiet hours/.test(outcome), "The college's quiet hours hold the alert; the API tests cover delivery after them");

    const ctx = await browser.newContext();
    const parent = await ctx.newPage();
    await loginAs(parent, "parent", { phone: "9876543214" });
    await parent.goto("/parent");
    await expect(parent.getByTestId("support-alert").filter({ hasText: "4 sessions missed" })).toBeVisible();
    await parent.getByTestId("support-alert").filter({ hasText: "4 sessions missed" }).click();
    await parent.waitForURL("**/parent/messages");
    await ctx.close();
  });

  test("logs a phone call, assigns a mentor and lists the mentee", async ({ page }) => {
    await loginAs(page, "trainer");
    await page.goto("/trainer/at-risk");
    await page.getByTestId("risk-row").first().click();
    const detail = page.getByTestId("risk-detail");
    await expect(detail).toBeVisible();
    const student = (await detail.getByRole("heading", { level: 2 }).innerText()).trim();

    await page.getByTestId("act-log-call").click();
    await expect(page.getByTestId("risk-error")).toHaveText("Choose how the call went.");
    await page.getByTestId("call-outcome-call_back").click();
    await page.getByTestId("risk-note").fill("Father asked for a call after 6 pm");
    await page.getByTestId("act-log-call").click();
    await expect(page.getByTestId("risk-msg")).toHaveText("Call logged.");
    await expect(page.getByTestId("risk-history")).toContainText("Phone call");
    await expect(page.getByTestId("risk-history")).toContainText("Asked to call back: Father asked for a call after 6 pm");

    const me = await page.getByTestId("mentor-select").locator("option", { hasText: "(me)" }).getAttribute("value");
    await page.getByTestId("mentor-select").selectOption(me!);
    await page.getByTestId("act-mentor").click();
    await expect(page.getByTestId("risk-msg")).toHaveText(/Mentor assigned/);
    await expect(page.getByTestId("mentor-current")).not.toHaveText("No mentor yet.");

    await page.getByTestId("risk-tab-mentees").click();
    await expect(page.getByTestId("mentee-row").filter({ hasText: student })).toBeVisible();
    await page.getByTestId("mentee-row").filter({ hasText: student }).click();
    await page.getByTestId("act-mentor-remove").click();
    await expect(page.getByTestId("risk-msg")).toHaveText("Mentor removed.");
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "trainer", { lang: "ta" });
    await page.goto("/trainer/at-risk");
    await expect(page.getByRole("heading", { level: 1, name: "கவனம் தேவைப்படும் மாணவர்கள்" })).toBeVisible();
    await expect(page.getByTestId("risk-tab-open")).toHaveText("திறந்தவை");
  });

  test("parents cannot open the at-risk screen", async ({ page }) => {
    await loginAs(page, "parent");
    await page.goto("/trainer/at-risk");
    await expect(page.getByTestId("risk-list")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});
