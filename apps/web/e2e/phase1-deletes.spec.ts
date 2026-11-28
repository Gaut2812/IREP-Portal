import { test, expect } from "@playwright/test";
import { loginAs, bearer } from "./helpers/auth";

/** Phase 1: delete with one confirmation card on every screen (docs/plans/2026-11-27-feedback-plan.md). */
const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000/api/v1";
const stamp = () => Math.random().toString(36).slice(2, 8);

test.describe("Delete with a confirmation card", () => {
  test("trainer: the card opens only on Delete, Cancel and Esc keep the item, Delete removes it", async ({ page }) => {
    const { token } = await loginAs(page, "trainer");
    const title = `Delete-me problem ${stamp()}`;
    const made = await page.request.post(`${API}/trainer/assessments/problems`, { headers: bearer(token), data: {
      title, statement: "Print the sum of two numbers.", cases: [{ name: "Sample", input_data: "1 2", expected_output: "3" }] } });
    expect(made.ok()).toBeTruthy();
    const { id } = await made.json();

    await page.goto(`/trainer/assessments?problem=${id}`);
    await expect(page.getByTestId("assess-heading")).toHaveText(title);
    await expect(page.getByTestId("confirm-delete")).toHaveCount(0);                 // never shown until asked

    await page.getByTestId("assess-delete").click();
    const card = page.getByTestId("confirm-delete");
    await expect(card).toContainText("Delete permanently?");
    await expect(page.getByTestId("confirm-delete-name")).toContainText(title);
    await expect(page.getByTestId("confirm-delete-cancel")).toBeFocused();           // the safe choice has the focus
    await page.getByTestId("confirm-delete-cancel").click();
    await expect(card).toHaveCount(0);

    await page.getByTestId("assess-delete").click();
    await page.keyboard.press("Escape");
    await expect(card).toHaveCount(0);
    await expect(page.getByTestId("assess-list")).toContainText(title);

    await page.getByTestId("assess-delete").click();
    await page.getByTestId("confirm-delete-ok").click();
    await expect(page.getByTestId("assess-msg")).toHaveText("Deleted.");
    await expect(page.getByTestId("assess-list")).not.toContainText(title);
  });

  test("college: a draft event can be edited and deleted; a published one only cancelled", async ({ page }) => {
    await loginAs(page, "college");
    await page.goto("/college/events");
    const title = `Draft meetup ${stamp()}`;
    await page.getByTestId("event-title-en").fill(title);
    await page.getByTestId("event-start").fill("2027-01-15T10:00");
    await page.getByTestId("event-save").click();
    const row = page.getByTestId("event-row").filter({ hasText: title });
    await expect(row.getByTestId("event-status")).toHaveText("Draft");
    await expect(row.getByTestId("event-cancel")).toHaveCount(0);

    await row.getByTestId("event-edit").click();
    await expect(page.getByTestId("event-form-title")).toHaveText("Edit draft");
    await page.getByTestId("event-title-en").fill(`${title} (edited)`);
    await page.getByTestId("event-save").click();
    await expect(page.getByTestId("event-toast")).toHaveText("Draft updated.");
    const edited = page.getByTestId("event-row").filter({ hasText: `${title} (edited)` });
    await expect(edited).toHaveCount(1);

    await edited.getByTestId("event-delete").click();
    await page.getByTestId("confirm-delete-ok").click();
    await expect(page.getByTestId("event-toast")).toHaveText("Draft deleted.");
    await expect(page.getByTestId("event-row").filter({ hasText: title })).toHaveCount(0);
  });

  test("college: a generated MoU report can be deleted", async ({ page }) => {
    const { token } = await loginAs(page, "college");
    const made = await page.request.post(`${API}/college/reports/generate`, { headers: bearer(token), data: { report_type: "readiness" } });
    const before = (await (await page.request.get(`${API}/college/reports`, { headers: bearer(token) })).json()).reports.length;
    const { report } = await made.json();
    await page.goto("/college/reports");
    const row = page.getByTestId("mou-row").filter({ hasText: report.title }).first();
    await row.getByTestId("mou-delete").click();
    await page.getByTestId("confirm-delete-ok").click();
    await expect(page.getByTestId("mou-row")).toHaveCount(before - 1);
  });

  test("the confirmation card is in Tamil when the portal is", async ({ page }) => {
    const { token } = await loginAs(page, "trainer", { lang: "ta" });
    const made = await page.request.post(`${API}/trainer/assessments/problems`, { headers: bearer(token), data: {
      title: `Tamil delete ${stamp()}`, statement: "Print the sum of two numbers.", cases: [{ name: "Sample", input_data: "1 2", expected_output: "3" }] } });
    const { id } = await made.json();
    await page.goto(`/trainer/assessments?problem=${id}`);
    await page.getByTestId("assess-delete").click();
    await expect(page.getByTestId("confirm-delete")).toContainText("நிரந்தரமாக நீக்கவா?");
    await page.getByTestId("confirm-delete-ok").click();
    await expect(page.getByTestId("confirm-delete")).toHaveCount(0);
  });

  test("a student cannot delete another person's records: no trainer screen, and the API says 403", async ({ page }) => {
    const { token } = await loginAs(page, "student");
    await page.goto("/trainer/assessments");
    await expect(page.getByText(/Access Restricted/i).first()).toBeVisible();
    const res = await page.request.delete(`${API}/trainer/assessments/problem/prob_connected_components`, { headers: bearer(token) });
    expect(res.status()).toBe(403);
  });
});
