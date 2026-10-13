import type { ReactNode } from "react";
import { cn } from "../../lib/format";

const toneClasses = {
  success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
  error: "border-red-500/30 bg-red-500/10 text-red-200",
  warning: "border-amber-500/30 bg-amber-500/10 text-amber-200",
  info: "border-brand-500/30 bg-brand-500/10 text-brand-200",
};

export function Alert({
  tone = "info",
  title,
  children,
  className,
  icon,
}: {
  tone?: keyof typeof toneClasses;
  title?: string;
  children?: ReactNode;
  className?: string;
  icon?: ReactNode;
}) {
  return (
    <div className={cn("rounded-xl border p-4 text-sm backdrop-blur-xl", toneClasses[tone], className)} role="alert">
      <div className="flex items-start gap-3">
        {icon && <span className="mt-0.5 shrink-0">{icon}</span>}
        <div className="space-y-1">
          {title && <p className="font-semibold">{title}</p>}
          {children && <div className="opacity-90">{children}</div>}
        </div>
      </div>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-white/15 py-16 text-center">
      {icon && (
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/5 text-3xl">
          {icon}
        </div>
      )}
      <h3 className="font-display text-base font-semibold text-white">{title}</h3>
      {description && <p className="max-w-sm text-sm text-slate-400">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  description,
  onRetry,
  className,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <Alert
      tone="error"
      title={title}
      className={className}
      icon={
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
        </svg>
      }
    >
      <div className="space-y-3">
        {description && <p>{description}</p>}
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-700"
          >
            Retry
          </button>
        )}
      </div>
    </Alert>
  );
}
