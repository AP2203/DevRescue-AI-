import { cn } from "../../lib/format";

export function Pagination({
  page,
  pages,
  onChange,
  className,
}: {
  page: number;
  pages: number;
  onChange: (page: number) => void;
  className?: string;
}) {
  if (pages <= 1) return null;
  const siblings = 1;
  const start = Math.max(1, page - siblings);
  const end = Math.min(pages, page + siblings);
  const items: Array<number | "…"> = [];
  if (start > 1) items.push(1);
  if (start > 2) items.push("…");
  for (let p = start; p <= end; p++) items.push(p);
  if (end < pages - 1) items.push("…");
  if (end < pages) items.push(pages);

  return (
    <nav className={cn("flex items-center justify-center gap-1.5", className)} aria-label="Pagination">
      <PageButton disabled={page <= 1} onClick={() => onChange(page - 1)}>
        Prev
      </PageButton>
      {items.map((item, index) =>
        item === "…" ? (
          <span key={`dots-${index}`} className="px-2 text-sm text-slate-500">
            …
          </span>
        ) : (
          <PageButton key={item} active={item === page} onClick={() => onChange(item)}>
            {item}
          </PageButton>
        ),
      )}
      <PageButton disabled={page >= pages} onClick={() => onChange(page + 1)}>
        Next
      </PageButton>
    </nav>
  );
}

function PageButton({
  children,
  active,
  disabled,
  onClick,
}: {
  children: React.ReactNode;
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "min-w-[36px] rounded-lg px-2.5 py-1.5 text-sm font-medium transition-all disabled:opacity-40",
        active
          ? "bg-brand-gradient text-white shadow-glow"
          : "text-slate-300 hover:bg-white/8 hover:text-white",
      )}
    >
      {children}
    </button>
  );
}