import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** Screen 03 · Branches and batches. Spec: docs/screens/03-branches-and-batches.md */
const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000/api/v1";

test.describe("Screen 03: Branches and batches (/college/structure)", () => {
  test("the first admin of a new college sets up branches, batches and imports students", { tag: "@L25" }, async ({ page }) => {
    // screen 45 (staff) creates the college and its first admin
    const staff = await (await page.request.post(`${API}/auth/login`, { data: { role: "admin", identifier: "staff@irep.demo", password: "password123" } })).json();
    const H = { Authorization: `Bearer ${staff.access_token}` };
    const code = `W${Date.now().toString(36).slice(-6).toUpperCase()}`;
    const col = await (await page.request.post(`${API}/admin/colleges`, { headers: H, data: { name: "Web Structure College", code, city: "Vellore", state: "Tamil Nadu" } })).json();
    const email = `first.admin.${code.toLowerCase()}@college.example`;
    const admin = await (await page.request.post(`${API}/admin/colleges/${col.id}/admins`, { headers: H, data: { name: "Dr. First Admin", email } })).json();

    await page.goto("/login");
    await page.getByTestId("role-college").click();
    await page.getByTestId("login-identifier").fill(email);
    await page.getByTestId("login-password").fill(admin.temporary_password);
    await page.getByTestId("login-submit").click();
    await page.waitForURL("**/college");

    await page.goto("/college/structure");
    await expect(page.getByTestId("structure-empty")).toBeVisible();
    await page.getByTestId("branch-name").fill("Information Technology");
    await page.getByTestId("branch-code").fill("IT");
    await page.getByTestId("branch-save").click();
    await expect(page.getByTestId("branch-IT")).toBeVisible();
    await page.getByTestId("batch-name").fill("IT-A");
    await page.getByTestId("batch-semester").selectOption("3");
    await page.getByTestId("batch-save").click();
    await expect(page.getByTestId("batch-IT-A")).toContainText("3");

    const tag = code.toLowerCase();
    const csv = "register_no,name,email,phone,branch_code,batch,semester,parent_name,parent_phone\n" +
      `R${tag}1,Kavin M,kavin.${tag}@stu.example,,IT,IT-A,3,,\n` +
      `R${tag}2,Lavanya P,lavanya.${tag}@stu.example,,IT,IT-A,4,,\n`;            // wrong semester
    await page.getByTestId("import-file").setInputFiles({ name: "students.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
    await page.getByTestId("import-check").click();
    await expect(page.getByTestId("import-errors")).toContainText("does not match batch IT-A");
    await expect(page.getByTestId("import-run")).toBeDisabled();

    const fixed = csv.replace(",IT,IT-A,4,", ",IT,IT-A,3,");
    await page.getByTestId("import-file").setInputFiles({ name: "students.csv", mimeType: "text/csv", buffer: Buffer.from(fixed) });
    await page.getByTestId("import-check").click();
    await expect(page.getByTestId("import-result")).toContainText("2 new");
    await page.getByTestId("import-run").click();
    await expect(page.getByTestId("import-result")).toContainText("Imported");
    await expect(page.getByTestId("count-students")).toHaveText("2");
    await expect(page.getByTestId("batch-IT-A").getByTestId("batch-students")).toHaveText("2");
  });

  test("shows the demo college structure and supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "college", { lang: "ta" });
    await page.goto("/college/structure");
    await expect(page.getByTestId("count-students")).toHaveText("612");
    await expect(page.getByTestId("import-check")).toContainText("கோப்பைச் சரிபார்");
  });

  test("blocks the trainer role", async ({ page }) => {
    await loginAs(page, "trainer");
    await page.goto("/college/structure");
    await expect(page.getByTestId("import-section")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});
