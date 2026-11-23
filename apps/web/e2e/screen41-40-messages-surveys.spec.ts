import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** Screens 41 (college messages) and 40 (parent survey, set up on 02). Spec: docs/screens/41-40-messages-surveys.md */
test.describe("Screens 41 and 40: college messages and parent surveys", () => {
  test("the college chats with a trainer", { tag: "@L20" }, async ({ page }) => {
    await loginAs(page, "college");
    await page.goto("/college/messages");
    await page.getByTestId("cmsg-new").selectOption({ label: "Arun Kumar" });
    await page.getByTestId("cmsg-input").fill("Can we move Friday's lab to 2 pm?");
    await page.getByTestId("cmsg-send").click();
    await expect(page.getByTestId("cmsg-chat")).toContainText("Friday's lab");
  });

  test("an announcement reaches parents' overview", { tag: "@L30" }, async ({ page, browser }) => {
    const title = `Parents' meeting ${Date.now().toString(36).slice(-5)}`;
    await loginAs(page, "college");
    await page.goto("/college/messages");
    await page.getByTestId("cmsg-tab-announcements").click();
    await page.getByTestId("ann-send").click();
    await expect(page.getByTestId("cmsg-error")).toContainText("Add a title");
    await page.getByTestId("ann-title").fill(title);
    await page.getByTestId("ann-body").fill("Saturday 10 am in the seminar hall.");
    await page.getByTestId("ann-audience").selectOption("parents");
    await page.getByTestId("ann-send").click();
    await expect(page.getByTestId("cmsg-msg")).toContainText("Sending to");
    await expect(page.getByTestId("ann-row").filter({ hasText: title })).toBeVisible();

    const ctx = await browser.newContext();
    const parent = await ctx.newPage();
    await loginAs(parent, "parent");
    await parent.goto("/parent");
    await expect(parent.getByTestId("announcement").filter({ hasText: title })).toContainText("From the college");
    await ctx.close();
  });

  test("a survey goes out and a parent answers it", { tag: "@L26" }, async ({ page, browser }) => {
    const title = `Lab week feedback ${Date.now().toString(36).slice(-5)}`;
    await loginAs(page, "college");
    await page.goto("/college/surveys");
    await page.getByTestId("survey-title").fill(title);
    await page.getByTestId("survey-title-ta").fill("ஆய்வக வாரக் கருத்து");
    await page.getByTestId("q-en").fill("How useful were the labs?");
    await page.getByTestId("q-ta").fill("ஆய்வகங்கள் எவ்வளவு பயனுள்ளவை?");
    await page.getByTestId("survey-save").click();
    const row = page.getByTestId("survey-row").filter({ hasText: title });
    await row.getByTestId("survey-publish").click();
    await expect(page.getByTestId("survey-msg")).toContainText("Parents notified");
    await expect(row.getByTestId("survey-status")).toContainText("Open");

    const ctx = await browser.newContext();
    const parent = await ctx.newPage();
    await loginAs(parent, "parent");
    await parent.goto("/parent/surveys");
    const s = parent.getByTestId("psurvey").filter({ hasText: title });
    await s.getByTestId("rate-4").click();
    await s.getByTestId("psurvey-submit").click();
    await expect(s.getByTestId("psurvey-thanks")).toContainText("Thank you");
    await ctx.close();
  });

  test("parent surveys support the Tamil toggle", async ({ page }) => {
    await loginAs(page, "parent", { lang: "ta" });
    await page.goto("/parent/surveys");
    await expect(page.getByRole("heading", { level: 1, name: "கருத்துக் கணிப்பு" })).toBeVisible();
    await expect(page.getByTestId("psurvey").filter({ hasText: "பருவக் கருத்துக் கணிப்பு" })).toContainText("இந்தப் பருவத்தில்");
  });

  test("trainers cannot open college messages", async ({ page }) => {
    await loginAs(page, "trainer");
    await page.goto("/college/messages");
    await expect(page.getByTestId("cmsg-threads")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});
