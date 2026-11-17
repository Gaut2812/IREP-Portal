import { test, expect, Browser } from "@playwright/test";
import { loginAs } from "./helpers/auth";

const ROOM = "/live/sess_thu_rag";

async function asRole(browser: Browser, role: "student" | "trainer", lang: "en" | "ta" = "en") {
  const context = await browser.newContext();
  const page = await context.newPage();
  await loginAs(page, role, { lang });
  return { context, page };
}

test.describe("Screen 07: Live Classroom (/live/:sessionId)", () => {
  test("trainer starts the class, student joins, votes, asks a question; trainer ends and attendance is recorded", async ({ browser }) => {
    const trainer = await asRole(browser, "trainer");
    const student = await asRole(browser, "student");

    // Trainer opens the waiting room and starts the class
    await trainer.page.goto(ROOM);
    await trainer.page.getByTestId("start-class").click();
    await expect(trainer.page.getByTestId("stage-sharing")).toContainText("rag_demo.ipynb");
    await expect(trainer.page.getByText("REC")).toBeVisible();

    // Student lands straight in the live room
    await student.page.goto(ROOM);
    await expect(student.page.getByTestId("stage-code")).toContainText("vector_db.search");
    await expect(student.page.getByTestId("stage-flow")).toContainText("Search vector DB");
    await expect(student.page.getByTestId("participants")).toContainText("Arun Kumar");
    await expect(student.page.getByTestId("participants")).toContainText("Priya R");
    await expect(student.page.getByTestId("attendance-pill")).toBeVisible();
    await expect(student.page.getByTestId("auto-attendance")).toContainText("Marked present automatically at 45 min (75% of the session)");

    // Poll: vote once, then the result locks
    const poll = student.page.getByTestId("live-poll");
    await expect(poll).toContainText("If the answer is not in the notes, the model should...");
    await expect(poll).toContainText("30 votes");
    await student.page.getByTestId("poll-option-b").click();
    await expect(poll).toContainText("31 votes");
    await expect(poll).toContainText("You voted");
    await expect(student.page.getByTestId("poll-option-a")).toBeDisabled();

    // Q&A
    await expect(student.page.getByTestId("live-qa")).toContainText("Answered live at 31:40");
    await student.page.getByTestId("qa-input").fill("Can we cache embeddings between labs?");
    await student.page.getByTestId("qa-input").press("Enter");
    await expect(student.page.getByTestId("live-qa")).toContainText("Can we cache embeddings between labs?");

    // Trainer sees the question, ends the class
    await expect(trainer.page.getByTestId("live-qa")).toContainText("Can we cache embeddings between labs?", { timeout: 10000 });
    await trainer.page.getByTestId("end-class").click();
    await expect(trainer.page.getByTestId("live-lobby")).toContainText("This class has ended");

    // Student's room follows (push or 5 s polling)
    await expect(student.page.getByTestId("live-lobby")).toContainText("This class has ended", { timeout: 12000 });

    await trainer.context.close();
    await student.context.close();
  });

  test("supports the Tamil toggle in the waiting room", async ({ browser }) => {
    const trainer = await asRole(browser, "trainer", "ta");
    await trainer.page.goto(ROOM);
    await expect(trainer.page.getByTestId("live-lobby")).toContainText(/காத்திருப்பு அறை|இந்த வகுப்பு முடிந்தது/);
    await trainer.context.close();
  });

  test("blocks the parent role", async ({ page }) => {
    await loginAs(page, "parent");
    await page.goto(ROOM);
    await expect(page.getByText(/Access Restricted/i).first()).toBeVisible();
  });
});
