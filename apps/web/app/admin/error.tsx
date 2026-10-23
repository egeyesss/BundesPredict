"use client";

import { RouteError } from "@/components/states/RouteError";

export default function AdminError({ reset }: { error: Error; reset: () => void }) {
  return <RouteError title="Couldn't load the dashboard" reset={reset} />;
}
