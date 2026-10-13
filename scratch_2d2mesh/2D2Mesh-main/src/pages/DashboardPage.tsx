import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  AreaChart,
  Area,
  Tooltip,
} from "recharts";
import { useAuth } from "../hooks/useAuth";
import { projectsApi } from "../api/projects";
import { jobsApi } from "../api/jobs";
import { usersApi } from "../api/auth";
import { formatBytes, formatDate, relativeTime, cn } from "../lib/format";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Skeleton } from "../components/ui/Skeleton";
import { Icon, type IconName } from "../components/ui/Icon";
import type { Project } from "../types/project";
import type { Job } from "../types/job";
import type { UserStats } from "../types/auth";

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

const CHART_COLORS = {
  brand: "#8b5cf6",
  accent: "#22d3ee",
  green: "#10b981",
  red: "#f43f5e",
  amber: "#f59e0b",
  gray: "#475569",
  grid: "rgba(255,255,255,0.06)",
  axis: "#64748b",
};

function ChartTooltip({ active, payload, label, formatter }: {
  active?: boolean;
  payload?: Array<{ name?: string; value?: number | string; payload?: Record<string, unknown> }>;
  label?: string | number;
  formatter?: (value: number) => string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-white/10 bg-ink-900/95 px-3.5 py-2.5 text-xs shadow-card backdrop-blur-xl">
      {label !== undefined && <p className="mb-1 font-medium text-slate-300">{String(label)}</p>}
      {payload.map((entry, i) => (
        <p key={i} className="flex items-center justify-between gap-4">
          <span className="text-slate-400">{entry.name ?? String(entry.payload?.name ?? "")}</span>
          <span className="font-mono font-semibold text-white">
            {formatter && typeof entry.value === "number" ? formatter(entry.value) : String(entry.value)}
          </span>
        </p>
      ))}
    </div>
  );
}

