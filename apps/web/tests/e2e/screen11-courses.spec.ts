/**
 * Screen 11 – My Courses · Playwright Happy-Path Test
 *
 * Pre-conditions: `pnpm dev` running on localhost:3000, API on localhost:8000.
 * The demo student role is selected by default (see AuthContext seed).
 *
 * Run: npx playwright test tests/e2e/screen11-courses.spec.ts
 */
import { test, expect } from "@playwright/test";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";

test.describe("Screen 11 – My Courses", () => {
  test.beforeEach(async ({ page }) => {
    // Set demo student token so the app skips the login form
    await page.goto(BASE_URL);
    await page.evaluate(() => {
      localStorage.setItem("irep_token", "mock_jwt_token_demo");
      localStorage.setItem(
        "irep_user",
        JSON.stringify({
          id: "usr_priya_01",
          email: "priya.r@demo.edu",
          role: "student",
          name: "Priya R",
          avatar: "PR",
          college_id: "col_demo_001",
        })
      );
    });
  });

  test("happy path: navigate to courses, see cards, open detail, mark complete", async ({ page }) => {
    // ── Step 1: Navigate to My Courses page ──────────────────────────────────
    await page.goto(`${BASE_URL}/student/courses`);

    // Page title is visible
    await expect(page.getByRole("heading", { name: /My Courses|எனது பாடங்கள்/i })).toBeVisible({
      timeout: 10_000,
    });

    // ── Step 2: At least one course card is rendered ──────────────────────────
    // Cards carry the .course-card class
    const cards = page.locator(".course-card");
    await expect(cards.first()).toBeVisible({ timeout: 10_000 });
    const cardCount = await cards.count();
    expect(cardCount).toBeGreaterThanOrEqual(1);

    // ── Step 3: Course card has a progress percentage and a CTA button ────────
    const firstCard = cards.first();
    await expect(firstCard.locator("text=/\\d+%/")).toBeVisible();

    // Click the first Resume / Start button inside the card
    const ctaButton = firstCard.getByRole("link");
    const href = await ctaButton.getAttribute("href");
    expect(href).toMatch(/\/student\/courses\/crs_/);

    // ── Step 4: Navigate to course detail page ───────────────────────────────
    await ctaButton.click();
    await page.waitForURL(/\/student\/courses\/crs_/, { timeout: 8_000 });

    // Back link is present
    await expect(page.getByText(/Back to My Courses|எனது பாடங்கள்களுக்கு/i)).toBeVisible({
      timeout: 8_000,
    });

    // At least one lesson row (circle or tick icon + lesson title)
    const lessonRows = page.locator("button").filter({ hasText: /video|slides|notes|assignment/i });
    await expect(lessonRows.first()).toBeVisible({ timeout: 8_000 });

    // ── Step 5: Select a lesson and click Mark Complete ───────────────────────
    // Click the first lesson row in the sidebar
    await lessonRows.first().click();

    // The viewer panel shows the Mark Complete button (only on incomplete lessons)
    const markBtn = page.getByRole("button", { name: /Mark Complete|முடிந்தது என/i });
    if (await markBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await markBtn.click();
      // After completing, the button should disappear and "Completed" badge should appear
      await expect(page.getByText(/Completed|முடிந்தது/i).first()).toBeVisible({
        timeout: 6_000,
      });
    }
    // If the lesson was already completed, the Completed badge is already showing — that's fine.

    // ── Step 6: Tab filter works ──────────────────────────────────────────────
    await page.goBack();
    await page.waitForURL(/\/student\/courses$/, { timeout: 5_000 });

    const dsaTab = page.getByRole("button", { name: /^DSA$/i });
    await expect(dsaTab).toBeVisible();
    await dsaTab.click();
    // After filtering, any visible card should show "DSA" track chip
    const trackChips = page.locator(".course-card").locator("text=DSA");
    await expect(trackChips.first()).toBeVisible({ timeout: 6_000 });
  });

  test("role guard: non-student sees access-restricted callout", async ({ page }) => {
    // Switch to parent role
    await page.goto(BASE_URL);
    await page.evaluate(() => {
      localStorage.setItem(
        "irep_user",
        JSON.stringify({
          id: "usr_ramesh_01",
          email: "ramesh.k@example.com",
          role: "parent",
          name: "Mr. Ramesh K",
          avatar: "RK",
          college_id: "col_demo_001",
        })
      );
    });

    await page.goto(`${BASE_URL}/student/courses`);

    // Role guard callout visible instead of course cards
    await expect(
      page.getByText(/Student access only|மாணவர்களுக்கு மட்டுமே/i)
    ).toBeVisible({ timeout: 8_000 });

    // No course cards rendered
    const cards = page.locator(".course-card");
    expect(await cards.count()).toBe(0);
  });
});

