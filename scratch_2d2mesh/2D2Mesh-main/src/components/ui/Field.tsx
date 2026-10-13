import { forwardRef, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes, type SelectHTMLAttributes } from "react";
import { cn } from "../../lib/format";

const fieldClasses = cn(
  "w-full rounded-xl border border-white/12 bg-ink-800/70 px-3.5 py-2.5 text-sm text-slate-100",
  "placeholder:text-slate-500 transition-colors focus:border-brand-400/60 focus:outline-none focus:ring-2 focus:ring-brand-500/25",
);

function FieldShell({
  label,
  error,
  hint,
  children,
  id,
}: {
  label?: string;
  error?: string;
  hint?: string;
  children: ReactNode;
  id?: string;
}) {
  return (
    <div className="block space-y-1.5">
      {label && (
        <label htmlFor={id} className="block text-sm font-medium text-slate-300">
          {label}
        </label>
      )}
      {children}
      {hint && !error && <span className="block text-xs text-slate-500">{hint}</span>}
      {error && <span className="block text-xs text-red-400">{error}</span>}
    </div>
  );
}

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, label, error, hint, id, ...props },
  ref,
) {
  return (
    <FieldShell label={label} error={error} hint={hint} id={id}>
      <input id={id} ref={ref} className={cn(fieldClasses, error && "border-red-500/60 focus:ring-red-500/25", className)} {...props} />
    </FieldShell>
  );
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label?: string;
  error?: string;
  hint?: string;
}>(function Textarea({ className, label, error, hint, id, ...props }, ref) {
  return (
    <FieldShell label={label} error={error} hint={hint} id={id}>
      <textarea id={id} ref={ref} className={cn(fieldClasses, "min-h-[90px] resize-y", className)} {...props} />
    </FieldShell>
  );
});

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement> & {
  label?: string;
  error?: string;
  hint?: string;
}>(function Select({ className, label, error, hint, id, children, ...props }, ref) {
  return (
    <FieldShell label={label} error={error} hint={hint} id={id}>
      <select id={id} ref={ref} className={cn(fieldClasses, "cursor-pointer appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20fill%3D%22none%22%20viewBox%3D%220%200%2024%2024%22%20stroke%3D%22%2394a3b8%22%20stroke-width%3D%222%22%3E%3Cpath%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%20d%3D%22m6%209%206%206%206-6%22%2F%3E%3C%2Fsvg%3E')] bg-[right_0.6rem_center] bg-no-repeat bg-[length:1rem] pr-9 dark:[&>option]:bg-ink-800", className)} {...props}>
        {children}
      </select>
    </FieldShell>
  );
});
