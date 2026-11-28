import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

const SOLUTION = [
  "class Solution:",
  "    def countComponents(self, n: int, edges: list[list[int]]) -> int:",
  "        parent = list(range(n))",
  "        def find(x):",
  "            while parent[x] != x:",
  "                parent[x] = parent[parent[x]]",
  "                x = parent[x]",
  "            return x",
  "        for a, b in edges:",
  "            parent[find(a)] = find(b)",
  "        return len({find(i) for i in range(n)})",
].join("\n");

test.describe("Screen 24 - Coding Lab (/student/coding/:problemId)", () => {
  test.beforeEach(async ({ page }) => {
    // Set student demo user in localStorage before navigating
    await loginAs(page, "student");
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
    // before "Analyze Code" the reviewer asks for a run: no canned review that fits only one problem
    await expect(page.getByTestId("review-empty")).toBeVisible();
    await expect(page.getByText("Trainer note")).toBeVisible();
    await expect(page.getByTestId("problem-attribution")).toContainText("Arun K.");
    // the problem list opens from one place only (the switcher), not a second footer button
    await expect(page.getByTestId("browse-problems-footer-button")).toHaveCount(0);
    await expect(page.getByTestId("problem-switcher-button")).toBeVisible();
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

    // Hint 1 is shown for free; asking unlocks hint 2 (wait for the page, do not skip)
    const askHintBtn = page.getByTestId("request-hint-button");
    await expect(askHintBtn).toBeVisible();
    await expect(page.getByText(/Hint 1:/i)).toBeVisible();
    await askHintBtn.click();
    await expect(page.getByText(/Hint 2:/i)).toBeVisible();
  });

  test("should submit code and display 18 / 18 hidden tests passed", async ({ page }) => {
    // the starter is now an empty stub, so the solution comes from a saved draft (the editor keeps drafts per problem)
    await page.addInitScript((code) => localStorage.setItem("irep_code:prob_connected_components:python", code), SOLUTION);
    await page.goto("/student/coding/prob_connected_components");

    const submitBtn = page.getByRole("button", { name: /Submit/i });
    await submitBtn.click();

    // Verify submission outcome
    await expect(page.getByText(/18 \/ 18 hidden tests passed/i)).toBeVisible();
  });

  test("a failed submit or hint says so: never Accepted, never an invented hint", async ({ page }) => {
    await page.goto("/student/coding/prob_connected_components");
    await expect(page.getByText(/Hint 1:/i)).toBeVisible();
    await page.route("**/api/v1/student/coding/*/submit", (r) => r.fulfill({ status: 500, body: "boom" }));
    await page.route("**/api/v1/student/coding/*/hint", (r) => r.abort());

    await page.getByTestId("submit-button").click();
    await expect(page.getByText(/could not confirm your submission/i)).toBeVisible();
    await expect(page.getByText(/hidden tests passed/i)).toHaveCount(0);
    await expect(page.getByText(/Accepted/)).toHaveCount(0);

    // earlier specs may already have unlocked hint 2 on the server: the count must simply not move
    const shown = await page.getByText(/^Hint \d+:/).count();
    const askHint = page.getByTestId("request-hint-button");
    if (await askHint.isVisible()) {
      await askHint.click();
      await expect(page.getByTestId("hint-error")).toBeVisible();
      await expect(page.getByText(/^Hint \d+:/)).toHaveCount(shown);
    }
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
    await loginAs(page, "parent");

    await page.goto("/student/coding/prob_connected_components");

    // Should display access restricted banner
    await expect(page.getByText(/Access Restricted/i)).toBeVisible();
    await expect(page.getByRole("link", { name: /Go to my dashboard/i })).toBeVisible();
  });

  test("starts from an empty stub, keeps a draft across reloads, and resets to the stub", async ({ page }) => {
    await page.goto("/student/coding/prob_two_sum");
    const editor = page.locator(".monaco-editor").first();
    await expect(editor).toContainText("def twoSum");
    await expect(editor).toContainText("pass");
    await expect(editor).not.toContainText("seen = {}");                  // the reference answer is never shown

    await page.evaluate(() => localStorage.setItem("irep_code:prob_two_sum:python", "# my draft\nclass Solution:\n    pass\n"));
    await page.reload();
    await expect(page.locator(".monaco-editor").first()).toContainText("# my draft");
    await page.getByTestId("reset-code").click();
    await expect(page.locator(".monaco-editor").first()).toContainText("def twoSum");
    expect(await page.evaluate(() => localStorage.getItem("irep_code:prob_two_sum:python"))).toBeNull();
  });

  test("the terminal runs on my input and says plainly when no code runner is set up", async ({ page }) => {
    await page.goto("/student/coding/prob_two_sum");
    await page.getByTestId("tab-terminal").click();
    await page.getByTestId("terminal-stdin").fill("2 7 11 15\n9");
    await page.getByTestId("terminal-run").click();
    // CI and local dev use JUDGE0_ADAPTER=fake: nothing runs, and the panel says so (never invented output)
    await expect(page.getByTestId("terminal-status")).toHaveText("Not available");
    await expect(page.getByTestId("terminal-unavailable")).toBeVisible();
  });

  test("Java, C++ and Node.js are terminal-only on a Python-judged problem", async ({ page }) => {
    await page.goto("/student/coding/prob_two_sum");
    await page.getByTestId("language-selector").selectOption("java");
    await expect(page.getByTestId("terminal-stdin")).toBeVisible();        // switched to the terminal
    await expect(page.getByTestId("run-button")).toBeDisabled();
    await expect(page.getByTestId("submit-button")).toBeDisabled();
    await expect(page.locator(".monaco-editor").first()).toContainText("public class Main");
  });

  test("full screen hides the problem and reviewer columns; Esc or the button brings them back", async ({ page }) => {
    await page.goto("/student/coding/prob_two_sum");
    await expect(page.getByText("AI Code Reviewer")).toBeVisible();
    await page.getByTestId("full-screen").click();
    await expect(page.getByTestId("coding-lab")).toHaveAttribute("data-focus", "true");
    await expect(page.getByText("AI Code Reviewer")).toBeHidden();
    await page.getByTestId("full-screen").click();
    await expect(page.getByTestId("coding-lab")).toHaveAttribute("data-focus", "false");
    await expect(page.getByText("AI Code Reviewer")).toBeVisible();
  });

  test("editor text size is adjustable and remembered", async ({ page }) => {
    await page.goto("/student/coding/prob_two_sum");
    await expect(page.getByTestId("font-size")).toHaveText("14");
    await page.getByTestId("font-larger").click();
    await page.getByTestId("font-larger").click();
    await expect(page.getByTestId("font-size")).toHaveText("16");
    await page.reload();
    await expect(page.getByTestId("font-size")).toHaveText("16");
  });
});

