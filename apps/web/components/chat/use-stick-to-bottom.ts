"use client";

import { useEffect, useRef, type RefObject } from "react";

const NEAR_BOTTOM_PX = 80;

/** Keeps a scrolling log pinned to its newest content, unless the reader has scrolled up. */
export function useStickToBottom(log: RefObject<HTMLElement | null>, content: RefObject<HTMLElement | null>) {
  const stuck = useRef(true);

  useEffect(() => {
    const scroller = log.current;
    const inner = content.current;
    if (!scroller || !inner) return;

    const onScroll = () => {
      stuck.current = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < NEAR_BOTTOM_PX;
    };
    const follow = new ResizeObserver(() => {
      if (stuck.current) scroller.scrollTop = scroller.scrollHeight;
    });
    scroller.addEventListener("scroll", onScroll, { passive: true });
    follow.observe(inner);
    return () => {
      scroller.removeEventListener("scroll", onScroll);
      follow.disconnect();
    };
  }, [log, content]);
}
