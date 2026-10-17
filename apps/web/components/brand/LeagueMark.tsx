import { cn } from "@/lib/utils";

/**
 * The only places the Bundesliga logo may appear. It names the competition
 * the data covers and never sits beside or inside the BundesPredict wordmark,
 * in a favicon, an OG image or an app icon, and is never recoloured, animated
 * or cropped. The asset is near-black, so it sits on a white plate instead of
 * being inverted.
 */
export type LeagueMarkPlacement = "matchday-header" | "coverage" | "footer";

type LeagueMarkProps = {
  placement: LeagueMarkPlacement;
  size?: 48 | 64;
  className?: string;
};

export function LeagueMark({ placement, size = 48, className }: LeagueMarkProps) {
  return (
    <span
      data-testid="league-mark"
      data-placement={placement}
      className={cn("inline-flex shrink-0 items-center rounded-md bg-white p-1", className)}
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- the official SVG is served unmodified */}
      <img
        src="/crests/league/bundesliga.svg"
        alt="Bundesliga"
        width={size}
        height={size}
        style={{ width: size, height: size }}
      />
    </span>
  );
}
