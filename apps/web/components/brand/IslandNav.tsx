"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Fragment,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type FocusEvent,
  type MouseEvent,
  type ReactNode,
} from "react";

import { toast } from "sonner";

import { useBillingRedirect } from "@/components/account/useBillingRedirect";
import { useSignOut } from "@/components/account/useSignOut";
import { SurfaceActive } from "@/components/signature/SurfaceActive";
import { Button } from "@/components/ui/button";
import { COMPACT_SCROLL_THRESHOLD, MOBILE_BREAKPOINT, isCurrentSection, islandMode, sectionLabel, type IslandMode } from "@/lib/island";
import { springEasing } from "@/lib/spring";
import { cn } from "@/lib/utils";

import { AccountMenu } from "./AccountMenu";
import { useIslandActivity } from "./IslandActivity";
import { ACCOUNT_LINK, NAV_LINKS, displayName, quotaSummary, type NavLink, type NavUser } from "./nav";
import { PlanPill } from "./PlanPill";

type IslandNavProps = {
  /** Rendered in every layer; the animated wordmark replaces the placeholder here. */
  wordmark: ReactNode;
  user: NavUser | null;
  /** True until the session answers, so a signed-in visitor never sees the signed-out buttons flash. */
  authPending?: boolean;
  links?: readonly NavLink[];
  /** Renders inline in a fixed mode instead of fixed to the viewport, for the styleguide. */
  preview?: { mode: IslandMode; label: string };
};

const LAYER_ORDER: readonly IslandMode[] = ["full", "compact", "mobile", "open"];
const HOVER_COLLAPSE_DELAY_MS = 180;

function subscribeViewport(onChange: () => void) {
  window.addEventListener("scroll", onChange, { passive: true });
  window.addEventListener("resize", onChange);
  return () => {
    window.removeEventListener("scroll", onChange);
    window.removeEventListener("resize", onChange);
  };
}

const readWidth = () => window.innerWidth;
const readScrolled = () => window.scrollY >= COMPACT_SCROLL_THRESHOLD;
const serverWidth = () => null;
const serverScrolled = () => false;

function isKeyboardFocus(element: Element): boolean {
  try {
    return element.matches(":focus-visible");
  } catch {
    return true;
  }
}

