import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { projectsApi } from "../api/projects";
import { modelApi } from "../api/models";
import { jobsApi } from "../api/jobs";
import { useToast } from "../hooks/useToast";
import { useAppStore } from "../store/appStore";
import { extractApiError } from "../api/client";
import { formatBytes, formatDate, relativeTime, getAuthenticatedFileUrl } from "../lib/format";
import { ModelViewer } from "../components/viewer/ModelViewer";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Modal } from "../components/ui/Modal";
import { ProgressBar } from "../components/ui/ProgressBar";
import { Skeleton } from "../components/ui/Skeleton";
import { Alert } from "../components/ui/Feedback";
import { Icon } from "../components/ui/Icon";
import { AutoRepairPanel } from "../components/analysis/AutoRepairPanel";
import { OptimizationPanel } from "../components/analysis/OptimizationPanel";
import { ExportPanel } from "../components/analysis/ExportPanel";
import type { ProjectDetail } from "../types/project";

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

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const setCurrentProject = useAppStore((state) => state.setCurrentProject);
  const clearCurrentProject = useAppStore((state) => state.clearCurrentProject);

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [modelUrl, setModelUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Rename
  const [renaming, setRenaming] = useState(false);
  const [newName, setNewName] = useState("");
  const [savingName, setSavingName] = useState(false);

  // Delete
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Share
  const [shareOpen, setShareOpen] = useState(false);

  // Downloads
  const [downloadingGlb, setDownloadingGlb] = useState(false);
  const [downloadingGltf, setDownloadingGltf] = useState(false);

  const fetchProject = useCallback(async () => {
    if (!projectId) return;
    try {
      const detail = await projectsApi.get(projectId);
      setProject(detail);
      setNewName(detail.name);
      setCurrentProject(detail);

      if (detail.status === "ready" && detail.model_asset_id) {
        try {
          const glb = await modelApi.fetchGlbBlob(projectId);
          setModelUrl(glb.url);
        } catch {
          /* model fetch optional */
        }
      }
    } catch (err) {
      setError(extractApiError(err));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchProject();
    return () => {
      if (modelUrl) URL.revokeObjectURL(modelUrl);
      clearCurrentProject();
    };
  }, [fetchProject]);

  // Poll if processing
  useEffect(() => {
    if (!project || project.status !== "processing") return;
    const interval = setInterval(fetchProject, 3000);
    return () => clearInterval(interval);
  }, [project?.status, fetchProject]);

  const handleRename = async () => {
    if (!projectId || !newName.trim()) return;
    setSavingName(true);
    try {
      const updated = await projectsApi.rename(projectId, newName.trim());
      setProject((prev) => (prev ? { ...prev, name: updated.name } : prev));
      setRenaming(false);
      toast("success", "Project renamed");
    } catch (err) {
      toast("error", "Rename failed", { description: extractApiError(err) });
    } finally {
      setSavingName(false);
    }
  };

  const handleDelete = async () => {
    if (!projectId) return;
    setDeleting(true);
    try {
      await projectsApi.remove(projectId);
      toast("success", "Project deleted");
      navigate("/projects", { replace: true });
    } catch (err) {
      toast("error", "Delete failed", { description: extractApiError(err) });
    } finally {
      setDeleting(false);
      setShowDeleteModal(false);
    }
  };

  const handleRetry = async () => {
    if (!project?.last_job_id) return;
    try {
      const result = await jobsApi.retry(project.last_job_id);
      toast("info", "Generation retried");
      navigate(`/generate/progress/${result.job.id}`, {
        state: { projectId, projectName: project.name },
      });
    } catch (err) {
      toast("error", "Retry failed", { description: extractApiError(err) });
    }
  };

  const handleDownloadGlb = async () => {
    if (!projectId) return;
    setDownloadingGlb(true);
    try {
      await modelApi.downloadGlb(projectId, `${project?.name ?? "model"}.glb`);
      toast("success", "GLB downloaded");
    } catch (err) {
      toast("error", "Download failed", { description: extractApiError(err) });
    } finally {
      setDownloadingGlb(false);
    }
  };

  const handleDownloadGltf = async () => {
    if (!projectId) return;
    setDownloadingGltf(true);
    try {
      await modelApi.downloadGltf(projectId, `${project?.name ?? "model"}.gltf`);
      toast("success", "GLTF downloaded");
    } catch (err) {
      toast("error", "Download failed", { description: extractApiError(err) });
    } finally {
      setDownloadingGltf(false);
    }
  };

  if (loading) return <ProjectDetailSkeleton />;

  if (error) {
    return (
      <div className="mx-auto max-w-lg pt-16">
        <Alert tone="error" title="Failed to load project">{error}</Alert>
        <Link to="/projects" className="mt-4 inline-block">
          <Button variant="outline">
            <Icon name="chevronLeft" className="h-4 w-4" /> Back to Projects
          </Button>
        </Link>
      </div>
    );
  }

  if (!project) return null;

  const stats = project.model_summary?.stats;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <Link to="/projects" className="inline-flex items-center gap-1 text-sm text-slate-500 transition-colors hover:text-white">
            <Icon name="chevronLeft" className="h-4 w-4" /> Projects
          </Link>

          <div className="mt-2 flex flex-wrap items-center gap-3">
            {renaming ? (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleRename();
                    if (e.key === "Escape") setRenaming(false);
                  }}
                  autoFocus
                  className="rounded-xl border border-brand-400/60 bg-ink-800/70 px-3 py-1.5 font-display text-2xl font-bold text-white outline-none ring-2 ring-brand-500/25"
                />
                <Button size="sm" onClick={handleRename} loading={savingName}>Save</Button>
                <Button size="sm" variant="ghost" onClick={() => setRenaming(false)}>Cancel</Button>
              </div>
            ) : (
              <h1
                className="group flex cursor-pointer items-center gap-2 font-display text-2xl font-bold tracking-tight text-white transition-colors hover:text-brand-300"
                onClick={() => setRenaming(true)}
                title="Click to rename"
              >
                {project.name}
                <Icon name="settings" className="h-4 w-4 text-slate-600 transition-colors group-hover:text-brand-300" />
              </h1>
            )}
            <Badge tone={statusTone[project.status] ?? "gray"} dot>
              {statusLabel[project.status] ?? project.status}
            </Badge>
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-500">
            <span className="flex items-center gap-1.5">
              <Icon name="clock" className="h-3.5 w-3.5" /> Generated {relativeTime(project.updated_at)}
            </span>
            <span>·</span>
            <span>{formatDate(project.created_at)}</span>
            {project.description && (
              <>
                <span>·</span>
                <span className="line-clamp-1">{project.description}</span>
              </>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-wrap gap-2">
          {project.status === "ready" && (
            <>
              <Link to={`/projects/${projectId}/viewer`}>
                <Button variant="outline">
                  <Icon name="fullscreen" className="h-4 w-4" /> Open viewer
                </Button>
              </Link>
              <Button variant="outline" onClick={() => setShareOpen(true)}>
                <Icon name="share" className="h-4 w-4" /> Share
              </Button>
              <Button onClick={handleDownloadGlb} loading={downloadingGlb}>
                <Icon name="download" className="h-4 w-4" /> GLB
              </Button>
            </>
          )}
          {project.status === "failed" && (
            <Button onClick={handleRetry}>
              <Icon name="refresh" className="h-4 w-4" /> Retry
            </Button>
          )}
          {project.status === "no_model" && (
            <Link to="/generate">
              <Button>
                <Icon name="generate" className="h-4 w-4" /> Generate
              </Button>
            </Link>
          )}
          <Button
            variant="ghost"
            onClick={() => setShowDeleteModal(true)}
            className="text-red-400 hover:bg-red-500/10"
          >
            <Icon name="trash" className="h-4 w-4" /> Delete
          </Button>
        </div>
      </div>

      {/* Main grid */}
      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        {/* Left: viewer or status */}
        <div className="space-y-6">
          {project.status === "ready" && modelUrl ? (
            <ModelViewer
              modelUrl={modelUrl}
              fallbackStats={project.model_summary?.stats}
              className="h-[420px] lg:h-[520px]"
            />
          ) : project.status === "processing" ? (
            <div className="panel flex h-[340px] flex-col items-center justify-center gap-4">
              <span className="relative flex h-16 w-16 items-center justify-center">
                <span className="absolute inset-0 animate-pulse rounded-2xl bg-brand-500/20 blur-xl" aria-hidden />
                <span className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-gradient text-white shadow-glow">
                  <Icon name="cube" className="h-8 w-8" />
                </span>
              </span>
              <p className="font-display text-lg font-semibold text-white">Processing…</p>
              {project.last_job && (
                <div className="w-64">
                  <ProgressBar value={project.last_job.progress} label="Reconstructing geometry" />
                </div>
              )}
            </div>
          ) : project.status === "failed" ? (
            <div className="panel flex h-[340px] flex-col items-center justify-center gap-3 text-center px-6">
              <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-red-500/15 text-red-300">
                <Icon name="alert" className="h-7 w-7" />
              </span>
              <p className="font-display text-lg font-semibold text-white">Generation failed</p>
              {project.last_job?.error && (
                <p className="max-w-sm text-sm text-slate-400">{project.last_job.error}</p>
              )}
              <Button onClick={handleRetry} className="mt-2">
                <Icon name="refresh" className="h-4 w-4" /> Retry generation
              </Button>
            </div>
          ) : (
            <div className="panel flex h-[340px] flex-col items-center justify-center gap-3 text-center">
              <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/5 text-slate-500">
                <Icon name="cube" className="h-7 w-7" />
              </span>
              <p className="font-display text-lg font-semibold text-white">No model generated yet</p>
              <Link to="/generate">
                <Button><Icon name="generate" className="h-4 w-4" /> Generate</Button>
              </Link>
            </div>
          )}

          {/* Source image */}
          <div className="panel overflow-hidden">
            <div className="flex items-center justify-between border-b border-white/8 px-4 py-3">
              <h2 className="flex items-center gap-2 text-sm font-medium text-slate-300">
                <Icon name="image" className="h-4 w-4 text-slate-500" /> Source image
              </h2>
            </div>
            {project.image_url ? (
              <img src={getAuthenticatedFileUrl(project.image_url)} alt="Source" className="max-h-64 w-full object-contain" />
            ) : (
              <div className="flex h-32 items-center justify-center text-slate-500">No image available</div>
            )}
          </div>
        </div>

        {/* Right: model info */}
        <div className="space-y-6">
          {project.model_summary && (
            <div className="panel p-5">
              <h2 className="flex items-center gap-2 font-display text-base font-semibold text-white">
                <Icon name="layers" className="h-4 w-4 text-brand-300" /> Model information
              </h2>
              <dl className="mt-4 grid grid-cols-2 gap-4">
                <InfoItem label="Filename" value={project.model_summary.filename} />
                <InfoItem label="Format" value={project.model_summary.mime_type.split("/").pop() ?? "GLB"} mono />
                <InfoItem label="File size" value={formatBytes(project.model_summary.size_bytes)} />
                <InfoItem label="Generated" value={relativeTime(project.model_summary.created_at)} />
                {stats && (
                  <>
                    <InfoItem label="Polygons / triangles" value={(stats.triangles ?? 0)?.toLocaleString()} />
                    <InfoItem label="Vertices" value={(stats.vertices ?? 0)?.toLocaleString()} />
                    <InfoItem label="Texture" value={stats.has_texture ? "Baked PBR" : "None"} />
                    {stats.texture_size ? (
                      <InfoItem label="Texture size" value={`${stats.texture_size}px`} />
                    ) : (
                      <InfoItem label="Watertight" value={stats.watertight === undefined ? "—" : stats.watertight ? "Yes" : "No"} />
                    )}
                  </>
                )}
              </dl>
            </div>
          )}

          {/* Downloads */}
          {project.status === "ready" && (
            <div className="panel p-5">
              <h2 className="flex items-center gap-2 font-display text-base font-semibold text-white">
                <Icon name="download" className="h-4 w-4 text-accent-300" /> Download
              </h2>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={handleDownloadGlb}
                  disabled={downloadingGlb}
                  className="group flex flex-col items-center gap-2 rounded-xl border border-white/10 bg-white/[0.02] p-4 transition-all hover:border-brand-400/40 hover:bg-brand-500/10"
                >
                  <Icon name="cube" className="h-6 w-6 text-brand-300 transition-transform group-hover:scale-110" />
                  <span className="text-sm font-semibold text-white">GLB</span>
                  <span className="font-mono text-[10px] text-slate-500">
                    {project.model_summary ? formatBytes(project.model_summary.size_bytes) : "—"}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={handleDownloadGltf}
                  disabled={downloadingGltf}
                  className="group flex flex-col items-center gap-2 rounded-xl border border-white/10 bg-white/[0.02] p-4 transition-all hover:border-accent-400/40 hover:bg-accent-500/10"
                >
                  <Icon name="cube" className="h-6 w-6 text-accent-300 transition-transform group-hover:scale-110" />
                  <span className="text-sm font-semibold text-white">GLTF</span>
                  <span className="font-mono text-[10px] text-slate-500">glTF 2.0</span>
                </button>
              </div>
              <p className="mt-3 flex items-center gap-1.5 text-[11px] text-slate-500">
                <Icon name="info" className="h-3.5 w-3.5" /> Open-standard formats, ready for any engine.
              </p>
            </div>
          )}

          {/* Job history */}
          {project.last_job && (
            <div className="panel p-5">
              <h2 className="flex items-center gap-2 font-display text-base font-semibold text-white">
                <Icon name="clock" className="h-4 w-4 text-purple-300" /> Last job
              </h2>
              <dl className="mt-4 grid grid-cols-2 gap-4">
                <InfoItem label="Status" value={project.last_job.status} />
                <InfoItem label="AI model" value={project.last_job.ai_model} mono />
                {project.last_job.settings?.resolution && (
                  <InfoItem label="Resolution" value={`${project.last_job.settings.resolution}px`} />
                )}
                <InfoItem label="Progress" value={`${Math.round(project.last_job.progress)}%`} />
              </dl>
            </div>
          )}

          {/* Actions */}
          <div className="panel flex flex-wrap gap-2 p-4">
            {project.status === "ready" && (
              <Button variant="outline" onClick={() => setShareOpen(true)} className="flex-1">
                <Icon name="share" className="h-4 w-4" /> Share
              </Button>
            )}
            {project.last_job_id && (
              <Button
                variant="outline"
                onClick={() => navigate(`/generate/progress/${project.last_job_id}`)}
                className="flex-1"
              >
                <Icon name="refresh" className="h-4 w-4" /> Regenerate
              </Button>
            )}
            <Button
              variant="ghost"
              onClick={() => setShowDeleteModal(true)}
              className="flex-1 text-red-400 hover:bg-red-500/10"
            >
              <Icon name="trash" className="h-4 w-4" /> Delete
            </Button>
          </div>
        </div>
      </div>

      {/* ── AI Advanced Features ── */}
      {project.status === "ready" && projectId && (
        <div className="space-y-4">
          <div className="flex items-center gap-3 border-b border-white/8 pb-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-brand-gradient text-white shadow-glow">
              <Icon name="generate" className="h-4 w-4" />
            </span>
            <div>
              <h2 className="font-display text-lg font-semibold text-white">AI Model Tools</h2>
              <p className="text-xs text-slate-500">Repair and optimize your 3D model.</p>
            </div>
          </div>

          {/* Export panel spans full width */}
          {project.model_summary && (
            <ExportPanel
              projectId={projectId}
              modelSummary={project.model_summary}
              projectName={project.name}
            />
          )}

          {/* 2-column grid for AI tools */}
          <div className="grid gap-4 lg:grid-cols-2">
            <AutoRepairPanel projectId={projectId} onProjectUpdated={fetchProject} />
            <OptimizationPanel projectId={projectId} onProjectUpdated={fetchProject} />
          </div>
        </div>
      )}

      {/* Share modal */}
      <Modal open={shareOpen} onClose={() => setShareOpen(false)} title="Share project">
        <div className="space-y-4">
          <p className="text-sm text-slate-400">
            Share a link to <strong className="text-white">{project.name}</strong> with your team.
          </p>
          <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-ink-800/70 p-2">
            <input
              readOnly
              value={`${window.location.origin}/projects/${project.id}`}
              className="min-w-0 flex-1 bg-transparent px-2 font-mono text-xs text-slate-300 outline-none"
              onFocus={(e) => e.target.select()}
            />
            <Button
              size="sm"
              onClick={() => {
                void navigator.clipboard?.writeText(`${window.location.origin}/projects/${project.id}`);
                toast("success", "Link copied to clipboard");
              }}
            >
              Copy
            </Button>
          </div>
          <div className="flex justify-end">
            <Button variant="outline" onClick={() => setShareOpen(false)}>Done</Button>
          </div>
        </div>
      </Modal>

      {/* Delete modal */}
      <Modal open={showDeleteModal} onClose={() => setShowDeleteModal(false)} title="Delete project">
        <div className="space-y-4">
          <p className="text-sm text-slate-400">
            Are you sure you want to delete <strong className="text-white">{project.name}</strong>? This action
            cannot be undone. All associated images and models will be permanently removed.
          </p>
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={() => setShowDeleteModal(false)}>Cancel</Button>
            <Button
              onClick={handleDelete}
              loading={deleting}
              variant="danger"
            >
              <Icon name="trash" className="h-4 w-4" /> Delete Project
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

/* ─── Helpers ─── */

function InfoItem({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-0.5 line-clamp-1 text-sm font-medium text-slate-200 ${mono ? "font-mono" : ""}`}>{value}</p>
    </div>
  );
}

function ProjectDetailSkeleton() {
  return (
    <div className="space-y-6">
      <div>
        <Skeleton className="h-8 w-48" />
        <Skeleton className="mt-2 h-5 w-72" />
      </div>
      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <Skeleton className="h-[420px] rounded-2xl" />
        <div className="space-y-6">
          <Skeleton className="h-40 rounded-2xl" />
          <Skeleton className="h-40 rounded-2xl" />
        </div>
      </div>
    </div>
  );
}