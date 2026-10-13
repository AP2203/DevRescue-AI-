import { client } from "./client";
import { downloadBlob, storageKeyFromUrl } from "../lib/format";
import type { EditHistoryEntry, EditResult, EditVersionsResponse, OptimizationProfile, OptimizationResult, QualityReport, RepairResult, UndoRedoResult } from "../types/analysis";

export const analysisApi = {
  // ── Quality ──────────────────────────────────────────────────────────────

  async runQualityAnalysis(projectId: string): Promise<QualityReport> {
    const { data } = await client.post(`/projects/${projectId}/quality-analysis`);
    return data as QualityReport;
  },

  async getQualityReport(projectId: string): Promise<QualityReport> {
    const { data } = await client.get(`/projects/${projectId}/quality-report`);
    return data as QualityReport;
  },

  // ── Repair ───────────────────────────────────────────────────────────────

  async repairModel(
    projectId: string,
    options: {
      fill_holes?: boolean;
      fix_normals?: boolean;
      remove_duplicates?: boolean;
      remove_degenerate?: boolean;
    } = {},
  ): Promise<RepairResult> {
    const { data } = await client.post(`/projects/${projectId}/repair`, {
      fill_holes: true,
      fix_normals: true,
      remove_duplicates: true,
      remove_degenerate: true,
      ...options,
    });
    return data as RepairResult;
  },

  // ── AI Edit ──────────────────────────────────────────────────────────────

  async applyEdit(projectId: string, command: string): Promise<EditResult> {
    const { data } = await client.post(`/projects/${projectId}/edit`, { command });
    return data as EditResult;
  },

  async getEditHistory(projectId: string, limit = 20): Promise<EditHistoryEntry[]> {
    const { data } = await client.get(`/projects/${projectId}/edit-history`, {
      params: { limit },
    });
    return data as EditHistoryEntry[];
  },

  async getEditVersions(projectId: string): Promise<EditVersionsResponse> {
    const { data } = await client.get(`/projects/${projectId}/edit/versions`);
    return data as EditVersionsResponse;
  },

  async undoEdit(projectId: string): Promise<UndoRedoResult> {
    const { data } = await client.post(`/projects/${projectId}/edit/undo`);
    return data as UndoRedoResult;
  },

  async redoEdit(projectId: string): Promise<UndoRedoResult> {
    const { data } = await client.post(`/projects/${projectId}/edit/redo`);
    return data as UndoRedoResult;
  },

  // ── Optimization ─────────────────────────────────────────────────────────

  async optimizeModel(projectId: string, profile: OptimizationProfile): Promise<OptimizationResult> {
    const { data } = await client.post(`/projects/${projectId}/optimize`, { profile });
    return data as OptimizationResult;
  },

  // ── STL Export ───────────────────────────────────────────────────────────

  async downloadStl(projectId: string, filename = "model.stl"): Promise<void> {
    const { data } = await client.get(`/projects/${projectId}/model/stl`, {
      responseType: "blob",
    });
    downloadBlob(data as Blob, filename);
  },

  // ── Authenticated file downloads ─────────────────────────────────────────

  /**
   * Download an asset file referenced by a `public_url` from the backend.
   *
   * Local storage URLs (`.../api/v1/files/{key}`) are re-fetched through the
   * authenticated axios client so the bearer token never leaks into a query
   * string. S3 presigned URLs are already signed and opened directly.
   */
  async downloadFile(url: string, filename: string): Promise<void> {
    const key = storageKeyFromUrl(url);
    if (!key) {
      window.open(url, "_blank", "noopener,noreferrer");
      return;
    }
    const { data } = await client.get(`/files/${key}`, { responseType: "blob" });
    downloadBlob(data as Blob, filename);
  },
};
