import React, { useState } from 'react';
import { Outlet, NavLink, Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useApp } from '../context/AppContext';
import {
  LayoutDashboard,
  FolderGit2,
  PlusCircle,
  Activity,
  GitPullRequest,
  CheckSquare,
  History,
  Bot,
  BarChart3,
  Settings,
  LogOut,
  Menu,
  X,
  Bug,
  ExternalLink,
} from 'lucide-react';
import Toast from '../components/common/Toast';
import Avatar from '../components/common/Avatar';
import Badge from '../components/common/Badge';
import Button from '../components/common/Button';

export default function AppLayout() {
  const { user, logout } = useAuth();
  const { investigations, notifications, removeNotification, appMode, setAppMode, backendHealth } = useApp();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const activeInv = investigations && investigations.length > 0 ? investigations[0] : null;
  const liveInvPath = activeInv ? `/investigations/${activeInv.id}` : '/investigations/new';
  const codeReviewPath = activeInv ? `/investigations/${activeInv.id}/review` : '/pull-requests';

  const mainNavItems = [
    { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    { name: 'Repositories', path: '/repositories', icon: FolderGit2 },
    { name: 'New Investigation', path: '/investigations/new', icon: PlusCircle },
    { name: 'Live Investigation', path: liveInvPath, icon: Activity },
    { name: 'Code Review', path: codeReviewPath, icon: CheckSquare },
    { name: 'Pull Requests', path: '/pull-requests', icon: GitPullRequest },
    { name: 'History', path: '/history', icon: History },
  ];

  const secondaryNavItems = [
    { name: 'AI Agents', path: '/agents', icon: Bot },
    { name: 'Analytics', path: '/analytics', icon: BarChart3 },
  ];

  const settingsNavItems = [
    { name: 'Settings', path: '/settings', icon: Settings },
  ];

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const getPageTitle = () => {
    const p = location.pathname;
    if (p === '/dashboard') return 'Dashboard';
    if (p === '/repositories') return 'Repositories';
    if (p === '/investigations/new') return 'New Investigation';
    if (p.includes('/review')) return 'Code Review';
    if (p.startsWith('/investigations/')) return 'Live Investigation';
    if (p === '/pull-requests') return 'Pull Requests';
    if (p === '/history') return 'Investigation History';
    if (p === '/agents') return 'AI Agents';
    if (p === '/analytics') return 'Analytics';
    if (p === '/settings') return 'Settings';
    return 'Dashboard';
  };

  return (
    <div className="min-h-screen bg-[#F7F9FC] text-[#0F172A] flex flex-col md:flex-row font-sans selection:bg-[#EFF6FF] selection:text-[#2563EB]">
      {/* Toast Notifications */}
      <Toast notifications={notifications} onDismiss={removeNotification} />

      {/* Mobile Top Header */}
      <div className="md:hidden flex items-center justify-between px-4 py-3 bg-white border-b border-[#E2E8F0] sticky top-0 z-30 shadow-xs">
        <Link to="/dashboard" className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-[#2563EB] text-white flex items-center justify-center">
            <Bug className="w-4 h-4" />
          </div>
          <span className="font-bold text-base text-[#0F172A]">DevRescue AI</span>
        </Link>

        <div className="flex items-center gap-2">
          <Badge variant="demo" size="sm">DEMO</Badge>
          <button
            type="button"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-1.5 rounded-lg border border-[#E2E8F0] hover:bg-slate-100 text-[#0F172A]"
            aria-label="Toggle menu"
          >
            {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-[#0F172A]/30 z-40 md:hidden backdrop-blur-xs"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* LEFT SIDEBAR */}
      <aside
        className={`fixed md:sticky top-0 left-0 h-screen w-64 bg-white border-r border-[#E2E8F0] z-50 flex flex-col justify-between transition-transform duration-200 ease-in-out md:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex-1 overflow-y-auto">
          {/* Logo & Platform Info */}
          <div className="p-5 border-b border-[#E2E8F0]">
            <Link
              to="/dashboard"
              onClick={() => setSidebarOpen(false)}
              className="flex items-center gap-2.5 group"
            >
              <div className="w-8 h-8 rounded-lg bg-[#2563EB] text-white flex items-center justify-center shadow-xs group-hover:bg-[#1D4ED8] transition-colors">
                <Bug className="w-5 h-5" />
              </div>
              <div className="flex flex-col">
                <span className="text-base font-bold tracking-tight text-[#0F172A] leading-tight">
                  DevRescue AI
                </span>
                <span className="text-[11px] text-[#64748B]">
                  Autonomous Bug Repair
                </span>
              </div>
            </Link>
          </div>

          {/* Quick Action Button */}
          <div className="p-3">
            <Link
              to="/investigations/new"
              onClick={() => setSidebarOpen(false)}
              className="w-full flex items-center justify-center gap-2 px-3.5 py-2 rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold shadow-xs transition-all active:scale-[0.98]"
            >
              <PlusCircle className="w-4 h-4" />
              <span>New Investigation</span>
            </Link>
          </div>

          {/* Main Navigation */}
          <div className="px-3 py-2 space-y-1">
            <div className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-[#94A3B8]">
              Workflow
            </div>
            {mainNavItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  onClick={() => setSidebarOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                      isActive
                        ? 'bg-[#EFF6FF] text-[#2563EB] font-semibold border-r-2 border-[#2563EB]'
                        : 'text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC]'
                    }`
                  }
                >
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  <span>{item.name}</span>
                </NavLink>
              );
            })}
          </div>

          {/* Divider */}
          <div className="my-2 mx-3 border-t border-[#E2E8F0]" />

          {/* Secondary Navigation */}
          <div className="px-3 py-2 space-y-1">
            <div className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-[#94A3B8]">
              Intelligence
            </div>
            {secondaryNavItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  onClick={() => setSidebarOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                      isActive
                        ? 'bg-[#EFF6FF] text-[#2563EB] font-semibold border-r-2 border-[#2563EB]'
                        : 'text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC]'
                    }`
                  }
                >
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  <span>{item.name}</span>
                </NavLink>
              );
            })}
          </div>

          {/* Divider */}
          <div className="my-2 mx-3 border-t border-[#E2E8F0]" />

          {/* Settings Navigation */}
          <div className="px-3 py-2 space-y-1">
            {settingsNavItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  onClick={() => setSidebarOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                      isActive
                        ? 'bg-[#EFF6FF] text-[#2563EB] font-semibold border-r-2 border-[#2563EB]'
                        : 'text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC]'
                    }`
                  }
                >
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  <span>{item.name}</span>
                </NavLink>
              );
            })}
          </div>
        </div>

        {/* BOTTOM SIDEBAR FOOTER */}
        <div className="p-3 border-t border-[#E2E8F0] bg-[#F8FAFC] space-y-3">
          {/* Mode Indicator & Switcher */}
          <div
            onClick={() => setAppMode(appMode === 'REAL' ? 'DEMO' : 'REAL')}
            className={`flex items-center justify-between px-2.5 py-1.5 rounded-lg border text-[11px] cursor-pointer transition-colors ${
              appMode === 'REAL'
                ? 'bg-emerald-50/70 border-emerald-200 text-emerald-800 hover:bg-emerald-100'
                : 'bg-amber-50/70 border-amber-200 text-amber-800 hover:bg-amber-100'
            }`}
            title="Click to switch mode"
          >
            <div className="flex items-center gap-1.5 font-medium">
              <span className={`w-2 h-2 rounded-full ${appMode === 'REAL' ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
              <span>{appMode === 'REAL' ? 'FastAPI + XGBoost' : 'Demo Prototype'}</span>
            </div>
            <span className="text-[10px] font-bold uppercase">{appMode}</span>
          </div>

          {/* User Profile Info & Logout */}
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-2.5 min-w-0">
              <Avatar name={user?.name || 'Ansh'} size="sm" />
              <div className="min-w-0 flex-1">
                <div className="text-xs font-semibold text-[#0F172A] truncate">
                  {user?.name || 'Ansh'}
                </div>
                <div className="text-[11px] text-[#64748B] truncate">
                  {user?.email || 'ansh@devrescue.ai'}
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={handleLogout}
              className="p-1.5 rounded-lg text-[#64748B] hover:text-[#DC2626] hover:bg-white transition-colors cursor-pointer"
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* MAIN APPLICATION CONTAINER */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header Bar */}
        <header className="hidden md:flex h-16 bg-white border-b border-[#E2E8F0] px-8 items-center justify-between sticky top-0 z-20">
          <div className="flex items-center gap-3">
            <h1 className="text-base font-semibold text-[#0F172A]">
              {getPageTitle()}
            </h1>
            <span className="text-slate-300">/</span>
            <span className="text-xs text-[#64748B]">
              DevRescue Engineering Console
            </span>
          </div>

          <div className="flex items-center gap-3">
            {/* Dynamic Mode Badge & Switcher */}
            <button
              type="button"
              onClick={() => setAppMode(appMode === 'REAL' ? 'DEMO' : 'REAL')}
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all border cursor-pointer ${
                appMode === 'REAL'
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'
                  : 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100'
              }`}
              title={`Mode: ${appMode} | Backend: ${backendHealth.status} | ML: ${backendHealth.mlStatus || 'healthy'}`}
            >
              <span className={`w-2 h-2 rounded-full ${appMode === 'REAL' ? (backendHealth.status === 'offline' ? 'bg-amber-500' : 'bg-emerald-500 animate-pulse') : 'bg-amber-500'}`} />
              <span>{appMode === 'REAL' ? `REAL MODE (${backendHealth.status === 'offline' ? 'Offline' : 'FastAPI'})` : 'DEMO MODE (Simulated)'}</span>
            </button>


            <Link
              to="/"
              className="text-xs font-medium text-[#64748B] hover:text-[#2563EB] flex items-center gap-1 transition-colors px-2 py-1"
            >
              <span>Landing Page</span>
              <ExternalLink className="w-3 h-3" />
            </Link>

            <Button
              to="/investigations/new"
              variant="primary"
              size="sm"
              icon={PlusCircle}
            >
              New Investigation
            </Button>
          </div>
        </header>

        {/* Content View */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto page-fade-in">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
