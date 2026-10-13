import { useState } from "react";
import { analysisApi } from "../../api/analysis";
import { useToast } from "../../hooks/useToast";
import { extractApiError } from "../../api/client";
import { cn, formatBytes } from "../../lib/format";
import { Button } from "../ui/Button";
import { Icon } from "../ui/Icon";
import type { OptimizationProfile, OptimizationResult } from "../../types/analysis";

type ProfileConfig = {
  id: OptimizationProfile;
  label: string;
  description: string;
  features: string[];
  gradient: string;
  iconGradient: string;
};

const PROFILES: ProfileConfig[] = [
  {
    id: "web",
    label: "Web",
    description: "Optimized for fast loading in browsers and web viewers.",
    features: ["60% polygon reduction", "Vertex merge", "Clean topology"],
    gradient: "from-brand-600 to-accent-400",
    iconGradient: "from-brand-600 to-accent-400",
  },
  {
    id: "game",
    label: "Game",
    description: "Ready for real-time game engines — reduced draw calls.",
    features: ["75% polygon reduction", "Normal recompute", "LOD prep"],
    gradient: "from-purple-600 to-brand-500",
    iconGradient: "from-purple-600 to-brand-500",
  },
  {
    id: "print",
    label: "3D Print",
    description: "Watertight repair + scale to mm + STL included.",
    features: ["Watertight repair", "Scale to mm", "STL export"],
    gradient: "from-amber-500 to-orange-400",
    iconGradient: "from-amber-500 to-orange-400",
  },
];

