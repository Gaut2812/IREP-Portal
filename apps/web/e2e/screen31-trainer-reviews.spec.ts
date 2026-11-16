import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

test.describe("Screen 31: Trainer Code Reviews (/trainer/reviews)", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, "trainer");
  });

  test("should render PR queue, automated checks, code diff viewer, and approve a PR", async ({ page }) => {
    await page.goto("/trainer/reviews");

    // 1. Header & Workspace Panels
    await expect(page.getByRole("main").getByRole("heading", { name: "Trainer Code Reviews" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Pull Request Queue" })).toBeVisible();

    // 2. PR Queue list items
    await expect(page.getByText("#39").first()).toBeVisible();
    await expect(page.getByText("Unit tests – booking service PR #39").first()).toBeVisible();
    await expect(page.getByText("Team Phoenix").first()).toBeVisible();

    // 3. Automated Checks Banner
    await expect(page.getByText("All Automated Checks Passed")).toBeVisible();
    await expect(page.getByText(/14\/14 Passed|14 Passed/i)).toBeVisible();

    // 4. File Diff Viewer
    await expect(page.getByText("services/booking_service.py").first()).toBeVisible();
    await expect(page.getByText("BookingService").first()).toBeVisible();
    await expect(page.getByText("raise BookingNotFoundException")).toBeVisible();

    // 5. Evaluation Rubrics
    await expect(page.getByText("Evaluation Rubrics")).toBeVisible();
    await expect(page.getByText("Code Quality & Readability")).toBeVisible();
    await expect(page.getByText("Test Coverage & Edge Cases")).toBeVisible();

    // 6. Action Button & Approval Flow
    const approveBtn = page.getByRole("button", { name: "Approve & Merge" });
    await expect(approveBtn).toBeVisible();
    await approveBtn.click();

    // Verify confirmation feedback toast appears
    await expect(
      page.getByText(/Pull Request approved|Sprint task moved to 'Done'/i)
    ).toBeVisible();
  });

  test("should render bilingual Tamil translation on trainer reviews", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("irep_lang", "ta");
    });

    await page.goto("/trainer/reviews");

    await expect(page.getByRole("main").getByRole("heading", { name: "பயிற்சியாளர் குறியீடு மதிப்பாய்வுகள்" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "புல் ரிக்வெஸ்ட் வரிசை" })).toBeVisible();
    await expect(page.getByText("அனைத்து தானியங்கு சோதனைகளும் வெற்றி")).toBeVisible();
    await expect(page.getByRole("button", { name: "ஒப்புதல் அளித்து இணைக்க" })).toBeVisible();
  });
});
