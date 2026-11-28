import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

test.describe("Screen 32: Student Portfolio (/student/portfolio)", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, "student");
  });

  test("should render student portfolio with hero card, KPI stats, projects, and skills", async ({ page }) => {
    await page.goto("/student/portfolio");

    // 1. Header & Hero Card
    await expect(page.getByRole("main").getByRole("heading", { name: "Student Portfolio" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Priya R" })).toBeVisible();
    await expect(page.getByText(/AI & DS/i).first()).toBeVisible();
    await expect(page.getByText(/Placement Readiness/i)).toBeVisible();

    // 2. Project cards
    await expect(page.getByRole("heading", { name: "Crop Price Predictor" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Clinic Appointment & Token System" })).toBeVisible();
    await expect(page.getByText("Team AgriVision")).toBeVisible();
    await expect(page.getByText("Team Phoenix")).toBeVisible();

    // 3. Action links on cards
    await expect(page.getByRole("link", { name: /GitHub Repo/i }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: /Live Demo/i }).first()).toBeVisible();

    // 4. Category filter tabs
    const mlFilter = page.getByRole("button", { name: "Machine Learning" });
    await mlFilter.click();
    await expect(page.getByRole("heading", { name: "Crop Price Predictor" })).toBeVisible();

    // 5. Verified Skills Section
    await expect(page.getByText("Verified Technical Skills")).toBeVisible();
    await expect(page.getByText("Data Structures & Algorithms").first()).toBeVisible();
    await expect(page.getByText("Gold").first()).toBeVisible();

    // 6. Add Project Modal opens
    const addProjectBtn = page.getByRole("button", { name: "+ Add Project" });
    await addProjectBtn.click();
    await expect(page.getByRole("heading", { name: "Add New Project" })).toBeVisible();
    await expect(page.getByPlaceholder("e.g. Smart City Traffic Optimizer")).toBeVisible();
  });

  test("should render bilingual Tamil translation on student portfolio", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("irep_lang", "ta");
    });

    await page.goto("/student/portfolio");
    await expect(page.getByRole("main").getByRole("heading", { name: "மாணவர் போர்ட்ஃபோலியோ" })).toBeVisible();
    await expect(page.getByRole("button", { name: "+ புதிய புராஜெக்ட் சேர்க்க" })).toBeVisible();
    await expect(page.getByText("சரிபார்க்கப்பட்ட தொழில்நுட்பத் திறன்கள்")).toBeVisible();
  });
});

test.describe("Screen 33: Parent Projects & Portfolio (/parent/portfolio)", () => {
  let parentToken = "";
  test.beforeEach(async ({ page }) => {
    parentToken = (await loginAs(page, "parent")).token;
  });

  test("should render parent portfolio with ward banner, sprint milestone, plain explanations, and interactive RSVP", async ({ page }) => {
    // Start from a known RSVP state: an earlier run (or spec) may have left "attending", which disables
    // the "Yes" button. Wait on that real state instead of letting click() time out.
    const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000/api/v1";
    const auth = { Authorization: `Bearer ${parentToken}` };
    const portfolio = await (await page.request.get(`${API}/parent/portfolio`, { headers: auth })).json();
    const reset = await page.request.post(`${API}/parent/portfolio/rsvp`, {
      headers: auth, data: { event_id: portfolio.demo_day_invitation.id, status: "declined", guest_count: 1 },
    });
    expect(reset.ok()).toBeTruthy();
    await page.goto("/parent/portfolio");

    // 1. Header & Ward Banner
    await expect(page.getByRole("main").getByRole("heading", { name: "Projects & Portfolio" })).toBeVisible();
    await expect(page.getByText("Engineering Project Portfolio")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Priya R" })).toBeVisible();

    // 2. Active Capstone Sprint Milestone
    await expect(page.getByText("Active Project Sprint")).toBeVisible();
    await expect(page.getByText("Milestone Progress", { exact: true })).toBeVisible();
    await expect(page.getByText("58%")).toBeVisible();

    // 3. Parent-friendly project showcase
    await expect(page.getByRole("heading", { name: "Crop Price Predictor" })).toBeVisible();
    await expect(page.getByRole("link", { name: "View Live Project" }).first()).toBeVisible();

    // 4. Project Demo Day Invitation & Interactive RSVP
    await expect(page.getByText("Project Demo Day Invitation")).toBeVisible();
    await expect(page.getByText("Auditorium A & Live Stream")).toBeVisible();

    const rsvpBtn = page.getByRole("button", { name: "Yes, I will attend" });
    await expect(rsvpBtn).toBeEnabled();
    await rsvpBtn.click();

    // Verify confirmation feedback shows
    await expect(page.getByText("Attending Confirmed")).toBeVisible();
    await expect(page.getByText("RSVP Confirmed! We look forward to seeing you.")).toBeVisible();
  });

  test("a failed RSVP is reported, not shown as confirmed", async ({ page }) => {
    const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000/api/v1";
    const auth = { Authorization: `Bearer ${parentToken}` };
    const portfolio = await (await page.request.get(`${API}/parent/portfolio`, { headers: auth })).json();
    await page.request.post(`${API}/parent/portfolio/rsvp`, {
      headers: auth, data: { event_id: portfolio.demo_day_invitation.id, status: "declined", guest_count: 1 },
    });
    await page.goto("/parent/portfolio");
    await page.route("**/api/v1/parent/portfolio/rsvp", (r) => r.fulfill({ status: 500, body: "boom" }));
    await page.getByRole("button", { name: "Yes, I will attend" }).click();
    await expect(page.getByTestId("rsvp-error")).toBeVisible();
    await expect(page.getByText("Attending Confirmed")).toHaveCount(0);
  });

  test("a portfolio that fails to load shows an error, not another child's portfolio", async ({ page }) => {
    await page.route("**/api/v1/parent/portfolio?*", (r) => r.fulfill({ status: 500, body: "boom" }));
    await page.goto("/parent/portfolio");
    await expect(page.getByRole("button", { name: /Try Again/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Priya R" })).toHaveCount(0);
  });

  test("should render bilingual Tamil translation on parent portfolio", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("irep_lang", "ta");
    });

    await page.goto("/parent/portfolio");
    await expect(page.getByRole("main").getByRole("heading", { name: "திட்டப்பணிகள் & போர்ட்ஃபோலியோ" })).toBeVisible();
    await expect(page.getByText("பொறியியல் திட்டப்பணி போர்ட்ஃபோலியோ")).toBeVisible();
    await expect(page.getByText("திட்டப்பணி டெமோ நாள் அழைப்பு")).toBeVisible();
    await expect(page.getByRole("button", { name: "ஆம், நான் கலந்துகொள்கிறேன்" })).toBeVisible();
  });
});
