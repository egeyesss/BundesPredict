import { Skeleton } from "@/components/ui/skeleton";

/** Same grid as the account page, so the cards do not jump when the data arrives. */
export function AccountSkeleton() {
  return (
    <div role="status" aria-busy="true" aria-label="Loading account" className="mx-auto grid w-full max-w-[860px] gap-4 px-4 pt-8 pb-16">
      <div className="grid gap-2">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-11 w-56" />
        <Skeleton className="h-4 w-48" />
      </div>
      <div className="grid gap-4 min-[760px]:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <Skeleton className="h-[290px] rounded-[14px]" />
        <Skeleton className="h-[190px] rounded-[14px]" />
      </div>
      <div className="grid gap-4 min-[760px]:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <Skeleton className="h-[170px] rounded-[14px]" />
        <Skeleton className="h-[170px] rounded-[14px]" />
      </div>
    </div>
  );
}
