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

    // resumes on the first unanswered question: the seed answered Q1 to Q12
    await expect(page.getByText(/Question 13 of \d+/)).toBeVisible();
    await expect(page.getByText("Question palette")).toBeVisible();

    // mark Q13 for review, answer it and go next
    await page.getByRole("button", { name: "Mark for review" }).click();
    await expect(page.getByRole("button", { name: "Marked for review" })).toBeVisible();
    await page.getByRole("button", { name: /^B\b/ }).first().click();
    await page.getByRole("button", { name: "Save & Next" }).click();
    await expect(page.getByText(/Question 14 of \d+/)).toBeVisible();

    // and back again
    await page.getByRole("button", { name: "Previous" }).click();
    await expect(page.getByText(/Question 13 of \d+/)).toBeVisible();

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

  test("submits exactly once when the timer runs out", async ({ page }) => {
    // the server's clock decides time left (the page checks in every 15 s); the faked browser clock cannot move it,
    // so the server is made to answer "time is up" for this test
    await page.route("**/api/v1/student/tests/attempts/*/heartbeat", (r) =>
      r.fulfill({ status: 200, contentType: "application/json",
        body: JSON.stringify({ time_remaining_sec: 0, credited_sec: 0, paused_seconds: 0, tab_switches: 0, max_tab_switches: 3 }) }));
    let submits = 0;
    page.on("request", (r) => { if (r.method() === "POST" && r.url().includes("/submit")) submits++; });
    await page.clock.install();
    await loginAs(page, "student");
    await page.goto(URL);
    // the first spec may already have submitted the seeded attempt, so this can be a fresh one (Q1)
    await expect(page.getByText(/Question \d+ of \d+/)).toBeVisible();
    await page.clock.runFor(2 * 60 * 60 * 1000);   // two hours: past any test duration
    await expect(page.getByText("Test Submitted Successfully!")).toBeVisible({ timeout: 15000 });
    await page.clock.runFor(10_000);
    expect(submits).toBe(1);
  });

  test("a lost connection pauses the timer and keeps answers; coming back resumes", async ({ page, context }) => {
    await loginAs(page, "student");
    await page.goto(URL);
    await expect(page.getByText(/Question \d+ of \d+/)).toBeVisible();
    await expect(page.getByTestId("test-rules")).toContainText("Stay on this page");

    await context.setOffline(true);
    await page.evaluate(() => window.dispatchEvent(new Event("offline")));
    await expect(page.getByTestId("offline-banner")).toBeVisible();
    await expect(page.getByTestId("test-timer")).toHaveAttribute("data-paused", "true");
    const frozen = await page.getByTestId("test-timer").innerText();
    await page.waitForTimeout(2500);
    await expect(page.getByTestId("test-timer")).toHaveText(frozen);                 // the clock does not move offline

    await page.getByRole("button", { name: /^C\b/ }).first().click();              // answering still works offline
    await context.setOffline(false);
    await page.evaluate(() => window.dispatchEvent(new Event("online")));
    await expect(page.getByTestId("resumed-banner")).toBeVisible();
    await expect(page.getByTestId("offline-banner")).toHaveCount(0);
    await expect(page.getByTestId("test-timer")).toHaveAttribute("data-paused", "false");
  });

  test("leaving the page saves, warns on return, and submits after the limit", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto(URL);
    await expect(page.getByText(/Question \d+ of \d+/)).toBeVisible();
    const leaveAndReturn = async () => {
      await page.evaluate(() => {
        Object.defineProperty(document, "hidden", { configurable: true, get: () => true });
        document.dispatchEvent(new Event("visibilitychange"));
        Object.defineProperty(document, "hidden", { configurable: true, get: () => false });
        document.dispatchEvent(new Event("visibilitychange"));
      });
    };
    const badge = page.getByTestId("tab-switch-count");                                // only shown once there is a switch
    const start = (await badge.count()) ? Number((await badge.innerText()).match(/(\d+) of/)?.[1] ?? 0) : 0;
    await leaveAndReturn();
    await expect(page.getByTestId("tab-warning")).toBeVisible();
    await expect(page.getByTestId("tab-warning-count")).toContainText(`Warning ${start + 1} of 3`);
    await page.getByTestId("tab-warning-ok").click();
    await expect(page.getByTestId("tab-warning")).toHaveCount(0);
    for (let n = start + 2; n <= 3; n++) {                                              // up to the limit (3): warnings only
      await leaveAndReturn();
      await page.getByTestId("tab-warning-ok").click();
    }
    await leaveAndReturn();                                                             // one more: submitted for the student
    await expect(page.getByText("Test Submitted Successfully!")).toBeVisible({ timeout: 15000 });
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
