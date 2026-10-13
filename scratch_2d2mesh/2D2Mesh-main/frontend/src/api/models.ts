import { client } from "./client";
import { downloadBlob } from "../lib/format";

export const modelApi = {
  /** Fetch the model as a blob (auth headers attached) then fall back to object URL. */
  async fetchGlbBlob(projectId: string): Promise<{ blob: Blob; url: string }> {
    const { data } = await client.get(`/projects/${projectId}/model`, { responseType: "blob" });
    const blob = data as Blob;
    return { blob, url: URL.createObjectURL(blob) };
  },

  async fetchGltfBlob(projectId: string): Promise<{ blob: Blob; url: string }> {
    const { data } = await client.get(`/projects/${projectId}/model/gltf`, { responseType: "blob" });
    const blob = data as Blob;
    return { blob, url: URL.createObjectURL(blob) };
  },

  async downloadGlb(projectId: string, filename = "model.glb") {
    const { blob } = await this.fetchGlbBlob(projectId);
    downloadBlob(blob, filename);
  },

  async downloadGltf(projectId: string, filename = "model.gltf") {
    const { blob } = await this.fetchGltfBlob(projectId);
    downloadBlob(blob, filename);
  },

  async downloadStl(projectId: string, filename = "model.stl") {
    const { data } = await client.get(`/projects/${projectId}/model/stl`, { responseType: "blob" });
    downloadBlob(data as Blob, filename);
  },
};