import type { OrbState } from "@/lib/agent-state";

import { readPalette, type Palette, type Rgb } from "./palette";
import {
  ORB_SETTINGS,
  ORB_TARGETS,
  buildSphere,
  depthAlpha,
  easeToward,
  glyphPxFor,
  pointCountFor,
  spinRate,
  usesDots,
  type OrbLive,
  type OrbPhase,
} from "./orb-sphere";

const MAX_DPR = 2;
const HOT_WHITE: Rgb = [255, 227, 229];
const FLASH_MS = 500;
const SPHERE_RADIUS = 0.38;
const PERSPECTIVE = 2.8;
const FONT_STEP_PX = 0.5;
const GLYPHS = [...ORB_SETTINGS.glyphs];

type Glyph = { x: number; y: number; z: number; character: string };

const mix = (from: Rgb, to: Rgb, amount: number): Rgb => [
  from[0] + (to[0] - from[0]) * amount,
  from[1] + (to[1] - from[1]) * amount,
  from[2] + (to[2] - from[2]) * amount,
];

/** A rotating sphere of digit glyphs (or dots when small) whose motion follows the agent's phase. */
export class OrbEngine {
  private readonly context: CanvasRenderingContext2D;
  private points: Glyph[] = [];
  private cssSize = 0;
  private dpr = 1;
  private glyphPx = 0;
  private dots = true;
  private palette: Palette;
  private monoFamily: string;
  private live: OrbLive = { ...ORB_TARGETS.idle };
  private phase: OrbPhase = "idle";
  private rotation = 0;
  private lastToolSeq = 0;
  private pulseStart = -Infinity;
  private flashStart = -Infinity;
  private jitterUntil = 0;

  constructor(private readonly canvas: HTMLCanvasElement) {
    const context = canvas.getContext("2d");
    if (!context) throw new Error("2d canvas is not available");
    this.context = context;
    this.palette = readPalette(canvas);
    this.monoFamily = getComputedStyle(canvas).getPropertyValue("--font-mono").trim() || "ui-monospace, monospace";
  }

  resize(cssSize: number) {
    if (cssSize <= 0) return;
    this.cssSize = cssSize;
    this.dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
    this.canvas.width = Math.round(cssSize * this.dpr);
    this.canvas.height = Math.round(cssSize * this.dpr);
    this.palette = readPalette(this.canvas);
    this.monoFamily = getComputedStyle(this.canvas).getPropertyValue("--font-mono").trim() || this.monoFamily;
    this.points = buildSphere(pointCountFor(cssSize)).map((point) => ({ ...point, character: this.randomGlyph() }));
    this.glyphPx = glyphPxFor(cssSize);
    this.dots = usesDots(cssSize);
  }

  get ready() {
    return this.cssSize > 0;
  }

  setState(state: OrbState, now: number) {
    const previous = this.phase;
    this.phase = state.phase;
    if (state.phase === "tool" && state.seq !== this.lastToolSeq) {
      this.lastToolSeq = state.seq;
      this.pulseStart = now;
    }
    if (state.phase === "done" && previous !== "done") this.flashStart = now;
    if (state.phase === "error" && previous !== "error") this.jitterUntil = now + ORB_SETTINGS.errorJitterMs;
    if (state.phase === "thinking" && previous !== "tool") this.lastToolSeq = 0;
  }

  /** Jumps the live values to the current phase, for the single still frame under reduced motion. */
  snap() {
    this.live = { ...ORB_TARGETS[this.phase] };
  }

  step(deltaSeconds: number) {
    const target = ORB_TARGETS[this.phase];
    for (const key of Object.keys(this.live) as Array<keyof OrbLive>) {
      this.live[key] = easeToward(this.live[key], target[key], deltaSeconds);
    }
    this.rotation += spinRate(this.live.spin) * deltaSeconds;
    this.mutate(deltaSeconds);
  }

  private randomGlyph() {
    return GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
  }

  private mutate(deltaSeconds: number) {
    const changes = this.live.mutate * deltaSeconds * this.points.length * 0.05;
    for (let change = 0; change < changes; change++) {
      this.points[Math.floor(Math.random() * this.points.length)].character = this.randomGlyph();
    }
  }

