import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider } from './context/AuthContext';
import { AppProvider } from './context/AppContext';
import ErrorBoundary from './components/common/ErrorBoundary';

// Layouts
import PublicLayout from './layouts/PublicLayout';
import AppLayout from './layouts/AppLayout';
import ProtectedRoute from './layouts/ProtectedRoute';

// Public Pages
import Landing from './pages/public/Landing';
import About from './pages/public/About';
import Documentation from './pages/public/Documentation';
import Support from './pages/support/Support';
import Login from './pages/auth/Login';
import NotFound from './pages/public/NotFound';

// App Pages (Authenticated)
import Dashboard from './pages/dashboard/Dashboard';
import Repositories from './pages/repositories/Repositories';
import NewInvestigation from './pages/investigations/NewInvestigation';
import LiveInvestigation from './pages/investigations/LiveInvestigation';
import CodeReview from './pages/investigations/CodeReview';
import PullRequests from './pages/pull-requests/PullRequests';
import InvestigationHistory from './pages/investigations/InvestigationHistory';
import Agents from './pages/agents/Agents';
import Analytics from './pages/analytics/Analytics';
import Settings from './pages/settings/Settings';

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <ThemeProvider>
          <AuthProvider>
            <AppProvider>
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
            </AppProvider>
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
