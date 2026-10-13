import type { ReactNode } from "react";
import { cn } from "../../lib/format";

type Tone = "gray" | "green" | "red" | "amber" | "blue" | "purple";

const tones: Record<Tone, string> = {
  gray: "bg-white/8 text-slate-300 border-white/10",
  green: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  red: "bg-red-500/15 text-red-300 border-red-500/30",
  amber: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  blue: "bg-accent-500/15 text-accent-300 border-accent-500/30",
  purple: "bg-brand-500/15 text-brand-300 border-brand-500/30",
};

export function Badge({
  tone = "gray",
  children,
  className,
  dot = false,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
  dot?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        tones[tone],
        className,
      )}
    >
      {dot && (
        <span
          className={cn(
            "glow-dot h-1.5 w-1.5",
            tone === "green" && "bg-emerald-400",
            tone === "red" && "bg-red-400",
            tone === "amber" && "bg-amber-400",
            tone === "blue" && "bg-accent-400",
            tone === "purple" && "bg-brand-400",
            tone === "gray" && "bg-slate-400",
          )}
        />
      )}
      {children}
    </span>
  );
}

export function jobStatusTone(status: string): Tone {
  switch (status) {
    case "succeeded":
      return "green";
    case "processing":
    case "queued":
      return "blue";
    case "failed":
      return "red";
    case "cancelled":
      return "amber";
    default:
      return "gray";
  }
}

export function projectStatusTone(status: string): Tone {
  switch (status) {
    case "ready":
      return "green";
    case "processing":
      return "blue";
    case "failed":
      return "red";
    default:
      return "gray";
  }
}
