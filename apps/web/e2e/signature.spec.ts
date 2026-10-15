import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { STREAMS, type TimedEvent } from "../app/styleguide/signature/streams";
import { DONE_HOLD_MS, foldAgentEvents, type AgentEvent } from "../lib/agent-state";

const PAGE_PATH = "/styleguide/signature";
const MAX_TASK_MS = 200;

async function open(page: Page) {
  await page.goto(PAGE_PATH);
  await expect(page.locator('.island[data-ready="true"]').first()).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
}

/**
 * Opens the page on a paused fake clock so a replay can be stepped one event at a
 * time. Real timers made these checks depend on how busy the machine was.
 */
async function openOnPausedClock(page: Page) {
  await page.clock.install();
  await open(page);
  await page.clock.pauseAt(new Date(Date.now() + 1_000));
}

const stageOrb = (page: Page) => page.locator('[data-testid="stage-orb"] [data-orb]');

/** Advances the paused clock to each event in turn and hands the events delivered so far to `check`. */
async function stepThrough(page: Page, events: readonly TimedEvent[], check: (delivered: AgentEvent[]) => Promise<void>) {
  const delivered: AgentEvent[] = [];
  let first = true;
  for (const [delay, event] of events) {
    await page.clock.runFor(delay + (first ? 1 : 0));
    first = false;
    delivered.push(event);
    await check(delivered);
  }
}

async function expectOrbToFollow(page: Page, delivered: AgentEvent[]) {
  const expected = foldAgentEvents(delivered);
  await expect(stageOrb(page)).toHaveAttribute("data-orb-state", expected.phase);
  if (expected.phase === "tool") await expect(stageOrb(page)).toHaveAttribute("data-orb-tool", expected.tool);
}

test.describe("wordmark with motion", () => {
  test.use({ reducedMotion: "no-preference" });

  for (const [name, testId] of [
    ["hero", "hero-wordmark"],
    ["nav", "nav-wordmark"],
  ] as const) {
    test(`the ${name} canvas sits within 1px of the Predict text`, async ({ page }) => {
      await open(page);
      const mark = page.locator(`[data-testid="${testId}"] .wm`);
      await expect(mark).toHaveAttribute("data-live", "true");
      const text = await mark.locator(".wm-predict").boundingBox();
      const canvas = await mark.locator("canvas").boundingBox();
      expect(text).not.toBeNull();
      expect(canvas).not.toBeNull();
      for (const edge of ["x", "y", "width", "height"] as const) {
        expect(Math.abs(canvas![edge] - text![edge]), edge).toBeLessThanOrEqual(1);
      }
    });
  }

  test("the canvas backing store matches devicePixelRatio", async ({ page }) => {
    await open(page);
    const sizes = await page.locator('[data-testid="hero-wordmark"] canvas').evaluate((canvas: HTMLCanvasElement) => ({
      scale: canvas.width / canvas.getBoundingClientRect().width,
      dpr: Math.min(window.devicePixelRatio, 2),
    }));
    expect(sizes.scale).toBeCloseTo(sizes.dpr, 1);
  });

  test("the island runs one canvas, in the visible layer", async ({ page }) => {
    await open(page);
    const island = page.locator(".island-wrap:not([data-preview]) nav.island");
    await expect(island.locator("canvas")).toHaveCount(1);
    await expect(island.locator('[data-layer].is-on canvas')).toHaveCount(1);
    for (const layer of await island.locator("[data-layer] .isl-logo").all()) {
      await expect(layer).toHaveText("BundesPredict");
    }
  });

  test("the rain speeds up while a stream replays and settles afterwards", async ({ page }) => {
    await openOnPausedClock(page);
    const hero = page.locator('[data-testid="hero-wordmark"] .wm');
    await expect(hero).toHaveAttribute("data-active", "false");
    await page.getByTestId("replay-tool-heavy").click();
    await page.clock.runFor(1);
    await expect(hero).toHaveAttribute("data-active", "true");
    await stepThrough(page, STREAMS.toolHeavy.events.slice(1), async () => {});
    await expect(hero).toHaveAttribute("data-active", "false");
  });
});

