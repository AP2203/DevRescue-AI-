import { useCallback, useEffect, useState } from "react";
import { analysisApi } from "../../api/analysis";
import { useToast } from "../../hooks/useToast";
import { extractApiError } from "../../api/client";
import { cn } from "../../lib/format";
import { Button } from "../ui/Button";
import { Icon } from "../ui/Icon";
import { Spinner } from "../ui/Spinner";
import type { QualityReport, QualityProblem } from "../../types/analysis";

const severityStyle = {
  error: "text-red-400 bg-red-500/10 border-red-500/20",
  warning: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  info: "text-blue-400 bg-blue-500/10 border-blue-500/20",
};

const severityIcon = {
  error: "alert",
  warning: "info",
  info: "info",
} as const;

function ScoreRing({ score }: { score: number }) {
  const r = 40;
  const circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;
  const color = score >= 80 ? "#10b981" : score >= 60 ? "#f59e0b" : "#f43f5e";

  return (
    <div className="relative flex h-28 w-28 items-center justify-center">
      <svg className="absolute h-28 w-28 -rotate-90" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="10" />
        <circle
          cx="50"
          cy="50"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 0.8s ease-out", filter: `drop-shadow(0 0 6px ${color}88)` }}
        />
      </svg>
      <div className="text-center">
        <p className="font-display text-2xl font-bold text-white">{Math.round(score)}</p>
        <p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">/ 100</p>
      </div>
    </div>
  );
}

function DimensionBar({ name, score, details }: { name: string; score: number; details: string }) {
  const color = score >= 80 ? "bg-emerald-500" : score >= 60 ? "bg-amber-500" : "bg-red-500";
  const label = name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-slate-300">{label}</span>
        <span className="font-mono text-xs font-semibold text-white">{Math.round(score)}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/8">
        <div
          className={cn("h-full rounded-full transition-all duration-700", color)}
          style={{ width: `${score}%` }}
        />
      </div>
      {details && <p className="text-[10px] text-slate-500">{details}</p>}
    </div>
  );
}

function ProblemItem({ problem }: { problem: QualityProblem }) {
  return (
    <div className={cn("flex items-start gap-2 rounded-xl border p-3 text-xs", severityStyle[problem.severity])}>
      <Icon name={severityIcon[problem.severity] as any} className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <span>{problem.message}</span>
    </div>
  );
}

export function QualityScorePanel({ projectId }: { projectId: string }) {
  const { toast } = useToast();
  const [report, setReport] = useState<QualityReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(true);
  const [showAll, setShowAll] = useState(false);

  const fetchReport = useCallback(async () => {
    try {
      const data = await analysisApi.getQualityReport(projectId);
      setReport(data);
    } catch {
      // No report yet — that's fine
    } finally {
      setFetching(false);
    }
  }, [projectId]);

  useEffect(() => {
    void fetchReport();
  }, [fetchReport]);

  const handleAnalyze = async () => {
    setLoading(true);
    try {
      const data = await analysisApi.runQualityAnalysis(projectId);
      setReport(data);
      toast("success", "Quality analysis complete");
    } catch (err) {
      toast("error", "Analysis failed", { description: extractApiError(err) });
    } finally {
      setLoading(false);
    }
  };

  const scoreColor = report
    ? report.overall_score >= 80 ? "text-emerald-400" : report.overall_score >= 60 ? "text-amber-400" : "text-red-400"
    : "text-slate-400";

  return (
    <div className="panel p-5 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 font-display text-base font-semibold text-white">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-teal-400 shadow-glow">
            <Icon name="check" className="h-4 w-4 text-white" />
          </span>
          AI Quality Score
        </h2>
        <Button size="sm" variant="outline" onClick={handleAnalyze} loading={loading} id="btn-run-quality-analysis">
          {report ? "Re-analyze" : "Analyze"}
        </Button>
      </div>

      {fetching ? (
        <div className="flex justify-center py-6"><Spinner /></div>
      ) : !report ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-white/10 py-10 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/5 text-slate-500">
            <Icon name="check" className="h-6 w-6" />
          </span>
          <p className="text-sm text-slate-400">No quality report yet.</p>
          <Button size="sm" onClick={handleAnalyze} loading={loading} id="btn-analyze-first">
            Run Analysis
          </Button>
        </div>
      ) : (
        <>
          {/* Score overview */}
          <div className="flex items-center gap-6">
            <ScoreRing score={report.overall_score} />
            <div className="flex-1 space-y-2">
              <div>
                <p className={cn("font-display text-3xl font-bold", scoreColor)}>
                  {Math.round(report.overall_score)}
                  <span className="ml-1 text-lg text-slate-500">/100</span>
                </p>
                <p className="text-xs text-slate-500">Overall quality score</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {report.problems.filter((p) => p.severity === "error").length > 0 && (
                  <span className="rounded-full border border-red-500/20 bg-red-500/10 px-2 py-0.5 text-[10px] font-medium text-red-400">
                    {report.problems.filter((p) => p.severity === "error").length} error(s)
                  </span>
                )}
                {report.problems.filter((p) => p.severity === "warning").length > 0 && (
                  <span className="rounded-full border border-amber-500/20 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-400">
                    {report.problems.filter((p) => p.severity === "warning").length} warning(s)
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Dimension breakdown */}
          <div className="space-y-3 border-t border-white/8 pt-4">
            <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Dimension Scores</p>
            <div className="space-y-3">
              {report.dimensions.map((d) => (
                <DimensionBar key={d.name} name={d.name} score={d.score} details={d.details} />
              ))}
            </div>
          </div>

          {/* Problems */}
          {report.problems.length > 0 && (
            <div className="space-y-2 border-t border-white/8 pt-4">
              <p className="text-xs font-medium uppercase tracking-wider text-slate-500">
                Detected Problems ({report.problems.length})
              </p>
              <div className="space-y-1.5">
                {(showAll ? report.problems : report.problems.slice(0, 3)).map((p) => (
                  <ProblemItem key={p.code} problem={p} />
                ))}
                {report.problems.length > 3 && (
                  <button
                    type="button"
                    onClick={() => setShowAll((v) => !v)}
                    className="text-xs font-medium text-brand-300 hover:underline"
                  >
                    {showAll ? "Show fewer" : `Show ${report.problems.length - 3} more…`}
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Recommendations */}
          {report.recommendations.length > 0 && (
            <div className="space-y-2 border-t border-white/8 pt-4">
              <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Recommendations</p>
              <ul className="space-y-1">
                {report.recommendations.map((r, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-slate-400">
                    <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-400" />
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}
