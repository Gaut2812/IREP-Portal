import { test, expect, Browser } from "@playwright/test";
import { loginAs } from "./helpers/auth";

async function asRole(browser: Browser, role: "student" | "trainer") {
  const context = await browser.newContext();
  const page = await context.newPage();
  await loginAs(page, role);
  return { context, page };
}

test.describe("Screen 30: Sprint Board (/student/projects/:teamId/board)", () => {
  test("renders the board, moves a card by drag and by menu, blocks Done without an approved PR, shares a stand-up", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/student/projects/board");
    await expect(page).toHaveURL(/\/student\/projects\/team_phoenix\/board/);

    const header = page.getByTestId("board-header");
    await expect(header).toContainText("Sprint 2 of 3");
    await expect(header).toContainText("Clinic Appointment System");
    await expect(header).toContainText("Ends Week 8");
    await expect(page.getByTestId("change-request")).toContainText("SMS reminders");
    await expect(page.getByTestId("count-todo")).toHaveText("3");
    await expect(page.getByTestId("count-code_review")).toHaveText("2");
    await expect(page.getByTestId("board-metrics")).toContainText("58%");
    await expect(page.getByTestId("board-metrics")).toContainText("21 / 36");
    await expect(page.getByTestId("board-metrics")).toContainText("Velocity last sprint: 30");
    await expect(page.getByTestId("build-status")).toContainText("Passing");

    // drag "Accessibility review" from To Do into In Progress
    const card = page.getByTestId("card-task_03").getByText("Accessibility review");
    const target = page.getByTestId("col-in_progress");
    const from = await card.boundingBox();
    const to = await target.boundingBox();
    await page.mouse.move(from!.x + from!.width / 2, from!.y + from!.height / 2);
    await page.mouse.down();
    await page.mouse.move(from!.x + 40, from!.y + 20, { steps: 5 });
    await page.mouse.move(to!.x + to!.width / 2, to!.y + to!.height - 30, { steps: 15 });
    await page.mouse.up();
    await expect(page.getByTestId("toast")).toContainText("Moved to In Progress");
    await expect(page.getByTestId("col-in_progress")).toContainText("Accessibility review");
    await expect(page.getByTestId("count-todo")).toHaveText("2");

    // keyboard-friendly menu: a card with a pending PR cannot jump to Done
    await page.getByTestId("move-task_08").selectOption("done");
    await expect(page.getByTestId("toast")).toContainText("pull request is approved");
    await expect(page.getByTestId("col-code_review")).toContainText("Unit tests – booking service");

    // stand-up
    await page.getByTestId("standup-button").click();
    await page.getByTestId("standup-yesterday").fill("AI triage prompt chaining");
    await page.getByTestId("standup-today").fill("Booking service tests");
    await page.getByTestId("standup-submit").click();
    await expect(page.getByTestId("toast")).toContainText("Stand-up shared");
    await expect(page.getByTestId("standup-button")).toContainText("Stand-up shared today");
  });

  test("a teammate's move and a trainer approval show up live", async ({ browser }) => {
    const student = await asRole(browser, "student");
    const trainer = await asRole(browser, "trainer");
    await student.page.goto("/student/projects/team_phoenix/board");
    await trainer.page.goto("/student/projects/team_phoenix/board");
    await expect(trainer.page.getByTestId("count-done")).toHaveText("4");

    await student.page.getByTestId("move-task_02").selectOption("in_progress");
    await expect(trainer.page.getByTestId("col-in_progress")).toContainText("Doctor availability calendar", { timeout: 16000 });

    // trainer approves PR #39 on Screen 31 -> the student's card moves to Done
    await trainer.page.goto("/trainer/reviews");
    await trainer.page.getByRole("button", { name: "Approve & Merge" }).click();
    await expect(student.page.getByTestId("col-done")).toContainText("Unit tests – booking service", { timeout: 16000 });

    await student.context.close();
    await trainer.context.close();
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "student", { lang: "ta" });
    await page.goto("/student/projects/team_phoenix/board");
    await expect(page.getByTestId("col-todo")).toContainText("செய்ய வேண்டியவை");
    await expect(page.getByTestId("board-metrics")).toContainText("ஸ்பிரிண்ட் முன்னேற்றம்");
  });

  test("blocks the parent role", async ({ page }) => {
    await loginAs(page, "parent");
    await page.goto("/student/projects/team_phoenix/board");
    await expect(page.getByText(/Access Restricted/i).first()).toBeVisible();
  });
});
