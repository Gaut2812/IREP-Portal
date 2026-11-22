import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

test.describe("Screen 12: Student Dashboard (/student)", () => {
  test("renders readiness, skills, week plan, project, upcoming and badges from the API", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/student");

    await expect(page.getByText(/Good (morning|afternoon|evening), Priya/)).toBeVisible();

    // Row 1 KPI cards
    const readiness = page.getByTestId("readiness-card");
    await expect(readiness).toContainText("74");
    await expect(readiness).toContainText("Nearly Ready");
    await expect(readiness).toContainText("+6 this month");
    await expect(page.getByText("Problems solved")).toBeVisible();
    await expect(page.getByText("92%")).toBeVisible();
    await expect(page.getByText("Practice streak")).toBeVisible();

    // Row 2 skills + week plan
    const skills = page.getByTestId("skill-progress");
    await expect(skills).toContainText("DSA patterns");
    await expect(skills).toContainText("78%");
    await expect(skills).toContainText("Communication");
    await expect(page.getByTestId("this-week")).toContainText("Sat");

    // Row 3
    await expect(page.getByText("Current project")).toBeVisible();
    await expect(page.getByTestId("upcoming-events")).toContainText("Mid-term DSA test");
    await expect(page.getByText("Cloud Deployer")).toBeVisible();

    // "Why this score" drawer
    await readiness.click();
    const drawer = page.getByTestId("why-score-drawer");
    await expect(drawer).toBeVisible();
    await expect(drawer).toContainText("How your score is calculated");
    await expect(drawer).toContainText("DSA patterns");
    await expect(drawer).toContainText("Attendance");
    await page.getByRole("button", { name: "Close" }).last().click();
    await expect(drawer).not.toBeVisible();
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "student", { lang: "ta" });
    await page.goto("/student");
    await expect(page.getByRole("heading", { name: "மாணவர் டாஷ்போர்டு" })).toBeVisible();
    await expect(page.getByText("தயார்நிலை மதிப்பெண்")).toBeVisible();
    await expect(page.getByTestId("skill-progress")).toContainText("DSA வடிவங்கள்");
  });

  test("blocks the parent role", async ({ page }) => {
    await loginAs(page, "parent");
    await page.goto("/student");
    await expect(page.getByText(/Access Restricted|This section is accessible/i).first()).toBeVisible();
  });
});
