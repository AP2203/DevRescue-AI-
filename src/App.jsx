import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider } from './context/AuthContext';
import { AppProvider } from './context/AppContext';
import ErrorBoundary from './components/common/ErrorBoundary';

// Layouts (loaded synchronously to preserve core shell structure)
import PublicLayout from './layouts/PublicLayout';
import AppLayout from './layouts/AppLayout';
import ProtectedRoute from './layouts/ProtectedRoute';

// Public Pages (dynamically imported for optimal chunking)
const Landing = lazy(() => import('./pages/public/Landing'));
const About = lazy(() => import('./pages/public/About'));
const Documentation = lazy(() => import('./pages/public/Documentation'));
const Support = lazy(() => import('./pages/support/Support'));
const Login = lazy(() => import('./pages/auth/Login'));
const NotFound = lazy(() => import('./pages/public/NotFound'));

// App Pages (dynamically imported for optimal chunking)
const Dashboard = lazy(() => import('./pages/dashboard/Dashboard'));
const Repositories = lazy(() => import('./pages/repositories/Repositories'));
const NewInvestigation = lazy(() => import('./pages/investigations/NewInvestigation'));
const LiveInvestigation = lazy(() => import('./pages/investigations/LiveInvestigation'));
const CodeReview = lazy(() => import('./pages/investigations/CodeReview'));
const PullRequests = lazy(() => import('./pages/pull-requests/PullRequests'));
const InvestigationHistory = lazy(() => import('./pages/investigations/InvestigationHistory'));
const Agents = lazy(() => import('./pages/agents/Agents'));
const Analytics = lazy(() => import('./pages/analytics/Analytics'));
const Settings = lazy(() => import('./pages/settings/Settings'));

function RouteLoader() {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center gap-3 p-8 text-center">
      <div className="w-8 h-8 rounded-full border-2 border-emerald-500/20 border-t-emerald-500 animate-spin" />
      <span className="text-xs font-mono tracking-widest text-slate-400 dark:text-slate-500 uppercase">
        Loading module...
      </span>
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <ThemeProvider>
          <AuthProvider>
            <AppProvider>
              <Suspense fallback={<RouteLoader />}>
                <Routes>
                  {/* Public Layout Routes */}
                  <Route element={<PublicLayout />}>
                    <Route path="/" element={<Landing />} />
                    <Route path="/about" element={<About />} />
                    <Route path="/docs" element={<Documentation />} />
                    <Route path="/support" element={<Support />} />
                    <Route path="/login" element={<Login />} />
                    <Route path="/404" element={<NotFound />} />
                  </Route>

                  {/* Authenticated Application Routes */}
                  <Route
                    element={
                      <ProtectedRoute>
                        <AppLayout />
                      </ProtectedRoute>
                    }
                  >
                    <Route path="/dashboard" element={<Dashboard />} />
                    <Route path="/repositories" element={<Repositories />} />
                    <Route path="/investigations" element={<Navigate to="/history" replace />} />
                    <Route path="/investigations/new" element={<NewInvestigation />} />
                    <Route path="/investigations/:id" element={<LiveInvestigation />} />
                    <Route path="/investigations/:id/review" element={<CodeReview />} />
                    <Route path="/pull-requests" element={<PullRequests />} />
                    <Route path="/history" element={<InvestigationHistory />} />
                    <Route path="/agents" element={<Agents />} />
                    <Route path="/analytics" element={<Analytics />} />
                    <Route path="/settings" element={<Settings />} />
                  </Route>

                  {/* Catch-all fallback to 404 */}
                  <Route path="*" element={<Navigate to="/404" replace />} />
                </Routes>
              </Suspense>
            </AppProvider>
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
