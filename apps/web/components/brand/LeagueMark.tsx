import { cn } from "@/lib/utils";

/**
 * The only places the Bundesliga wordmark may appear. It names the competition
 * the data covers and never sits beside or inside the BundesPredict wordmark,
 * in a favicon, an OG image or an app icon, and is never recoloured, animated
 * or cropped. The asset is near-black, so it sits on a white plate instead of
 * being inverted.
 */
export type LeagueMarkPlacement = "matchday-header" | "coverage" | "footer";

type LeagueMarkProps = {
  placement: LeagueMarkPlacement;
  size?: 24 | 32;
  className?: string;
};

const ASPECT_RATIO = 404 / 48.51;

export function LeagueMark({ placement, size = 24, className }: LeagueMarkProps) {
  return (
    <span
      data-testid="league-mark"
      data-placement={placement}
      className={cn("inline-flex max-w-full items-center rounded-md bg-white px-2.5 py-1.5", className)}
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- the official SVG is served unmodified */}
      <img
        src="/crests/league/bundesliga.svg"
        alt="Bundesliga"
        width={Math.round(size * ASPECT_RATIO)}
        height={size}
        className="h-auto w-auto max-w-full"
        style={{ height: size }}
      />
    </span>
  );
}
