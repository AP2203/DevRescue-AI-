import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { useToast } from "../hooks/useToast";
import { uploadsApi } from "../api/uploads";
import { projectsApi } from "../api/projects";
import { jobsApi } from "../api/jobs";
import { extractApiError } from "../api/client";
import { useAppStore } from "../store/appStore";
import { ImageDropzone, type DroppedImage } from "../components/upload/ImageDropzone";
import { Button } from "../components/ui/Button";
import { Input, Select } from "../components/ui/Field";
import { ProgressBar } from "../components/ui/ProgressBar";
import { Alert } from "../components/ui/Feedback";
import { Icon } from "../components/ui/Icon";
import { MODEL_OPTIONS, RESOLUTION_OPTIONS, TEXTURE_QUALITY_OPTIONS } from "../lib/constants";
import { formatBytes } from "../lib/format";
import type { GenerationSettings } from "../types/job";

type Step = "upload" | "configure" | "launching";

export function GeneratePage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { setUploadStatus, resetUpload, setGenerationStatus } = useAppStore();

  const [step, setStep] = useState<Step>("upload");
  const [image, setImage] = useState<DroppedImage | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [projectName, setProjectName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [launching, setLaunching] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      abortRef.current = null;
    };
  }, []);

  const [settings, setSettings] = useState<GenerationSettings>({
    model: "auto",
    resolution: 512,
    texture_quality: "medium",
    remesh: true,
    simplify_target: null,
  });

  const handleImageSelect = useCallback((img: DroppedImage) => {
    setImage(img);
    setError(null);
    const baseName = img.file.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ");
    setProjectName(baseName.charAt(0).toUpperCase() + baseName.slice(1));
  }, []);

  const handleClearImage = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setImage(null);
    setUploadId(null);
    setUploadProgress(0);
    setStep("upload");
    resetUpload();
  }, [resetUpload]);

  const handleCancelUpload = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setUploading(false);
    setUploadProgress(0);
    resetUpload();
    toast("info", "Upload cancelled");
  }, [resetUpload, toast]);

  const handleUpload = async () => {
    if (!image) return;
    const controller = new AbortController();
    abortRef.current = controller;
    setUploading(true);
    setUploadProgress(0);
    setError(null);
    try {
      const upload = await uploadsApi.upload(
        image.file,
        (percent) => {
          setUploadProgress(percent);
          setUploadStatus({ uploading: true, progress: percent, fileName: image.file.name });
        },
        controller.signal,
      );
      setUploadId(upload.id);
      setUploadStatus({ uploading: false, progress: 100, fileName: null });
      setStep("configure");
      toast("success", "Image uploaded", { description: "Now configure your generation settings." });
    } catch (err) {
      if (axios.isCancel(err)) return;
      setError(extractApiError(err));
    } finally {
      abortRef.current = null;
      setUploading(false);
    }
  };

  const handleLaunch = async () => {
    if (!uploadId) return;
    setLaunching(true);
    setError(null);
    try {
      const project = await projectsApi.create({
        name: projectName || "Untitled Project",
        description: `Generated from ${image?.file.name ?? "uploaded image"}`,
      });

      const job = await jobsApi.create(project.id, {
        upload_id: uploadId,
        name: projectName || "Untitled",
        settings,
      });

      setGenerationStatus({
        jobId: job.id,
        status: job.status,
        stage: job.stage,
        progress: job.progress,
        message: job.message,
      });

      toast("success", "Generation started!", {
        description: "Your 3D model is being generated.",
      });

      navigate(`/generate/progress/${job.id}`, {
        state: { projectId: project.id, projectName: project.name },
      });
    } catch (err) {
      setError(extractApiError(err));
    } finally {
      setLaunching(false);
    }
  };

  const updateSetting = <K extends keyof GenerationSettings>(
    key: K,
    value: GenerationSettings[K],
  ) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold tracking-tight text-white">Generate 3D Model</h1>
          <p className="mt-1 text-slate-400">
            Upload an image and let the AI reconstruct a 3D model.
          </p>
        </div>
        <StepStepper step={step} />
      </div>

      {error && <Alert tone="error" title="Error">{error}</Alert>}

      <div className="grid gap-6 lg:grid-cols-[1.05fr_1fr]">
        {/* LEFT: upload + settings */}
        <div className="space-y-5">
          {step === "upload" && (
            <div className="panel p-5">
              <div className="mb-4 flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500/15 text-brand-300">
                  <Icon name="image" className="h-4 w-4" />
                </span>
                <div>
                  <h2 className="font-display text-base font-semibold text-white">Source image</h2>
                  <p className="text-xs text-slate-500">Start with a clear, well-lit photo</p>
                </div>
              </div>

              <ImageDropzone
                value={image}
                onSelect={handleImageSelect}
                onClear={handleClearImage}
                disabled={uploading}
              />

              {image && (
                <div className="mt-4 space-y-4">
                  <div className="overflow-hidden rounded-xl border border-white/10 bg-ink-800/50">
                    <img src={image.previewUrl} alt="Preview" className="mx-auto max-h-64 object-contain" />
                  </div>

                  {uploading && (
                    <div className="space-y-2">
                      <ProgressBar
                        value={uploadProgress}
                        label="Uploading image"
                      />
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleCancelUpload}
                        className="border-red-500/30 text-red-300 hover:bg-red-500/10"
                        fullWidth
                      >
                        <Icon name="close" className="h-3.5 w-3.5" /> Cancel upload
                      </Button>
                    </div>
                  )}

                  <Button onClick={handleUpload} loading={uploading} fullWidth disabled={uploading}>
                    <Icon name="upload" className="h-4 w-4" />
                    {uploading ? "Uploading..." : "Upload image & continue"}
                  </Button>
                </div>
              )}
            </div>
          )}

          {step === "configure" && (
            <div className="panel p-5">
              <div className="mb-4 flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-500/15 text-accent-300">
                  <Icon name="settings" className="h-4 w-4" />
                </span>
                <div>
                  <h2 className="font-display text-base font-semibold text-white">Generation settings</h2>
                  <p className="text-xs text-slate-500">Tune how the AI reconstructs your model</p>
                </div>
              </div>

              <div className="space-y-4">
                <Input
                  label="Project Name"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  placeholder="My awesome model"
                />

                <div className="grid gap-4 sm:grid-cols-3">
                  <Select
                    label="AI Model"
                    value={settings.model}
                    onChange={(e) => updateSetting("model", e.target.value)}
                  >
                    {MODEL_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </Select>

                  <Select
                    label="Resolution"
                    value={String(settings.resolution)}
                    onChange={(e) => updateSetting("resolution", Number(e.target.value))}
                  >
                    {RESOLUTION_OPTIONS.map((opt) => (
                      <option key={opt.value} value={String(opt.value)}>
                        {opt.label}
                      </option>
                    ))}
                  </Select>

                  <Select
                    label="Texture Quality"
                    value={settings.texture_quality}
                    onChange={(e) =>
                      updateSetting("texture_quality", e.target.value as "low" | "medium" | "high")
                    }
                  >
                    {TEXTURE_QUALITY_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </Select>
                </div>

                <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-white/10 bg-white/[0.02] p-3.5 transition-colors hover:border-brand-400/30">
                  <input
                    type="checkbox"
                    checked={settings.remesh}
                    onChange={(e) => updateSetting("remesh", e.target.checked)}
                    className="mt-0.5 h-4 w-4 rounded border-white/20 bg-ink-800 accent-brand-500"
                  />
                  <div>
                    <p className="text-sm font-medium text-white">Remesh / smooth geometry</p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      Apply Laplacian smoothing for cleaner surfaces
                    </p>
                  </div>
                </label>

                <div className="flex gap-3 pt-2">
                  <Button variant="outline" onClick={() => setStep("upload")} className="flex-1">
                    <Icon name="chevronLeft" className="h-4 w-4" /> Back
                  </Button>
                  <Button
                    onClick={handleLaunch}
                    loading={launching}
                    disabled={launching || !projectName.trim()}
                    className="flex-1"
                  >
                    <Icon name="sparkles" className="h-4 w-4" /> Start generation
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* RIGHT: live preview + status */}
        <div className="panel overflow-hidden lg:sticky lg:top-20 self-start">
          <div className="flex items-center justify-between border-b border-white/8 px-4 py-3">
            <span className="flex items-center gap-2 text-sm font-medium text-slate-300">
              <Icon name="cube" className="h-4 w-4 text-brand-300" /> Output preview
            </span>
            <span className="flex items-center gap-1.5 rounded-md bg-white/5 px-2 py-0.5 font-mono text-[10px] text-slate-400">
              GLB
            </span>
          </div>

          <div className="relative flex h-72 items-center justify-center overflow-hidden bg-ink-900/60 sm:h-96">
            <div className="absolute inset-0 bg-aurora" aria-hidden />

            {step === "upload" && (
              <div className="relative z-10 flex flex-col items-center gap-3 text-center">
                <span className="flex h-16 w-16 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.03]">
                  <Icon name="cube" className="h-8 w-8 text-slate-600" strokeWidth={1.2} />
                </span>
                <p className="max-w-[240px] text-sm text-slate-500">
                  Your generated model preview will appear here
                </p>
              </div>
            )}

            {step === "configure" && image && (
              <>
                <img
                  src={image.previewUrl}
                  alt="Source preview"
                  className="absolute inset-0 h-full w-full object-cover opacity-20 blur-sm"
                />
                <div className="relative z-10 flex h-52 w-52 items-center justify-center animate-float">
                  <span className="absolute inset-0 rounded-2xl bg-brand-500/20 blur-2xl" aria-hidden />
                  <Icon name="cube" className="relative h-20 w-20 text-brand-300/70 drop-shadow-[0_0_20px_rgba(124,58,237,0.6)]" strokeWidth={1.1} />
                </div>
                <div className="absolute bottom-4 left-4 z-10 flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-[11px] font-medium text-emerald-300 backdrop-blur">
                  <span className="glow-dot h-1.5 w-1.5 bg-emerald-400" /> Ready to generate
                </div>
              </>
            )}

            {step === "launching" && (
              <div className="relative z-10 flex flex-col items-center gap-3">
                <span className="h-10 w-10 animate-spin rounded-full border-2 border-brand-500 border-t-transparent shadow-glow" />
                <p className="text-sm text-slate-400">Launching generation…</p>
              </div>
            )}

            {/* Scanlines */}
            <div className="scanlines absolute inset-0" aria-hidden />
          </div>

          {/* File info bar */}
          {image && (
            <div className="border-t border-white/8 px-4 py-3">
              <div className="flex items-center justify-between text-xs">
                <span className="flex min-w-0 items-center gap-2 text-slate-300">
                  <Icon name="image" className="h-4 w-4 shrink-0 text-slate-500" />
                  <span className="truncate">{image.file.name}</span>
                </span>
                <span className="ml-3 shrink-0 font-mono text-slate-500">
                  {formatBytes(image.file.size)} · {image.width}×{image.height}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── Helpers ─── */

function StepStepper({ step }: { step: Step }) {
  const steps: { label: string; state: "done" | "active" | "todo" }[] = [
    { label: "Upload", state: step === "upload" ? "active" : "done" },
    { label: "Configure", state: step === "configure" ? "active" : step === "upload" ? "todo" : "done" },
    { label: "Generate", state: step === "launching" ? "active" : "todo" },
  ];
  return (
    <ol className="hidden items-center gap-2 sm:flex" aria-label="Generation steps">
      {steps.map((s, i) => (
        <li key={s.label} className="flex items-center gap-2">
          {i > 0 && <span className="h-px w-6 bg-white/10" aria-hidden />}
          <span
            className={
              s.state === "active"
                ? "flex h-8 w-8 items-center justify-center rounded-full bg-brand-gradient text-xs font-bold text-white shadow-glow"
                : s.state === "done"
                  ? "flex h-8 w-8 items-center justify-center rounded-full border border-emerald-500/40 bg-emerald-500/10 text-xs text-emerald-300"
                  : "flex h-8 w-8 items-center justify-center rounded-full border border-white/10 text-xs text-slate-500"
            }
          >
            {s.state === "done" ? <Icon name="check" className="h-4 w-4" /> : i + 1}
          </span>
          <span className={`text-xs font-medium ${s.state === "active" ? "text-white" : "text-slate-500"}`}>
            {s.label}
          </span>
        </li>
      ))}
    </ol>
  );
}