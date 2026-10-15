"use client";

import { useState } from "react";

import { clubColors, crestUrl, type CrestSize } from "@/lib/brand";
import { cn } from "@/lib/utils";

export type CrestTeam = {
  name: string;
  code: string;
  /** `null` means the API has no asset for this club; `undefined` looks it up in the manifest. */
  crest?: string | null;
};

type ClubCrestProps = {
  team: CrestTeam;
  size: CrestSize;
  className?: string;
};

export function ClubCrest({ team, size, className }: ClubCrestProps) {
  const src = team.crest === undefined ? crestUrl(team.code) : team.crest;
  const [failedSrc, setFailedSrc] = useState<string | null>(null);

  if (!src || failedSrc === src) {
    return <KitChip team={team} size={size} className={className} />;
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element -- SVG crests gain nothing from the image optimizer
    <img
      src={src}
      alt={team.name}
      width={size}
      height={size}
      onError={() => setFailedSrc(src)}
      className={cn("shrink-0 object-contain", className)}
      style={{ width: size, height: size }}
    />
  );
}

function KitChip({ team, size, className }: ClubCrestProps) {
  const { primary, secondary } = clubColors(team.code);

  return (
    <span
      role="img"
      aria-label={team.name}
      data-fallback="chip"
      className={cn(
        "grid shrink-0 place-items-center rounded-[22%] bg-[linear-gradient(135deg,var(--chip-primary)_0_50%,var(--chip-secondary)_50%_100%)] font-display font-bold text-white shadow-[inset_0_0_0_1px_rgb(255_255_255/0.14)] [text-shadow:0_1px_2px_rgb(0_0_0/0.7)]",
        className,
      )}
      style={
        {
          width: size,
          height: size,
          fontSize: Math.max(7, size * 0.36),
          "--chip-primary": primary,
          "--chip-secondary": secondary,
        } as React.CSSProperties
      }
    >
      {size >= 32 ? team.code : team.code.charAt(0)}
    </span>
  );
}
