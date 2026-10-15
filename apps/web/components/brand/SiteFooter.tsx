import Link from "next/link";
import type { ReactNode } from "react";

import { LEAGUE_DISCLAIMER } from "@/lib/brand";

import { LeagueMark } from "./LeagueMark";

const FOOTER_LINKS = [
  { href: "/how-its-built", label: "How it's built" },
  { href: "/track-record", label: "Track record" },
  { href: "/legal/terms", label: "Terms" },
  { href: "/legal/privacy", label: "Privacy" },
  { href: "/legal/refunds", label: "Refunds" },
] as const;

const REPO_URL = "https://github.com/egeyesss/BundesPredict";

export function SiteFooter({ wordmark }: { wordmark: ReactNode }) {
  return (
    <footer className="border-t border-bp-border px-[max(16px,env(safe-area-inset-left))]">
      <div className="mx-auto grid max-w-[1160px] gap-5 pt-10 pb-[calc(40px+env(safe-area-inset-bottom,0px))]">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <Link href="/" aria-label="BundesPredict home" className="rounded-md">
            {wordmark}
          </Link>
          <nav aria-label="Footer" className="flex flex-wrap gap-x-[18px] gap-y-2 text-sm text-bp-text-muted">
            {FOOTER_LINKS.map(({ href, label }) => (
              <Link key={href} href={href} className="hover:text-bp-text">
                {label}
              </Link>
            ))}
            <a href={REPO_URL} className="hover:text-bp-text">
              GitHub
            </a>
          </nav>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
          <LeagueMark placement="footer" />
          <p className="max-w-[90ch] flex-1 basis-80 text-[13px] leading-relaxed text-bp-text-muted">
            {LEAGUE_DISCLAIMER}
          </p>
        </div>
        <p className="text-[13px] text-bp-text-muted">
          FAQ and code input by{" "}
          <a href="https://www.rareui.com" className="underline underline-offset-4 hover:text-bp-text">
            Rare UI
          </a>
        </p>
      </div>
    </footer>
  );
}
