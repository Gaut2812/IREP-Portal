import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

test.describe("Screen 34: Discussion Groups (/student/discussions)", () => {
  test("shows groups with unread badges, the moderated thread and group info; posts, reacts and reports", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/student/discussions");

    await expect(page.getByText("One-to-one messaging between students is turned off")).toBeVisible();
    await expect(page.getByTestId("unread-grp_batch")).toHaveText("3");
    await expect(page.getByTestId("unread-grp_team")).toHaveText("2");

    const convo = page.getByTestId("conversation");
    await expect(convo).toContainText("Track Doubts · ML");
    await expect(convo).toContainText("Moderated by Arun K. & Meena S.");
    await expect(convo).toContainText("18 online");
    await expect(convo).toContainText("Post code as snippets");
    await expect(convo).toContainText("Marked as answer");
    await expect(convo).toContainText("X_scaled = scaler.fit_transform(X)");

    await expect(page.getByTestId("group-info")).toContainText("42 students");
    await expect(page.getByTestId("group-info")).toContainText("128 doubts answered");
    await expect(page.getByTestId("top-helpers")).toContainText("Vikram R · 24 answers");

    // post a doubt with a code snippet
    await page.getByTestId("message-input").fill("Why does my XGBoost model overfit?");
    await page.getByTestId("toggle-code").click();
    await page.getByTestId("code-input").fill("model = XGBClassifier(max_depth=12)");
    await page.getByTestId("send").click();
    await expect(page.getByTestId("messages")).toContainText("Why does my XGBoost model overfit?");
    await expect(page.getByTestId("messages")).toContainText("XGBClassifier(max_depth=12)");

    // rule filter
    await page.getByTestId("message-input").fill("sharing the test answers here");
    await page.getByTestId("send").click();
    await expect(page.getByTestId("toast")).toContainText("breaks the group rules");

    // react + report Vikram's reply
    const vikram = page.getByTestId("messages").locator("[data-testid^='msg-']", { hasText: "classic data leakage" });
    await vikram.locator("[data-testid^='react-']").click();
    await expect(vikram.locator("[data-testid^='react-']")).toHaveAttribute("aria-pressed", "true");
    await vikram.locator("[data-testid^='report-']").click();
    await page.getByTestId("report-reason").fill("Shares a full solution");
    await page.getByTestId("report-send").click();
    await expect(page.getByTestId("toast")).toContainText("Reported to the moderators");

    // announcement-only group is read-only for students
    await page.getByTestId("group-grp_placement").click();
    await expect(page.getByTestId("locked-input")).toContainText("Only trainers can post here");
    await expect(page.getByTestId("unread-grp_placement")).toHaveCount(0);
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "student", { lang: "ta" });
    await page.goto("/student/discussions");
    await expect(page.getByText("என் குழுக்கள்")).toBeVisible();
    await expect(page.getByText("சிறந்த உதவியாளர்கள்")).toBeVisible();
  });

  test("blocks the parent role", async ({ page }) => {
    await loginAs(page, "parent");
    await page.goto("/student/discussions");
    await expect(page.getByText(/Access Restricted/i).first()).toBeVisible();
  });
});
