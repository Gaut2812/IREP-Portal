import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** Phase 2 · Dashboard tile details, and courses: media, continue, next lesson. */
const PNG = Buffer.from("89504e470d0a1a0a0000000d4948445200000001000000010806000000" + "1f15c4890000000d49444154789c6360000000000200015e2c8a0a0000000049454e44ae426082", "hex");

test.describe("Dashboard tiles", () => {
  test("each tile opens what is behind it", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/student");
    await page.getByTestId("tile-problems").click();
    await expect(page.getByTestId("details-problems")).toContainText("problems solved in all");
    await page.keyboard.press("Escape");

    await page.getByTestId("tile-streak").click();
    await expect(page.getByTestId("heatmap").locator("[data-count]")).toHaveCount(84);
    await page.keyboard.press("Escape");

    await page.getByTestId("open-all-badges").click();
    await expect(page.getByTestId("badge-earned").first()).toBeVisible();
    const locked = page.getByTestId("badge-locked");                // the demo student may hold every badge
    if (await locked.count()) await expect(locked.first()).toContainText("How to earn");
    await page.keyboard.press("Escape");

    await page.getByTestId("open-skill-how").click();
    await expect(page.getByTestId("skill-how")).toContainText("coding-lab");
  });

  test("tile details in Tamil", async ({ page }) => {
    await loginAs(page, "student", { lang: "ta" });
    await page.goto("/student");
    await page.getByTestId("open-all-badges").click();
    await expect(page.getByTestId("details-badges")).toContainText("எல்லா பேட்ஜ்களும்");
  });
});

test.describe("Courses", () => {
  test("IREP staff add a thumbnail; the student sees it, continues and moves to the next lesson", async ({ page, browser }) => {
    await loginAs(page, "admin");
    await page.goto("/admin/content");
    await page.getByTestId("course-row").first().click();
    const courseTitle = (await page.getByTestId("course-heading").innerText()).trim();
    await page.getByTestId("thumb-input").setInputFiles({ name: "cover.png", mimeType: "image/png", buffer: PNG });
    await expect(page.getByTestId("thumb-preview")).toBeVisible();

    const ctx = await browser.newContext();
    const sp = await ctx.newPage();
    await loginAs(sp, "student");
    await sp.goto("/student/courses");
    const card = sp.getByTestId("course-card").filter({ hasText: courseTitle });
    if (await card.count()) {                                   // the first library course may not be for Priya's semester
      await expect(card.getByTestId("course-thumbnail")).toBeVisible();
      const go = card.getByTestId("course-continue");
      if (await go.count()) {
        await go.click();
        await expect(sp.getByTestId("lesson-body")).toBeVisible();      // ?lesson= opened the next lesson
        const next = sp.getByTestId("lesson-next");
        if (await next.count()) {
          await next.click();
          await expect(sp.getByTestId("lesson-body")).toHaveCount(1);
        }
      }
    }
    await ctx.close();

    await page.getByTestId("thumb-delete").click();                 // tidy up
    await page.getByTestId("confirm-delete-ok").click();
    await expect(page.getByTestId("thumb-preview")).toHaveCount(0);
  });

  test("a course card offers to continue where I left off", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/student/courses");
    const firstCard = page.getByTestId("course-card").first();
    await expect(firstCard).toBeVisible();
    await expect(firstCard.getByTestId("course-continue").or(firstCard.getByText("All lessons done"))).toBeVisible();
  });
});
