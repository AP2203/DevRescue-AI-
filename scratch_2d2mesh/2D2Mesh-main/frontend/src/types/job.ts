import type { JobStatus } from "./api";

export type GenerationSettings = {
  model: string;
  resolution: number;
  texture_quality: "low" | "medium" | "high";
  remesh: boolean;
  simplify_target?: number | null;
};

export type Job = {
  id: string;
  project_id: string;
  upload_id: string;
  status: JobStatus;
  stage: string | null;
  progress: number;
  message: string | null;
  error: string | null;
  ai_model: string;
  settings: Partial<GenerationSettings>;
  metrics: Record<string, unknown>;
  retry_count: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type GenerateRequest = {
  upload_id: string;
  name?: string;
  settings: GenerationSettings;
};

export type RetryResponse = {
  job: Job;
  message: string;
};