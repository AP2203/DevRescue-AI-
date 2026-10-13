export type ViteEnv = {
  VITE_API_URL: string;
  VITE_APP_NAME: string;
};

export const API_URL: string = import.meta.env.VITE_API_URL ?? "/api/v1";
export const APP_NAME: string = import.meta.env.VITE_APP_NAME ?? "Vision3D AI";

export const MAX_UPLOAD_MB = 10;
export const ALLOWED_MIME_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const ALLOWED_EXTENSIONS = ["jpg", "jpeg", "png", "webp"];

export const MODEL_OPTIONS = [
  { value: "auto", label: "Auto (server default)" },
  { value: "mock", label: "Mock (dev, no GPU)" },
  { value: "stable-fast-3d", label: "Stable Fast 3D" },
  { value: "hunyuan3d", label: "Hunyuan3D-2" },
];

export const RESOLUTION_OPTIONS = [
  { value: 256, label: "Low (256px)" },
  { value: 512, label: "Medium (512px)" },
  { value: 1024, label: "High (1024px)" },
  { value: 2048, label: "Ultra (2048px)" },
];

export const TEXTURE_QUALITY_OPTIONS = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
];