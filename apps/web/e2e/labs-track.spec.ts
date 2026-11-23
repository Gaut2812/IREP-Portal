import { test, expect } from "@playwright/test";
import { bearer, loginAs } from "./helpers/auth";

const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000/api/v1";

/** Labs track: browser labs (PGlite) with beacons, and the trainer lab board. Spec: docs/labs/README.md */
test.describe("Labs track: browser labs and the trainer lab board", () => {
  test("a student runs SQL in the browser lab and the trainer sees and stops it", async ({ page, browser }) => {
    test.setTimeout(120_000);                                                         // PGlite downloads once (~3 MB)
    const { token } = await loginAs(page, "student");
    await page.goto("/student/labs");
    await page.getByTestId("stop-session").click();                                    // the seeded notebook session
    await expect(page.getByTestId("active-session")).toContainText("No lab running");
    await page.getByTestId("lab-lab_sql_browser").getByRole("button", { name: /Launch/ }).click();
    await page.getByTestId("open-session").click();
    await expect(page.getByTestId("workspace-status")).toContainText("running");
    await expect(page.getByTestId("engine-status")).toHaveText("Ready", { timeout: 90_000 });
    await page.getByTestId("sql-run").click();
    await expect(page.getByTestId("sql-output")).toContainText("Asha");
    await expect(page.getByTestId("sql-output")).toContainText("82");

    // S13 exercise checker: the answer is checked on the server, which never sends it to the page
    await expect(page.getByTestId("exercise-score")).toHaveText("0/35");
    await page.getByTestId("exercise-item").first().click();
    await page.getByTestId("sql-editor").fill("SELECT name FROM marks WHERE score >= 80;");
    await page.getByTestId("sql-run").click();
    await expect(page.getByTestId("sql-output")).toContainText("Meera");
    await page.getByTestId("exercise-check").click();
    await expect(page.getByTestId("exercise-verdict")).toHaveText("Correct! Well done.");
    await expect(page.getByTestId("exercise-score")).toHaveText("10/35");

    const ctx = await browser.newContext();
    const trainer = await ctx.newPage();
    await loginAs(trainer, "trainer");
    await trainer.goto("/trainer/labs");
    const row = trainer.getByTestId("lab-board-row").filter({ hasText: "Priya R" });
    await expect(row).toContainText("SQL Playground");
    await trainer.getByTestId("lab-board-reason").fill("Class is over");
    await row.getByTestId("lab-board-stop").click();
    await expect(trainer.getByTestId("lab-board-msg")).toContainText("Priya R");
    await ctx.close();

    await page.reload();
    await expect(page.getByTestId("workspace-status")).toContainText("stopped");
    // leave Priya as the seed has her (the AI Notebook running) for the screen 29 spec
    const relaunch = await page.request.post(`${API}/student/labs/lab_ai_notebook/launch`, { headers: bearer(token) });
    expect(relaunch.ok()).toBeTruthy();
  });

  test("the lab board supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "trainer", { lang: "ta" });
    await page.goto("/trainer/labs");
    await expect(page.getByRole("heading", { level: 1, name: "ஆய்வகப் பலகை" })).toBeVisible();
  });

  test("students cannot open the lab board", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/trainer/labs");
    await expect(page.getByTestId("lab-board")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});
