import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** Screens 46 Content library and 11 My courses. Spec: docs/screens/46-11-content-and-courses.md */
test.describe("Screens 46 and 11: content library (/admin/content) and my courses (/student/courses)", () => {
  test("staff publish a course; the student reads it and finishing a lesson raises the skill bar", { tag: ["@L12", "@L33"] }, async ({ page, browser }) => {
    const title = `Presenting your project ${Date.now().toString(36).slice(-5)}`;
    await loginAs(page, "admin");
    await page.goto("/admin/content");
    await page.getByTestId("course-save").click();                                   // empty title: inline error, no request
    await expect(page.getByTestId("content-error")).toHaveText("Enter a title.");
    await page.getByTestId("course-title-en").fill(title);
    await page.getByTestId("course-title-ta").fill("உங்கள் திட்டத்தை வழங்குதல்");
    await page.getByLabel("Skill bar it feeds").selectOption("communication");
    await page.getByTestId("course-save").click();
    await expect(page.getByTestId("course-heading")).toHaveText(title);

    await page.getByTestId("lesson-title-en").fill("Structure a five-minute demo");
    await page.getByTestId("lesson-title-ta").fill("ஐந்து நிமிட விளக்கத்தை அமைத்தல்");
    await page.getByTestId("lesson-body-en").fill("Problem, approach, live demo, results, next steps.");
    await page.getByTestId("lesson-body-ta").fill("சிக்கல், அணுகுமுறை, நேரடி விளக்கம், முடிவுகள், அடுத்த படிகள்.");
    await page.getByTestId("lesson-save").click();
    await expect(page.getByTestId("lesson-row")).toHaveCount(1);
    await page.getByTestId("course-publish").click();
    await expect(page.getByTestId("course-publish")).toHaveText("Unpublish");

    const ctx = await browser.newContext();
    const student = await ctx.newPage();
    await loginAs(student, "student");
    await student.goto("/student/courses");
    const card = student.getByTestId("course-card").filter({ hasText: title });
    await expect(card).toContainText("0/1");
    await card.click();
    await student.getByRole("button", { name: /Structure a five-minute demo/ }).click();
    await expect(student.getByTestId("lesson-body")).toContainText("Problem, approach");
    await student.getByTestId("lesson-complete").click();
    await expect(student.getByTestId("skill-updated")).toHaveText("Your skill bar is now 100%");
    await expect(student.getByTestId("lesson-done")).toBeVisible();
    await ctx.close();

    await page.getByTestId("course-publish").click();                               // unpublish again: keeps the demo tidy
    await expect(page.getByTestId("course-publish")).toHaveText("Publish");
  });

  test("staff save a notification template", async ({ page }) => {
    await loginAs(page, "admin");
    await page.goto("/admin/content");
    await page.getByTestId("content-tab-templates").click();
    await page.getByTestId("template-key").fill("e2e.reminder");
    await page.getByTestId("template-title-en").fill("Reminder for {student}");
    await page.getByTestId("template-save").click();
    await expect(page.getByTestId("template-row").filter({ hasText: "e2e.reminder" })).toContainText("Reminder for {student}");
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "student", { lang: "ta" });
    await page.goto("/student/courses");
    await expect(page.getByRole("heading", { level: 1, name: "என் பாடநெறிகள்" })).toBeVisible();
    await page.getByTestId("course-card").filter({ hasText: "உருவாக்க AI அடிப்படைகள்" }).click();
    await expect(page.getByRole("button", { name: /மொழி மாதிரி என்ன செய்கிறது/ })).toBeVisible();
  });

  test("blocks students and college admins from the library", async ({ page, browser }) => {
    await loginAs(page, "student");
    await page.goto("/admin/content");
    await expect(page.getByTestId("course-form")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
    const ctx = await browser.newContext();
    const college = await ctx.newPage();
    await loginAs(college, "college");
    await college.goto("/admin/content");
    await expect(college.getByText(/Access restricted/i)).toBeVisible();
    await ctx.close();
  });
});