export function IslandNav({ wordmark, user, authPending = false, links = NAV_LINKS, preview }: IslandNavProps) {
  const pathname = usePathname();
  const billing = useBillingRedirect({ onError: (message) => toast.error(message) });
  const { signOut } = useSignOut({ onError: (message) => toast.error(message) });
  const { agentCaption, sectionName } = useIslandActivity();

  const width = useSyncExternalStore(subscribeViewport, readWidth, serverWidth);
  const scrolled = useSyncExternalStore(subscribeViewport, readScrolled, serverScrolled);
  const [hover, setHover] = useState(false);
  const [focus, setFocus] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [size, setSize] = useState<{ width: number; height: number } | null>(null);

  const islandRef = useRef<HTMLDivElement>(null);
  const layerRefs = useRef<Partial<Record<IslandMode, HTMLDivElement | null>>>({});
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const collapseTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const restoreMenuFocus = useRef(false);
  const pendingFocusKey = useRef<string | null>(null);

  if (menuOpen && width !== null && width >= MOBILE_BREAKPOINT) setMenuOpen(false);

  const ready = preview !== undefined || width !== null;
  const mode: IslandMode =
    preview?.mode ??
    (width === null
      ? "full"
      : islandMode({ width, scrollY: scrolled ? COMPACT_SCROLL_THRESHOLD : 0, hover, focus, menuOpen }));

  const closeMenu = useCallback((returnFocus: boolean) => {
    restoreMenuFocus.current = returnFocus;
    setMenuOpen(false);
  }, []);

  useEffect(() => {
    if (!CSS.supports("transition-timing-function", "linear(0, 1)")) return;
    const { css, ms } = springEasing(0.25, 0.42);
    const root = document.documentElement.style;
    root.setProperty("--island-spring", css);
    root.setProperty("--island-spring-duration", `${ms}ms`);
  }, []);

  useLayoutEffect(() => {
    const layer = layerRefs.current[mode];
    const island = islandRef.current;
    if (!layer || !island) return;

    const measure = () => {
      setSize((previous) =>
        previous?.width === layer.offsetWidth && previous.height === layer.offsetHeight
          ? previous
          : { width: layer.offsetWidth, height: layer.offsetHeight },
      );
      island.scrollLeft = 0;
      island.scrollTop = 0;
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(layer);
    return () => observer.disconnect();
  }, [mode]);

  // Expanding on keyboard focus swaps layers, and the focused element's old layer goes inert,
  // so focus is carried over to the same control in the layer that just turned on.
  useLayoutEffect(() => {
    const key = pendingFocusKey.current;
    if (!key) return;
    pendingFocusKey.current = null;
    layerRefs.current[mode]
      ?.querySelector<HTMLElement>(`[data-focus-key="${key}"]`)
      ?.focus({ preventScroll: true });
  }, [mode]);

  useEffect(() => {
    if (menuOpen) {
      closeButtonRef.current?.focus({ preventScroll: true });
    } else if (restoreMenuFocus.current) {
      restoreMenuFocus.current = false;
      menuButtonRef.current?.focus({ preventScroll: true });
    }
  }, [menuOpen]);

  useEffect(() => {
    if (!menuOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeMenu(true);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [menuOpen, closeMenu]);

  useEffect(() => () => clearTimeout(collapseTimer.current), []);

  const handleHomeClick = (event: MouseEvent<HTMLAnchorElement>) => {
    closeMenu(false);
    if (pathname !== "/") return;
    event.preventDefault();
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" });
  };

  const handleFocus = (event: FocusEvent<HTMLElement>) => {
    if (!isKeyboardFocus(event.target)) return;
    const key = event.target.closest<HTMLElement>("[data-focus-key]")?.dataset.focusKey ?? null;
    pendingFocusKey.current = mode === "compact" ? key : null;
    setFocus(true);
  };

  const handleBlur = (event: FocusEvent<HTMLElement>) => {
    if (pendingFocusKey.current) return;
    if (!event.currentTarget.contains(event.relatedTarget)) setFocus(false);
  };

  const Root = preview ? "div" : "nav";
  const label = sectionName ?? sectionLabel(pathname);
  const logo = (
    <Link href="/" aria-label="BundesPredict home" className="isl-logo" data-focus-key="logo" onClick={handleHomeClick}>
      {wordmark}
    </Link>
  );
  const live = (
    <span className="isl-live" aria-live="polite">
      {agentCaption ? (
        <>
          <span className="isl-orb" aria-hidden="true" />
          <span>Agent · {agentCaption}</span>
        </>
      ) : (
        <>
          <span className="isl-live-dot" aria-hidden="true" />
          <span>{label}</span>
        </>
      )}
    </span>
  );
  const pageLinks = user && mode === "open" ? [...links, ACCOUNT_LINK] : links;

  const layer = (id: IslandMode, className: string, children: ReactNode) => (
    <div
      key={id}
      ref={(element) => {
        layerRefs.current[id] = element;
      }}
      data-layer={id}
      className={cn("island-layer", className, mode === id && "is-on")}
      inert={mode !== id}
      aria-hidden={mode !== id}
    >
      <SurfaceActive active={mode === id}>{children}</SurfaceActive>
    </div>
  );

  const layers: Record<IslandMode, ReactNode> = {
    full: layer(
      "full",
      "island-layer-full",
      <>
        {logo}
        <span className="isl-div" />
        <div className="isl-links">
          {links.map((link, index) => (
            <Fragment key={link.href}>
              {index > 0 && <span className="isl-div" />}
              <Link href={link.href} aria-current={isCurrentSection(pathname, link.href) ? "page" : undefined}>
                {link.label}
              </Link>
            </Fragment>
          ))}
        </div>
        {user ? (
          <div className="isl-account">
            <PlanPill plan={user.plan} />
            <AccountMenu user={user} />
          </div>
        ) : (
          <div className="isl-actions">
            <Link className="isl-signin" href="/login">
              Sign in
            </Link>
            <Link className="isl-cta" href="/demo" data-focus-key="cta">
              Try the demo
            </Link>
          </div>
        )}
      </>,
    ),
    compact: layer(
      "compact",
      "island-layer-compact",
      <>
        {logo}
        <span className="isl-div" />
        {live}
        {user ? (
          <AccountMenu user={user} />
        ) : (
          <Link className="isl-cta" href="/demo" data-focus-key="cta">
            Try the demo
          </Link>
        )}
      </>,
    ),
    mobile: layer(
      "mobile",
      "island-layer-mobile",
      <>
        {logo}
        {live}
        <button
          ref={menuButtonRef}
          type="button"
          className="burger"
          aria-label="Open menu"
          aria-expanded={mode === "open"}
          onClick={() => setMenuOpen(true)}
        >
          <i />
          <i />
          <i />
        </button>
      </>,
    ),
    open: layer(
      "open",
      "island-layer-open",
      <>
        <div className="menu-top">
          {logo}
          <button
            ref={closeButtonRef}
            type="button"
            className="burger burger-close"
            aria-label="Close menu"
            onClick={() => closeMenu(true)}
          >
            ✕
          </button>
        </div>
        {user && <MenuAccountCard user={user} />}
        <div className="menu-links">
          {pageLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={isCurrentSection(pathname, link.href) ? "page" : undefined}
              onClick={() => closeMenu(false)}
            >
              {link.label}
              {user && link.hint && <small>{link.hint}</small>}
            </Link>
          ))}
        </div>
        <div className="menu-actions">
          {user ? (
            <>
              <Button
                variant={user.plan === "free" ? "default" : "secondary"}
                size="lg"
                disabled={billing.pending !== null}
                onClick={() => void billing.start(user.plan === "free" ? "checkout" : "portal")}
              >
                {user.plan === "free" ? "Upgrade to Pro" : "Manage billing"}
              </Button>
              <Button variant="secondary" size="lg" onClick={() => void signOut()}>
                Sign out
              </Button>
            </>
          ) : (
            <>
              <Button asChild variant="secondary" size="lg">
                <Link href="/login" onClick={() => closeMenu(false)}>
                  Sign in
                </Link>
              </Button>
              <Button asChild size="lg">
                <Link href="/demo" onClick={() => closeMenu(false)}>
                  Try the demo
                </Link>
              </Button>
            </>
          )}
        </div>
      </>,
    ),
  };

  return (
    <>
      <div data-island-wrap className="island-wrap" data-preview={preview ? "true" : undefined}>
        <Root
          ref={islandRef}
          className="island"
          role={preview ? "group" : undefined}
          aria-label={preview ? preview.label : "Main"}
          data-mode={mode}
          data-ready={ready}
          data-auth={authPending ? "pending" : undefined}
          style={size ? { width: size.width, height: size.height } : undefined}
          onMouseEnter={() => {
            clearTimeout(collapseTimer.current);
            setHover(true);
          }}
          onMouseLeave={() => {
            collapseTimer.current = setTimeout(() => setHover(false), HOVER_COLLAPSE_DELAY_MS);
          }}
          onFocus={handleFocus}
          onBlur={handleBlur}
        >
          {LAYER_ORDER.map((id) => layers[id])}
        </Root>
      </div>
      {preview === undefined && (
        <div data-island-scrim className="island-scrim" hidden={mode !== "open"} onClick={() => closeMenu(true)} />
      )}
    </>
  );
}

function MenuAccountCard({ user }: { user: NavUser }) {
  const name = displayName(user);
  const pips = user.plan === "pro" ? 0 : user.chatsLimit;

  return (
    <div className="menu-who">
      <span className="grid size-10 place-items-center rounded-full bg-bp-surface-2 text-[15px] font-semibold">
        {name.charAt(0).toUpperCase()}
      </span>
      <span className="min-w-0">
        <span className="menu-who-name">{name}</span>
        <span className="menu-who-email">{user.email}</span>
      </span>
      <PlanPill plan={user.plan} />
      <span className="menu-quota">
        {pips > 0 && (
          <span className="menu-pips" aria-hidden="true">
            {Array.from({ length: pips }, (_, index) => (
              <i key={index} className={index < user.chatsUsed ? "used" : undefined} />
            ))}
          </span>
        )}
        <span>{quotaSummary(user)}</span>
      </span>
    </div>
  );
}
