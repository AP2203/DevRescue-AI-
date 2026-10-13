export type ApiError = {
  code: string;
  message: string;
  details?: Record<string, unknown>;
};

export type ApiErrorEnvelope = { error: ApiError };

export type Page<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type JobStatus = "queued" | "processing" | "succeeded" | "failed" | "cancelled";

export type ProjectStatus = "no_model" | "processing" | "ready" | "failed";

export type ThemePreference = "system" | "light" | "dark";

export type AiModelName = "mock" | "stable-fast-3d" | "hunyuan3d" | "auto";