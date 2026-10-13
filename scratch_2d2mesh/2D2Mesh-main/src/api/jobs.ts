import { client } from "./client";
import type { Page } from "../types/api";
import type { GenerateRequest, Job, RetryResponse } from "../types/job";

export const jobsApi = {
  async list(params: { status?: string; page?: number; page_size?: number } = {}): Promise<Page<Job>> {
    const { data } = await client.get<Page<Job>>("/jobs", {
      params: {
        page: params.page ?? 1,
        page_size: params.page_size ?? 20,
        job_status: params.status || undefined,
      },
    });
    return data;
  },

  async create(projectId: string, payload: GenerateRequest): Promise<Job> {
    const { data } = await client.post<Job>(`/jobs/projects/${projectId}/generate`, payload);
    return data;
  },

  async get(id: string): Promise<Job> {
    const { data } = await client.get<Job>(`/jobs/${id}`);
    return data;
  },

  async retry(id: string): Promise<RetryResponse> {
    const { data } = await client.post<RetryResponse>(`/jobs/${id}/retry`);
    return data;
  },

  async cancel(id: string): Promise<Job> {
    const { data } = await client.post<Job>(`/jobs/${id}/cancel`);
    return data;
  },
};