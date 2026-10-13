import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Project } from "../types/project";
import type { JobStatus } from "../types/api";

export type GenerationStatus = {
  jobId: string | null;
  status: JobStatus | null;
  stage: string | null;
  progress: number;
  message: string | null;
};

export type UploadStatus = {
  uploading: boolean;
  progress: number;
  fileName: string | null;
};

export type ViewerSettings = {
  autoRotate: boolean;
  wireframe: boolean;
  solidPreview: boolean;
  showGrid: boolean;
  showAxes: boolean;
  showBBox: boolean;
  lighting: boolean;
};

const DEFAULT_VIEWER: ViewerSettings = {
  autoRotate: true,
  wireframe: false,
  solidPreview: false,
  showGrid: true,
  showAxes: false,
  showBBox: false,
  lighting: true,
};

const DEFAULT_GENERATION: GenerationStatus = {
  jobId: null,
  status: null,
  stage: null,
  progress: 0,
  message: null,
};

const DEFAULT_UPLOAD: UploadStatus = {
  uploading: false,
  progress: 0,
  fileName: null,
};

type AppState = {
  currentProject: Project | null;
  generation: GenerationStatus;
  upload: UploadStatus;
  viewer: ViewerSettings;

  setCurrentProject: (project: Project | null) => void;
  clearCurrentProject: () => void;
  setGenerationStatus: (patch: Partial<GenerationStatus>) => void;
  resetGeneration: () => void;
  setUploadStatus: (upload: UploadStatus) => void;
  resetUpload: () => void;
  setViewer: (patch: Partial<ViewerSettings>) => void;
  resetViewer: () => void;
};

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      currentProject: null,
      generation: DEFAULT_GENERATION,
      upload: DEFAULT_UPLOAD,
      viewer: DEFAULT_VIEWER,

      setCurrentProject: (currentProject) => set({ currentProject }),
      clearCurrentProject: () => set({ currentProject: null }),

      setGenerationStatus: (patch) =>
        set((state) => ({ generation: { ...state.generation, ...patch } })),

      resetGeneration: () => set({ generation: DEFAULT_GENERATION }),

      setUploadStatus: (upload) => set({ upload }),
      resetUpload: () => set({ upload: DEFAULT_UPLOAD }),

      setViewer: (patch) =>
        set((state) => ({
          viewer: { ...state.viewer, ...patch },
        })),

      resetViewer: () => set({ viewer: DEFAULT_VIEWER }),
    }),
    {
      name: "vision3d.ui",
      partialize: (state) => ({ viewer: state.viewer }),
    },
  ),
);