export function OptimizationPanel({
  projectId,
  onProjectUpdated,
}: {
  projectId: string;
  onProjectUpdated?: () => void;
}) {
  const { toast } = useToast();
  const [selected, setSelected] = useState<OptimizationProfile>("web");
  const [setActiveModel, setSetActiveModel] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OptimizationResult | null>(null);
  const [downloading, setDownloading] = useState(false);

  const currentProfile = PROFILES.find((p) => p.id === selected)!;

  const handleOptimize = async () => {
    setLoading(true);
    setResult(null);
    try {
      const data = await analysisApi.optimizeModel(projectId, selected, setActiveModel);
      setResult(data);
      if (setActiveModel && onProjectUpdated) {
        onProjectUpdated();
      }
      toast("success", `${currentProfile.label} optimization complete`);
    } catch (err) {
      toast("error", "Optimization failed", { description: extractApiError(err) });
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (url: string, filename: string) => {
    if (downloading) return;
    setDownloading(true);
    try {
      await analysisApi.downloadFile(url, filename);
      toast("success", "Download started");
    } catch (err) {
      toast("error", "Download failed", { description: extractApiError(err) });
    } finally {
      setDownloading(false);
    }
  };

  const faceReduction =
    result && result.before_stats.faces > 0
      ? Math.round(
          ((result.before_stats.faces - result.after_stats.faces) /
            result.before_stats.faces) *
            100,
        )
      : 0;

  const sizeReduction =
    result && result.before_stats.size_bytes > 0
      ? Math.round(
          ((result.before_stats.size_bytes - result.after_stats.size_bytes) /
            result.before_stats.size_bytes) *
            100,
        )
      : 0;

  return (
    <div className="panel p-5 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 font-display text-base font-semibold text-white">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500 to-brand-400 shadow-glow">
            <Icon name="zap" className="h-4 w-4 text-white" />
          </span>
          Model Optimization
        </h2>
        <span className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-[10px] text-slate-400">
          Deterministic
        </span>
      </div>

      {/* Profile selector */}
      <div className="grid grid-cols-3 gap-2">
        {PROFILES.map((profile) => (
          <button
            key={profile.id}
            type="button"
            id={`btn-optimize-${profile.id}`}
            onClick={() => setSelected(profile.id)}
            className={cn(
              "relative overflow-hidden rounded-xl border p-3 text-left transition-all",
              selected === profile.id
                ? "border-brand-400/60 bg-brand-500/15 shadow-glow"
                : "border-white/8 bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.04]",
            )}
          >
            {selected === profile.id && (
              <div className="pointer-events-none absolute inset-0 bg-brand-gradient-soft opacity-20" aria-hidden />
            )}
            <p className="text-sm font-semibold text-white">{profile.label}</p>
            <p className="mt-1 text-[10px] text-slate-500">{profile.description}</p>
            <ul className="mt-2 space-y-1">
              {profile.features.map((f) => (
                <li key={f} className="flex items-center gap-1 text-[10px] text-slate-400">
                  <span className="h-1 w-1 rounded-full bg-brand-400" />
                  {f}
                </li>
              ))}
            </ul>
          </button>
        ))}
      </div>

      {/* Set active model toggle */}
      <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-300">
        <input
          type="checkbox"
          checked={setActiveModel}
          onChange={(e) => setSetActiveModel(e.target.checked)}
          className="rounded border-white/20 bg-ink-900 text-brand-500 focus:ring-brand-500/40"
        />
        <span>Update active 3D model in viewer after optimization</span>
      </label>

      <Button
        onClick={handleOptimize}
        loading={loading}
        fullWidth
        id="btn-run-optimization"
      >
        <Icon name="zap" className="h-4 w-4" />
        Optimize for {currentProfile.label}
      </Button>

      {/* Result */}
      {result && (
        <div className="space-y-3 rounded-xl border border-emerald-500/20 bg-emerald-500/8 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Icon name="check" className="h-4 w-4 text-emerald-400" />
              <p className="text-xs font-semibold text-emerald-300">
                {currentProfile.label} optimization complete
              </p>
            </div>
            <div className="flex items-center gap-1.5">
              {faceReduction > 0 && (
                <span className="rounded-md bg-emerald-500/15 px-2 py-0.5 font-mono text-[10px] font-semibold text-emerald-300">
                  -{faceReduction}% faces
                </span>
              )}
              {sizeReduction > 0 && (
                <span className="rounded-md bg-cyan-500/15 px-2 py-0.5 font-mono text-[10px] font-semibold text-cyan-300">
                  -{sizeReduction}% size
                </span>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
            <div className="rounded-lg border border-white/8 p-2">
              <p className="text-slate-500">Faces before</p>
              <p className="text-sm font-bold text-white">{result.before_stats.faces.toLocaleString()}</p>
            </div>
            <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-2">
              <p className="text-slate-500">Faces after</p>
              <p className="text-sm font-bold text-emerald-300">{result.after_stats.faces.toLocaleString()}</p>
            </div>
            <div className="rounded-lg border border-white/8 p-2">
              <p className="text-slate-500">Size before</p>
              <p className="text-sm font-bold text-white">{formatBytes(result.before_stats.size_bytes)}</p>
            </div>
            <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-2">
              <p className="text-slate-500">Size after</p>
              <p className="text-sm font-bold text-emerald-300">{formatBytes(result.after_stats.size_bytes)}</p>
            </div>
          </div>

          {/* Operations applied */}
          {result.operations && result.operations.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {result.operations.map((op) => (
                <span
                  key={op}
                  className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-[10px] text-slate-300"
                >
                  ✔ {op.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          )}

          <div className="flex flex-wrap gap-2 pt-1">
            <Button size="sm" variant="outline" onClick={() => handleDownload(result.download_url, `optimized_${selected}.glb`)} loading={downloading} id="btn-download-optimized">
              <Icon name="download" className="h-3.5 w-3.5" /> Download GLB
            </Button>
            {result.stl_download_url && (
              <Button size="sm" variant="outline" onClick={() => handleDownload(result.stl_download_url!, `optimized_${selected}.stl`)} loading={downloading} id="btn-download-stl-optimized">
                <Icon name="download" className="h-3.5 w-3.5" /> Download STL
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
