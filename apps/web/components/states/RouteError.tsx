"use client";

import { TriangleAlert } from "lucide-react";
import Link from "next/link";

import { StateMessage } from "@/components/states/StateMessage";
import { Button } from "@/components/ui/button";

/** The error boundary body for pages that load the signed-in user: name what broke and offer a retry. */
export function RouteError({ title, reset }: { title: string; reset: () => void }) {
  return (
    <div className="mx-auto w-full max-w-[860px] px-4 pt-10 pb-16">
      <StateMessage
        tone="crit"
        icon={<TriangleAlert className="size-4" />}
        title={title}
        actions={
          <>
            <Button onClick={reset}>Try again</Button>
            <Button asChild variant="secondary">
              <Link href="/matchday">Back to the matchday</Link>
            </Button>
          </>
        }
      >
        The connection to our server failed, so we couldn&apos;t check your session. Your chats and account are safe.
      </StateMessage>
    </div>
  );
}
