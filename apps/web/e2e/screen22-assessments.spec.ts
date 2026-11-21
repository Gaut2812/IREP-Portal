import { test, expect } from "@playwright/test";
import { bearer, loginAs } from "./helpers/auth";

/** Screen 22 · Assessments. Spec: docs/screens/22-assessments.md */
const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000/api/v1";

test.describe("Screen 22: assessments (/trainer/assessments)", () => {
  test("a test goes down to the batch and the score comes back", { tag: "@L13" }, async ({ page, browser }) => {
    const title = `Quick aptitude ${Date.now().toString(36).slice(-5)}`;
    await loginAs(page, "trainer");
    await page.goto("/trainer/assessments");
    await page.getByTestId("assess-tab-tests").click();
    await page.getByTestId("assess-new").click();
    await page.getByTestId("t-save").click();                                              // empty: inline error, no request
    await expect(page.getByTestId("assess-error")).toContainText("Add a title");
    await page.getByTestId("t-title").fill(title);
    const q = page.getByTestId("t-question").first();
    await q.getByTestId("q-text").fill("Next in 2, 4, 8, ?");
    for (const [o, v] of [["a", "10"], ["b", "12"], ["c", "16"], ["d", "14"]]) await q.getByTestId(`q-opt-${o}`).fill(v);
    await q.getByTestId("q-correct").selectOption("C");
    await page.getByTestId("t-save").click();
    await expect(page.getByTestId("assess-heading")).toHaveText(title);
    await expect(page.getByTestId("assess-status")).toHaveText("Draft");
    await page.getByTestId("batch-bat_aids_s5_aids").check();
    await page.getByTestId("assess-publish").click();
    await expect(page.getByTestId("assess-msg")).toContainText("Published");
    await expect(page.getByTestId("assess-status")).toHaveText("Published");

    const ctx = await browser.newContext();
    const student = await ctx.newPage();
    const { token } = await loginAs(student, "student");
    await student.goto("/student/tests");
    const card = student.getByTestId("student-test").filter({ hasText: title });
    await expect(card).toContainText("1 questions");
    const href = await card.getAttribute("href");
    const testId = (href || "").split("/").pop() as string;
    const att = await (await student.request.post(`${API}/student/tests/${testId}/attempts`, { headers: bearer(token) })).json();
    await student.request.post(`${API}/student/tests/attempts/${att.attempt_id}/submit`, { headers: bearer(token), data: { answers: { "1": "C" } } });
    await ctx.close();

    await page.getByTestId("assess-row").filter({ hasText: title }).click();
    await expect(page.getByTestId("result-row").filter({ hasText: "Priya R" })).toContainText("1/1");
  });

  test("a bank test imports as a draft", { tag: "@L37" }, async ({ page }) => {
    await loginAs(page, "trainer");
    await page.goto("/trainer/assessments");
    await page.getByTestId("assess-tab-bank").click();
    await page.getByTestId("bank-row").filter({ hasText: "Aptitude core" }).getByTestId("bank-import").click();
    await expect(page.getByTestId("assess-msg")).toContainText("Imported as a draft");
    await expect(page.getByTestId("assess-heading")).toHaveText("Aptitude core: 5 questions");
    await expect(page.getByTestId("assess-status")).toHaveText("Draft");
  });

  test("IREP staff see the bank on the content library", async ({ page }) => {
    await loginAs(page, "admin");
    await page.goto("/admin/content");
    await page.getByTestId("content-tab-bank").click();
    await expect(page.getByTestId("bank-item").filter({ hasText: "Pair with a target sum" })).toBeVisible();
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "trainer", { lang: "ta" });
    await page.goto("/trainer/assessments");
    await expect(page.getByRole("heading", { level: 1, name: "மதிப்பீடுகள்" })).toBeVisible();
    await expect(page.getByTestId("assess-tab-bank")).toHaveText("IREP வங்கி");
  });

  test("students cannot open assessments", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/trainer/assessments");
    await expect(page.getByTestId("assess-list")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});
