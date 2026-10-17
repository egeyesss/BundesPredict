"use client";

import { RouteError } from "@/components/states/RouteError";

export default function ChatError({ reset }: { error: Error; reset: () => void }) {
  return <RouteError title="Couldn't open the chat" reset={reset} />;
}
