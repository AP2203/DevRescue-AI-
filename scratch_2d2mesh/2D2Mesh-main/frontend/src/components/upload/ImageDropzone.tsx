import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "../../lib/format";
import { ALLOWED_EXTENSIONS, ALLOWED_MIME_TYPES, MAX_UPLOAD_MB } from "../../lib/constants";
import { Icon } from "../ui/Icon";

export type DroppedImage = {
  file: File;
  previewUrl: string;
  width: number;
  height: number;
};

function fileExtension(name: string): string {
  return name.includes(".") ? name.split(".").pop()!.toLowerCase() : "";
}

function readDimensions(file: File): Promise<{ width: number; height: number }> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight });
    img.onerror = () => resolve({ width: 0, height: 0 });
    img.src = url;
  });
}

export function ImageDropzone({
  value,
  onSelect,
  onClear,
  disabled = false,
}: {
  value?: DroppedImage | null;
  onSelect: (image: DroppedImage) => void;
  onClear?: () => void;
  disabled?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validate = useCallback((file: File): string | null => {
    const ext = fileExtension(file.name);
    if (!ALLOWED_MIME_TYPES.includes(file.type) && !ALLOWED_EXTENSIONS.includes(ext)) {
      return "Unsupported file type. Upload JPG, PNG or WEBP.";
    }
    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
      return `File exceeds the ${MAX_UPLOAD_MB} MB maximum size.`;
    }
    return null;
  }, []);

  const handleFile = useCallback(
    async (file?: File | null) => {
      if (!file) return;
      setError(null);
      const problem = validate(file);
      if (problem) {
        setError(problem);
        return;
      }
      const { width, height } = await readDimensions(file);
      onSelect({
        file,
        previewUrl: URL.createObjectURL(file),
        width,
        height,
      });
    },
    [onSelect, validate],
  );

  useEffect(() => {
    return () => {
      if (value?.previewUrl) URL.revokeObjectURL(value.previewUrl);
    };
  }, [value?.previewUrl]);

  return (
    <div className="space-y-2">
      <div
        role="button"
        tabIndex={0}
        aria-disabled={disabled}
        aria-label="Upload an image file"
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
        }}
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          void handleFile(event.dataTransfer.files?.[0]);
        }}
        className={cn(
          "group relative flex min-h-[240px] cursor-pointer flex-col items-center justify-center gap-4 overflow-hidden rounded-2xl border-2 border-dashed p-6 text-center transition-all duration-300",
          dragging
            ? "border-brand-400 bg-brand-500/10 shadow-glow scale-[1.01]"
            : "border-white/15 bg-white/[0.03] hover:border-brand-400/40 hover:bg-white/[0.05] hover:shadow-card",
          disabled && "pointer-events-none opacity-60",
        )}
      >
        {/* Corner glow */}
        <div className="pointer-events-none absolute -top-16 -right-16 h-40 w-40 rounded-full bg-brand-500/20 blur-3xl transition-opacity group-hover:opacity-100 opacity-50" />

        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-gradient text-white shadow-glow transition-transform duration-300 group-hover:scale-110 group-hover:rotate-3">
          <Icon name="upload" className="h-8 w-8" strokeWidth={1.6} />
        </div>
        <div className="relative z-10">
          <p className="text-base font-semibold text-white">
            Drag &amp; drop your image here
          </p>
          <p className="mt-1 text-xs text-slate-400">
            or click to browse · <span className="font-mono">JPG, PNG, WEBP</span> · max {MAX_UPLOAD_MB} MB
          </p>
        </div>
        {value && (
          <div className="mt-2 flex items-center gap-3 rounded-xl border border-white/10 bg-ink-800/80 px-3 py-2">
            <img
              src={value.previewUrl}
              alt="Selected preview"
              className="h-12 w-12 rounded-lg object-cover"
            />
            <div className="text-left">
              <p className="max-w-[220px] truncate text-sm font-medium text-white">
                {value.file.name}
              </p>
              <p className="text-xs text-slate-400">
                {(value.file.size / 1024).toFixed(1)} KB · {value.width}×{value.height}
              </p>
            </div>
            <button
              type="button"
              aria-label="Remove image"
              onClick={(event) => {
                event.stopPropagation();
                onClear?.();
              }}
              className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-white/5 hover:text-red-400"
            >
              <Icon name="close" className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <input
        ref={inputRef}
        type="file"
        accept={ALLOWED_MIME_TYPES.join(",")}
        className="hidden"
        onChange={(event) => {
          void handleFile(event.target.files?.[0]);
          event.target.value = "";
        }}
      />
    </div>
  );
}