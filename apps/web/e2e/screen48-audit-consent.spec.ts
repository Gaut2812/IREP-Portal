import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** Screen 48 · Audit and consent. Spec: docs/screens/48-audit-and-consent.md */
const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000/api/v1";

/** The super admin opens a support session for IREP staff on the demo college; returns a closer. */
async function supportSession(browser: import("@playwright/test").Browser) {
  const ctx = await browser.newContext();
  const sp = await ctx.newPage();
  const { token } = await loginAs(sp, "super");
  const h = { Authorization: `Bearer ${token}` };
  const s = await (await sp.request.post(`${API}/admin/support-sessions`, {
    headers: h, data: { college_id: "col_demo_001", staff_user_id: "usr_irep_staff_01", minutes: 15, reason: "Screen 48 end-to-end test" },
  })).json();
  return async () => { await sp.request.post(`${API}/admin/support-sessions/${s.id}/end`, { headers: h }); await ctx.close(); };
}

test.describe("Screen 48: Audit and consent (/admin/audit)", () => {
  test("staff filter the read-only audit trail", async ({ page }) => {
    await loginAs(page, "admin");
    await page.goto("/admin/audit");
    await page.getByTestId("filter-action").fill("college.");
    await page.getByTestId("filter-apply").click();
    const rows = page.getByTestId("audit-row");
    await expect(rows.first()).toBeVisible();
    await expect(rows.first()).toContainText("college.");
    await rows.first().click();
    await expect(page.getByTestId("audit-detail")).toBeVisible();
    await expect(page.getByTestId("audit-csv")).toBeVisible();
  });

  test("a college export request is built by the outbox and downloadable", async ({ page, browser }) => {
    const college = await browser.newContext();
    const cp = await college.newPage();
    const { token } = await loginAs(cp, "college");
    const created = await cp.request.post(`${API}/college/data-requests`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { student_id: "std_priya_01", kind: "export", reason: "Student asked for a copy of her data" },
    });
    expect([201, 409]).toContain(created.status());      // 409: one already open from an earlier run
    const rid: string = created.status() === 201 ? (await created.json()).id
      : (await (await cp.request.get(`${API}/college/data-requests`, { headers: { Authorization: `Bearer ${token}` } })).json()).items
        .find((i: { student_id: string; kind: string; status: string }) => i.student_id === "std_priya_01" && i.kind === "export"
          && (i.status === "received" || i.status === "in_progress")).id;
    await college.close();

    const close = await supportSession(browser);          // names and the export file need a session
    try {
      await loginAs(page, "admin");
      await page.goto("/admin/audit/requests");
      const card = page.getByTestId(`request-${rid}`);
      await expect(card).toContainText("Priya R");          // the name shows inside a support session
      await expect(card).toBeVisible();
      const build = card.getByTestId("request-complete");
      if (await build.count()) await build.click();
      // the API's outbox thread builds the file within a few seconds
      await expect(async () => {
        await page.reload();
        await expect(page.getByTestId(`request-${rid}`).getByTestId("request-download")).toBeVisible({ timeout: 1000 });
      }).toPass({ timeout: 20000 });
    } finally {
      await close();
    }
  });

  test("without a support session staff see no student data", async ({ page, browser }) => {
    // end any session left open for the demo staff account (e.g. by an interrupted run)
    const ctx = await browser.newContext();
    const sp = await ctx.newPage();
    const { token } = await loginAs(sp, "super");
    const h = { Authorization: `Bearer ${token}` };
    const open = (await (await sp.request.get(`${API}/admin/support-sessions`, { headers: h })).json()).items
      .filter((s: { active: boolean; staff_user_id: string }) => s.active && s.staff_user_id === "usr_irep_staff_01");
    for (const s of open) await sp.request.post(`${API}/admin/support-sessions/${s.id}/end`, { headers: h });
    await ctx.close();

    await loginAs(page, "admin");
    await page.goto("/admin/audit/consent");
    await expect(page.getByTestId("needs-support-session")).toContainText("support session");
    await page.goto("/admin/audit/requests");
    const hidden = page.getByTestId("request-name-hidden").first();
    if (await hidden.count()) await expect(hidden).toContainText("Name hidden");
    await expect(page.locator("[data-testid^='request-dr_']").filter({ hasText: "Priya R" })).toHaveCount(0);
  });

  test("a parent who withdrew consent sees the consent card and can agree again", { tag: "@L38" }, async ({ page }) => {
    const { token } = await loginAs(page, "parent", { phone: "9876543214" });
    const w = await page.request.post(`${API}/consent`, {
      headers: { Authorization: `Bearer ${token}` }, data: { purpose: "parent_data_processing", status: "withdrawn" },
    });
    expect(w.status()).toBe(201);
    await page.goto("/parent");
    await expect(page.getByTestId("consent-card")).toBeVisible();
    await expect(page.getByTestId("readiness-card")).toHaveCount(0);
    await page.getByTestId("consent-agree").click();
    await expect(page.getByTestId("readiness-card")).toBeVisible();
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "admin", { lang: "ta" });
    await page.goto("/admin/audit/requests");
    await expect(page.getByRole("link", { name: "தரவுக் கோரிக்கைகள்" })).toBeVisible();
  });

  test("blocks the college admin role", async ({ page }) => {
    await loginAs(page, "college");
    await page.goto("/admin/audit");
    await expect(page.getByTestId("audit-table")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});
