/** TypeScript types for the advanced AI features */

// ── Quality Analysis ──────────────────────────────────────────────────────────

export type DimensionScore = {
  name: string;
  score: number;
  weight: number;
  details: string;
};

export type QualityProblem = {
  severity: "error" | "warning" | "info";
  code: string;
  message: string;
  value?: unknown;
};

export type QualityReport = {
  id: string;
  project_id: string;
  model_asset_id: string;
  overall_score: number;
  dimensions: DimensionScore[];
  problems: QualityProblem[];
  recommendations: string[];
  stats_snapshot: {
    vertices: number;
    faces: number;
    triangles: number;
    edges: number;
    mesh_count: number;
    watertight_count: number;
    boundary_edges: number;
    non_manifold_edges: number;
    degenerate_faces: number;
    duplicate_vertices: number;
    has_texture: boolean;
    has_uvs: boolean;
    has_normals: boolean;
    disconnected_components: number;
  };
  created_at: string;
};

// ── Repair ────────────────────────────────────────────────────────────────────

export type MeshStats = {
  vertices: number;
  faces: number;
  watertight_count: number;
  mesh_count: number;
};

export type RepairResult = {
  asset_id: string;
  before_stats: MeshStats;
  after_stats: MeshStats;
  operations_applied: string[];
  download_url: string;
  before_score: number;
  after_score: number;
  problems_found: QualityProblem[];
  problems_fixed: string[];
};

// ── AI Edit ───────────────────────────────────────────────────────────────────

export type EditOperation = {
  type:
    | "change_material"
    | "change_color"
    | "change_roughness"
    | "change_metalness"
    | "reduce_polygons"
    | "scale"
    | "translate"
    | "rotate"
    | "prepare_print";
  target?: string;
  value?: string | number | number[];
  roughness?: number;
  metalness?: number;
};

export type ParsedCommand = {
  operations: EditOperation[];
  operation?: string;
  error?: string;
};

export type EditResult = {
  asset_id: string;
  version: number;
  parsed_command: ParsedCommand;
  message: string;
  before_stats: { vertices: number; faces: number; mesh_count: number };
  after_stats: { vertices: number; faces: number; mesh_count: number };
  quality_score: number;
  download_url: string;
};

export type EditVersionEntry = {
  version: number;
  label: string;
  asset_id: string | null;
  user_command?: string | null;
  operation_type?: string | null;
};

export type EditVersionsResponse = {
  versions: EditVersionEntry[];
  current_version: number;
  max_version: number;
  can_undo: boolean;
  can_redo: boolean;
};

export type UndoRedoResult = {
  asset_id: string;
  version: number;
  can_undo: boolean;
  can_redo: boolean;
};

export type EditHistoryEntry = {
  id: string;
  project_id: string;
  operation_type: "repair" | "ai_edit" | "optimization";
  version: number;
  user_command?: string;
  parsed_command?: ParsedCommand;
  before_stats: Record<string, number>;
  after_stats: Record<string, number>;
  meta: Record<string, unknown>;
  status: "completed" | "failed";
  created_at: string;
};

// ── Optimization ──────────────────────────────────────────────────────────────

export type OptimizationProfile = "web" | "game" | "print";

export type OptimizationResult = {
  asset_id: string;
  profile: OptimizationProfile;
  before_stats: { vertices: number; faces: number; size_bytes: number };
  after_stats: { vertices: number; faces: number; size_bytes: number };
  operations: string[];
  download_url: string;
  stl_download_url?: string;
};
