import { test, expect } from "@playwright/test";
import { loginAs, bearer } from "./helpers/auth";

/** Phase 2 · Mock interview booking calendar (screen 36). */
const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000/api/v1";

test.describe("Mock interview calendar", () => {
  test("days with slots are marked; picking one lists its times; booking a type explains why others of it are off", async ({ page }) => {
    const { token } = await loginAs(page, "student");
    const data = await (await page.request.get(`${API}/student/interviews`, { headers: bearer(token) })).json();
    // more than 24 h ahead, so the booking can be cancelled at the end and the demo data is left as it was
    const free = data.available_slots.filter((s: { blocked_reason: string | null; starts_at: string }) =>
      !s.blocked_reason && new Date(s.starts_at).getTime() > Date.now() + 25 * 3600 * 1000);
    test.skip(free.length < 2, "needs two open slots");
    const localDay = (iso: string) => { const d = new Date(iso); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
    const target = free[0];

    await page.goto("/student/interviews");
    const cal = page.getByTestId("slot-calendar");
    await expect(cal).toBeVisible();
    const day = page.getByTestId(`day-${localDay(target.starts_at)}`);
    await expect(day).toHaveAttribute("data-has-slots", "true");
    await day.click();
    await expect(page.getByTestId(`slot-${target.id}`)).toBeVisible();
    for (const s of data.available_slots.filter((x: { starts_at: string }) => localDay(x.starts_at) !== localDay(target.starts_at)).slice(0, 3)) {
      await expect(page.getByTestId(`slot-${s.id}`)).toHaveCount(0);                 // only that day's times
    }

    await page.getByTestId(`book-${target.id}`).click();
    await expect(page.getByTestId("toast")).toContainText("booked");
    await expect(page.getByTestId(`booking-${target.id}`)).toBeVisible();
    const month = (iso: string) => localDay(iso).slice(0, 7);
    const sameType = data.available_slots.find((s: { id: string; round_type: string; starts_at: string }) =>
      s.id !== target.id && s.round_type === target.round_type && month(s.starts_at) === month(target.starts_at));   // on the month shown
    if (sameType) {
      await page.getByTestId(`day-${localDay(sameType.starts_at)}`).click();
      await expect(page.getByTestId(`blocked-${sameType.id}`)).toContainText("already have an upcoming");
      await expect(page.getByTestId(`book-${sameType.id}`)).toBeDisabled();
    }
    // tidy up: cancel (bookings more than 24 h ahead can be cancelled)
    await page.getByTestId(`cancel-${target.id}`).click();
    await expect(page.getByTestId(`booking-${target.id}`)).toHaveCount(0);
  });

  test("the calendar in Tamil", async ({ page }) => {
    await loginAs(page, "student", { lang: "ta" });
    await page.goto("/student/interviews");
    await expect(page.getByTestId("slot-calendar")).toContainText("AI அனுமதிக்கப்பட்ட கோடிங்");
  });
});
