import { client } from "./client";
import type { AdminStats, AdminUserRow } from "../types/admin";
import type { Page } from "../types/api";

export const adminApi = {
  async stats(): Promise<AdminStats> {
    const { data } = await client.get<AdminStats>("/admin/stats");
    return data;
  },

  async users(params: { query?: string; page?: number; page_size?: number } = {}): Promise<Page<AdminUserRow>> {
    const { data } = await client.get<Page<AdminUserRow>>("/admin/users", {
      params: { query: params.query || undefined, page: params.page ?? 1, page_size: params.page_size ?? 20 },
    });
    return data;
  },

  async updateUser(userId: string, payload: { role?: string; is_active?: boolean }): Promise<AdminUserRow> {
    const { data } = await client.patch<AdminUserRow>(`/admin/users/${userId}`, payload);
    return data;
  },

  async jobs(params: { status?: string; page?: number; page_size?: number } = {}): Promise<Page<Record<string, unknown>>> {
    const { data } = await client.get<Page<Record<string, unknown>>>("/admin/jobs", {
      params: { job_status: params.status || undefined, page: params.page ?? 1, page_size: params.page_size ?? 20 },
    });
    return data;
  },
};