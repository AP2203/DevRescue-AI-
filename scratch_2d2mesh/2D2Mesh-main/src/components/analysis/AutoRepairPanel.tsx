import { useState } from "react";
import { analysisApi } from "../../api/analysis";
import { useToast } from "../../hooks/useToast";
import { extractApiError } from "../../api/client";
import { cn } from "../../lib/format";
import { Button } from "../ui/Button";
import { Icon } from "../ui/Icon";
import { Spinner } from "../ui/Spinner";
import type { RepairResult } from "../../types/analysis";

function StatDiff({
  label,
  before,
  after,
}: {
  label: string;
  before: number;
  after: number;
}) {
  const delta = after - before;
  const improved = delta <= 0; // fewer is better for faces/verts
  return (
    <div className="flex flex-col items-center rounded-xl border border-white/8 bg-white/[0.02] p-3 text-center">
      <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 font-mono text-sm font-semibold text-white">{before.toLocaleString()}</p>
      {delta === 0 ? (
        <div className="mt-1.5 text-[11px] font-medium text-slate-500">
          No change
        </div>
      ) : (
        <div className={cn("mt-1 flex items-center gap-1 text-[11px] font-medium", improved ? "text-emerald-400" : "text-red-400")}>
          <Icon name={improved ? "chevronDown" : "chevronRight"} className="h-3 w-3" />
          {Math.abs(delta).toLocaleString()}
        </div>
      )}
      <p className="mt-1 font-mono text-sm font-bold text-white">{after.toLocaleString()}</p>
      <p className="text-[9px] text-slate-600">after</p>
    </div>
  );
}

function getScoreColor(score: number) {
  if (score >= 80) return "text-emerald-400";
  if (score >= 60) return "text-amber-400";
  return "text-red-400";
}

