import { useToast } from "../../hooks/useToast";
import { cn } from "../../lib/format";
import { Icon } from "./Icon";

const toneStyles: Record<string, string> = {
  success: "border-emerald-500/40 text-emerald-300",
  error: "border-red-500/40 text-red-300",
  warning: "border-amber-500/40 text-amber-300",
  info: "border-brand-500/40 text-brand-300",
};

const icons: Record<string, "check" | "close" | "alert" | "info"> = {
  success: "check",
  error: "close",
  warning: "alert",
  info: "info",
};

export function Toaster() {
  const { toasts, dismiss } = useToast();

  return (
    <div className="pointer-events-none fixed inset-x-0 top-4 z-[60] flex flex-col items-center gap-2 px-4 sm:items-end sm:pr-6">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={cn(
            "pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl glass-strong p-4 shadow-card animate-slide-up",
            toneStyles[toast.type],
          )}
          role="status"
        >
          <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-current/10">
            <Icon name={icons[toast.type]} className="h-4 w-4" strokeWidth={2.2} />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-white">{toast.title}</p>
            {toast.description && <p className="mt-0.5 text-xs text-slate-400">{toast.description}</p>}
            {toast.action && (
              <button
                type="button"
                onClick={() => {
                  toast.action?.onClick();
                  dismiss(toast.id);
                }}
                className="mt-2 text-xs font-semibold text-brand-300 hover:underline"
              >
                {toast.action.label}
              </button>
            )}
          </div>
          <button
            type="button"
            onClick={() => dismiss(toast.id)}
            aria-label="Dismiss"
            className="shrink-0 rounded-lg p-1 text-slate-400 transition-colors hover:bg-white/5 hover:text-white"
          >
            <Icon name="close" className="h-4 w-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
