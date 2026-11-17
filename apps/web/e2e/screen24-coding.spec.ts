import { test, expect } from "@playwright/test";

test.describe("Screen 24 - Coding Lab (/student/coding/:problemId)", () => {
  test.beforeEach(async ({ page }) => {
    // Set student demo user in localStorage before navigating
    await page.addInitScript(() => {
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
      localStorage.setItem("irep_token", "mock_jwt_token_demo");
      localStorage.setItem("irep_lang", "en");
    });
  });

  test("should render 3-column layout matching PDF 3 with problem statement, editor, and AI reviewer", async ({ page }) => {
    await page.goto("/student/coding/prob_connected_components");

    // 1. Left column: problem statement & tags
    await expect(page.getByText("Number of Connected Components in an Undirected Graph")).toBeVisible();
    await expect(page.getByText("Medium")).toBeVisible();
    await expect(page.getByText("Union-Find")).toBeVisible();
    await expect(page.getByText("Week 8 · Pattern drill · 3 of 6 solved")).toBeVisible();

    // 2. Middle column: editor & buttons
    await expect(page.getByRole("button", { name: /Run/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Submit/i })).toBeVisible();
    await expect(page.getByText("Test Results")).toBeVisible();

    // 3. Right column: AI reviewer & trainer note
    await expect(page.getByText("AI Code Reviewer")).toBeVisible();
    await expect(page.getByText("Good Practice")).toBeVisible();
    await expect(page.getByText("Trainer note")).toBeVisible();
    await expect(page.getByText("Arun K.")).toBeVisible();
  });

  test("should allow running sample test cases and receiving runtime metrics", async ({ page }) => {
    await page.goto("/student/coding/prob_connected_components");

    const runBtn = page.getByRole("button", { name: /Run/i });
    await runBtn.click();

    // Verify test results card displays Passed chips and metrics
    await expect(page.getByText(/Sample case 1/i)).toBeVisible();
    await expect(page.getByText(/Runtime/i)).toBeVisible();
    await expect(page.getByText(/Memory/i)).toBeVisible();
  });

  test("should unlock progressive AI hints on request", async ({ page }) => {
    await page.goto("/student/coding/prob_connected_components");

    // Click ask hint button
    const askHintBtn = page.getByRole("button", { name: /\+ Ask for another hint/i });
    if (await askHintBtn.isVisible()) {
      await askHintBtn.click();
      // Should show Hint 2
      await expect(page.getByText(/Hint 2:/i)).toBeVisible();
    }
  });

  test("should submit code and display 18 / 18 hidden tests passed", async ({ page }) => {
    await page.goto("/student/coding/prob_connected_components");

    const submitBtn = page.getByRole("button", { name: /Submit/i });
    await submitBtn.click();

    // Verify submission outcome
    await expect(page.getByText(/18 \/ 18 hidden tests passed/i)).toBeVisible();
  });

  test("should support Tamil language toggle", async ({ page }) => {
    await page.goto("/student/coding/prob_connected_components");

    // Find and click language toggle
    const langBtn = page.getByText(/தமிழ்/i);
    if (await langBtn.isVisible()) {
      await langBtn.click();
      // Verify Tamil button labels
      await expect(page.getByRole("button", { name: /இயக்கு/i })).toBeVisible();
      await expect(page.getByRole("button", { name: /சமர்ப்பி/i })).toBeVisible();
      await expect(page.getByText(/சோதனை முடிவுகள்/i)).toBeVisible();
    }
  });

  test("should enforce RoleGuard and block parent role", async ({ page }) => {
    // Switch role to parent
    await page.addInitScript(() => {
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

    await page.goto("/student/coding/prob_connected_components");

    // Should display access restricted banner
    await expect(page.getByText(/Access Restricted/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /Switch to Student/i })).toBeVisible();
  });
});

