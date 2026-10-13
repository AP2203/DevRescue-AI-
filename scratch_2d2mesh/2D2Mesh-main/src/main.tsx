import { StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./hooks/useAuth";
import { ThemeProvider } from "./hooks/useTheme";
import { ToastProvider } from "./hooks/useToast";
import { Toaster } from "./components/ui/Toaster";
import { ErrorBoundary } from "./components/ui/ErrorBoundary";
import { Spinner } from "./components/ui/Spinner";
import { AppShell } from "./components/layout/AppShell";
import { ProtectedRoute } from "./components/layout/ProtectedRoute";

import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { NotFoundPage } from "./pages/NotFoundPage";

const DashboardPage = lazy(() =>
  import("./pages/DashboardPage").then((m) => ({ default: m.DashboardPage })),
);
const GeneratePage = lazy(() =>
  import("./pages/GeneratePage").then((m) => ({ default: m.GeneratePage })),
);
const GenerationProgressPage = lazy(() =>
  import("./pages/GenerationProgressPage").then((m) => ({ default: m.GenerationProgressPage })),
);
const ProjectsPage = lazy(() =>
  import("./pages/ProjectsPage").then((m) => ({ default: m.ProjectsPage })),
);
const ProjectDetailPage = lazy(() =>
  import("./pages/ProjectDetailPage").then((m) => ({ default: m.ProjectDetailPage })),
);
const ViewerPage = lazy(() =>
  import("./pages/ViewerPage").then((m) => ({ default: m.ViewerPage })),
);
const ProfilePage = lazy(() =>
  import("./pages/ProfilePage").then((m) => ({ default: m.ProfilePage })),
);
const SettingsPage = lazy(() =>
  import("./pages/SettingsPage").then((m) => ({ default: m.SettingsPage })),
);
const AdminPage = lazy(() =>
  import("./pages/AdminPage").then((m) => ({ default: m.AdminPage })),
);

function PageFallback() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <Spinner className="h-8 w-8" />
    </div>
  );
}

import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <ToastProvider>
          <AuthProvider>
            <ErrorBoundary>
              <Routes>
              {/* Public routes */}
              <Route path="/" element={<LandingPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />

              {/* Protected routes inside AppShell */}
              <Route
                element={
                  <ProtectedRoute>
                    <AppShell />
                  </ProtectedRoute>
                }
              >
              <Route path="/dashboard" element={<Suspense fallback={<PageFallback />}><DashboardPage /></Suspense>} />
                <Route path="/generate" element={<Suspense fallback={<PageFallback />}><GeneratePage /></Suspense>} />
                <Route path="/generate/progress/:jobId" element={<Suspense fallback={<PageFallback />}><GenerationProgressPage /></Suspense>} />
                <Route path="/projects" element={<Suspense fallback={<PageFallback />}><ProjectsPage /></Suspense>} />
                <Route path="/projects/:projectId" element={<Suspense fallback={<PageFallback />}><ProjectDetailPage /></Suspense>} />
                <Route path="/projects/:projectId/viewer" element={<Suspense fallback={<PageFallback />}><ViewerPage /></Suspense>} />
                <Route path="/profile" element={<Suspense fallback={<PageFallback />}><ProfilePage /></Suspense>} />
                <Route path="/settings" element={<Suspense fallback={<PageFallback />}><SettingsPage /></Suspense>} />
                <Route path="/admin" element={<Suspense fallback={<PageFallback />}><AdminPage /></Suspense>} />
              </Route>

              {/* Fallbacks */}
              <Route path="/app" element={<Navigate to="/dashboard" replace />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
            </ErrorBoundary>
            <Toaster />
          </AuthProvider>
        </ToastProvider>
      </ThemeProvider>
    </BrowserRouter>
  </StrictMode>,
);
