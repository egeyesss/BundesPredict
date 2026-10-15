import manifest from "@/public/crests/manifest.json";

export type CrestSize = 20 | 32 | 48 | 96;

export type CrestManifestEntry = {
  name: string;
  file: string;
  primary: string;
  secondary: string;
  dark: boolean;
  source: string;
};

export type ChipColors = { primary: string; secondary: string };

export const crestManifest: Record<string, CrestManifestEntry> = manifest;

export const DEFAULT_CHIP_COLORS: ChipColors = { primary: "#3F3F46", secondary: "#A1A1AA" };

export function crestUrl(code: string): string | null {
  const entry = crestManifest[code];
  return entry ? `/crests/${entry.file}` : null;
}

export function clubColors(code: string): ChipColors {
  const entry = crestManifest[code];
  return entry ? { primary: entry.primary, secondary: entry.secondary } : DEFAULT_CHIP_COLORS;
}

export const LEAGUE_DISCLAIMER =
  "BundesPredict is an independent project. It is not affiliated with, endorsed by or sponsored by DFL Deutsche Fußball Liga or the Bundesliga. Club names and crests are trademarks of their respective owners. Not betting advice.";
