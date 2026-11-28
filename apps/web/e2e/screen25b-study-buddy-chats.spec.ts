import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** Phase 2 · AI Study Buddy: saved chats, practice mode, feedback, rename/delete, and "why did my submission fail".
 *  Named to run after screen23: the seed leaves Priya a practice test in progress, and Study Buddy is locked during a test. */
test.describe("Study Buddy chats", () => {
  test("a practice chat quizzes me; answers take thumbs; chats rename and delete", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/student/buddy");
    await page.getByTestId("buddy-new").click();
    await page.getByTestId("buddy-mode-practice").check();
    await page.getByTestId("buddy-start").click();
    await expect(page.getByTestId("buddy-context")).toContainText("Practice");
    await expect(page.getByTestId("buddy-input")).toHaveValue(/Quiz me/);
    await page.getByTestId("buddy-send").click();
    await expect(page.getByTestId("buddy-answer").last()).toContainText("Practice question");

    const up = page.getByTestId("buddy-up").last();
    await up.click();
    await expect(up).toHaveAttribute("aria-pressed", "true");

    const chat = page.getByTestId("buddy-conversation").first();
    await chat.hover();
    await chat.getByRole("button", { name: /Rename chat/ }).click();
    await page.getByTestId("buddy-rename-input").fill("Arrays quiz");
    await page.getByTestId("buddy-rename-input").press("Enter");
    await expect(page.getByTestId("buddy-conversations")).toContainText("Arrays quiz");

    const renamed = page.getByTestId("buddy-conversation").filter({ hasText: "Arrays quiz" });
    await renamed.hover();
    await renamed.getByTestId("buddy-delete-chat").click();
    await page.getByTestId("confirm-delete-ok").click();
    await expect(page.getByTestId("buddy-conversation").filter({ hasText: "Arrays quiz" })).toHaveCount(0);
  });

  test("a failed submission links to Study Buddy, which explains it in a new chat", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/student/coding/prob_two_sum");
    await page.getByTestId("submit-button").click();                                 // the stub fails the tests
    const link = page.getByTestId("explain-failure");
    await expect(link).toBeVisible();
    await link.click();
    await expect(page).toHaveURL(/\/student\/buddy\?explain=prob_two_sum/);
    await expect(page.getByTestId("buddy-conversations")).toContainText("Why did Two Sum fail?");
    await expect(page.getByTestId("buddy-question").first()).toContainText("Two Sum");
    await expect(page.getByTestId("buddy-answer").first()).toBeVisible();
  });

  test("Study Buddy chats in Tamil", async ({ page }) => {
    await loginAs(page, "student", { lang: "ta" });
    await page.goto("/student/buddy");
    await expect(page.getByTestId("buddy-new")).toContainText("புதிய உரையாடல்");
  });
});
