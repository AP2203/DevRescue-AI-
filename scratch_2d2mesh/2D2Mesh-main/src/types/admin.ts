export type Upload = {
  id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  width: number | null;
  height: number | null;
  url: string | null;
  created_at: string;
};

export type AdminStats = {
  users: number;
  projects: number;
  jobs: number;
  uploads: number;
  models: number;
  storage_total_bytes: number;
  jobs_by_status: { status: string; count: number }[];
  storage_by_kind: { kind: string; count: number; bytes: number }[];
  active_in_last_24h: number;
};

export type AdminUserRow = {
  id: string;
  email: string;
  username: string;
  role: string;
  is_active: boolean;
  metrics: Record<string, number>;
  created_at: string;
};

export type AdminJobsRow = {
  id: string;
  user_id: string;
  status: string;
  ai_model: string;
  progress: number;
  error: string | null;
  created_at: string;
};