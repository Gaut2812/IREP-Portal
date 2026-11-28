import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** Phase 4: College › Certifications names (D1), thread messages edit / delete for everyone, college explainers. */

test.describe("College certifications: who holds which certificate", () => {
  test("lists holders with names and filters by search", async ({ page }) => {
    await loginAs(page, "college");
    await page.goto("/college/certifications");
    const rows = page.getByTestId("holder-row");
    await expect(rows.first()).toBeVisible();
    const name = (await rows.first().locator("td").first().innerText()).trim();
    await expect(page.getByTestId("holders-total")).toContainText("certificates");
    await page.getByTestId("holders-search").fill(name.split(" ")[0]);
    await expect(rows.first()).toContainText(name.split(" ")[0]);
    await page.getByTestId("holders-search").fill("zzzz-nobody");
    await expect(page.getByTestId("cert-holders")).toContainText("No earned certificates match.");
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "college", { lang: "ta" });
    await page.goto("/college/certifications");
    await expect(page.getByTestId("cert-holders")).toContainText("யாரிடம் எந்தச் சான்றிதழ்");
  });

  test("parents cannot open it", async ({ page }) => {
    await loginAs(page, "parent");
    await page.goto("/college/certifications");
    await expect(page.getByTestId("cert-holders")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});

test.describe("Thread messages: edit and delete for everyone", () => {
  test("a parent edits a message, then deletes it after confirming", async ({ page }) => {
    const text = `Will send the form ${Date.now().toString(36).slice(-5)}`;
    await loginAs(page, "parent");
    await page.goto("/parent/messages");
    await page.getByTestId("parent-input").fill(text);
    await page.getByTestId("parent-send").click();
    const bubble = page.getByTestId("messages").locator("div.rounded-card").filter({ hasText: text });
    await expect(bubble).toBeVisible();
    await expect(bubble.getByTestId("dm-sent").or(bubble.getByTestId("dm-seen"))).toBeVisible();

    await bubble.getByTestId("dm-edit").click();
    await bubble.getByTestId("dm-edit-input").fill(`${text} tomorrow`);
    await bubble.getByTestId("dm-edit-save").click();
    const edited = page.getByTestId("messages").locator("div.rounded-card").filter({ hasText: `${text} tomorrow` });
    await expect(edited.getByTestId("dm-edited")).toHaveText("edited");

    await edited.getByTestId("dm-delete").click();
    await expect(page.getByTestId("confirm-delete")).toBeVisible();                  // asks first
    await page.getByTestId("confirm-delete-ok").click();
    await expect(page.getByTestId("messages")).not.toContainText(`${text} tomorrow`);
    await expect(page.getByTestId("dm-deleted").last()).toContainText("This message was deleted.");
  });
});

test.describe("College explainers", () => {
  for (const [path, title] of [
    ["/college/structure", "How branches and batches work"],
    ["/college/readiness", "How placement readiness works"],
    ["/college/drives", "How mock drives work"],
    ["/college/timetable", "Who changes the timetable"],
  ] as const) {
    test(`${path} explains itself`, async ({ page }) => {
      await loginAs(page, "college");
      await page.goto(path);
      await expect(page.getByText(title)).toBeVisible();
    });
  }
});
