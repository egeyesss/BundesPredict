import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Card({ className, ...props }: ComponentProps<"section">) {
  return <section className={cn("grid min-w-0 gap-3.5 rounded-[14px] border border-bp-border bg-bp-surface-1 p-5", className)} {...props} />;
}

export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cn("font-mono text-xs tracking-[0.08em] text-bp-text-muted uppercase", className)}>{children}</span>;
}
