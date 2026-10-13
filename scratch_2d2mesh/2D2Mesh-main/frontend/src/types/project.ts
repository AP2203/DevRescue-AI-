import type { Job } from "./job";

export type Project = {
  id: string;
  name: string;
  description: string | null;
  status: "no_model" | "processing" | "ready" | "failed";
  image_upload_id: string | null;
  model_asset_id: string | null;
  last_job_id: string | null;
  edit_version: number;
  created_at: string;
  updated_at: string;
};

export type ModelStats = {
  vertices: number;
  faces: number;
  edges: number;
  triangles: number;
  bounds?: [number, number, number][] | null;
  has_texture: boolean;
  texture_size?: number | null;
  watertight?: boolean;
};

export type ModelSummary = {
  filename: string;
  size_bytes: number;
  mime_type: string;
  stats: ModelStats | null;
  created_at: string;
  download_glb_url: string | null;
  download_gltf_url: string | null;
  download_obj_url?: string | null;
  preview_url?: string | null;
};

export type ProjectDetail = Project & {
  image_url?: string | null;
  model_summary?: ModelSummary | null;
  last_job?: Job | null;
};

export type ProjectCreateRequest = {
  name: string;
  description?: string;
};

export type ProjectUpdateRequest = {
  name?: string;
  description?: string | null;
};

export type ProjectFilter = {
  query?: string;
  status?: string;
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
};