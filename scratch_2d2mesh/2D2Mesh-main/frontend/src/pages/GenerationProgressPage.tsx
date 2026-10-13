import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { jobsApi } from "../api/jobs";
import { useToast } from "../hooks/useToast";
import { useAppStore } from "../store/appStore";
import { extractApiError } from "../api/client";
import { formatDate, relativeTime } from "../lib/format";
import { Button } from "../components/ui/Button";
import { ProgressBar } from "../components/ui/ProgressBar";
import { Badge } from "../components/ui/Badge";
import { Alert } from "../components/ui/Feedback";
import { Spinner } from "../components/ui/Spinner";
import { Icon, type IconName } from "../components/ui/Icon";
import type { Job } from "../types/job";

type Stage = {
  key: string;
  label: string;
  detail: string;
  icon: IconName;
};

const STAGES: Stage[] = [
  { key: "preprocessing", label: "Preprocessing image", detail: "Normalizing input, extracting features", icon: "image" },
  { key: "reconstruction", label: "Generating geometry", detail: "Reconstructing 3D shape & topology", icon: "cube" },
  { key: "texturing", label: "Generating texture", detail: "Baking PBR albedo, normal & roughness", icon: "layers" },
  { key: "postprocessing", label: "Optimizing mesh", detail: "Remeshing, decimating, welding verts", icon: "sparkles" },
  { key: "exporting", label: "Finalizing", detail: "Compressing & writing GLB / GLTF", icon: "download" },
];

const POLL_INTERVAL = 2000;

const statusMeta: Record<string, { label: string; tone: "green" | "red" | "amber" | "gray" | "blue" }> = {
  succeeded: { label: "Completed", tone: "green" },
  processing: { label: "Processing", tone: "blue" },
  queued: { label: "Queued", tone: "amber" },
  failed: { label: "Failed", tone: "red" },
  cancelled: { label: "Cancelled", tone: "gray" },
};

function stageIndex(job: Job | null): number {
  if (!job?.stage) return -1;
  const idx = STAGES.findIndex((s) => s.key === job.stage);
  if (idx >= 0) return idx;
  if (job.status === "succeeded") return STAGES.length - 1;
  return -1;
}

