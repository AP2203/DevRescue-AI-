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

export function OptimizationPanel({ projectId }: { projectId: string }) {
  const { toast } = useToast();
  const [selected, setSelected] = useState<OptimizationProfile>("web");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OptimizationResult | null>(null);
  const [downloading, setDownloading] = useState(false);

  const handleOptimize = async () => {
    setLoading(true);
    setResult(null);
    try {
      const data = await analysisApi.optimizeModel(projectId, selected);
      setResult(data);
      toast("success", `${selected} optimization complete`);
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

  const currentProfile = PROFILES.find((p) => p.id === selected)!;

  return (
    <div className="panel p-5 space-y-5">
      {/* Header */}
      <h2 className="flex items-center gap-2 font-display text-base font-semibold text-white">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500 to-brand-400 shadow-glow">
          <Icon name="zap" className="h-4 w-4 text-white" />
        </span>
        Model Optimization
      </h2>

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
          <div className="flex items-center gap-2">
            <Icon name="check" className="h-4 w-4 text-emerald-400" />
            <p className="text-xs font-semibold text-emerald-300">Optimization complete</p>
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

          <div className="flex flex-wrap gap-2">
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
