import type { ThemePreference } from "./api";

export type UserMetrics = {
  projects_created: number;
  generations_completed: number;
  generations_failed: number;
  total_model_size_bytes: number;
  total_upload_bytes: number;
};

export type UserPreferences = {
  theme: ThemePreference;
  default_model: string;
};

export type User = {
  id: string;
  email: string;
  username: string;
  role: "user" | "admin";
  avatar_url: string | null;
  preferences: UserPreferences;
  metrics: UserMetrics;
  created_at: string;
};

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
};

export type AuthResponse = {
  user: User;
  tokens: TokenPair;
};

export type RegisterRequest = {
  email: string;
  username: string;
  password: string;
};

export type LoginRequest = {
  email: string;
  password: string;
};

export type UpdateProfileRequest = {
  username?: string;
  avatar_url?: string | null;
  preferences?: Partial<UserPreferences>;
};

export type UsageSummary = {
  uploads: number;
  generations: number;
  completed_generations: number;
  failed_generations: number;
  downloads: number;
  total_upload_bytes: number;
  total_model_bytes: number;
  by_day: DailyUsage[];
};

export type DailyUsage = {
  date: string;
  kind: string;
  count: number;
  bytes: number;
};

export type UserStats = {
  usage: UsageSummary;
  metrics: UserMetrics;
};