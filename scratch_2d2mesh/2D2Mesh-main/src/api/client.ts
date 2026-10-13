import axios, { type AxiosError } from "axios";
import { API_URL } from "../lib/constants";
import type { ApiErrorEnvelope } from "../types/api";

export const TOKEN_STORAGE_KEY = "vision3d.access_token";
export const REFRESH_TOKEN_STORAGE_KEY = "vision3d.refresh_token";

export const client = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let isRefreshing = false;
let refreshQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (reason: unknown) => void;
}> = [];

client.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiErrorEnvelope>) => {
    const originalRequest = error.config as { _retry?: boolean } & typeof error.config;
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);

    if (error.response?.status === 401 && refreshToken && originalRequest && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          refreshQueue.push({ resolve: resolve as never, reject });
        }).then(() => client(originalRequest));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const { data } = await axios.post<{ access_token: string }>(
          `${API_URL}/auth/refresh`,
          { refresh_token: refreshToken },
        );
        localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token);
        refreshQueue.forEach(({ resolve }) => resolve());
        refreshQueue = [];
        return client(originalRequest);
      } catch (refreshError) {
        localStorage.removeItem(TOKEN_STORAGE_KEY);
        localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
        window.dispatchEvent(new CustomEvent("vision3d:unauthorized"));
        refreshQueue.forEach(({ reject }) => reject(refreshError));
        refreshQueue = [];
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  },
);

export function tokenFromResponse(access: string, refresh: string) {
  localStorage.setItem(TOKEN_STORAGE_KEY, access);
  localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, refresh);
}

export function clearTokens() {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
}

export function extractApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const envelope = error.response?.data as ApiErrorEnvelope | undefined;
    if (envelope?.error?.message) return envelope.error.message;
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return "Unexpected error";
}