test.describe("orb replay", () => {
  test.use({ reducedMotion: "no-preference" });

  test("replaying the tool-heavy stream walks the orb through every state", async ({ page }) => {
    await openOnPausedClock(page);
    await expect(stageOrb(page)).toHaveAttribute("data-orb-state", "idle");
    await page.getByTestId("replay-tool-heavy").click();

    const phases = new Set<string>(["idle"]);
    const tools: string[] = [];
    await stepThrough(page, STREAMS.toolHeavy.events, async (delivered) => {
      await expectOrbToFollow(page, delivered);
      const state = foldAgentEvents(delivered);
      phases.add(state.phase);
      if (state.phase === "tool") tools.push(state.tool);
    });

    await page.clock.runFor(DONE_HOLD_MS);
    await expect(stageOrb(page)).toHaveAttribute("data-orb-state", "idle");
    phases.add("idle");
    expect([...phases].sort()).toEqual(["done", "idle", "thinking", "tool"]);
    expect(tools).toEqual(["predict_match", "lookup_player", "get_weather", "predict_with_adjustments"]);
  });

  test("an erroring stream ends in error with the server message, and a second send recovers", async ({ page }) => {
    await openOnPausedClock(page);
    const caption = page.getByTestId("stage-orb").locator("xpath=..").getByRole("status");
    await page.getByTestId("replay-error").click();
    await stepThrough(page, STREAMS.withError.events, (delivered) => expectOrbToFollow(page, delivered));
    await expect(stageOrb(page)).toHaveAttribute("data-orb-state", "error");
    await expect(caption).toHaveText("The model is unavailable right now. Your chat was not counted.");

    await page.getByTestId("replay-tool-heavy").click();
    await page.clock.runFor(1);
    await expect(stageOrb(page)).toHaveAttribute("data-orb-state", "thinking");
    await expect(caption).toHaveText("Reading the question");
  });

  test("captions announce each tool through a polite live region", async ({ page }) => {
    await openOnPausedClock(page);
    const caption = page.getByTestId("stage-orb").locator("xpath=..").getByRole("status");
    await expect(caption).toHaveAttribute("aria-live", "polite");
    await page.getByTestId("replay-tool-heavy").click();
    const captions: string[] = [];
    await stepThrough(page, STREAMS.toolHeavy.events, async () => {
      const text = (await caption.textContent()) ?? "";
      if (captions.at(-1) !== text) captions.push(text);
    });
    await expect(caption).toHaveText("Done");
    expect(captions).toEqual(expect.arrayContaining(["Reading the question", "Running the model"]));
  });

  test("the ticker fills with each tool and folds once the answer arrives", async ({ page }) => {
    await openOnPausedClock(page);
    const ticker = page.getByText("Streaming message · 56px").locator("xpath=..").locator("details");
    await page.getByTestId("replay-tool-heavy").click();
    await stepThrough(page, STREAMS.toolHeavy.events.slice(0, 5), async () => {});
    await expect(ticker).toHaveJSProperty("open", true);
    await expect(ticker.getByText("Ran the model for Bayern v Leipzig")).toBeVisible();
    await stepThrough(page, STREAMS.toolHeavy.events.slice(5), async () => {});
    await expect(ticker).toHaveJSProperty("open", false);
    await expect(ticker.locator("li")).toHaveCount(4);
  });

  test("no task runs longer than 200ms while the stream replays", async ({ page, browser }) => {
    test.setTimeout(90_000);
    await open(page);
    await browser.startTracing(page, {
      categories: ["-*", "toplevel", "devtools.timeline", "disabled-by-default-devtools.timeline"],
    });
    await page.getByTestId("replay-tool-heavy").click();
    await expect(stageOrb(page)).toHaveAttribute("data-orb-state", "done", { timeout: 30_000 });
    const trace = JSON.parse((await browser.stopTracing()).toString()) as {
      traceEvents: Array<{ name: string; ph: string; dur?: number; tdur?: number }>;
    };

    const tasks = trace.traceEvents.filter((event) => event.name === "RunTask" && event.ph === "X");
    expect(tasks.length).toBeGreaterThan(100);
    // tdur is the main thread's CPU time, so a busy CI box descheduling the browser cannot fail the check.
    const longest = Math.max(...tasks.map((task) => (task.tdur ?? task.dur ?? 0) / 1000));
    test.info().annotations.push({ type: "longest task", description: `${longest.toFixed(1)}ms CPU of ${tasks.length} tasks` });
    expect(longest).toBeLessThan(MAX_TASK_MS);
  });
});

test.describe("bars and chips", () => {
  test.use({ reducedMotion: "no-preference" });

  test("the adjusted bar tweens from the baseline to the adjusted odds", async ({ page }) => {
    await open(page);
    const row = page.locator("span", { hasText: /^With your news$/ }).locator("xpath=..");
    const growths = () => row.locator("[data-segment]").evaluateAll((segments) => segments.map((segment) => Number((segment as HTMLElement).style.flexGrow)));
    await expect.poll(growths).toEqual([0.5811, 0.2424, 0.1765]);
  });

  test("a chip shows its rationale on hover", async ({ page }) => {
    await open(page);
    await page.locator("[tabindex='0']", { hasText: "player_out" }).hover();
    await expect(page.getByRole("tooltip")).toContainText("Harry Kane ruled out");
  });
});

test.describe("reduced motion", () => {
  test.use({ reducedMotion: "reduce" });

  test("never mounts a wordmark canvas and keeps the real text", async ({ page }) => {
    await open(page);
    await expect(page.locator(".wm canvas")).toHaveCount(0);
    await expect(page.locator('[data-testid="hero-wordmark"] .wm')).toHaveText("BundesPredict");
  });

  test("the wordmark matches its screenshot at both sizes", async ({ page }) => {
    await open(page);
    await expect(page.getByTestId("hero-wordmark")).toHaveScreenshot("wordmark-hero.png");
    await expect(page.getByTestId("nav-wordmark")).toHaveScreenshot("wordmark-nav.png");
  });

  test("every orb state draws one still frame with the ring carrying the state", async ({ page }) => {
    await open(page);
    const gallery = page.getByText("Every state, 120px").locator("xpath=..");
    await expect(gallery.locator('[data-orb][data-reduced="true"]')).toHaveCount(6);
    await expect(gallery).toHaveScreenshot("orb-states.png");
  });

  test("the page matches its snapshot", async ({ page }) => {
    await open(page);
    await expect(page).toHaveScreenshot("signature.png", { fullPage: true });
  });

  test("the bars jump straight to the adjusted odds", async ({ page }) => {
    await open(page);
    const row = page.locator("span", { hasText: /^With your news$/ }).locator("xpath=..");
    const growths = await row.locator("[data-segment]").evaluateAll((segments) => segments.map((segment) => Number((segment as HTMLElement).style.flexGrow)));
    expect(growths).toEqual([0.5811, 0.2424, 0.1765]);
  });

  test("has no axe violations", async ({ page }) => {
    test.setTimeout(120_000);
    await open(page);
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });
});
