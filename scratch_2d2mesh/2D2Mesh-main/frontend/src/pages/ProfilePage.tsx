import { useEffect, useState } from "react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";
import { useAuth } from "../hooks/useAuth";
import { usersApi } from "../api/auth";
import { formatBytes, formatDate, cn, initials } from "../lib/format";
import { Card, CardBody } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Skeleton } from "../components/ui/Skeleton";
import { Icon, type IconName } from "../components/ui/Icon";
import type { UserStats } from "../types/auth";

export function ProfilePage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<UserStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const data = await usersApi.stats();
        if (!cancelled) setStats(data);
      } catch {
        /* silently ignore */
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  if (!user) return null;

  return (
    <div className="mx-auto max-w-4xl space-y-8 animate-fade-in">
      <h1 className="font-display text-3xl font-bold tracking-tight text-white">Profile</h1>

      {/* User card */}
      <Card>
        <CardBody className="flex flex-col items-center gap-6 sm:flex-row sm:items-start">
          {/* Avatar */}
          <div className="relative flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl bg-brand-gradient text-2xl font-bold text-white shadow-glow-lg">
            <span className="absolute inset-0 rounded-2xl bg-brand-gradient opacity-40 blur-xl" aria-hidden />
            <span className="relative">{initials(user.username)}</span>
          </div>

          <div className="flex-1 text-center sm:text-left">
            <h2 className="font-display text-xl font-bold text-white">{user.username}</h2>
            <p className="mt-0.5 text-sm text-slate-400">{user.email}</p>
            <div className="mt-3 flex flex-wrap items-center justify-center gap-2 sm:justify-start">
              <Badge tone={user.role === "admin" ? "purple" : "gray"} dot={user.role === "admin"}>
                {user.role === "admin" ? "Administrator" : "User"}
              </Badge>
              <span className="text-xs text-slate-500">
                Member since {formatDate(user.created_at)}
              </span>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Usage stats */}
      <div>
        <h2 className="mb-4 font-display text-xl font-bold text-white">Usage statistics</h2>
        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-28 rounded-2xl" />
            ))}
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <UsageCard
              icon="cube"
              label="Total Projects"
              value={String(user.metrics.projects_created)}
              accent="from-brand-600 to-accent-400"
            />
            <UsageCard
              icon="check"
              label="Generations Completed"
              value={String(user.metrics.generations_completed)}
              accent="from-emerald-500 to-teal-400"
            />
            <UsageCard
              icon="alert"
              label="Generations Failed"
              value={String(user.metrics.generations_failed)}
              accent="from-rose-500 to-pink-400"
            />
            <UsageCard
              icon="hardDrive"
              label="Total Storage"
              value={formatBytes(user.metrics.total_model_size_bytes)}
              accent="from-amber-500 to-orange-400"
            />
          </div>
        )}
      </div>

      {/* Extended usage */}
      {stats?.usage && (
        <Card>
          <CardBody>
            <h2 className="mb-4 font-display text-lg font-semibold text-white">Detailed usage</h2>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <DetailItem label="Uploads" value={String(stats.usage.uploads)} />
              <DetailItem label="Total Generations" value={String(stats.usage.generations)} />
              <DetailItem label="Downloads" value={String(stats.usage.downloads)} />
              <DetailItem label="Upload Volume" value={formatBytes(stats.usage.total_upload_bytes)} />
            </div>

            {stats.usage.by_day && stats.usage.by_day.length > 0 && (
              <div className="mt-6">
                <h3 className="mb-3 flex items-center gap-1.5 text-sm font-medium text-slate-400">
                  <Icon name="clock" className="h-4 w-4" /> Recent activity
                </h3>
                <div className="h-32 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={stats.usage.by_day.slice(-14).map((day) => ({
                        date: day.date.slice(5),
                        full: day.date,
                        count: day.count,
                      }))}
                      margin={{ top: 8, right: 8, left: -22, bottom: 0 }}
                    >
                      <defs>
                        <linearGradient id="activityFill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.9} />
                          <stop offset="100%" stopColor="#22d3ee" stopOpacity={0.4} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" vertical={false} />
                      <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                      <YAxis tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
                      <Tooltip
                        cursor={{ fill: "rgba(255,255,255,0.04)" }}
                        contentStyle={{
                          background: "#09090e",
                          border: "1px solid rgba(255,255,255,0.1)",
                          borderRadius: "12px",
                          fontSize: "12px",
                          color: "#e2e8f0",
                        }}
                        labelFormatter={(label, payload) => (payload?.[0]?.payload as { full?: string })?.full ?? String(label)}
                        formatter={(value) => [`${String(value)}`, "Generations"]}
                      />
                      <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={26} fill="url(#activityFill)" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <p className="mt-1 text-center text-xs text-slate-500">Last 14 days</p>
              </div>
            )}
          </CardBody>
        </Card>
      )}
    </div>
  );
}

/* ─── Helpers ─── */

function UsageCard({
  icon,
  label,
  value,
  accent,
}: {
  icon: IconName;
  label: string;
  value: string;
  accent: string;
}) {
  return (
    <div className="panel panel-hover p-5">
      <div className={cn("flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-glow", accent)}>
        <Icon name={icon} className="h-5 w-5" />
      </div>
      <p className="mt-4 font-display text-2xl font-bold text-white">{value}</p>
      <p className="text-xs uppercase tracking-wider text-slate-500">{label}</p>
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-0.5 font-display text-lg font-semibold text-white">{value}</p>
    </div>
  );
}