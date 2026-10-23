import type { Metadata } from "next";

import { DemoStarter } from "@/components/marketing/DemoStarter";

export const metadata: Metadata = { title: "Demo", robots: { index: false, follow: false } };

export default function DemoPage() {
  return (
    <section aria-label="Demo" className="grid flex-1 content-start justify-items-start px-[max(16px,env(safe-area-inset-left,0px))] py-16 sm:mx-auto sm:w-full sm:max-w-[560px]">
      <DemoStarter />
    </section>
  );
}
