import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { projectsApi } from "../api/projects";
import { formatDate, relativeTime, cn } from "../lib/format";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Skeleton } from "../components/ui/Skeleton";
import { Pagination } from "../components/ui/Pagination";
import { Icon } from "../components/ui/Icon";
import type { Project, ProjectFilter } from "../types/project";
import type { Page } from "../types/api";

const statusTone: Record<string, "green" | "amber" | "red" | "gray" | "blue"> = {
  ready: "green",
  processing: "blue",
  failed: "red",
  no_model: "gray",
};

const statusLabel: Record<string, string> = {
  ready: "Ready",
  processing: "Processing",
  failed: "Failed",
  no_model: "No model",
};

const STATUS_FILTERS = [
  { value: "", label: "All Statuses" },
  { value: "ready", label: "Ready" },
  { value: "processing", label: "Processing" },
  { value: "failed", label: "Failed" },
  { value: "no_model", label: "No Model" },
];

const SORT_OPTIONS = [
  { value: "created_at", label: "Date Created" },
  { value: "updated_at", label: "Last Updated" },
  { value: "name", label: "Name" },
];

type ViewMode = "grid" | "list";

export function ProjectsPage() {
  const [data, setData] = useState<Page<Project> | null>(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<ViewMode>("grid");
  const [filters, setFilters] = useState<ProjectFilter>({
    page: 1,
    page_size: 12,
    sort_by: "created_at",
    sort_dir: "desc",
    query: "",
    status: "",
  });

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchProjects = useCallback(async (f: ProjectFilter) => {
    setLoading(true);
    try {
      const result = await projectsApi.list(f);
      setData(result);
    } catch {
      /* interceptor handles */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProjects(filters);
  }, [filters.page, filters.status, filters.sort_by, filters.sort_dir, fetchProjects]);

  const handleSearchChange = (value: string) => {
    setFilters((prev) => ({ ...prev, query: value }));
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setFilters((prev) => ({ ...prev, page: 1, query: value }));
      fetchProjects({ ...filters, page: 1, query: value });
    }, 400);
  };

  const updateFilter = <K extends keyof ProjectFilter>(key: K, value: ProjectFilter[K]) => {
    setFilters((prev) => ({ ...prev, [key]: value, page: 1 }));
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold tracking-tight text-white">Projects</h1>
          <p className="mt-1 text-slate-400">
            {data ? `${data.total} project${data.total !== 1 ? "s" : ""}` : "Loading…"}
          </p>
        </div>
        <Link to="/generate">
          <Button size="lg">
            <Icon name="generate" className="h-4 w-4" /> New Project
          </Button>
        </Link>
      </div>

      {/* Toolbar */}
      <div className="flex flex-col gap-3 rounded-2xl border border-white/10 bg-ink-850/70 p-3 backdrop-blur-xl sm:flex-row sm:items-center">
        {/* Search */}
        <div className="relative flex-1">
          <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search projects..."
            value={filters.query ?? ""}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="w-full rounded-xl border border-white/12 bg-ink-800/70 py-2.5 pl-10 pr-3 text-sm text-slate-100 outline-none transition-colors placeholder:text-slate-500 focus:border-brand-400/60 focus:ring-2 focus:ring-brand-500/25"
          />
        </div>

        {/* Status filter */}
        <div className="flex items-center gap-2">
          <label className="sr-only" htmlFor="status-filter">Filter by status</label>
          <select
            id="status-filter"
            value={filters.status ?? ""}
            onChange={(e) => updateFilter("status", e.target.value)}
            className="cursor-pointer rounded-xl border border-white/12 bg-ink-800/70 px-3 py-2.5 text-sm text-slate-200 outline-none transition-colors focus:border-brand-400/60 dark:[&>option]:bg-ink-800"
          >
            {STATUS_FILTERS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>

          {/* Sort */}
          <div className="flex items-center gap-1.5">
            <label className="sr-only" htmlFor="sort-by">Sort by</label>
            <select
              id="sort-by"
              value={filters.sort_by ?? "created_at"}
              onChange={(e) => updateFilter("sort_by", e.target.value)}
              className="cursor-pointer rounded-xl border border-white/12 bg-ink-800/70 px-3 py-2.5 text-sm text-slate-200 outline-none transition-colors focus:border-brand-400/60 dark:[&>option]:bg-ink-800"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => updateFilter("sort_dir", filters.sort_dir === "desc" ? "asc" : "desc")}
              aria-label={filters.sort_dir === "desc" ? "Sort ascending" : "Sort descending"}
              title={filters.sort_dir === "desc" ? "Newest first" : "Oldest first"}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/12 text-slate-400 transition-colors hover:bg-white/5 hover:text-white"
            >
              <Icon name="sort" className={cn("h-4 w-4 transition-transform", filters.sort_dir === "asc" && "rotate-180")} />
            </button>
          </div>

          {/* View toggle */}
          <div className="ml-1 flex shrink-0 items-center gap-1 rounded-xl border border-white/12 bg-ink-800/70 p-1">
            <button
              type="button"
              aria-label="Grid view"
              aria-pressed={view === "grid"}
              onClick={() => setView("grid")}
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-lg transition-colors",
                view === "grid" ? "bg-brand-500/20 text-brand-300" : "text-slate-500 hover:text-white",
              )}
            >
              <Icon name="grid" className="h-4 w-4" />
            </button>
            <button
              type="button"
              aria-label="List view"
              aria-pressed={view === "list"}
              onClick={() => setView("list")}
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-lg transition-colors",
                view === "list" ? "bg-brand-500/20 text-brand-300" : "text-slate-500 hover:text-white",
              )}
            >
              <Icon name="list" className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className={cn("grid gap-4", view === "grid" ? "sm:grid-cols-2 lg:grid-cols-3" : "grid-cols-1")}>
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-44 rounded-2xl" />
          ))}
        </div>
      ) : data && data.items.length > 0 ? (
        <>
          <div className={cn("grid gap-4", view === "grid" ? "sm:grid-cols-2 lg:grid-cols-3" : "grid-cols-1")}>
            {data.items.map((project) =>
              view === "grid" ? (
                <ProjectCard key={project.id} project={project} />
              ) : (
                <ProjectRow key={project.id} project={project} />
              ),
            )}
          </div>

          {data.pages > 1 && (
            <div className="flex justify-center">
              <Pagination
                page={data.page}
                pages={data.pages}
                onChange={(page) => setFilters((prev) => ({ ...prev, page }))}
              />
            </div>
          )}
        </>
      ) : (
        <div className="panel flex flex-col items-center py-16 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-gradient text-white shadow-glow-lg">
            <Icon name="projects" className="h-8 w-8" />
          </div>
          <h3 className="mt-4 font-display text-lg font-semibold text-white">
            {filters.query || filters.status ? "No matching projects" : "No projects yet"}
          </h3>
          <p className="mt-1 max-w-sm text-sm text-slate-400">
            {filters.query || filters.status
              ? "Try adjusting your search or filters."
              : "Create your first project by uploading an image."}
          </p>
          {!filters.query && !filters.status && (
            <Link to="/generate" className="mt-5">
              <Button size="lg">
                <Icon name="generate" className="h-4 w-4" /> Create your first project
              </Button>
            </Link>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Cards ─── */

function ProjectCard({ project }: { project: Project }) {
  return (
    <Link to={`/projects/${project.id}`}>
      <div className="panel panel-hover group h-full overflow-hidden">
        {/* Thumbnail */}
        <div className="relative flex h-36 items-center justify-center overflow-hidden bg-ink-800/50">
          <div className="absolute inset-0 bg-brand-gradient-soft opacity-60 blur-2xl transition-all group-hover:opacity-100" aria-hidden />
          <Icon name="cube" className="h-14 w-14 text-white/15 transition-transform duration-300 group-hover:scale-110" strokeWidth={1.1} />
          <span className="absolute right-3 top-3">
            <Badge tone={statusTone[project.status] ?? "gray"} dot>
              {statusLabel[project.status] ?? project.status}
            </Badge>
          </span>
        </div>

        <div className="space-y-2 p-4">
          <div className="flex items-start justify-between gap-2">
            <h3 className="line-clamp-1 font-display text-sm font-semibold text-slate-200 group-hover:text-white">
              {project.name}
            </h3>
            <Icon name="arrowUpRight" className="h-4 w-4 shrink-0 text-slate-600 transition-colors group-hover:text-brand-300" />
          </div>
          {project.description && (
            <p className="line-clamp-2 text-xs text-slate-500">{project.description}</p>
          )}
          <div className="flex items-center justify-between text-[11px] text-slate-500">
            <span>{formatDate(project.created_at)}</span>
            <span className="flex items-center gap-1">
              <Icon name="clock" className="h-3 w-3" /> {relativeTime(project.updated_at)}
            </span>
          </div>
        </div>
      </div>
    </Link>
  );
}

function ProjectRow({ project }: { project: Project }) {
  return (
    <Link to={`/projects/${project.id}`}>
      <div className="panel panel-hover group flex items-center gap-4 p-4">
        <div className="relative flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-ink-800/60">
          <div className="absolute inset-0 bg-brand-gradient-soft blur-lg" aria-hidden />
          <Icon name="cube" className="relative h-6 w-6 text-white/30" strokeWidth={1.2} />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="line-clamp-1 font-display text-sm font-semibold text-slate-200 group-hover:text-white">
            {project.name}
          </h3>
          <p className="mt-0.5 truncate text-xs text-slate-500">
            {project.description ?? "No description"} · {formatDate(project.created_at)}
          </p>
        </div>
        <div className="hidden sm:block">
          <Badge tone={statusTone[project.status] ?? "gray"} dot>
            {statusLabel[project.status] ?? project.status}
          </Badge>
        </div>
        <span className="hidden text-[11px] text-slate-500 md:block">
          {relativeTime(project.updated_at)}
        </span>
        <Icon name="chevronRight" className="h-4 w-4 shrink-0 text-slate-600 transition-colors group-hover:text-brand-300" />
      </div>
    </Link>
  );
}