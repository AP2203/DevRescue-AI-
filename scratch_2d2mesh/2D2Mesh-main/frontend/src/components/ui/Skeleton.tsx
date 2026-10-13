import type { ReactNode } from "react";
import { cn } from "../../lib/format";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "rounded-lg bg-gradient-to-r from-white/8 via-white/14 to-white/8 bg-[length:200%_100%]",
        "animate-shimmer",
        className,
      )}
    />
  );
}

type SkeletonListProps = {
  rows?: number;
  variant?: "card" | "line";
};

export function SkeletonList({ rows = 6, variant = "line" }: SkeletonListProps) {
  return (
    <div className="space-y-4">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className={variant === "card" ? "rounded-2xl border border-white/10 p-4" : ""}>
          <div className="flex items-center gap-4">
            {variant === "card" && <Skeleton className="h-16 w-16 rounded-xl" />}
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-3 w-2/3" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function LoadingView({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
      <div className="h-10 w-10 animate-spin rounded-full border-2 border-brand-500 border-t-transparent shadow-glow" />
      <p className="text-sm text-slate-400">{label}</p>
    </div>
  );
}

export type { ReactNode };
