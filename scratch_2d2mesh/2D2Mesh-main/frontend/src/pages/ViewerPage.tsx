import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { modelApi } from "../api/models";
import { projectsApi } from "../api/projects";
import { useToast } from "../hooks/useToast";
import { extractApiError } from "../api/client";
import { formatBytes } from "../lib/format";
import { ModelViewer } from "../components/viewer/ModelViewer";
import { Button } from "../components/ui/Button";
import { Spinner } from "../components/ui/Spinner";
import { Alert } from "../components/ui/Feedback";
import { Icon } from "../components/ui/Icon";
import type { ProjectDetail } from "../types/project";

export function ViewerPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { toast } = useToast();

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [modelUrl, setModelUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloadingGlb, setDownloadingGlb] = useState(false);
  const [downloadingGltf, setDownloadingGltf] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;

    const load = async () => {
      try {
        const [detail, glb] = await Promise.all([
          projectsApi.get(projectId),
          modelApi.fetchGlbBlob(projectId),
        ]);
        if (!cancelled) {
          setProject(detail);
          setModelUrl(glb.url);
        }
      } catch (err) {
        if (!cancelled) setError(extractApiError(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();

    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    return () => {
      if (modelUrl) URL.revokeObjectURL(modelUrl);
    };
  }, [modelUrl]);

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

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="relative">
            <Spinner className="h-10 w-10" />
            <span className="absolute inset-0 -z-10 animate-pulse rounded-full bg-brand-500/20 blur-xl" aria-hidden />
          </div>
          <p className="text-sm text-slate-400">Loading 3D model…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-lg pt-16">
        <Alert tone="error" title="Failed to load model">{error}</Alert>
        <div className="mt-4">
          <Link to={`/projects/${projectId}`}>
            <Button variant="outline">
              <Icon name="chevronLeft" className="h-4 w-4" /> Back to Project
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Link to={`/projects/${projectId}`}>
            <Button variant="ghost" size="sm">
              <Icon name="chevronLeft" className="h-4 w-4" /> Back
            </Button>
          </Link>
          <div>
            <h1 className="font-display text-xl font-bold tracking-tight text-white">
              {project?.name ?? "3D Viewer"}
            </h1>
            {project?.model_summary && (
              <p className="text-sm text-slate-400">
                {formatBytes(project.model_summary.size_bytes)} · {project.model_summary.filename}
              </p>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleDownloadGlb} loading={downloadingGlb}>
            <Icon name="download" className="h-4 w-4" /> GLB
          </Button>
          <Button variant="outline" size="sm" onClick={handleDownloadGltf} loading={downloadingGltf}>
            <Icon name="download" className="h-4 w-4" /> GLTF
          </Button>
        </div>
      </div>

      {/* 3D Viewer */}
      {modelUrl ? (
        <ModelViewer
          modelUrl={modelUrl}
          fallbackStats={project?.model_summary?.stats}
          className="h-[calc(100vh-13rem)]"
        />
      ) : (
        <div className="flex h-96 items-center justify-center rounded-2xl border border-white/10 bg-ink-800">
          <p className="text-slate-500">No model available</p>
        </div>
      )}
    </div>
  );
}
