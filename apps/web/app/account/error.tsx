"use client";

import { RouteError } from "@/components/states/RouteError";

export default function AccountError({ reset }: { error: Error; reset: () => void }) {
  return <RouteError title="Couldn't load your account" reset={reset} />;
}
