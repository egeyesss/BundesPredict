export type IslandMode = "full" | "compact" | "mobile" | "open";

export const MOBILE_BREAKPOINT = 800;
export const COMPACT_SCROLL_THRESHOLD = 60;

type IslandModeInput = {
  width: number;
  scrollY: number;
  hover: boolean;
  focus: boolean;
  menuOpen: boolean;
};

export function islandMode({ width, scrollY, hover, focus, menuOpen }: IslandModeInput): IslandMode {
  if (width < MOBILE_BREAKPOINT) return menuOpen ? "open" : "mobile";
  return scrollY < COMPACT_SCROLL_THRESHOLD || hover || focus ? "full" : "compact";
}

const SECTIONS: ReadonlyArray<{ href: string; label: string }> = [
  { href: "/matchday", label: "Matchday" },
  { href: "/chat", label: "Chat" },
  { href: "/track-record", label: "Track record" },
  { href: "/account", label: "Account" },
  { href: "/login", label: "Sign in" },
  { href: "/how-its-built", label: "How it's built" },
  { href: "/legal", label: "Legal" },
  { href: "/styleguide", label: "Styleguide" },
];

function sectionFor(pathname: string) {
  return SECTIONS.find(({ href }) => pathname === href || pathname.startsWith(`${href}/`));
}

/** The page name the island's live activity shows when the agent is idle. */
export function sectionLabel(pathname: string): string {
  return sectionFor(pathname)?.label ?? "BundesPredict";
}

export function isCurrentSection(pathname: string, href: string): boolean {
  return sectionFor(pathname)?.href === href;
}
