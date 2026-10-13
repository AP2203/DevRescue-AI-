import { client } from "./client";
import type { Upload } from "../types/admin";

export const uploadsApi = {
  async upload(
    file: File,
    onProgress?: (percent: number) => void,
    signal?: AbortSignal,
  ): Promise<Upload> {
    const form = new FormData();
    form.append("file", file);
    const { data } = await client.post<Upload>("/uploads", form, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 60000,
      signal,
      onUploadProgress: (event) => {
        if (event.total && onProgress) {
          onProgress(Math.round((event.loaded / event.total) * 100));
        }
      },
    });
    return data;
  },

  async get(id: string): Promise<Upload> {
    const { data } = await client.get<Upload>(`/uploads/${id}`);
    return data;
  },
};