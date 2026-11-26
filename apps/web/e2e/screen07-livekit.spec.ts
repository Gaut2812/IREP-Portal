import { test, expect, Browser } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/**
 * Screen 07 on a real LiveKit server (open-source audio and video).
 * Opt-in: needs `docker compose -f infra/livekit/docker-compose.yml up -d` and an API started with
 * LIVE_CLASS_ADAPTER=livekit, then LIVEKIT_E2E=1. The default suite stays on the fake adapter.
 * The session must have no LiveMeeting yet (re-seed, or delete it), so the room is created as LiveKit.
 */
const SESSION = process.env.LIVEKIT_E2E_SESSION || "sess_thu_rag";
const ROOM = `/live/${SESSION}`;

test.skip(!process.env.LIVEKIT_E2E, "set LIVEKIT_E2E=1 with a LiveKit server and an API on LIVE_CLASS_ADAPTER=livekit");
test.use({ launchOptions: { args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required"] } });

async function asRole(browser: Browser, role: "student" | "trainer", lang: "en" | "ta" = "en") {
  const context = await browser.newContext({ permissions: ["camera", "microphone"] });
  const page = await context.newPage();
  await loginAs(page, role, { lang });
  return { context, page };
}

test.describe("Screen 07 on LiveKit", () => {
  test("trainer goes live on camera, student joins in Tamil, moderation and attendance work, end disconnects everyone",
    { tag: ["@L04", "@L06"] }, async ({ browser }) => {
      test.setTimeout(120_000);
      const trainer = await asRole(browser, "trainer");
      const student = await asRole(browser, "student", "ta");

      // trainer starts: connected, own camera on the main view
      await trainer.page.goto(ROOM);
      await trainer.page.getByTestId("start-class").click();
      await expect(trainer.page.getByTestId("lk-stage")).toHaveAttribute("data-state", "connected", { timeout: 20_000 });
      await expect(trainer.page.getByTestId("lk-main-video")).toBeVisible({ timeout: 15_000 });

      // student lands in the room (auto-join), camera and mic off, sees the trainer's video
      await student.page.goto(ROOM);
      await expect(student.page.getByTestId("lk-stage")).toHaveAttribute("data-state", "connected", { timeout: 20_000 });
      await expect(student.page.getByTestId("lk-main-video")).toBeVisible({ timeout: 15_000 });
      await expect(student.page.getByTestId("lk-cam")).toHaveAttribute("aria-pressed", "false");
      await expect(student.page.getByTestId("lk-mic")).toHaveAttribute("aria-pressed", "false");
      await expect(student.page.getByTestId("lk-audio-only")).toHaveAttribute("aria-label", "ஒலி மட்டும் (டேட்டா சேமிப்பு)");
      await expect(student.page.getByTestId("lk-screen")).toBeDisabled();             // not granted yet

      // LiveKit's participant_joined webhook marks her in the room (attendance source)
      await expect(student.page.getByTestId("auto-attendance")).toContainText("சேர்ந்தீர்கள்", { timeout: 20_000 });

      // trainer sees her tile; raise hand reaches the trainer
      const tile = trainer.page.locator('[data-testid="lk-tile"][data-identity="usr_priya_01"]');
      await expect(tile).toBeVisible({ timeout: 15_000 });
      await student.page.getByTestId("lk-hand").click();
      await expect(trainer.page.getByTestId("lk-hands-count")).toContainText("1", { timeout: 10_000 });

      // trainer allows screen share: the student's button turns on
      await tile.getByTestId("lk-share-grant").click();
      await expect(student.page.getByTestId("lk-screen")).toBeEnabled({ timeout: 15_000 });

      // student unmutes, trainer mutes her through the outbox → LiveKit
      await student.page.getByTestId("lk-mic").click();
      await expect(student.page.getByTestId("lk-mic")).toHaveAttribute("aria-pressed", "true");
      await expect(tile.getByTestId("lk-mute")).toBeVisible({ timeout: 10_000 });
      await tile.getByTestId("lk-mute").click();
      await expect(student.page.getByTestId("lk-mic")).toHaveAttribute("aria-pressed", "false", { timeout: 15_000 });

      // trainer ends: attendance summary, and LiveKit closes the room for the student
      await trainer.page.getByTestId("end-class").click();
      await expect(trainer.page.getByTestId("toast")).toBeVisible();
      await expect(student.page.getByTestId("live-lobby")).toContainText("இந்த வகுப்பு முடிந்தது", { timeout: 20_000 });

      await trainer.context.close();
      await student.context.close();
    });

  test("blocks the parent role", async ({ page }) => {
    await loginAs(page, "parent");
    await page.goto(ROOM);
    await expect(page.getByText(/Access Restricted/i).first()).toBeVisible();
  });
});
