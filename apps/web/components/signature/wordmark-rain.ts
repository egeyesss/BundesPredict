import { rgb, type Palette } from "./palette";

export const WORDMARK_SETTINGS = {
  glyphs: "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ0123456789",
  glyphScale: 0.15,
  minGlyphPx: 6,
  baseLayerAlpha: 0.35,
  navBaseLayerAlpha: 0.6,
  navFontPx: 40,
  stepsPerSecond: 18,
  density: 0.6,
  trailLength: 8,
  activeBoost: 2,
  activeRampMs: 400,
} as const;

const GLYPHS = [...WORDMARK_SETTINGS.glyphs];
const COLUMN_PITCH = 0.9;
const MAX_STEP_BOOST = 1.6;
const GLYPH_MUTATION_CHANCE = 0.08;
const EXTRA_BUFFER_ROWS = 24;
const ACTIVE_DENSITY_GAIN = 0.6;

export const glyphSizeFor = (fontPx: number) =>
  Math.max(WORDMARK_SETTINGS.minGlyphPx, fontPx * WORDMARK_SETTINGS.glyphScale);

/** The hero-tuned base layer reads too dark below the nav threshold, so small sizes get a stronger one. */
export const baseLayerAlpha = (fontPx: number) =>
  fontPx < WORDMARK_SETTINGS.navFontPx ? WORDMARK_SETTINGS.navBaseLayerAlpha : WORDMARK_SETTINGS.baseLayerAlpha;

export const stepIntervalMs = (activity: number) =>
  1000 / (WORDMARK_SETTINGS.stepsPerSecond * (1 + (WORDMARK_SETTINGS.activeBoost - 1) * activity));

export function rampActivity(current: number, target: number, deltaMs: number): number {
  const change = deltaMs / WORDMARK_SETTINGS.activeRampMs;
  return current < target ? Math.min(target, current + change) : Math.max(target, current - change);
}

/** Colour and alpha of the glyph `fraction` (0 to 1) of the way down the trail. */
export function trailColor(palette: Palette, fraction: number): [number, number, number, number] {
  const mix = (index: 0 | 1 | 2) => Math.round(palette.red[index] + (palette.redDim[index] - palette.red[index]) * fraction);
  return [mix(0), mix(1), mix(2), Math.pow(1 - fraction, 1.2) * 0.9 + 0.1];
}

export type RainColumn = {
  head: number;
  speed: number;
  active: boolean;
  glyphs: string[];
};

export class RainField {
  readonly rows: number;
  readonly columnWidth: number;
  columns: RainColumn[];

  constructor(
    readonly width: number,
    readonly height: number,
    readonly glyphPx: number,
    private readonly random: () => number = Math.random,
    initialShare: number = WORDMARK_SETTINGS.density,
  ) {
    this.rows = Math.ceil(height / glyphPx);
    const count = Math.max(1, Math.ceil(width / (glyphPx * COLUMN_PITCH)));
    this.columnWidth = width / count;
    this.columns = Array.from({ length: count }, () => this.createColumn(true, initialShare));
  }

  density(activity: number) {
    return WORDMARK_SETTINGS.density + (1 - WORDMARK_SETTINGS.density) * ACTIVE_DENSITY_GAIN * activity;
  }

  step(boost: number, activity: number) {
    const share = this.density(activity);
    this.columns.forEach((column, index) => {
      column.head += column.speed * Math.min(boost, MAX_STEP_BOOST);
      if (column.head - WORDMARK_SETTINGS.trailLength > this.rows) {
        this.columns[index] = this.createColumn(false, share);
        return;
      }
      if (this.random() < GLYPH_MUTATION_CHANCE) {
        column.glyphs[Math.floor(this.random() * column.glyphs.length)] = this.randomGlyph();
      }
    });
  }

  private randomGlyph() {
    return GLYPHS[Math.floor(this.random() * GLYPHS.length)];
  }

  private createColumn(initial: boolean, share: number): RainColumn {
    return {
      head: initial ? this.random() * this.rows * 2 - this.rows : -this.random() * this.rows * 0.8,
      speed: 0.6 + this.random() * 0.8,
      active: this.random() < share,
      glyphs: Array.from({ length: this.rows + EXTRA_BUFFER_ROWS }, () => this.randomGlyph()),
    };
  }
}

/** Draws the glyph columns onto `context`; the caller masks the result with the word. */
export function paintRain(context: CanvasRenderingContext2D, field: RainField, palette: Palette, monoFamily: string) {
  const { trailLength } = WORDMARK_SETTINGS;
  context.font = `500 ${field.glyphPx}px ${monoFamily}`;
  context.textBaseline = "top";
  context.textAlign = "center";

  field.columns.forEach((column, index) => {
    if (!column.active) return;
    const x = (index + 0.5) * field.columnWidth;
    const headRow = Math.floor(column.head);
    for (let offset = 0; offset <= trailLength; offset++) {
      const row = headRow - offset;
      if (row < 0 || row >= field.rows) continue;
      if (offset === 0) {
        context.fillStyle = rgb(palette.redText);
      } else {
        const [red, green, blue, alpha] = trailColor(palette, offset / trailLength);
        context.fillStyle = rgb([red, green, blue], alpha);
      }
      context.fillText(column.glyphs[row % column.glyphs.length], x, row * field.glyphPx);
    }
  });
}
