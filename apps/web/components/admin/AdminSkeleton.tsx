import { Skeleton } from "@/components/ui/skeleton";

/** Same grid as the dashboard, so nothing jumps when the numbers arrive. */
export function AdminSkeleton() {
  return (
    <div role="status" aria-busy="true" aria-label="Loading the dashboard" className="mx-auto grid w-full max-w-[1200px] gap-[18px] px-4 pt-8 pb-16">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="grid gap-2">
          <Skeleton className="h-3 w-10" />
          <Skeleton className="h-11 w-52" />
          <Skeleton className="h-4 w-64" />
        </div>
        <Skeleton className="h-10 w-60 rounded-full" />
      </div>
      <div className="grid grid-cols-2 gap-2.5 min-[561px]:grid-cols-3 min-[1081px]:grid-cols-6">
        {Array.from({ length: 6 }, (_, index) => (
          <Skeleton key={index} className="h-[98px] rounded-xl" />
        ))}
      </div>
      <div className="grid gap-3.5 min-[900px]:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Skeleton className="h-[380px] rounded-[14px]" />
        <Skeleton className="h-[380px] rounded-[14px]" />
      </div>
      <Skeleton className="h-[420px] rounded-[14px]" />
    </div>
  );
}
