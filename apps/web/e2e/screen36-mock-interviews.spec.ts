import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

test.describe("Screen 36: Mock Interviews (/student/interviews)", () => {
  test("shows the scored round, trend, slots and recording comments; books and cancels a slot", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/student/interviews");

    const latest = page.getByTestId("latest-interview");
    await expect(latest).toContainText("Mock Interview #2 – Technical");
    await expect(latest).toContainText("Interviewer: Arun Kumar");
    await expect(page.getByTestId("overall")).toContainText("3.8");
    await expect(latest).toContainText("Hire-ready for service roles");
    await expect(latest).toContainText("Improve for product roles");
    await expect(page.getByTestId("rubric")).toContainText("Thinking aloud");
    await expect(page.getByTestId("rubric")).toContainText("3/5");
    await expect(latest).toContainText("Strong on DSA");

    await expect(page.getByTestId("trend")).toContainText("Target 4.2");

    const slots = page.getByTestId("book-slots");
    await expect(slots).toContainText("Technical");
    await expect(slots).toContainText("HR round");
    await expect(slots).toContainText("AI-allowed coding");

    await page.getByTestId("book-slot_demo_hr").click();
    await expect(page.getByTestId("toast")).toContainText("Slot booked");
    await expect(page.getByTestId("booking-slot_demo_hr")).toContainText("Booked");
    await expect(page.getByTestId("slot-slot_demo_hr")).toHaveCount(0);
    await page.getByTestId("cancel-slot_demo_hr").click();
    await expect(page.getByTestId("toast")).toContainText("Booking cancelled");
    await expect(page.getByTestId("slot-slot_demo_hr")).toBeVisible();

    // clicking a timestamped comment loads the signed recording and seeks to it
    await page.getByTestId("comment-540").click();
    const video = page.getByTestId("recording").locator("video");
    await expect(video).toHaveAttribute("src", /\/media\/recordings\/interviews\/priya_round2\.mp4\?exp=/);
    await expect(video).toHaveAttribute("data-seek", "540");
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "student", { lang: "ta" });
    await page.goto("/student/interviews");
    await expect(page.getByText("அடுத்த நேரத்தைப் பதிவு செய்")).toBeVisible();
    await expect(page.getByTestId("rubric")).toContainText("உரக்கச் சிந்தித்தல்");
  });

  test("blocks the parent role", async ({ page }) => {
    await loginAs(page, "parent");
    await page.goto("/student/interviews");
    await expect(page.getByText(/Access Restricted/i).first()).toBeVisible();
  });
});