  draw(now: number) {
    if (!this.ready) return;
    const { context, cssSize, palette, live } = this;
    context.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    context.clearRect(0, 0, cssSize, cssSize);

    const center = cssSize / 2;
    const radius = cssSize * SPHERE_RADIUS;
    this.paintGlow(center, radius);

    const jitter = now < this.jitterUntil ? (Math.random() - 0.5) * 0.12 : 0;
    const rotation = this.rotation + jitter;
    const cosY = Math.cos(rotation);
    const sinY = Math.sin(rotation);
    const cosTilt = Math.cos(ORB_SETTINGS.axisTiltRad);
    const sinTilt = Math.sin(ORB_SETTINGS.axisTiltRad);
    const pulseProgress = (now - this.pulseStart) / ORB_SETTINGS.toolPulseMs;
    const pulseY = pulseProgress >= 0 && pulseProgress <= 1 ? -1.2 + pulseProgress * 2.4 : null;
    const flash = Math.max(0, 1 - (now - this.flashStart) / FLASH_MS);
    const seconds = now / 1000;
    const breath = 1 + 0.025 * Math.sin(seconds * Math.PI * 0.5);

    const projected = this.points.map((point) => {
      const x = point.x * cosY + point.z * sinY;
      const z1 = -point.x * sinY + point.z * cosY;
      const y = point.y * cosTilt - z1 * sinTilt;
      const z = point.y * sinTilt + z1 * cosTilt;
      const ripple = 1 - ORB_SETTINGS.thinkingRipple * live.ripple * (0.5 + 0.5 * Math.sin(point.y * 7 + seconds * 5));
      const scale = radius * breath * ripple * (PERSPECTIVE / (PERSPECTIVE - z));
      const highlight =
        pulseY === null ? flash : Math.max(flash, Math.exp(-(((y - pulseY) / 0.16) ** 2)));
      return { sx: center + x * scale, sy: center + y * scale, depth: (z + 1) / 2, highlight, character: point.character, z };
    });
    projected.sort((a, b) => a.z - b.z);

    context.textAlign = "center";
    context.textBaseline = "middle";
    let fontBucket = 0;
    for (const item of projected) {
      let color = mix(palette.redDim, palette.red, item.depth);
      if (item.depth > 0.85) color = mix(color, palette.redText, ((item.depth - 0.85) / 0.15) * 0.6);
      if (item.highlight > 0) color = mix(color, HOT_WHITE, item.highlight);
      if (live.grey > 0) color = mix(color, palette.grey, live.grey);
      const alpha = Math.min(1, depthAlpha(item.depth) + item.highlight * 0.5);
      context.fillStyle = `rgb(${color[0] | 0} ${color[1] | 0} ${color[2] | 0} / ${alpha})`;

      if (this.dots) {
        const side = Math.max(0.8, cssSize * 0.035 * (0.5 + 0.6 * item.depth));
        context.fillRect(item.sx - side / 2, item.sy - side / 2, side, side);
      } else {
        const bucket = Math.round((this.glyphPx * (0.55 + 0.55 * item.depth)) / FONT_STEP_PX) * FONT_STEP_PX;
        if (bucket !== fontBucket) {
          context.font = `500 ${bucket}px ${this.monoFamily}`;
          fontBucket = bucket;
        }
        context.fillText(item.character, item.sx, item.sy);
      }
    }
  }

  private paintGlow(center: number, radius: number) {
    const { context, palette, live, cssSize } = this;
    const strength = ORB_SETTINGS.coreGlow * live.glow * (1 - live.grey * 0.8);
    const gradient = context.createRadialGradient(center, center, 0, center, center, radius * 1.25);
    gradient.addColorStop(0, `rgb(${palette.red[0]} ${palette.red[1]} ${palette.red[2]} / ${0.55 * strength})`);
    gradient.addColorStop(1, `rgb(${palette.red[0]} ${palette.red[1]} ${palette.red[2]} / 0)`);
    context.fillStyle = gradient;
    context.fillRect(0, 0, cssSize, cssSize);
  }
}
