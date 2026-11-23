import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** Screen 04 · Trainer batches. Spec: docs/screens/04-trainer-batches.md */
test.describe("Screen 04: Trainer batches (/trainer/batches)", () => {
  test("roster, student profile, private note, roster request rejected by the college", { tag: "@L24" }, async ({ page, browser }) => {
    await loginAs(page, "trainer");
    await page.goto("/trainer/batches");
    await page.getByTestId("batch-card-AI&DS").click();
    await expect(page.getByTestId("roster-row")).toHaveCount(50);
    await page.getByTestId("roster-search").fill("Vikram");
    await page.getByTestId("roster-row").first().getByRole("link").click();
    await expect(page.getByTestId("student-name")).toContainText("Vikram");

    await page.getByTestId("note-text").fill("Strong helper in the doubts group; give him the RAG lab lead.");
    await page.getByTestId("note-save").click();
    const note = page.getByTestId("note-row").filter({ hasText: "RAG lab lead" });
    await expect(note).toBeVisible();
    await note.getByTestId("note-delete").click();
    await expect(page.getByTestId("note-row").filter({ hasText: "RAG lab lead" })).toHaveCount(0);

    await page.getByTestId("request-kind").selectOption("remove");
    await page.getByTestId("request-reason").fill("Moving to the placement fast-track cohort");
    await page.getByTestId("request-send").click();
    await expect(page.getByTestId("request-pending")).toBeVisible();

    // the college sees it on screen 03 and rejects it (leaves the demo roster unchanged)
    const ctx = await browser.newContext();
    const cp = await ctx.newPage();
    await loginAs(cp, "college");
    await cp.goto("/college/structure");
    const req = cp.getByTestId("roster-request").filter({ hasText: "Vikram" });
    await expect(req).toBeVisible();
    cp.once("dialog", (d) => d.accept("Keep him in the batch until the end of the semester"));
    await req.getByTestId("roster-reject").click();
    await expect(cp.getByTestId("roster-request").filter({ hasText: "Vikram" })).toHaveCount(0);
    await ctx.close();
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "trainer", { lang: "ta" });
    await page.goto("/trainer/batches");
    await expect(page.getByRole("heading", { name: "மாணவர் பட்டியல்" })).toBeVisible();
  });

  test("blocks the student role", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/trainer/batches");
    await expect(page.getByTestId("batch-cards")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});
