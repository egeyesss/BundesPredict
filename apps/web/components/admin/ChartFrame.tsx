"use client";

import { useId, useState, type ReactNode } from "react";

import { Card } from "@/components/account/AccountUi";

type ChartFrameProps = {
  title: string;
  description: string;
  legend?: ReactNode;
  table: ReactNode;
  children: ReactNode;
  /** Value for the `data-tour` anchor attribute. */
  tour?: string;
};

/** A titled card whose chart can be swapped for the same numbers as a table. */
export function ChartFrame({ title, description, legend, table, children, tour }: ChartFrameProps) {
  const [showTable, setShowTable] = useState(false);
  const tableId = useId();
  return (
    <Card data-tour={tour}>
      <div className="flex flex-wrap items-start justify-between gap-x-3.5 gap-y-2">
        <div className="grid min-w-0 flex-[1_1_240px] gap-1">
          <h3 className="font-display text-[19px] leading-[1.15] font-semibold tracking-[0.02em]">{title}</h3>
          <p className="text-[13px] text-bp-text-muted">{description}</p>
        </div>
        <button
          type="button"
          aria-expanded={showTable}
          aria-controls={tableId}
          onClick={() => setShowTable((open) => !open)}
          className="rounded-md border border-bp-border bg-bp-surface-2 px-2.5 py-1.5 font-mono text-[11px] font-medium whitespace-nowrap text-bp-text-muted hover:text-bp-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-bp-red-text"
        >
          {showTable ? "Hide table" : "Show as table"}
        </button>
      </div>
      {legend}
      <div id={tableId}>
        <div hidden={showTable}>{children}</div>
        <div hidden={!showTable} className="max-h-[320px] overflow-auto">
          {table}
        </div>
      </div>
    </Card>
  );
}
