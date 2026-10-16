import { subscribeFrames } from "./frame-loop";
import { readPalette, rgb, type Palette } from "./palette";
import { RainField, baseLayerAlpha, glyphSizeFor, paintRain, rampActivity, stepIntervalMs, WORDMARK_SETTINGS } from "./wordmark-rain";

const MAX_DPR = 2;
const FALLBACK_MONO = 'ui-monospace, "SF Mono", Menlo, monospace';

type Measure = {
  width: number;
  height: number;
  dpr: number;
  fontPx: number;
  font: string;
  baseline: number;
  palette: Palette;
  monoFamily: string;
  field: RainField;
};

/**
 * Paints the code rain inside the word "Predict" on a canvas laid exactly over the
 * real text. The rain is drawn on an offscreen canvas and masked with the word
 * (`destination-in`), then composited over a solid base layer of the same word.
 */
export class WordmarkRenderer {
  private readonly context: CanvasRenderingContext2D;
  private readonly offscreen = document.createElement("canvas");
  private readonly offscreenContext: CanvasRenderingContext2D;
  private measured: Measure | null = null;
  private layoutSize: { width: number; height: number } | null = null;
  private activity = 0;
  private target = 0;
  private elapsedSinceStep = 0;
  private visible = true;
  private drawnOnce = false;
  private teardown: Array<() => void> = [];

  constructor(
    private readonly predict: HTMLElement,
    private readonly canvas: HTMLCanvasElement,
    private readonly onFirstDraw: () => void,
  ) {
    const context = canvas.getContext("2d");
    const offscreenContext = this.offscreen.getContext("2d");
    if (!context || !offscreenContext) throw new Error("2d canvas is not available");
    this.context = context;
    this.offscreenContext = offscreenContext;
  }

  setActive(active: boolean) {
    this.target = active ? 1 : 0;
  }

  start() {
    const resizeObserver = new ResizeObserver((entries) => {
      const box = entries[0]?.borderBoxSize?.[0];
      if (!box) return;
      this.layoutSize = { width: box.inlineSize, height: box.blockSize };
      this.measure();
    });
    resizeObserver.observe(this.predict);
    this.teardown.push(() => resizeObserver.disconnect());

    if (typeof IntersectionObserver !== "undefined") {
      const intersectionObserver = new IntersectionObserver(([entry]) => {
        this.visible = entry.isIntersecting;
      });
      intersectionObserver.observe(this.predict);
      this.teardown.push(() => intersectionObserver.disconnect());
    }

    const remeasure = () => this.measure();
    document.fonts.addEventListener("loadingdone", remeasure);
    this.teardown.push(() => document.fonts.removeEventListener("loadingdone", remeasure));
    this.loadFonts().then(remeasure);

    this.watchDevicePixelRatio();
    this.teardown.push(subscribeFrames((_, delta) => this.tick(delta)));
    this.measure();
  }

  stop() {
    this.teardown.forEach((undo) => undo());
    this.teardown = [];
  }

  private async loadFonts() {
    const style = getComputedStyle(this.predict);
    const display = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
    const mono = `500 12px ${this.monoFamily()}`;
    await Promise.all([document.fonts.load(display, "Predict"), document.fonts.load(mono, "0")]).catch(() => {});
    await document.fonts.ready;
  }

  private monoFamily() {
    const declared = getComputedStyle(this.predict).getPropertyValue("--font-mono").trim();
    return declared || FALLBACK_MONO;
  }

  private watchDevicePixelRatio() {
    let query: MediaQueryList | null = null;
    const onChange = () => {
      this.measure();
      listen();
    };
    const listen = () => {
      query?.removeEventListener("change", onChange);
      query = window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`);
      query.addEventListener("change", onChange);
    };
    listen();
    this.teardown.push(() => query?.removeEventListener("change", onChange));
  }

  private measure() {
    const size = this.layoutSize ?? { width: this.predict.offsetWidth, height: this.predict.offsetHeight };
    if (size.width === 0 || size.height === 0) return;

    const style = getComputedStyle(this.predict);
    const fontPx = parseFloat(style.fontSize);
    const font = `${style.fontWeight} ${fontPx}px ${style.fontFamily}`;
    const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);

    for (const canvas of [this.canvas, this.offscreen]) {
      canvas.width = Math.round(size.width * dpr);
      canvas.height = Math.round(size.height * dpr);
    }

    this.context.font = font;
    const metrics = this.context.measureText(this.word());
    const ascent = metrics.fontBoundingBoxAscent ?? metrics.actualBoundingBoxAscent;
    const descent = metrics.fontBoundingBoxDescent ?? metrics.actualBoundingBoxDescent;
    // The span is inline-block with line-height 1, so the baseline sits half the
    // leftover leading below the top, plus the ascent.
    const baseline = (size.height - (ascent + descent)) / 2 + ascent;

    this.measured = {
      width: size.width,
      height: size.height,
      dpr,
      fontPx,
      font,
      baseline,
      palette: readPalette(this.predict),
      monoFamily: this.monoFamily(),
      field: new RainField(size.width, size.height, glyphSizeFor(fontPx), Math.random, WORDMARK_SETTINGS.density),
    };
    this.draw();
  }

  private word() {
    return this.predict.querySelector("[data-wordmark-text]")?.textContent ?? "Predict";
  }

  private tick(delta: number) {
    if (!this.measured) return;
    this.activity = rampActivity(this.activity, this.target, delta);
    if (!this.visible) return;

    this.elapsedSinceStep += delta;
    const interval = stepIntervalMs(this.activity);
    if (this.elapsedSinceStep < interval) return;
    this.elapsedSinceStep %= interval;

    const boost = 1 + (WORDMARK_SETTINGS.activeBoost - 1) * this.activity;
    this.measured.field.step(boost, this.activity);
    this.draw();
  }

  private draw() {
    const measured = this.measured;
    if (!measured) return;
    const { width, height, dpr, font, baseline, palette, fontPx, field, monoFamily } = measured;
    const word = this.word();
    const mask = this.offscreenContext;
    const output = this.context;

    mask.setTransform(dpr, 0, 0, dpr, 0, 0);
    mask.globalCompositeOperation = "source-over";
    mask.clearRect(0, 0, width, height);
    paintRain(mask, field, palette, monoFamily);
    mask.globalCompositeOperation = "destination-in";
    mask.font = font;
    mask.textBaseline = "alphabetic";
    mask.textAlign = "left";
    mask.fillStyle = "#000";
    mask.fillText(word, 0, baseline);

    output.setTransform(dpr, 0, 0, dpr, 0, 0);
    output.clearRect(0, 0, width, height);
    output.font = font;
    output.textBaseline = "alphabetic";
    output.textAlign = "left";
    output.globalAlpha = baseLayerAlpha(fontPx);
    output.fillStyle = rgb(palette.red);
    output.fillText(word, 0, baseline);
    output.globalAlpha = 1;
    output.setTransform(1, 0, 0, 1, 0, 0);
    output.drawImage(this.offscreen, 0, 0);

    if (!this.drawnOnce) {
      this.drawnOnce = true;
      this.onFirstDraw();
    }
  }
}
