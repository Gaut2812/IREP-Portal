import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

const URL = "/student/tests/test_service_aptitude";

test.describe("Screen 23: Practice Test (/student/tests/:id)", () => {
  test("starts an attempt, answers, marks for review, submits and shows the result", async ({ page }) => {
    const crashes: string[] = [];
    page.on("crash", () => crashes.push("renderer crashed"));
    page.on("pageerror", (e) => crashes.push(e.message));

    await loginAs(page, "student");
    await page.goto(URL);

    // resumes on Q12 as in the mockup, with the palette and timer
    await expect(page.getByText(/Question 12 of \d+/)).toBeVisible();
    await expect(page.getByText("Question palette")).toBeVisible();

    // answer Q12 and go next
    await page.getByRole("button", { name: /^B\b/ }).first().click();
    await page.getByRole("button", { name: "Save & Next" }).click();
    await expect(page.getByText(/Question 13 of \d+/)).toBeVisible();

    // mark Q13 for review, then go back
    await page.getByRole("button", { name: "Mark for review" }).click();
    await expect(page.getByRole("button", { name: "Marked for review" })).toBeVisible();
    await page.getByRole("button", { name: "Previous" }).click();
    await expect(page.getByText(/Question 12 of \d+/)).toBeVisible();

    // submit
    await page.getByRole("button", { name: "Submit Test" }).first().click();
    await page.getByRole("button", { name: "Confirm Submit" }).click();
    await expect(page.getByText("Test Submitted Successfully!")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("Accuracy").first()).toBeVisible();
    await expect(page.getByText("Review Questions & Explanations")).toBeVisible();

    // let the page idle a moment: timers and autosave must not crash it
    await page.waitForTimeout(3000);
    expect(crashes).toEqual([]);
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "student", { lang: "ta" });
    await page.goto(URL);
    await expect(page.getByText("வினா பலகை")).toBeVisible();
    await expect(page.getByRole("button", { name: "சேமித்து அடுத்தது" })).toBeVisible();
  });

  test("blocks the parent role", async ({ page }) => {
    await loginAs(page, "parent");
    await page.goto(URL);
    await expect(page.getByText(/student/i).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Save & Next" })).toHaveCount(0);
  });
});
