import { useState } from "react";
import { modelApi } from "../../api/models";
import { useToast } from "../../hooks/useToast";
import { extractApiError } from "../../api/client";
import { formatBytes } from "../../lib/format";
import { Icon } from "../ui/Icon";
import type { ModelSummary } from "../../types/project";

type ExportFormat = "glb" | "gltf" | "obj" | "stl";

type FormatConfig = {
  id: ExportFormat;
  label: string;
  description: string;
  iconColor: string;
  available: (summary: ModelSummary) => boolean;
};

const FORMATS: FormatConfig[] = [
  {
    id: "glb",
    label: "GLB",
    description: "Binary glTF · Universal",
    iconColor: "text-brand-300",
    available: () => true,
  },
  {
    id: "gltf",
    label: "GLTF",
    description: "JSON glTF 2.0",
    iconColor: "text-accent-300",
    available: (s) => Boolean(s.download_gltf_url),
  },
  {
    id: "obj",
    label: "OBJ",
    description: "Wavefront · Legacy",
    iconColor: "text-purple-300",
    available: (s) => Boolean((s as any).download_obj_url),
  },
  {
    id: "stl",
    label: "STL",
    description: "3D Printing · Slicer",
    iconColor: "text-amber-300",
    available: () => true,
  },
];

export function ExportPanel({
  projectId,
  modelSummary,
  projectName,
}: {
  projectId: string;
  modelSummary: ModelSummary;
  projectName: string;
}) {
  const { toast } = useToast();
  const [downloading, setDownloading] = useState<ExportFormat | null>(null);

  const handleDownload = async (format: ExportFormat) => {
    if (downloading) return;
    setDownloading(format);
    try {
      const name = projectName.replace(/\s+/g, "_").toLowerCase();
      if (format === "glb") {
        await modelApi.downloadGlb(projectId, `${name}.glb`);
      } else if (format === "gltf") {
        await modelApi.downloadGltf(projectId, `${name}.gltf`);
      } else if (format === "obj") {
        const { client } = await import("../../api/client");
        const { downloadBlob } = await import("../../lib/format");
        const { data } = await client.get(`/projects/${projectId}/model/obj`, { responseType: "blob" });
        downloadBlob(data as Blob, `${name}.obj`);
      } else if (format === "stl") {
        await modelApi.downloadStl(projectId, `${name}.stl`);
      }
      toast("success", `${format.toUpperCase()} downloaded`);
    } catch (err) {
      toast("error", "Download failed", { description: extractApiError(err) });
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="panel p-5 space-y-4">
      {/* Header */}
      <h2 className="flex items-center gap-2 font-display text-base font-semibold text-white">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-accent-500 to-cyan-400 shadow-glow">
          <Icon name="download" className="h-4 w-4 text-white" />
        </span>
        Export Model
      </h2>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {FORMATS.map((fmt) => {
          const isAvailable = fmt.available(modelSummary);
          const isLoading = downloading === fmt.id;
          return (
            <button
              key={fmt.id}
              type="button"
              id={`btn-export-${fmt.id}`}
              disabled={!isAvailable || Boolean(downloading)}
              onClick={() => isAvailable && void handleDownload(fmt.id)}
              className="group relative flex flex-col items-center gap-2 rounded-xl border border-white/10 bg-white/[0.02] p-4 transition-all hover:border-brand-400/40 hover:bg-brand-500/10 disabled:pointer-events-none disabled:opacity-40"
            >
              {isLoading ? (
                <div className="flex h-6 w-6 items-center justify-center">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                </div>
              ) : (
                <Icon name="cube" className={`h-6 w-6 transition-transform group-hover:scale-110 ${fmt.iconColor}`} />
              )}
              <span className="text-sm font-semibold text-white">{fmt.label}</span>
              <span className="text-center font-mono text-[10px] text-slate-500">{fmt.description}</span>
              {!isAvailable && (
                <span className="absolute right-1.5 top-1.5 rounded-full bg-white/5 px-1.5 py-0.5 text-[9px] text-slate-600">
                  N/A
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
        <Icon name="info" className="h-3.5 w-3.5" />
        File size: <span className="font-mono font-medium text-slate-400">{formatBytes(modelSummary.size_bytes)}</span>
        · Open-standard formats ready for any 3D tool.
      </div>
    </div>
  );
}
