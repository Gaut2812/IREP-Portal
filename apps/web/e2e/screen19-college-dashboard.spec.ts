import { test, expect } from "@playwright/test";
import { loginAs, bearer } from "./helpers/auth";

const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000/api/v1";

test.describe("Screen 19: College Dashboard (/college)", () => {
  test("renders KPIs, readiness donut, branch table, certifications, events and MoU reports", async ({ page }) => {
    const { token } = await loginAs(page, "college");
    const expected = await (await page.request.get(`${API}/college/overview`, { headers: bearer(token) })).json();

    await page.goto("/college");
    const kpis = page.getByTestId("college-kpis");
    await expect(kpis).toContainText(String(expected.kpis.students_enrolled.value));
    await expect(kpis).toContainText(`${expected.kpis.avg_attendance.value}%`);
    await expect(kpis).toContainText(String(expected.kpis.certifications.value));
    await expect(kpis).toContainText(String(expected.kpis.internships.value));

    await expect(page.getByTestId("readiness-donut")).toContainText(`Placement Ready ${expected.readiness_distribution[0].percentage}%`);
    const table = page.getByTestId("branch-table");
    await expect(table).toContainText("CSE");
    await expect(table).toContainText("Cybersecurity");
    await expect(page.getByText(`${expected.branch_readiness.length} branches`, { exact: true })).toBeVisible();
    await expect(table).toContainText(String(expected.branch_readiness[0].students));

    await expect(page.getByTestId("cert-chart")).toBeVisible();
    await expect(page.getByTestId("college-events")).toContainText("Project Demo Day");
    await expect(page.getByTestId("mou-reports")).toContainText("September progress report");

    // PDF download produces a file
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: /PDF September progress report/ }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.pdf$/);

    // semester filter changes the enrolled count
    await page.getByTestId("semester-filter").selectOption("6");
    await expect(kpis).toContainText("112");
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "college", { lang: "ta" });
    await page.goto("/college");
    await expect(page.getByText("வேலைவாய்ப்பு தயார்நிலை").first()).toBeVisible();
    await expect(page.getByText("பிரிவு வாரியான தயார்நிலை")).toBeVisible();
    await expect(page.getByTestId("mou-reports")).toContainText("செப்டம்பர் முன்னேற்ற அறிக்கை");
  });

  test("blocks trainers and parents", async ({ page }) => {
    await loginAs(page, "trainer");
    await page.goto("/college");
    await expect(page.getByText(/Access Restricted/i).first()).toBeVisible();
  });
});
