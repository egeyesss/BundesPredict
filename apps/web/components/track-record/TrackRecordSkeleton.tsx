import { Skeleton } from "@/components/ui/skeleton";

/** Same grid as the page: header, four tiles, one chart card. */
export function TrackRecordSkeleton() {
  return (
    <div role="status" aria-busy="true" aria-label="Loading the track record" className="mx-auto grid w-full max-w-[1160px] gap-7 px-[max(16px,env(safe-area-inset-left))] pt-10 pb-20">
      <div className="grid gap-4">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-16 w-[min(100%,520px)]" />
        <Skeleton className="h-5 w-[min(100%,560px)]" />
      </div>
      <Skeleton className="h-11 w-72 rounded-full" />
      <div className="grid grid-cols-4 gap-3 max-[900px]:grid-cols-2 max-[480px]:grid-cols-1">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-[112px] rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-[400px] rounded-xl" />
    </div>
  );
}
