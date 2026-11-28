import { test, expect } from "@playwright/test";
import { loginAs, bearer } from "./helpers/auth";

/** Phase 2 · Sprint Board: project details, students add/edit/delete cards, trainers create and run projects. */
const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000/api/v1";
const stamp = () => Math.random().toString(36).slice(2, 7);

test.describe("Sprint Board: project details and cards", () => {
  test("the board shows what the team builds, its goals, members and repo", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/student/projects/board");
    const details = page.getByTestId("project-details");
    await expect(details).toContainText("Project details");
    await expect(page.getByTestId("project-description")).toContainText("clinic");
    await expect(page.getByTestId("project-goals").locator("li")).toHaveCount(4);
    await expect(details).toContainText("Priya R");
    await expect(details.getByRole("link", { name: /irep-demo\/clinic-appointment-system/ })).toBeVisible();
  });

  test("a student adds a card, edits it and deletes it", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/student/projects/board");
    const title = `Seat booking tests ${stamp()}`;
    await page.getByTestId("add-task").click();
    await page.getByTestId("task-title").fill(title);
    await page.getByTestId("task-tag").selectOption("qa");
    await page.getByTestId("task-points").selectOption("5");
    await page.getByTestId("task-save").click();
    const todo = page.getByTestId("col-todo");
    await expect(todo).toContainText(title);
    const card = todo.locator("[data-testid^='card-']").filter({ hasText: title });
    await expect(card).toContainText("5 pts");

    await card.locator("[data-testid^='edit-']").click();
    await page.getByTestId("task-title").fill(`${title} (edited)`);
    await page.getByTestId("task-save").click();
    await expect(todo).toContainText(`${title} (edited)`);

    await todo.locator("[data-testid^='card-']").filter({ hasText: `${title} (edited)` }).locator("[data-testid^='delete-']").click();
    await expect(page.getByTestId("confirm-delete-name")).toContainText(title);
    await page.getByTestId("confirm-delete-ok").click();
    await expect(todo).not.toContainText(title);
  });

  test("the Tamil board labels", async ({ page }) => {
    await loginAs(page, "student", { lang: "ta" });
    await page.goto("/student/projects/board");
    await expect(page.getByTestId("add-task")).toContainText("பணியைச் சேர்");
    await expect(page.getByTestId("project-details")).toContainText("புராஜெக்ட் விவரங்கள்");
  });
});

test.describe("Trainer · Projects", () => {
  test("the trainer creates a project for students, sees it on the board, and deletes it", async ({ page }) => {
    const { token } = await loginAs(page, "trainer");
    const before = await (await page.request.get(`${API}/trainer/projects`, { headers: bearer(token) })).json();
    const free = before.students.filter((s: { team_id: string | null }) => !s.team_id).slice(0, 2);
    const title = `Library seats ${stamp()}`;

    await page.goto("/trainer/projects");
    await page.getByTestId("project-new").click();
    await page.getByTestId("project-name").fill(`Team ${stamp()}`);
    await page.getByTestId("project-title").fill(title);
    await page.getByTestId("project-description-input").fill("Book a reading-room seat from the phone.");
    await page.getByTestId("project-goals-input").fill("Book a seat\nSee free seats live");
    for (const s of free) await page.getByTestId(`member-${s.student_id}`).check();
    await page.getByTestId("project-lead").selectOption(free[0].student_id);
    await page.getByTestId("project-save").click();
    await expect(page.getByTestId("project-msg")).toContainText("Project created");

    const card = page.getByTestId("project-card").filter({ hasText: title });
    await expect(card).toContainText("Sprint 1 of 3");
    await card.getByTestId("project-open-board").click();
    await expect(page.getByTestId("project-description")).toContainText("reading-room seat");
    await page.goBack();

    await page.getByTestId("project-card").filter({ hasText: title }).getByTestId("project-delete").click();
    await page.getByTestId("confirm-delete-ok").click();
    await expect(page.getByTestId("project-card").filter({ hasText: title })).toHaveCount(0);
  });

  test("students cannot open the trainer projects page", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/trainer/projects");
    await expect(page.getByText(/Access Restricted/i).first()).toBeVisible();
  });
});
