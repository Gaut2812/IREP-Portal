import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

test.describe("Screen 35: Trainer Message Hub (/trainer/messages)", () => {
  test("threads, per-thread messages, translate, reply, moderation and broadcast", async ({ page }) => {
    await loginAs(page, "trainer");
    await page.goto("/trainer/messages");

    await expect(page.getByTestId("unread-th_lakshmi")).toHaveText("2");
    await expect(page.getByTestId("unread-th_kavitha")).toHaveText("1");
    await expect(page.getByTestId("permission-matrix")).toHaveCount(0);   // the "who can message whom" card was removed
    await expect(page.getByTestId("mod-rep_seed_01")).toBeVisible();
    const queueBefore = Number(await page.getByTestId("queue-count").innerText());

    // Ramesh thread (newest) is open by default
    const convo = page.getByTestId("conversation");
    await expect(convo).toContainText("Parent of Priya R");
    await expect(convo).toContainText("Prefers Tamil");
    await expect(page.getByTestId("messages")).toContainText("Her coding score improved nicely");
    await page.getByTestId("toggle-tamil").click();
    await expect(page.getByTestId("messages")).toContainText("வணக்கம் அருண் சார்");
    await page.getByTestId("toggle-tamil").click();

    // switching threads loads that thread's own messages and clears its badge
    await page.getByTestId("thread-th_lakshmi").click();
    await expect(page.getByTestId("messages")).toContainText("Will Karthik have extra coaching this Saturday?");
    await expect(page.getByTestId("unread-th_lakshmi")).toHaveCount(0);
    await page.getByTestId("reply-input").fill("Yes, extra coaching is at 10 AM on Saturday in Lab 3.");
    await page.getByTestId("send").click();
    await expect(page.getByTestId("messages")).toContainText("extra coaching is at 10 AM");

    // moderation: remove needs a reason
    await page.getByTestId("remove-rep_seed_01").click();
    await expect(page.getByTestId("toast")).toContainText("Enter a reason");
    await page.getByTestId("reason-rep_seed_01").fill("Shares graded test answers");
    await page.getByTestId("remove-rep_seed_01").click();
    await expect(page.getByTestId("mod-rep_seed_01")).toHaveCount(0);
    await expect(page.getByTestId("queue-count")).toHaveText(String(queueBefore - 1));

    // broadcast with a delivery report
    await page.getByTestId("new-broadcast").click();
    await page.getByTestId("bc-batch").selectOption("bat_aids_s5_aids");
    await page.getByTestId("bc-title").fill("Saturday lab timing");
    await page.getByTestId("bc-body").fill("Lab starts at 10:00 in Lab 3.");
    await page.getByTestId("bc-send").click();
    await expect(page.getByTestId("toast")).toContainText("Delivered to 51: 50 students, 1 parents (1 SMS)");
    await expect(page.getByTestId("broadcast-history")).toContainText("Saturday lab timing");
  });

  test("category filter and Tamil UI", async ({ page }) => {
    await loginAs(page, "trainer", { lang: "ta" });
    await page.goto("/trainer/messages");
    await expect(page.getByTestId("moderation-queue")).toBeVisible();   // Tamil UI loaded (the "who can message whom" card is gone)
    await page.getByTestId("cat-College").click();
    await expect(page.getByTestId("thread-th_kavitha")).toBeVisible();
    await expect(page.getByTestId("thread-th_ramesh")).toHaveCount(0);
  });

  test("parent sees the trainer thread at /parent/messages and replies", { tag: "@L19" }, async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 760 });
    await loginAs(page, "parent");
    await page.goto("/parent/messages");
    await expect(page.getByTestId("sla-banner")).toContainText("24 hours");
    await expect(page.getByTestId("messages")).toContainText("Nandri");
    await page.getByTestId("parent-input").fill("Thank you sir.");
    await page.getByTestId("parent-send").click();
    await expect(page.getByTestId("messages")).toContainText("Thank you sir.");
  });

  test("blocks the student role", async ({ page }) => {
    await loginAs(page, "student");
    await page.goto("/trainer/messages");
    await expect(page.getByText(/Access Restricted/i).first()).toBeVisible();
  });
});
