import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** Screens 26, 27, 28 and the 43 proof decision. Spec: docs/screens/26-27-28-certificates.md */
const PNG = Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), Buffer.alloc(200, 48)]);

test.describe("Screens 26, 27 and 28: certificates", () => {
  test("a proof goes to the trainer and the approved certificate reaches the parent", { tag: ["@L10", "@L32"] }, async ({ page, browser }) => {
    const title = `Oracle Java Foundations ${Date.now().toString(36).slice(-5)}`;
    await loginAs(page, "student");
    await page.goto("/student/certificates");
    await page.getByTestId("cert-submit").click();
    await expect(page.getByTestId("certs-error")).toContainText("choose the proof file");
    await page.getByTestId("cert-title").fill(title);
    await page.getByTestId("cert-issuer").fill("Oracle");
    await page.getByTestId("cert-date").fill("2026-11-01");
    await page.getByTestId("cert-file").setInputFiles({ name: "proof.png", mimeType: "image/png", buffer: PNG });
    await page.getByTestId("cert-submit").click();
    await expect(page.getByTestId("certs-msg")).toContainText("Sent to your trainer");
    await expect(page.getByTestId("cert-row").filter({ hasText: title }).getByTestId("cert-status")).toHaveText("Pending proof");

    const t = await browser.newContext();
    const trainer = await t.newPage();
    await loginAs(trainer, "trainer");
    await trainer.goto("/trainer/approvals");
    const item = trainer.getByTestId("approval-certificate").filter({ hasText: title });
    await expect(item).toContainText("Priya R");
    await item.getByTestId("approve").click();
    await expect(trainer.getByTestId("approval-certificate").filter({ hasText: title })).toHaveCount(0);
    await t.close();

    const p = await browser.newContext();
    const parent = await p.newPage();
    await loginAs(parent, "parent");
    await parent.goto("/parent/certificates");
    await expect(parent.getByTestId("parent-cert").filter({ hasText: title })).toContainText("Earned");
    await p.close();

    await page.reload();
    await expect(page.getByTestId("cert-row").filter({ hasText: title }).getByTestId("cert-status")).toHaveText("Earned");
  });

  test("the college sees counts only", async ({ page }) => {
    await loginAs(page, "college");
    await page.goto("/college/certifications");
    await expect(page.getByTestId("tile-earned")).not.toHaveText("0");
    await expect(page.getByTestId("cert-batches")).toBeVisible();
    await expect(page.getByText("Priya R")).toHaveCount(0);
  });

  test("parent certificates support the Tamil toggle", async ({ page }) => {
    await loginAs(page, "parent", { lang: "ta" });
    await page.goto("/parent/certificates");
    await expect(page.getByRole("heading", { level: 1, name: "சான்றிதழ்கள்" })).toBeVisible();
  });

  test("students cannot open the college certifications", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/college/certifications");
    await expect(page.getByTestId("cert-tiles")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});
