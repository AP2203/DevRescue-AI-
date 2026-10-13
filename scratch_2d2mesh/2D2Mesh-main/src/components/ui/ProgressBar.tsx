import { cn } from "../../lib/format";

export function ProgressBar({
  value,
  className,
  label,
  indeterminate = false,
  tone = "brand",
}: {
  value?: number;
  className?: string;
  label?: string;
  indeterminate?: boolean;
  tone?: "brand" | "success" | "danger";
}) {
  const clamped = Math.max(0, Math.min(100, value ?? 0));
  const fill =
    tone === "success"
      ? "bg-gradient-to-r from-emerald-500 to-teal-400 shadow-[0_0_12px_rgba(16,185,129,0.5)]"
      : tone === "danger"
        ? "bg-gradient-to-r from-red-500 to-rose-400 shadow-[0_0_12px_rgba(239,68,68,0.5)]"
        : "bg-brand-gradient shadow-[0_0_12px_rgba(139,92,246,0.5)]";

  return (
    <div className={cn("w-full", className)}>
      {label && (
        <div className="mb-1.5 flex items-center justify-between text-xs">
          <span className="font-medium text-slate-300">{label}</span>
          {!indeterminate && <span className="font-mono text-slate-400">{Math.round(clamped)}%</span>}
        </div>
      )}
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-white/8"
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        {indeterminate ? (
          <div className="h-full w-1/2 animate-[shimmer_1.2s_infinite_linear] rounded-full bg-brand-gradient" />
        ) : (
          <div
            className={cn("h-full rounded-full transition-all duration-500 ease-out", fill)}
            style={{ width: `${clamped}%` }}
          />
        )}
      </div>
    </div>
  );
}
