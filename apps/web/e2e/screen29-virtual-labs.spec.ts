import { test, expect } from "@playwright/test";
import { loginAs, bearer } from "./helpers/auth";

const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000/api/v1";

test.describe("Screen 29: Virtual Labs (/student/labs)", () => {
  test("shows the catalog and active session, stops and launches labs, opens a workspace", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/student/labs");

    await expect(page.getByTestId("lab-lab_linux")).toContainText("Sem 2+");
    await expect(page.getByTestId("lab-lab_cloud")).toContainText("Credits: 68%");
    await expect(page.getByTestId("lab-lab_docker_k8s")).toContainText("Last used: yesterday");
    await expect(page.getByTestId("lab-lab_ai_notebook")).toContainText("AI & DS");
    await expect(page.getByTestId("lab-lab_cyber_range")).toContainText("Trainer approval needed");

    const active = page.getByTestId("active-session");
    await expect(active).toContainText("AI Notebook Lab");
    await expect(active).toContainText("rag_notes_demo.ipynb");
    await expect(active).toContainText(/running \d+ min/);

    // filter chips
    await page.getByRole("tab", { name: "Cybersecurity" }).click();
    await expect(page.getByTestId("lab-lab_linux")).toHaveCount(0);
    await page.getByRole("tab", { name: "All labs" }).click();

    // one lab at a time: stop, then launch Linux
    await page.getByTestId("stop-session").click();
    await expect(page.getByTestId("toast")).toContainText("Lab stopped");
    await expect(active).toContainText("No lab running");
    await page.getByTestId("launch-lab_linux").click();
    await expect(page.getByTestId("toast")).toContainText("Linux Sandbox is starting");
    await expect(active).toContainText("Linux Sandbox");

    // open the workspace
    await page.getByTestId("open-session").click();
    await expect(page.getByTestId("lab-workspace")).toBeVisible();
    await expect(page.getByTestId("workspace-status")).toContainText("running");
    await page.getByTestId("terminal-input").fill("echo hello irep");
    await page.getByTestId("terminal-input").press("Enter");
    await expect(page.getByTestId("terminal")).toContainText("hello irep");
    await page.getByTestId("workspace-stop").click();
    await expect(page.getByTestId("workspace-status")).toContainText("stopped");
  });

  test("Cyber Range: AUP, request, trainer approves on the dashboard, student launches", async ({ page, browser }) => {
    await loginAs(page, "student");
    await page.goto("/student/labs");
    await page.getByTestId("launch-lab_cyber_range").click();
    const dialog = page.getByTestId("aup-dialog");
    await expect(dialog).toContainText("acceptable-use agreement");
    await expect(page.getByTestId("aup-submit")).toBeDisabled();
    await page.getByTestId("aup-accept").check();
    await page.getByTestId("aup-submit").click();
    await expect(page.getByTestId("toast")).toContainText("Request sent to your trainer");
    await expect(page.getByTestId("pending-lab_cyber_range")).toBeVisible();

    // trainer sees the request on the dashboard and approves it in the UI
    const trainerPage = await browser.newPage();
    await loginAs(trainerPage, "trainer");
    await trainerPage.goto("/trainer");
    const card = trainerPage.getByTestId("lab-approvals");
    const row = card.locator("[data-testid^='approval-']", { hasText: "Priya R" });
    await expect(row).toContainText("Cyber Range");
    await row.getByTestId("approve").click();
    await expect(card).toContainText("Access approved for Priya R");
    await trainerPage.close();

    // student is notified and can now launch the lab
    await page.reload();
    await expect(page.getByTestId("lab-lab_cyber_range")).toContainText("Access approved");
    await page.getByTestId("notification-bell").click();
    await expect(page.getByTestId("notification-panel")).toContainText("Access approved: Cyber Range");
    await page.keyboard.press("Escape");
    await page.mouse.click(5, 300);
    await page.getByTestId("launch-lab_cyber_range").click();
    await expect(page.getByTestId("toast")).toContainText("Cyber Range is starting");
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "student", { lang: "ta" });
    await page.goto("/student/labs");
    await expect(page.getByRole("tab", { name: "அனைத்து லேப்கள்" })).toBeVisible();
    await expect(page.getByText("செயலில் உள்ள அமர்வு")).toBeVisible();
  });

  test("blocks the parent role", async ({ page }) => {
    await loginAs(page, "parent");
    await page.goto("/student/labs");
    await expect(page.getByText(/Access Restricted/i).first()).toBeVisible();
  });
});
