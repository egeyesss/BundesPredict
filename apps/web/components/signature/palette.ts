export type Rgb = readonly [number, number, number];

export type Palette = {
  red: Rgb;
  redText: Rgb;
  redDim: Rgb;
  text: Rgb;
  grey: Rgb;
};

/** Mirrors tokens.css; used when the variables cannot be read (tests, first paint without CSS). */
export const DEFAULT_PALETTE: Palette = {
  red: [210, 5, 21],
  redText: [255, 77, 90],
  redDim: [92, 2, 9],
  text: [244, 244, 245],
  grey: [113, 113, 122],
};

const TOKENS: Record<keyof Palette, string> = {
  red: "--bp-red",
  redText: "--bp-red-text",
  redDim: "--bp-red-dim",
  text: "--bp-text",
  grey: "--odds-draw",
};

export function parseColor(value: string): Rgb | null {
  const text = value.trim();
  const hex = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(text);
  if (hex) {
    const digits = hex[1].length === 3 ? [...hex[1]].map((digit) => digit + digit).join("") : hex[1];
    return [0, 2, 4].map((offset) => parseInt(digits.slice(offset, offset + 2), 16)) as unknown as Rgb;
  }
  const rgb = /^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)/i.exec(text);
  return rgb ? [Number(rgb[1]), Number(rgb[2]), Number(rgb[3])] : null;
}

export function readPalette(element: Element): Palette {
  const style = getComputedStyle(element);
  const read = (key: keyof Palette) => parseColor(style.getPropertyValue(TOKENS[key])) ?? DEFAULT_PALETTE[key];
  return { red: read("red"), redText: read("redText"), redDim: read("redDim"), text: read("text"), grey: read("grey") };
}

export const rgb = ([red, green, blue]: Rgb, alpha = 1) =>
  alpha === 1 ? `rgb(${red} ${green} ${blue})` : `rgb(${red} ${green} ${blue} / ${alpha})`;
