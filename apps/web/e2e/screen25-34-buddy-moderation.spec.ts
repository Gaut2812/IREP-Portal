import { test, expect } from "@playwright/test";
import { bearer, loginAs } from "./helpers/auth";

const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000/api/v1";

/** Screen 25 AI Study Buddy and screen 34 moderation words (S10). Specs: docs/screens/25-study-buddy.md */
test.describe("Screen 25: AI Study Buddy (/student/buddy)", () => {
  test("a student asks and gets a hint; the daily count goes down", async ({ page }) => {
    const { token } = await loginAs(page, "student");
    // Study Buddy pauses during a practice test: finish any attempt an earlier spec left running
    const att = await (await page.request.post(`${API}/student/tests/test_service_aptitude/attempts`, { headers: bearer(token) })).json();
    await page.request.post(`${API}/student/tests/attempts/${att.attempt_id}/submit`, { headers: bearer(token), data: { answers: {} } });
    await page.goto("/student/buddy");
    await expect(page.getByTestId("buddy-locked")).toHaveCount(0);
    const usage = page.getByTestId("buddy-usage");
    await expect(usage).toContainText("questions left today");
    const before = Number((await usage.innerText()).split("/")[0]);
    await page.getByTestId("buddy-topic").fill("Arrays");
    await page.getByTestId("buddy-input").fill("How do I find a pair that adds up to a target?");
    await page.getByTestId("buddy-send").click();
    await expect(page.getByTestId("buddy-answer").last()).toContainText("Good question about Arrays");
    await expect(usage).toContainText(`${before - 1}/`);
    await page.getByTestId("buddy-clear").click();
    await expect(page.getByTestId("buddy-answer")).toHaveCount(0);
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "student", { lang: "ta" });
    await page.goto("/student/buddy");
    await expect(page.getByRole("heading", { level: 1, name: "AI படிப்புத் துணை" })).toBeVisible();
  });

  test("trainers cannot open Study Buddy", async ({ page }) => {
    await loginAs(page, "trainer");
    await page.goto("/student/buddy");
    await expect(page.getByTestId("buddy-chat")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});

test.describe("Screen 34: moderation words (/college/moderation)", () => {
  test("the college adds and removes a word", async ({ page }) => {
    await loginAs(page, "college");
    await page.goto("/college/moderation");
    await page.getByTestId("mod-add").click();
    await expect(page.getByTestId("mod-error")).toContainText("Enter a word");
    await page.getByTestId("mod-term").fill("proxy attendance");
    await page.getByTestId("mod-action").selectOption("flag");
    await page.getByTestId("mod-add").click();
    const row = page.getByTestId("mod-row").filter({ hasText: "proxy attendance" });
    await expect(row).toContainText("Flag for review");
    await row.getByRole("button", { name: "Remove" }).click();
    await expect(page.getByTestId("mod-row")).toHaveCount(0);
  });

  test("students cannot open moderation words", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/college/moderation");
    await expect(page.getByTestId("mod-form")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});
