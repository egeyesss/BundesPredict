import { MatchdaySkeleton } from "@/components/matchday/MatchdayStates";

export default function Loading() {
  return (
    <div className="mx-auto w-full max-w-[1120px] px-[max(16px,env(safe-area-inset-left))] pt-6 pb-12">
      <MatchdaySkeleton />
    </div>
  );
}
