import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** S15: screens 37 (trainer mock interviews), 38 (mock drives), 39 (placement readiness).
 *  Spec: docs/screens/37-38-39-interviews-drives-readiness.md. Re-seed before running (demo drives). */

function inDays(days: number, hh = 10): string {
  const d = new Date(Date.now() + days * 86_400_000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(hh)}:00`;
}

test.describe("Screen 37: trainer mock interviews (/trainer/interviews)", () => {
  test("the trainer scores a booked interview and the student sees it on 36", { tag: "@L16" }, async ({ page, browser }) => {
    await loginAs(page, "trainer");
    await page.goto("/trainer/interviews");
    // Meena's drive interview waits to be scored, marked with the drive (L17 label)
    const row = page.getByTestId("iv-iv_drive_service_4");
    await expect(row).toContainText("Meena V");
    await expect(row.getByTestId("drive-badge")).toHaveText("Mock drive: service-company pattern");
    await row.getByTestId("iv-score").click();
    await page.getByTestId("score-submit").click();                                     // nothing scored: inline error
    await expect(page.getByTestId("ti-error")).toHaveText("Score every criterion.");
    for (const sel of await page.locator("select[data-testid^='score-']").all()) await sel.selectOption("4");
    await page.getByTestId("feedback-en").fill("Clear approach; explain trade-offs before coding.");
    await page.getByTestId("note-add").click();
    await page.getByTestId("note-at-0").fill("3:15");
    await page.getByTestId("note-text-0").fill("Good clarifying questions.");
    await page.getByTestId("score-submit").click();
    await expect(page.getByTestId("ti-msg")).toContainText("Scores submitted");
    await expect(page.getByTestId("submitted").getByTestId("iv-iv_drive_service_4").getByTestId("iv-overall")).toHaveText("4.0");

    // a new slot appears on Priya's 36 and her booking comes back to 37 (L16)
    await page.getByTestId("slot-start").fill(inDays(6, 15));
    await page.getByTestId("slot-type").selectOption("hr");
    await page.getByTestId("slot-batch").selectOption("bat_aids_s5_aids");
    await page.getByTestId("slot-add").click();
    await expect(page.getByTestId("ti-msg")).toContainText("Slot opened");
    const ctx = await browser.newContext();
    const student = await ctx.newPage();
    const { token } = await loginAs(student, "student");
    const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000/api/v1";
    const mine = await (await student.request.get(`${API}/student/interviews`, { headers: { Authorization: `Bearer ${token}` } })).json();
    const hr = mine.available_slots.find((s: { round_type: string }) => s.round_type === "hr");
    expect(hr).toBeTruthy();
    const booked = await student.request.post(`${API}/student/interview-slots/${hr.id}/book`, { headers: { Authorization: `Bearer ${token}` } });
    expect([200, 409]).toContain(booked.status());                                       // 409: already holds an HR booking
    await ctx.close();
    await page.reload();
    await expect(page.getByTestId("slots").getByTestId("slot-booked").filter({ hasText: "Priya R" }).first()).toBeVisible();
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "trainer", { lang: "ta" });
    await page.goto("/trainer/interviews");
    await expect(page.getByRole("heading", { level: 1, name: "மாதிரி நேர்காணல்கள்" })).toBeVisible();
    await expect(page.getByTestId("to-score")).toContainText("மதிப்பிட வேண்டியவை");
  });

  test("blocks the student role", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/trainer/interviews");
    await expect(page.getByTestId("slots")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});

test.describe("Screen 38: mock drives (/college/drives)", () => {
  test("a drive event on 42 becomes a drive; publishing puts interview slots on the trainer's 37", { tag: ["@L29", "@L17"] }, async ({ page, browser }) => {
    const title = `Mock drive ${Date.now().toString(36).slice(-5)}`;
    await loginAs(page, "college");
    await page.goto("/college/events");
    await page.getByTestId("event-title-en").fill(title);
    await page.getByTestId("event-title-ta").fill("மாதிரி முகாம் சோதனை");
    await page.getByTestId("event-kind").selectOption("drive");
    await page.getByTestId("event-audience").selectOption("students");
    await page.getByTestId("event-batch").selectOption("bat_aids_s5_aids");
    await page.getByTestId("event-start").fill(inDays(15));
    await page.getByTestId("event-save").click();
    await expect(page.getByTestId("event-row").filter({ hasText: title })).toBeVisible();

    await page.goto("/college/drives");                                                    // L29
    const item = page.locator("[data-testid^='drive-drv_']").filter({ hasText: title });
    await expect(item).toContainText("Draft");
    await item.click();
    await page.getByTestId("round-add").click();                                           // no test chosen: inline error
    await expect(page.getByTestId("drives-error")).toHaveText("Choose the test for this round.");
    await page.getByTestId("round-test").selectOption("test_service_aptitude");
    await page.getByTestId("round-cutoff").fill("60");
    await page.getByTestId("round-add").click();
    await expect(page.getByTestId("round-row")).toHaveCount(1);
    await page.getByTestId("round-kind").selectOption("interview");
    await page.getByTestId("round-trainer").selectOption("trn_arun_01");
    await page.getByTestId("round-start").fill(inDays(15, 14));
    await page.getByTestId("round-slots").fill("2");
    await page.getByTestId("round-cutoff").fill("3.5");
    await page.getByTestId("round-add").click();
    await expect(page.getByTestId("round-row")).toHaveCount(2);
    await page.getByTestId("drive-publish").click();
    await expect(page.getByTestId("drives-msg")).toContainText("Drive published");
    await expect(page.getByTestId("round-form")).toHaveCount(0);

    const ctx = await browser.newContext();                                                // L17: slots on Arun's 37
    const trainer = await ctx.newPage();
    await loginAs(trainer, "trainer");
    await trainer.goto("/trainer/interviews");
    await expect(trainer.getByTestId("slots").getByTestId("drive-badge").filter({ hasText: title })).toHaveCount(2);
    await ctx.close();
  });

  test("results show scores only and the shortlist is published", async ({ page }) => {
    await loginAs(page, "college");
    await page.goto("/college/drives");
    await page.getByTestId("drive-drv_demo_service").click();
    // 2 from the seed, 3 if the screen 37 test above has just scored Meena: the summary matches the rows
    await expect(page.getByTestId("result-row").filter({ hasText: "Sneha N" })).toBeVisible();      // results rendered
    const shortlisted = await page.getByTestId("result-row").filter({ hasText: "Shortlisted" }).count();
    expect(shortlisted).toBeGreaterThanOrEqual(2);
    await expect(page.getByTestId("results-summary")).toContainText(`Shortlisted: ${shortlisted} / `);
    await expect(page.getByTestId("result-row").filter({ hasText: "Sneha N" })).toContainText("80");
    await expect(page.getByTestId("drive-results")).not.toContainText("practise");          // no trainer feedback (5.4)
    page.once("dialog", (d) => d.accept());
    await page.getByTestId("shortlist-publish").click();
    await expect(page.getByTestId("drives-msg")).toHaveText("Shortlist published.");
    await expect(page.getByTestId("drive-drv_demo_service")).toContainText("Shortlist published");
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "college", { lang: "ta" });
    await page.goto("/college/drives");
    await expect(page.getByRole("heading", { level: 1, name: "மாதிரி வேலைவாய்ப்பு முகாம்கள்" })).toBeVisible();
    await expect(page.getByTestId("drive-drv_demo_product")).toContainText("மாதிரி முகாம்: தயாரிப்பு நிறுவன முறை");
  });

  test("blocks the trainer role", async ({ page }) => {
    await loginAs(page, "trainer");
    await page.goto("/college/drives");
    await expect(page.getByTestId("drive-list")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});

test.describe("Screen 39: placement readiness (/college/readiness)", () => {
  test("drill down college, branch, batch to students: score, band and change only", { tag: ["@L34", "@L35"] }, async ({ page }) => {
    await loginAs(page, "college");
    await page.goto("/college/readiness");
    await expect(page.getByTestId("avg-score")).not.toHaveText("–");
    await page.getByTestId("group-br_aids").click();
    await expect(page.getByTestId("readiness-path")).toContainText("AI & DS");
    await page.getByTestId("group-bat_aids_s5_aids").click();
    const priya = page.getByTestId("readiness-student").filter({ hasText: "Priya R" });
    await expect(priya).toBeVisible();
    await page.getByTestId("band-filter").selectOption("support");
    await expect(page.getByTestId("readiness-student").first()).toContainText("Needs Support");
    await expect(page.getByTestId("readiness-students")).toContainText("Trainer notes and chats are never shown");
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "college", { lang: "ta" });
    await page.goto("/college/readiness");
    await expect(page.getByRole("heading", { level: 1, name: "வேலைவாய்ப்புத் தயார்நிலை" })).toBeVisible();
    await expect(page.getByTestId("readiness-groups")).toContainText("பிரிவு வாரியாக");
  });

  test("blocks the parent role", async ({ page }) => {
    await loginAs(page, "parent");
    await page.goto("/college/readiness");
    await expect(page.getByTestId("readiness-summary")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});
