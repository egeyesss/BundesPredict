import Link from "next/link";

import { Button } from "@/components/ui/button";
import { loginUrl } from "@/lib/auth/next-path";
import { cn } from "@/lib/utils";

import { Section, SectionHead } from "./Section";

type Plan = {
  name: string;
  price: string;
  period?: string;
  features: readonly string[];
  cta: { label: string; href: string; primary: boolean };
};

const PLANS: readonly Plan[] = [
  {
    name: "Free",
    price: "$0",
    features: ["Probabilities for every fixture", "3 agent chats a day", "Saved chat history", "Public track record"],
    cta: { label: "Start free", href: "/login", primary: false },
  },
  {
    name: "Pro",
    price: "$5",
    period: "CAD / month",
    features: ["Everything in Free", "100 agent chats a day (fair use)", "Matchday email every Thursday", "Cancel any time from your account"],
    cta: { label: "Go Pro", href: loginUrl("/account"), primary: true },
  },
];

export function Pricing() {
  return (
    <Section id="pricing" name="Pricing">
      <SectionHead id="pricing" eyebrow="Pricing" title="Free to look. Pro to talk all day." centered />
      <div className="mx-auto grid w-full max-w-[820px] gap-4 min-[701px]:grid-cols-2">
        {PLANS.map((plan) => (
          <div
            key={plan.name}
            className={cn(
              "grid content-start gap-4 rounded-xl border bg-bp-surface-1 p-6",
              plan.cta.primary ? "border-bp-text" : "border-bp-border",
            )}
          >
            <h3 className="m-0 font-display text-[22px] leading-[1.15] font-semibold tracking-[0.02em]">{plan.name}</h3>
            <div className="font-display text-[52px] leading-none font-bold">
              {plan.price}
              {plan.period && <small className="ml-2 font-sans text-base font-medium text-bp-text-muted">{plan.period}</small>}
            </div>
            <ul className="m-0 grid list-none gap-2.5 p-0 text-[15px] text-bp-text">
              {plan.features.map((feature) => (
                <li key={feature} className="grid grid-cols-[16px_minmax(0,1fr)] gap-2.5">
                  <span aria-hidden="true" className="text-bp-text-muted">
                    ✓
                  </span>
                  <span>{feature}</span>
                </li>
              ))}
            </ul>
            <Button asChild size="lg" variant={plan.cta.primary ? "default" : "secondary"}>
              <Link href={plan.cta.href}>{plan.cta.label}</Link>
            </Button>
          </div>
        ))}
      </div>
    </Section>
  );
}