export function DashboardPage() {
  const { user } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<UserStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [projectsRes, statsRes, jobsRes] = await Promise.all([
          projectsApi.list({ page: 1, page_size: 6, sort_by: "created_at", sort_dir: "desc" }),
          usersApi.stats(),
          jobsApi.list({ page: 1, page_size: 8 }),
        ]);
        if (!cancelled) {
          setProjects(projectsRes.items);
          setStats(statsRes);
          setJobs(jobsRes.items);
        }
      } catch {
        /* toast handled by interceptor */
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  const metrics = stats?.metrics ?? user?.metrics;
  const storageBytes = metrics?.total_model_size_bytes ?? 0;
  const completed = metrics?.generations_completed ?? 0;
  const failed = metrics?.generations_failed ?? 0;
  const total = completed + failed;
  const successRate = total > 0 ? Math.round((completed / total) * 100) : 100;

  // Pie data — success vs failure
  const outcomeData = [
    { name: "Successful", value: completed, color: CHART_COLORS.green },
    { name: "Failed", value: failed, color: CHART_COLORS.red },
  ].filter((d) => d.value > 0);

  // Bar data — processing time of recent jobs
  const timeData: Array<{ name: string; seconds: number; fill: string }> = jobs
    .filter((j) => j.status === "succeeded" && j.started_at && j.completed_at)
    .slice(0, 6)
    .map((j) => {
      const ms = new Date(j.completed_at!).getTime() - new Date(j.started_at!).getTime();
      return { name: (j.settings?.resolution ?? "") + "px", seconds: Math.round(ms / 100) / 10, fill: CHART_COLORS.accent };
    });

  // Area data — usage trend from stats.usage.by_day
  const byDay = stats?.usage.by_day ?? [];
  const trendByDate = new Map<string, { date: string; count: number; bytes: number }>();
  for (const day of byDay.slice(-14)) {
    const key = day.date;
    const existing = trendByDate.get(key) ?? { date: day.date.slice(5), count: 0, bytes: day.bytes ?? 0 };
    existing.count += day.count;
    if (day.bytes) existing.bytes += day.bytes;
    trendByDate.set(key, existing);
  }
  const trendData = Array.from(trendByDate.values());

  const storageData = [
    { name: "Models", bytes: storageBytes, fill: CHART_COLORS.brand },
    { name: "Uploads", bytes: metrics?.total_upload_bytes ?? 0, fill: CHART_COLORS.accent },
  ];

  if (loading) return <DashboardSkeleton />;

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Welcome */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm text-slate-500">
            <span className="mr-1.5 inline-block h-2 w-2 rounded-full bg-emerald-400 shadow-glow align-middle" />
            Workspace · {relativeTime(user?.created_at ?? new Date()) === "just now" ? "new member" : "active"}
          </p>
          <h1 className="mt-2 font-display text-3xl font-bold tracking-tight text-white">
            Welcome back, <span className="text-gradient">{user?.username}</span>
          </h1>
          <p className="mt-1 text-slate-400">Here&apos;s an overview of your Vision3D workspace.</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Link to="/projects">
            <Button variant="outline">
              <Icon name="projects" className="h-4 w-4" /> View all projects
            </Button>
          </Link>
          <Link to="/generate">
            <Button size="lg">
              <Icon name="generate" className="h-4 w-4" /> Generate 3D Model
            </Button>
          </Link>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon="cube"
          label="Total Projects"
          value={String(metrics?.projects_created ?? 0)}
          accent="from-brand-600 to-accent-400"
          trend={`${projects.length} recent`}
        />
        <StatCard
          icon="check"
          label="Completed"
          value={String(completed)}
          accent="from-emerald-500 to-teal-400"
          trend={`${successRate}% success rate`}
        />
        <StatCard
          icon="zap"
          label="Processing Stats"
          value={`${successRate}%`}
          accent="from-accent-500 to-brand-500"
          trend={`${failed} failed attempts`}
        />
        <StatCard
          icon="hardDrive"
          label="Storage Used"
          value={formatBytes(storageBytes)}
          accent="from-amber-500 to-orange-400"
          trend="across all models"
        />
      </div>

      {/* Quick actions */}
      <div className="grid gap-4 md:grid-cols-4">
        <QuickAction
          icon="upload"
          title="New Generation"
          description="Upload an image and convert it to 3D"
          to="/generate"
          accent="from-brand-600 to-purple-500"
        />
        <QuickAction
          icon="projects"
          title="Browse Projects"
          description="Search, filter and manage your models"
          to="/projects"
          accent="from-accent-500 to-cyan-400"
        />
        <QuickAction
          icon="layers"
          title="Model Viewer"
          description="Inspect any ready model in 3D"
          to={projects.find((p) => p.status === "ready") ? `/projects/${projects.find((p) => p.status === "ready")!.id}/viewer` : "/projects"}
          accent="from-purple-500 to-accent-400"
        />
        <QuickAction
          icon="settings"
          title="Settings"
          description="Tune your default AI model & preferences"
          to="/settings"
          accent="from-slate-500 to-slate-400"
        />
      </div>

      {/* Analytics charts */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Outcome donut */}
        <div className="panel p-6">
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-2 font-display text-base font-semibold text-white">
              <Icon name="check" className="h-4 w-4 text-emerald-300" /> Success rate
            </h2>
            <span className="font-mono text-sm font-semibold text-white">{successRate}%</span>
          </div>
          <div className="mt-2 h-48">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={outcomeData}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={58}
                  outerRadius={80}
                  paddingAngle={4}
                  strokeWidth={0}
                >
                  {outcomeData.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip content={<ChartTooltip />} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 flex items-center justify-center gap-4 text-xs text-slate-400">
            {outcomeData.map((d) => (
              <span key={d.name} className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ background: d.color }} />
                {d.name} · {d.value}
              </span>
            ))}
          </div>
        </div>

        {/* Processing time */}
        <div className="panel p-6">
          <h2 className="flex items-center gap-2 font-display text-base font-semibold text-white">
            <Icon name="cpu" className="h-4 w-4 text-accent-300" /> Processing time
          </h2>
          {timeData.length === 0 ? (
            <div className="flex h-56 flex-col items-center justify-center gap-2 text-center">
              <Icon name="clock" className="h-8 w-8 text-slate-600" />
              <p className="text-sm text-slate-500">No completed generations yet</p>
            </div>
          ) : (
            <div className="mt-2 h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={timeData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: CHART_COLORS.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: CHART_COLORS.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<ChartTooltip formatter={(v) => `${v}s`} />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
                  <Bar dataKey="seconds" name="Duration" radius={[6, 6, 0, 0]} maxBarSize={34}>
                    {timeData.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* Activity trend */}
        <div className="panel p-6">
          <h2 className="flex items-center gap-2 font-display text-base font-semibold text-white">
            <Icon name="layers" className="h-4 w-4 text-brand-300" /> Activity trend
          </h2>
          {trendData.length === 0 ? (
            <div className="flex h-56 flex-col items-center justify-center gap-2 text-center">
              <Icon name="clock" className="h-8 w-8 text-slate-600" />
              <p className="text-sm text-slate-500">No activity recorded yet</p>
            </div>
          ) : (
            <div className="mt-2 h-56">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trendData} margin={{ top: 8, right: 8, left: -24, bottom: 0 }}>
                  <defs>
                    <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={CHART_COLORS.brand} stopOpacity={0.45} />
                      <stop offset="100%" stopColor={CHART_COLORS.brand} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} vertical={false} />
                  <XAxis dataKey="date" tick={{ fill: CHART_COLORS.axis, fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                  <YAxis tick={{ fill: CHART_COLORS.axis, fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <Tooltip content={<ChartTooltip />} />
                  <Area type="monotone" dataKey="count" name="Generations" stroke={CHART_COLORS.brand} strokeWidth={2} fill="url(#trendFill)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      {/* ── AI Operations Analytics ── */}
      {stats && (
        <div className="panel p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="flex items-center gap-2 font-display text-base font-semibold text-white">
              <Icon name="generate" className="h-4 w-4 text-brand-300" /> AI Operations
            </h2>
            <span className="text-xs text-slate-500">Quality · Repair · Edit · Optimize</span>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {([
              { label: "Analyses", kind: "quality_analysis", color: "from-emerald-500 to-teal-400", icon: "check" },
              { label: "Repairs", kind: "repair", color: "from-orange-500 to-amber-400", icon: "settings" },
              { label: "AI Edits", kind: "ai_edit", color: "from-purple-500 to-brand-400", icon: "generate" },
              { label: "Optimizations", kind: "optimization", color: "from-cyan-500 to-brand-400", icon: "zap" },
            ] as const).map(({ label, kind, color, icon }) => {
              const count = stats.usage.by_day
                .filter((d: { kind: string; count: number }) => d.kind === kind)
                .reduce((acc: number, d: { count: number }) => acc + d.count, 0);
              return (
                <div key={kind} className="rounded-xl border border-white/8 bg-white/[0.02] p-4">
                  <div className={`mb-2 flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br ${color}`}>
                    <Icon name={icon as any} className="h-4 w-4 text-white" />
                  </div>
                  <p className="font-display text-2xl font-bold text-white">{count}</p>
                  <p className="text-xs text-slate-500">{label}</p>
                </div>
              );
            })}
          </div>
          {stats.usage.by_day.filter((d: { kind: string }) =>
            ["quality_analysis", "repair", "ai_edit", "optimization"].includes(d.kind)
          ).length > 0 && (
            <div className="mt-4 h-32">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={(() => {
                    const aiKinds = ["quality_analysis", "repair", "ai_edit", "optimization"];
                    const aiByDate = new Map<string, { date: string; count: number }>();
                    for (const d of stats.usage.by_day) {
                      if (!aiKinds.includes(d.kind)) continue;
                      const existing = aiByDate.get(d.date) ?? { date: d.date.slice(5), count: 0 };
                      existing.count += d.count;
                      aiByDate.set(d.date, existing);
                    }
                    return Array.from(aiByDate.values()).slice(-14);
                  })()}
                  margin={{ top: 4, right: 8, left: -24, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="aiFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.4} />
                      <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} vertical={false} />
                  <XAxis dataKey="date" tick={{ fill: CHART_COLORS.axis, fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: CHART_COLORS.axis, fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <Tooltip content={<ChartTooltip />} />
                  <Area type="monotone" dataKey="count" name="AI Ops" stroke="#8b5cf6" strokeWidth={2} fill="url(#aiFill)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* Storage + recent */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Storage usage */}
        <div className="panel p-6">
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-2 font-display text-base font-semibold text-white">
              <Icon name="hardDrive" className="h-4 w-4 text-brand-300" /> Storage usage
            </h2>
          </div>
          <div className="mt-4 flex items-end justify-between">
            <p className="font-display text-3xl font-bold text-white">{formatBytes(storageBytes)}</p>
            <p className="text-xs text-slate-500">of 1 GB plan</p>
          </div>
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-white/8">
            <div
              className="h-full rounded-full bg-brand-gradient shadow-glow"
              style={{ width: `${Math.min(100, (storageBytes / (1024 * 1024 * 1024)) * 100)}%` }}
            />
          </div>
          <div className="mt-4 h-24">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={storageData} layout="vertical" margin={{ top: 0, right: 8, left: -8, bottom: 0 }}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="name" tick={{ fill: CHART_COLORS.axis, fontSize: 11 }} width={60} axisLine={false} tickLine={false} />
                <Tooltip content={<ChartTooltip formatter={(v) => formatBytes(v)} />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
                <Bar dataKey="bytes" name="Used" radius={[4, 8, 8, 4]} maxBarSize={14}>
                  {storageData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Recent generations */}
        <div className="panel p-6">
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-2 font-display text-base font-semibold text-white">
              <Icon name="clock" className="h-4 w-4 text-purple-300" /> Recent generations
            </h2>
            <Link to="/projects" className="text-xs font-medium text-brand-300 hover:underline">
              View all →
            </Link>
          </div>
          <div className="mt-4 space-y-3">
            {projects.length === 0 ? (
              <div className="rounded-xl border border-dashed border-white/10 py-10 text-center">
                <Icon name="cube" className="mx-auto h-8 w-8 text-slate-600" />
                <p className="mt-2 text-sm text-slate-500">No generations yet</p>
              </div>
            ) : (
              projects.slice(0, 4).map((project) => (
                <Link
                  key={project.id}
                  to={`/projects/${project.id}`}
                  className="group flex items-center gap-3 rounded-xl border border-white/8 bg-white/[0.02] p-3 transition-all hover:border-brand-400/30 hover:bg-white/[0.04]"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-gradient/60">
                    <Icon name="cube" className="h-4 w-4 text-white" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-slate-200 group-hover:text-white">{project.name}</p>
                    <p className="text-xs text-slate-500">{relativeTime(project.updated_at)}</p>
                  </div>
                  <Badge tone={statusTone[project.status] ?? "gray"} dot>
                    {statusLabel[project.status] ?? project.status}
                  </Badge>
                </Link>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Recent projects grid */}
      <div>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-xl font-bold text-white">Recent Projects</h2>
          {projects.length > 0 && (
            <Link to="/projects" className="text-sm font-medium text-brand-300 hover:underline">
              View all →
            </Link>
          )}
        </div>

        {projects.length === 0 ? (
          <div className="panel flex flex-col items-center py-16 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-gradient text-white shadow-glow-lg">
              <Icon name="cube" className="h-8 w-8" />
            </div>
            <h3 className="mt-4 font-display text-lg font-semibold text-white">No projects yet</h3>
            <p className="mt-1 max-w-sm text-sm text-slate-400">
              Upload an image and let the AI turn it into a 3D model. It only takes a few seconds.
            </p>
            <Link to="/generate" className="mt-5">
              <Button size="lg">
                <Icon name="generate" className="h-4 w-4" /> Create your first project
              </Button>
            </Link>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((project) => (
              <Link key={project.id} to={`/projects/${project.id}`}>
                <div className="panel panel-hover group h-full">
                  <div className="relative flex h-36 items-center justify-center overflow-hidden rounded-t-2xl bg-ink-800/50">
                    <div className="absolute inset-0 bg-brand-gradient-soft opacity-60 blur-2xl" aria-hidden />
                    <Icon name="cube" className="h-12 w-12 text-white/20 transition-transform duration-300 group-hover:scale-110" strokeWidth={1.2} />
                    <span className="absolute right-3 top-3">
                      <Badge tone={statusTone[project.status] ?? "gray"} dot>
                        {statusLabel[project.status] ?? project.status}
                      </Badge>
                    </span>
                  </div>
                  <div className="space-y-2 p-4">
                    <h3 className="line-clamp-1 font-display text-sm font-semibold text-slate-200 group-hover:text-white">
                      {project.name}
                    </h3>
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
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Helpers ─── */

function StatCard({
  icon,
  label,
  value,
  accent,
  trend,
}: {
  icon: IconName;
  label: string;
  value: string;
  accent: string;
  trend: string;
}) {
  return (
    <div className="panel panel-hover group relative overflow-hidden p-5">
      <div className="pointer-events-none absolute -right-8 -top-8 h-28 w-28 rounded-full bg-white/[0.03] blur-2xl transition-colors group-hover:bg-brand-500/10" aria-hidden />
      <div className="flex items-center justify-between">
        <div className={cn("flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-glow", accent)}>
          <Icon name={icon} className="h-5 w-5" strokeWidth={1.8} />
        </div>
        <Icon name="arrowUpRight" className="h-4 w-4 text-slate-600" />
      </div>
      <p className="mt-4 font-display text-2xl font-bold text-white">{value}</p>
      <p className="text-xs font-medium uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1.5 text-[11px] text-slate-600">{trend}</p>
    </div>
  );
}

function QuickAction({
  icon,
  title,
  description,
  to,
  accent,
}: {
  icon: IconName;
  title: string;
  description: string;
  to: string;
  accent: string;
}) {
  return (
    <Link to={to} className="panel panel-hover group flex items-start gap-3 p-4">
      <span className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-glow transition-transform duration-300 group-hover:scale-110", accent)}>
        <Icon name={icon} className="h-5 w-5" />
      </span>
      <span>
        <span className="block text-sm font-semibold text-white">{title}</span>
        <span className="mt-0.5 block text-xs text-slate-500">{description}</span>
      </span>
    </Link>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-8">
      <div>
        <Skeleton className="h-8 w-72" />
        <Skeleton className="mt-2 h-5 w-56" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-32 rounded-2xl" />
        ))}
      </div>
      <Skeleton className="h-72 rounded-2xl" />
      <div className="grid gap-4 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-56 rounded-2xl" />
        ))}
      </div>
    </div>
  );
}