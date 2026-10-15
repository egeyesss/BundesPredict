import { cn } from "@/lib/utils";

type WordmarkPlaceholderProps = {
  size?: "nav" | "hero";
  className?: string;
};

/** Static stand-in with the same props as the animated Wordmark that replaces it. */
export function WordmarkPlaceholder({ size = "nav", className }: WordmarkPlaceholderProps) {
  return (
    <span
      className={cn(
        "inline-block font-display leading-none font-bold whitespace-nowrap",
        size === "nav" ? "text-[20px]" : "text-[clamp(56px,12.5vw,140px)]",
        className,
      )}
    >
      <span className="text-bp-text">Bundes</span>
      <span className="text-bp-red">Predict</span>
    </span>
  );
}
