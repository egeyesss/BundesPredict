import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function DataTable({ head, children, label }: { head: string[]; children: ReactNode; label: string }) {
  return (
    <div className="overflow-x-auto">
      <table aria-label={label} className="w-full border-collapse text-[13px] tabular-nums">
        <thead>
          <tr>
            {head.map((column) => (
              <th key={column} scope="col" className="border-b border-bp-border py-1.5 pr-2.5 pb-2 text-left font-mono text-[11px] font-medium tracking-[0.06em] whitespace-nowrap text-[#71717A] uppercase">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export function Cell({ children, mono, className }: { children: ReactNode; mono?: boolean; className?: string }) {
  return (
    <td className={cn("border-b border-bp-border py-2.5 pr-2.5 align-top group-last:border-b-0", mono && "font-mono text-xs whitespace-nowrap text-bp-text-muted", className)}>
      {children}
    </td>
  );
}