export function GenerationProgressPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { toast } = useToast();
  const setGenerationStatus = useAppStore((state) => state.setGenerationStatus);
  const resetGeneration = useAppStore((state) => state.resetGeneration);

  const projectId = (location.state as { projectId?: string } | null)?.projectId;
  const projectName = (location.state as { projectName?: string } | null)?.projectName;

  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchJob = useCallback(async () => {
    if (!jobId) return;
    try {
      const data = await jobsApi.get(jobId);
      setJob(data);
      setError(null);
      setGenerationStatus({
        jobId: data.id,
        status: data.status,
        stage: data.stage,
        progress: data.progress,
        message: data.message,
      });

      if (data.status === "succeeded") {
        if (pollingRef.current) clearInterval(pollingRef.current);
        toast("success", "3D model generated!", {
          description: "Your model is ready to view and download.",
        });
        const pid = data.project_id ?? projectId;
        if (pid) {
          setTimeout(() => navigate(`/projects/${pid}`, { replace: true }), 1800);
        }
      } else if (data.status === "failed" || data.status === "cancelled") {
        if (pollingRef.current) clearInterval(pollingRef.current);
      }
    } catch (err) {
      setError(extractApiError(err));
    } finally {
      setLoading(false);
    }
  }, [jobId, navigate, projectId, setGenerationStatus, toast]);

  useEffect(() => {
    fetchJob();
    pollingRef.current = setInterval(fetchJob, POLL_INTERVAL);
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
      resetGeneration();
    };
  }, [fetchJob, resetGeneration]);

  const handleRetry = async () => {
    if (!jobId) return;
    setRetrying(true);
    try {
      const result = await jobsApi.retry(jobId);
      toast("info", "Generation retried", { description: result.message });
      navigate(`/generate/progress/${result.job.id}`, {
        state: { projectId, projectName },
        replace: true,
      });
    } catch (err) {
      toast("error", "Retry failed", { description: extractApiError(err) });
    } finally {
      setRetrying(false);
    }
  };

  const handleCancel = async () => {
    if (!jobId) return;
    setCancelling(true);
    try {
      await jobsApi.cancel(jobId);
      toast("info", "Generation cancelled");
    } catch (err) {
      toast("error", "Cancel failed", { description: extractApiError(err) });
    } finally {
      setCancelling(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Spinner className="h-8 w-8" />
          <p className="text-sm text-slate-400">Loading job…</p>
        </div>
      </div>
    );
  }

  if (error && !job) {
    return (
      <div className="mx-auto max-w-lg pt-16">
        <Alert tone="error" title="Failed to load job">{error}</Alert>
        <div className="mt-4 flex gap-3">
          <Button variant="outline" onClick={() => navigate("/dashboard")}>
            Back to Dashboard
          </Button>
          <Button onClick={fetchJob}>Retry</Button>
        </div>
      </div>
    );
  }

  if (!job) return null;

  const isActive = job.status === "queued" || job.status === "processing";
  const isFailed = job.status === "failed";
  const isSucceeded = job.status === "succeeded";
  const isCancelled = job.status === "cancelled";
  const meta = statusMeta[job.status] ?? statusMeta.processing;
  const currentStage = stageIndex(job);

  return (
    <div className="mx-auto max-w-5xl space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="font-display text-2xl font-bold tracking-tight text-white">
              {isSucceeded
                ? "Generation complete"
                : isFailed
                  ? "Generation failed"
                  : isCancelled
                    ? "Generation cancelled"
                    : "Generating 3D model"}
            </h1>
            <Badge tone={meta.tone} dot>
              {meta.label}
            </Badge>
          </div>
          {projectName && (
            <p className="mt-1 text-slate-400">
              Project: <span className="font-medium text-slate-200">{projectName}</span>
            </p>
          )}
        </div>
        {job.retry_count > 0 && (
          <span className="rounded-md border border-white/10 px-2 py-1 font-mono text-xs text-slate-400">
            retry #{job.retry_count}
          </span>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.15fr_1fr]">
        {/* Pipeline stages */}
        <div className="panel p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="flex items-center gap-2 font-display text-base font-semibold text-white">
              <Icon name="cpu" className="h-4 w-4 text-brand-300" /> Pipeline
            </h2>
            <span className="font-mono text-xs text-slate-400">
              model: {job.ai_model}
            </span>
          </div>

          {/* Progress */}
          <div className="mb-6">
            <ProgressBar
              value={job.progress}
              tone={isSucceeded ? "success" : isFailed ? "danger" : "brand"}
              label="Overall progress"
            />
            <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
              <span className="flex items-center gap-1.5">
                {isActive && <span className="glow-dot h-1.5 w-1.5 bg-brand-400 animate-pulse" />}
                {job.stage
                  ? STAGES.find((s) => s.key === job.stage)?.label ?? job.stage
                  : isSucceeded
                    ? "Done"
                    : "Queued…"}
              </span>
              <span className="font-mono font-medium text-slate-300">{Math.round(job.progress)}%</span>
            </div>
            {job.message && (
              <p className="mt-1 text-xs italic text-slate-500">{job.message}</p>
            )}
          </div>

          {/* Stage list */}
          <ol className="space-y-2.5">
            {STAGES.map((stage, i) => {
              const state = isSucceeded && i === STAGES.length - 1 ? "done" : i < currentStage || isSucceeded ? "done" : i === currentStage ? "active" : "todo";
              return (
                <li
                  key={stage.key}
                  className={
                    state === "todo"
                      ? "flex items-center gap-3 rounded-xl border border-white/5 bg-white/[0.01] px-4 py-3 opacity-50"
                      : "flex items-center gap-3 rounded-xl border px-4 py-3 " +
                        (state === "active"
                          ? "border-brand-400/40 bg-brand-500/10 shadow-glow"
                          : "border-emerald-500/25 bg-emerald-500/[0.06]")
                  }
                >
                  <span
                    className={
                      state === "active"
                        ? "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-gradient text-white shadow-glow"
                        : state === "done"
                          ? "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-500/15 text-emerald-300"
                          : "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/10 text-slate-600"
                    }
                  >
                    {state === "active" ? (
                      <Spinner size="sm" />
                    ) : state === "done" ? (
                      <Icon name="check" className="h-4 w-4" strokeWidth={2.4} />
                    ) : (
                      <Icon name={stage.icon} className="h-4 w-4" />
                    )}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className={`text-sm font-medium ${state === "todo" ? "text-slate-500" : "text-white"}`}>
                      {stage.label}
                    </p>
                    <p className="truncate text-xs text-slate-500">{stage.detail}</p>
                  </div>
                  <span className="font-mono text-[10px] text-slate-600">{`0${i + 1}`}</span>
                </li>
              );
            })}
          </ol>
        </div>

        {/* Status / details */}
        <div className="space-y-5">
          <div className="panel p-5">
            <h2 className="flex items-center gap-2 font-display text-base font-semibold text-white">
              <Icon name="clock" className="h-4 w-4 text-accent-300" /> Job details
            </h2>
            <dl className="mt-4 space-y-3 text-sm">
              <Detail label="Created" value={`${formatDate(job.created_at)} (${relativeTime(job.created_at)})`} />
              <Detail label="Started" value={job.started_at ? relativeTime(job.started_at) : "—"} />
              <Detail label="Completed" value={job.completed_at ? relativeTime(job.completed_at) : "—"} />
              <Detail label="AI model" value={job.ai_model} mono />
              <Detail label="Resolution" value={String(job.settings?.resolution ?? 512)} />
              <Detail label="Texture quality" value={job.settings?.texture_quality ?? "—"} />
            </dl>
          </div>

          {isFailed && job.error && (
            <Alert tone="error" title="Generation error">{job.error}</Alert>
          )}
          {isSucceeded && (
            <Alert tone="success" title="Model ready">
              Your 3D model has been generated. Redirecting to the project…
            </Alert>
          )}
          {isCancelled && (
            <Alert tone="warning" title="Cancelled">This generation was cancelled.</Alert>
          )}

          {/* Actions */}
          <div className="panel flex flex-wrap gap-2 p-4">
            {isActive && (
              <Button
                variant="outline"
                onClick={handleCancel}
                loading={cancelling}
                className="border-red-500/30 text-red-300 hover:bg-red-500/10"
              >
                <Icon name="close" className="h-4 w-4" /> Cancel
              </Button>
            )}
            {(isFailed || isCancelled) && (
              <Button onClick={handleRetry} loading={retrying}>
                <Icon name="refresh" className="h-4 w-4" /> Retry generation
              </Button>
            )}
            {isSucceeded && (projectId || job.project_id) && (
              <>
                <Link to={`/projects/${projectId ?? job.project_id}`}>
                  <Button>
                    <Icon name="projects" className="h-4 w-4" /> View project
                  </Button>
                </Link>
                <Link to={`/projects/${projectId ?? job.project_id}/viewer`}>
                  <Button variant="outline">
                    <Icon name="cube" className="h-4 w-4" /> Open 3D viewer
                  </Button>
                </Link>
              </>
            )}
            <Link to="/dashboard">
              <Button variant="ghost">Back to dashboard</Button>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

function Detail({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-xs uppercase tracking-wider text-slate-500">{label}</dt>
      <dd className={`text-right text-sm text-slate-300 ${mono ? "font-mono" : ""}`}>{value}</dd>
    </div>
  );
}