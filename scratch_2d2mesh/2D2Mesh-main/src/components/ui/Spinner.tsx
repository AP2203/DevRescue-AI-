import { cn } from "../../lib/format";

export function Spinner({
  size = "md",
  className,
}: {
  size?: "xs" | "sm" | "md" | "lg";
  className?: string;
}) {
  const sizes = {
    xs: "h-3 w-3 border-2",
    sm: "h-4 w-4 border-2",
    md: "h-6 w-6 border-[3px]",
    lg: "h-10 w-10 border-4",
  };
  return (
    <span
      role="status"
      aria-label="Loading"
      className={cn(
        "inline-block animate-spin rounded-full border-transparent border-t-current",
        sizes[size],
        className,
      )}
    />
  );
}
