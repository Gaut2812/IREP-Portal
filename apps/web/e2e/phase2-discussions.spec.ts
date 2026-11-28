import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** Phase 2 · Discussions: edit and delete your own message, emoji, seen ticks. */
test.describe("Discussion messages", () => {
  test("send with an emoji, edit it, react, then delete it", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/student/discussions");
    const text = `Edit-me question ${Math.random().toString(36).slice(2, 6)}`;
    await page.getByTestId("message-input").fill(text);
    await page.getByTestId("emoji-button").click();
    await page.getByTestId("emoji-🤔").click();
    await expect(page.getByTestId("message-input")).toHaveValue(`${text}🤔`);
    await page.getByTestId("send").click();

    const sent = page.getByTestId("messages").locator("[data-testid^='msg-']", { hasText: text });
    await expect(sent).toBeVisible();
    const msg = page.getByTestId((await sent.getAttribute("data-testid"))!);    // by id: the text changes on edit and delete
    await expect(msg.locator("[data-testid^='ticks-']")).toContainText(/Sent|Seen/);

    await msg.locator("[data-testid^='edit-']").first().click();
    await msg.locator("[data-testid^='edit-input-']").fill(`${text} (edited text)`);
    await msg.locator("[data-testid^='edit-save-']").click();
    await expect(msg.locator("[data-testid^='text-']")).toContainText("(edited text)");
    await expect(msg.locator("[data-testid^='text-']")).toContainText("edited");

    await msg.locator("[data-testid^='add-reaction-']").click();
    await msg.locator("[data-testid^='pick-'][data-testid$='-❤️']").click();
    await expect(msg.locator("[data-testid^='reaction-']").first()).toContainText("1");

    await msg.locator("[data-testid^='delete-']").click();
    await page.getByTestId("confirm-delete-ok").click();
    await expect(msg.locator("[data-testid^='text-']")).toContainText("This message was deleted.");
    await expect(msg.locator("[data-testid^='edit-']")).toHaveCount(0);
  });

  test("the message actions in Tamil", async ({ page }) => {
    await loginAs(page, "student", { lang: "ta" });
    await page.goto("/student/discussions");
    await page.getByTestId("message-input").fill("வணக்கம்");
    await page.getByTestId("send").click();
    const sent = page.getByTestId("messages").locator("[data-testid^='msg-']", { hasText: "வணக்கம்" }).last();
    await expect(sent).toContainText("திருத்து");
    const msg = page.getByTestId((await sent.getAttribute("data-testid"))!);
    await msg.locator("[data-testid^='delete-']").click();
    await page.getByTestId("confirm-delete-ok").click();
  });
});
