import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "../../lib/format";
import { Spinner } from "./Spinner";

type Variant = "primary" | "secondary" | "outline" | "ghost" | "danger" | "success";
type Size = "xs" | "sm" | "md" | "lg";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  fullWidth?: boolean;
};

const variants: Record<Variant, string> = {
  primary:
    "bg-brand-gradient text-white shadow-glow hover:shadow-glow-lg hover:brightness-110 focus-visible:ring-brand-400 border border-white/10",
  secondary:
    "bg-slate-100 text-slate-800 hover:bg-slate-200 border border-slate-200 focus-visible:ring-slate-400 dark:bg-white/8 dark:text-slate-100 dark:hover:bg-white/12 dark:border-white/10",
  outline:
    "border border-slate-300 text-slate-700 hover:border-brand-500/50 hover:bg-slate-50 hover:text-slate-900 focus-visible:ring-brand-500 dark:border-white/15 dark:text-slate-200 dark:hover:border-brand-400/40 dark:hover:bg-white/5 dark:hover:text-white dark:focus-visible:ring-brand-400 bg-transparent",
  ghost:
    "text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:ring-brand-500 dark:text-slate-400 dark:hover:bg-white/5 dark:hover:text-white dark:focus-visible:ring-brand-400",
  danger:
    "bg-gradient-to-b from-red-500 to-red-600 text-white shadow-[0_0_20px_-6px_rgba(239,68,68,0.6)] hover:brightness-110 focus-visible:ring-red-400 border border-red-400/20",
  success:
    "bg-gradient-to-b from-emerald-500 to-emerald-600 text-white shadow-[0_0_20px_-6px_rgba(16,185,129,0.6)] hover:brightness-110 focus-visible:ring-emerald-400 border border-emerald-400/20",
};

const sizes: Record<Size, string> = {
  xs: "px-2.5 py-1.5 text-xs",
  sm: "px-3 py-2 text-sm",
  md: "px-4 py-2.5 text-sm",
  lg: "px-6 py-3 text-base",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = "primary", size = "md", loading = false, disabled, fullWidth, children, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled ?? loading}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-all duration-200 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50",
        variants[variant],
        sizes[size],
        fullWidth && "w-full",
        className,
      )}
      {...props}
    >
      {loading && <Spinner size="sm" className="text-current" />}
      {children}
    </button>
  );
});
