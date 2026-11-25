import { test, expect } from "@playwright/test";
import { loginAs, bearer } from "./helpers/auth";

const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000/api/v1";

test.describe("Screen 13: Trainer Dashboard (/trainer)", () => {
  test("renders KPIs, readiness chart, schedule, support table and quick actions from the API", async ({ page }) => {
    const { token } = await loginAs(page, "trainer");
    const api = await page.request.get(`${API}/trainer/dashboard`, { headers: bearer(token) });
    const expected = await api.json();

    await page.goto("/trainer");

    const kpis = page.getByTestId("trainer-kpis");
    await expect(kpis).toContainText(String(expected.kpis.active_batches.value));
    await expect(kpis).toContainText(`${expected.kpis.active_batches.students} students`);
    await expect(kpis).toContainText(String(expected.kpis.pending_code_reviews.value));
    await expect(kpis).toContainText(`Parents notified: ${expected.kpis.at_risk_students.parents_notified}`);

    await expect(page.getByText("Batch readiness score")).toBeVisible();
    await expect(page.getByTestId("batch-readiness-chart")).toContainText("CSE-A");

    const schedule = page.getByTestId("today-schedule");
    await expect(schedule).toContainText("System design basics");
    await expect(schedule).toContainText("OWASP lab: XSS");

    const table = page.getByTestId("support-table");
    await expect(table).toContainText(expected.students_needing_support[0].name);
    await expect(table).toContainText(String(expected.students_needing_support[0].score));

    // an action chip records a flag action and shows a toast
    await page.getByTestId("support-action").first().click();
    await expect(page.getByTestId("toast")).toContainText("recorded for");

    const quick = page.getByTestId("quick-actions");
    await expect(quick.getByRole("link", { name: "Review PRs" })).toHaveAttribute("href", "/trainer/reviews");
    await expect(quick.getByRole("link", { name: "Monthly report" })).toBeVisible();
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "trainer", { lang: "ta" });
    await page.goto("/trainer");
    await expect(page.getByRole("heading", { name: "பயிற்சியாளர் டாஷ்போர்டு" })).toBeVisible();
    await expect(page.getByText("பேட்ச் தயார்நிலை மதிப்பெண்")).toBeVisible();
    await expect(page.getByText("ஆதரவு தேவைப்படும் மாணவர்கள்")).toBeVisible();
    // the weekly DSA widget is translated too (column heads and week filter)
    const dsa = page.getByTestId("trainer-dsa-widget");
    await expect(dsa).toContainText("சமர்ப்பிப்புகள்");
    await expect(dsa.getByRole("combobox")).toContainText("எல்லா வாரங்களும் (1–8)");
  });

  test("blocks the student role", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/trainer");
    await expect(page.getByText(/Access Restricted/i).first()).toBeVisible();
  });
});
