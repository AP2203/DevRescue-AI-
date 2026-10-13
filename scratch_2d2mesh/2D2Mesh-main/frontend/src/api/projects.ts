import { client } from "./client";
import type { Page } from "../types/api";
import type { Project, ProjectCreateRequest, ProjectDetail, ProjectFilter, ProjectUpdateRequest } from "../types/project";

export const projectsApi = {
  async list(filters: ProjectFilter = {}): Promise<Page<Project>> {
    const { data } = await client.get<Page<Project>>("/projects", {
      params: {
        page: filters.page ?? 1,
        page_size: filters.page_size ?? 12,
        query: filters.query || undefined,
        status_filter: filters.status || undefined,
        sort_by: filters.sort_by || "created_at",
        sort_dir: filters.sort_dir || "desc",
      },
    });
    return data;
  },

  async create(payload: ProjectCreateRequest): Promise<Project> {
    const { data } = await client.post<Project>("/projects", payload);
    return data;
  },

  async get(id: string): Promise<ProjectDetail> {
    const { data } = await client.get<ProjectDetail>(`/projects/${id}`);
    return data;
  },

  async update(id: string, payload: ProjectUpdateRequest): Promise<Project> {
    const { data } = await client.patch<Project>(`/projects/${id}`, payload);
    return data;
  },

  async rename(id: string, name: string): Promise<Project> {
    const { data } = await client.patch<Project>(`/projects/${id}/rename`, { name });
    return data;
  },

  async remove(id: string): Promise<void> {
    await client.delete(`/projects/${id}`);
  },
};