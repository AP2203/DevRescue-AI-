import { useEffect, useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { adminApi } from "../api/admin";
import { extractApiError } from "../api/client";
import { formatBytes, formatDate, cn } from "../lib/format";
import { Button } from "../components/ui/Button";
import { Card, CardBody } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Skeleton } from "../components/ui/Skeleton";
import { Alert } from "../components/ui/Feedback";
import { Pagination } from "../components/ui/Pagination";
import { Icon, type IconName } from "../components/ui/Icon";
import type { AdminStats, AdminUserRow } from "../types/admin";
import type { Page } from "../types/api";

export function AdminPage() {
  const { user } = useAuth();
  const { toast } = useToast();

  const [stats, setStats] = useState<AdminStats | null>(null);
  const [usersData, setUsersData] = useState<Page<AdminUserRow> | null>(null);
  const [loading, setLoading] = useState(true);
  const [userSearch, setUserSearch] = useState("");
  const [userPage, setUserPage] = useState(1);

  useEffect(() => {
    if (user?.role !== "admin") return;
    const load = async () => {
      try {
        const [statsData, usersRes] = await Promise.all([
          adminApi.stats(),
          adminApi.users({ query: userSearch || undefined, page: userPage, page_size: 10 }),
        ]);
        setStats(statsData);
        setUsersData(usersRes);
      } catch {
        /* handled */
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [userPage, userSearch, user?.role]);

  if (user?.role !== "admin") {
    return (
      <div className="mx-auto max-w-lg pt-16">
        <Alert tone="error" title="Access Denied">
          You must be an administrator to view this page.
        </Alert>
      </div>
    );
  }

  const handleToggleActive = async (userId: string, isActive: boolean) => {
    try {
      await adminApi.updateUser(userId, { is_active: !isActive });
      toast("success", `User ${isActive ? "deactivated" : "activated"}`);
      const usersRes = await adminApi.users({
        query: userSearch || undefined,
        page: userPage,
        page_size: 10,
      });
      setUsersData(usersRes);
    } catch (err) {
      toast("error", "Action failed", { description: extractApiError(err) });
    }
  };

  const handleToggleRole = async (userId: string, currentRole: string) => {
    const newRole = currentRole === "admin" ? "user" : "admin";
    try {
      await adminApi.updateUser(userId, { role: newRole });
      toast("success", `Role changed to ${newRole}`);
      const usersRes = await adminApi.users({
        query: userSearch || undefined,
        page: userPage,
        page_size: 10,
      });
      setUsersData(usersRes);
    } catch (err) {
      toast("error", "Action failed", { description: extractApiError(err) });
    }
  };

  if (loading) return <AdminSkeleton />;

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="font-display text-3xl font-bold tracking-tight text-white">Admin dashboard</h1>
        <p className="mt-1 text-slate-400">Platform-wide statistics and user management.</p>
      </div>

      {/* Platform stats */}
      {stats && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <AdminStatCard icon="user" label="Users" value={stats.users} accent="from-brand-600 to-accent-400" />
          <AdminStatCard icon="cube" label="Projects" value={stats.projects} accent="from-purple-500 to-brand-400" />
          <AdminStatCard icon="zap" label="Jobs" value={stats.jobs} accent="from-accent-500 to-cyan-400" />
          <AdminStatCard icon="upload" label="Uploads" value={stats.uploads} accent="from-emerald-500 to-teal-400" />
          <AdminStatCard icon="hardDrive" label="Storage" value={formatBytes(stats.storage_total_bytes)} accent="from-amber-500 to-orange-400" isText />
        </div>
      )}

      {/* Jobs by status */}
      {stats?.jobs_by_status && stats.jobs_by_status.length > 0 && (
        <Card>
          <CardBody>
            <h2 className="mb-4 flex items-center gap-2 font-display text-lg font-semibold text-white">
              <Icon name="layers" className="h-4 w-4 text-brand-300" /> Jobs by status
            </h2>
            <div className="flex flex-wrap gap-4">
              {stats.jobs_by_status.map((item) => (
                <div
                  key={item.status}
                  className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.02] px-4 py-2"
                >
                  <Badge
                    tone={
                      item.status === "succeeded"
                        ? "green"
                        : item.status === "failed"
                          ? "red"
                          : item.status === "processing"
                            ? "amber"
                            : "gray"
                    }
                    dot
                  >
                    {item.status}
                  </Badge>
                  <span className="font-display font-semibold text-white">{item.count}</span>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      )}

      {/* Active users */}
      {stats && (
        <div className="panel flex items-center gap-3 p-4">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-300">
            <Icon name="eye" className="h-5 w-5" />
          </span>
          <p className="text-sm text-slate-400">
            <span className="font-display font-semibold text-emerald-300">{stats.active_in_last_24h}</span>{" "}
            users active in the last 24 hours
          </p>
        </div>
      )}

      {/* User management */}
      <Card>
        <CardBody className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="flex items-center gap-2 font-display text-lg font-semibold text-white">
              <Icon name="user" className="h-4 w-4 text-accent-300" /> User management
            </h2>
            <div className="relative">
              <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                placeholder="Search users..."
                value={userSearch}
                onChange={(e) => {
                  setUserSearch(e.target.value);
                  setUserPage(1);
                }}
                className="w-full rounded-xl border border-white/12 bg-ink-800/70 py-2.5 pl-10 pr-3 text-sm text-slate-100 outline-none transition-colors placeholder:text-slate-500 focus:border-brand-400/60 sm:w-64"
              />
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/8">
                  <th className="px-3 py-2.5 text-left font-medium text-slate-500">Username</th>
                  <th className="px-3 py-2.5 text-left font-medium text-slate-500">Email</th>
                  <th className="px-3 py-2.5 text-left font-medium text-slate-500">Role</th>
                  <th className="px-3 py-2.5 text-left font-medium text-slate-500">Status</th>
                  <th className="px-3 py-2.5 text-left font-medium text-slate-500">Projects</th>
                  <th className="px-3 py-2.5 text-left font-medium text-slate-500">Joined</th>
                  <th className="px-3 py-2.5 text-left font-medium text-slate-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {usersData?.items.map((u) => (
                  <tr key={u.id} className="transition-colors hover:bg-white/[0.02]">
                    <td className="px-3 py-3 font-medium text-white">{u.username}</td>
                    <td className="px-3 py-3 text-slate-400">{u.email}</td>
                    <td className="px-3 py-3">
                      <Badge tone={u.role === "admin" ? "purple" : "gray"}>{u.role}</Badge>
                    </td>
                    <td className="px-3 py-3">
                      <Badge tone={u.is_active ? "green" : "red"} dot>{u.is_active ? "Active" : "Disabled"}</Badge>
                    </td>
                    <td className="px-3 py-3 font-mono text-slate-300">{u.metrics?.projects_created ?? 0}</td>
                    <td className="px-3 py-3 text-slate-500">{formatDate(u.created_at)}</td>
                    <td className="px-3 py-3">
                      <div className="flex gap-1">
                        <Button size="xs" variant="ghost" onClick={() => handleToggleActive(u.id, u.is_active)}>
                          {u.is_active ? "Deactivate" : "Activate"}
                        </Button>
                        <Button
                          size="xs"
                          variant="ghost"
                          onClick={() => handleToggleRole(u.id, u.role)}
                          disabled={u.id === user?.id}
                        >
                          {u.role === "admin" ? "Demote" : "Promote"}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {usersData && usersData.pages > 1 && (
            <div className="flex justify-center">
              <Pagination
                page={usersData.page}
                pages={usersData.pages}
                onChange={setUserPage}
              />
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

/* ─── Helpers ─── */

function AdminStatCard({
  icon,
  label,
  value,
  accent,
  isText = false,
}: {
  icon: IconName;
  label: string;
  value: number | string;
  accent: string;
  isText?: boolean;
}) {
  return (
    <div className="panel panel-hover p-5 text-center">
      <div className={cn("mx-auto flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-glow", accent)}>
        <Icon name={icon} className="h-5 w-5" />
      </div>
      <p className="mt-3 font-display text-2xl font-bold text-white">
        {isText ? value : Number(value).toLocaleString()}
      </p>
      <p className="text-xs uppercase tracking-wider text-slate-500">{label}</p>
    </div>
  );
}

function AdminSkeleton() {
  return (
    <div className="space-y-8">
      <div>
        <Skeleton className="h-9 w-56" />
        <Skeleton className="mt-2 h-5 w-72" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-24 rounded-2xl" />
        ))}
      </div>
      <Skeleton className="h-96 rounded-2xl" />
    </div>
  );
}