import { useEffect, useRef, useState } from "react";

const SERVER_WIDTH = 640;

/** The element's content width, so SVG text keeps its pixel size on a phone instead of scaling down. */
export function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(SERVER_WIDTH);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    setWidth(node.clientWidth || SERVER_WIDTH);
    const observer = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width) || SERVER_WIDTH));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return [ref, width] as const;
}
