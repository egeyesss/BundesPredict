import { cn } from "cn"

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("animate-shimmer rounded-md bg-linear-to-r from-bp-surface-2 via-bp-border to-bp-surface-2 bg-[length:240%_100%] motion-reduce:animate-none", className)}
      {...props}
    />
  )
}

export { Skeleton }
