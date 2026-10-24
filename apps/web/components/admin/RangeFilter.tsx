import Link from "next/link";

import { RANGES, type Range } from "@/lib/admin/load";
import { cn } from "@/lib/utils";

export function RangeFilter({ selected }: { selected: Range }) {
  return (
    <nav aria-label="Range" className="inline-flex gap-0.5 rounded-full border border-bp-border bg-bp-surface-1 p-[3px]">
      {RANGES.map((range) => (
        <Link
          key={range}
          href={`/admin?days=${range}`}
          scroll={false}
          aria-current={range === selected ? "page" : undefined}
          className={cn(
            "rounded-full px-3.5 py-1.5 text-[13px] whitespace-nowrap focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-bp-red-text",
            range === selected ? "bg-bp-text font-semibold text-bp-bg" : "text-bp-text-muted hover:text-bp-text",
          )}
        >
          {range} days
        </Link>
      ))}
    </nav>
  );
}