export function AutoRepairPanel({
  projectId,
  onProjectUpdated,
}: {
  projectId: string;
  onProjectUpdated?: () => void;
}) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RepairResult | null>(null);

  const handleRepair = async () => {
    setLoading(true);
    setResult(null);

    try {
      const data = await analysisApi.repairModel(projectId);
      setResult(data);
      toast("success", "Mesh repair complete");
      onProjectUpdated?.();
    } catch (err) {
      toast("error", "Repair failed", { description: extractApiError(err) });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel p-5 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 font-display text-base font-semibold text-white">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-orange-500 to-amber-400 shadow-glow">
            <Icon name="settings" className="h-4 w-4 text-white" />
          </span>
          Auto Repair
        </h2>
        <Button
          size="sm"
          variant="outline"
          onClick={handleRepair}
          loading={loading}
          disabled={loading}
          id="btn-auto-repair"
        >
          {result ? "Repair again" : "Run Repair"}
        </Button>
      </div>

      {/* Repair features list */}
      {!result && !loading && (
        <div className="space-y-2">
          <p className="text-xs text-slate-400">Automatically detects and fixes common mesh issues:</p>
          <div className="grid grid-cols-2 gap-2">
            {[
              { label: "Holes & Open boundaries", icon: "check" },
              { label: "Bad & Inverted normals", icon: "check" },
              { label: "Duplicate vertices", icon: "check" },
              { label: "Degenerate faces", icon: "check" },
              { label: "Non-manifold geometry", icon: "check" },
              { label: "Disconnected components", icon: "check" },
              { label: "Excessive geometry", icon: "check" },
              { label: "Missing textures", icon: "check" },
            ].map(({ label, icon }) => (
              <div key={label} className="flex items-center gap-1.5 text-xs text-slate-400">
                <Icon name={icon as any} className="h-3 w-3 text-emerald-400" />
                {label}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Progress View */}
      {loading && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 py-10 text-center space-y-3">
          <Spinner className="h-8 w-8 text-amber-400" />
          <p className="text-sm font-semibold text-white">Repairing Mesh</p>
          <p className="text-xs text-slate-400">Applying mesh repair — this may take a few seconds.</p>
        </div>
      )}

      {/* Repair result */}
      {result && !loading && (
        <div className="space-y-4 animate-fade-in">
          {/* Status Badge */}
          <div className="flex items-center gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-3">
            <Icon name="check" className="h-4 w-4 text-emerald-400" />
            <p className="text-xs font-medium text-emerald-300">Repair completed successfully</p>
          </div>

          {/* Scores Comparison */}
          <div className="grid grid-cols-2 gap-4 rounded-xl border border-white/8 bg-white/[0.01] p-4 text-center">
            <div className="space-y-1">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Before Score</span>
              <div className="flex items-center justify-center gap-1">
                <span className={cn("font-display text-2xl font-bold", getScoreColor(result.before_score))}>
                  {Math.round(result.before_score)}
                </span>
                <span className="text-xs text-slate-600">/ 100</span>
              </div>
            </div>
            <div className="relative space-y-1 border-l border-white/8">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">After Score</span>
              <div className="flex items-center justify-center gap-1">
                <span className={cn("font-display text-2xl font-bold", getScoreColor(result.after_score))}>
                  {Math.round(result.after_score)}
                </span>
                <span className="text-xs text-slate-600">/ 100</span>
                {result.after_score > result.before_score && (
                  <span className="absolute -top-1.5 right-2 rounded bg-emerald-500/15 px-1 py-0.2 text-[9px] font-bold text-emerald-400">
                    +{Math.round(result.after_score - result.before_score)}
                  </span>
                )}
                {result.after_score === result.before_score && (
                  <span className="absolute -top-1.5 right-2 rounded bg-slate-500/15 px-1 py-0.2 text-[9px] font-bold text-slate-400">
                    No change
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Problems Found & Fixed */}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Problems Found</span>
              {result.problems_found.length === 0 ? (
                <p className="text-xs text-slate-500 italic">No critical issues detected.</p>
              ) : (
                <div className="max-h-36 overflow-y-auto space-y-1.5 pr-1">
                  {result.problems_found.map((p, idx) => (
                    <div key={idx} className="flex items-start gap-2 rounded-xl border border-red-500/10 bg-red-500/5 p-2.5 text-xs text-red-400">
                      <Icon name="alert" className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                      <span>{p.message}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="space-y-2">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Problems Fixed</span>
              {result.problems_fixed.length === 0 ? (
                <p className="text-xs text-slate-500 italic">No fixes required.</p>
              ) : (
                <div className="max-h-36 overflow-y-auto space-y-1.5 pr-1">
                  {result.problems_fixed.map((msg, idx) => (
                    <div key={idx} className="flex items-start gap-2 rounded-xl border border-emerald-500/10 bg-emerald-500/5 p-2.5 text-xs text-emerald-400">
                      <Icon name="check" className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                      <span>{msg}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Stat Diffs */}
          <div className="space-y-2 border-t border-white/8 pt-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Before → After Stats</p>
            <div className="grid grid-cols-3 gap-2">
              <StatDiff label="Faces" before={result.before_stats.faces} after={result.after_stats.faces} />
              <StatDiff label="Vertices" before={result.before_stats.vertices} after={result.after_stats.vertices} />
              <div className="flex flex-col items-center rounded-xl border border-white/8 bg-white/[0.02] p-3 text-center">
                <p className="text-[10px] uppercase tracking-wider text-slate-500">Watertight</p>
                <p className="mt-1 font-mono text-sm font-semibold text-white">
                  {result.before_stats.watertight_count}/{result.before_stats.mesh_count}
                </p>
                <div className={cn("mt-1 flex items-center justify-center", result.after_stats.watertight_count > result.before_stats.watertight_count ? "text-emerald-400" : "text-slate-500")}>
                  <Icon name="chevronRight" className="h-3 w-3 -rotate-90" />
                </div>
                <p className={cn("mt-1 font-mono text-sm font-bold", result.after_stats.watertight_count > result.before_stats.watertight_count ? "text-emerald-400" : "text-white")}>
                  {result.after_stats.watertight_count}/{result.after_stats.mesh_count}
                </p>
              </div>
            </div>
          </div>

          {/* Operations applied */}
          {result.operations_applied.length > 0 && (
            <div className="space-y-2 border-t border-white/8 pt-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Engine Actions</p>
              <div className="flex flex-wrap gap-1.5">
                {result.operations_applied.map((op) => (
                  <span
                    key={op}
                    className="rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 font-mono text-[10px] text-slate-400"
                  >
                    {op.replace(/_/g, " ").replace(/:(\d+)/, " ($1 resolved)")}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
