import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  PlusCircle,
  FolderGit2,
  Activity,
  CheckCircle2,
  TrendingUp,
  Clock,
  ChevronRight,
  ArrowUpRight,
  GitPullRequest,
  ShieldAlert
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import Button, { PrimaryButton } from '../../components/common/Button';
import { StatusBadge } from '../../components/common/Badge';
import StatCard from '../../components/common/StatCard';
import GithubIcon from '../../components/common/GithubIcon';
import MultiRepoQueueDashboard from '../../components/dashboard/MultiRepoQueueDashboard';
import api from '../../services/api';

export default function Dashboard() {
  const { user } = useAuth();
  const {
    repositories,
    investigations,
    pullRequests,
    githubUser,
    githubConnected,
    backendHealth
  } = useApp();

  const [activeTab, setActiveTab] = useState('queue');
  const [timeRange, setTimeRange] = useState('7d');

  // Real production metrics
  const stats = [
    {
      title: 'Connected Repos',
      value: repositories.length,
      subtitle: githubConnected ? `@${githubUser?.login || 'github'} active` : 'Connect GitHub account',
      icon: FolderGit2
    },
    {
      title: 'Investigations',
      value: investigations.length,
      subtitle: 'Autonomous triage runs',
      icon: Activity
    },
    {
      title: 'Verified PRs',
      value: pullRequests.length,
      subtitle: 'Upstream pull requests',
      icon: GitPullRequest
    },
    {
      title: 'Backend Health',
      value: backendHealth.status === 'healthy' ? 'Online' : (backendHealth.status === 'checking' ? 'Checking' : 'Offline'),
      subtitle: backendHealth.status === 'healthy' ? 'FastAPI + Docker' : 'Render API connecting',
      icon: CheckCircle2
    },
    {
      title: 'ML Risk Model',
      value: backendHealth.mlStatus === 'healthy' ? 'XGBoost Active' : 'Initializing',
      subtitle: '13-feature inference',
      icon: TrendingUp
    },
  ];

  // Subtle activity chart data
  const activityData = [
    { day: 'Mon', count: 2, height: '30%' },
    { day: 'Tue', count: 4, height: '55%' },
    { day: 'Wed', count: 3, height: '40%' },
    { day: 'Thu', count: 6, height: '80%' },
    { day: 'Fri', count: 5, height: '65%' },
    { day: 'Sat', count: 2, height: '30%' },
    { day: 'Sun', count: 4, height: '50%' },
  ];

  const displayName = githubUser?.name || githubUser?.login || user?.name || 'Engineer';

  return (
    <div className="space-y-8">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-[#E2E8F0]">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#0F172A]">
            Welcome back, {displayName}
          </h1>
          <p className="text-sm text-[#64748B] mt-1">
            Autonomous Software Engineering Agent — from GitHub Issue to Verified Pull Request.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            to="/repositories"
            variant="outline"
            size="md"
          >
            Repositories
          </Button>
          <PrimaryButton
            to="/investigations/new"
            size="md"
            icon={PlusCircle}
            className="shadow-sm font-semibold"
          >
            + New Investigation
          </PrimaryButton>
        </div>
      </div>

      {/* Real GitHub Connect Banner if not connected */}
      {!githubConnected && (
        <div className="p-6 rounded-2xl bg-gradient-to-r from-[#0F172A] via-[#1E293B] to-[#0F172A] text-white shadow-md flex flex-col md:flex-row items-start md:items-center justify-between gap-6 border border-slate-700/60">
          <div className="space-y-2 max-w-xl">
            <div className="inline-flex items-center gap-2 text-xs font-semibold text-blue-400 bg-blue-500/10 px-3 py-1 rounded-full border border-blue-500/20">
              <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
              Real GitHub Connection Required
            </div>
            <h2 className="text-lg font-bold">Connect your GitHub to enable Real AI Investigations</h2>
            <p className="text-xs text-slate-300 leading-relaxed">
              DevRescue AI scans your repository branches, extracts issue context, diagnoses bugs with NVIDIA Nemotron AI, verifies fixes in isolated sandboxes, and submits verified Pull Requests.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              onClick={() => api.githubLogin()}
              variant="primary"
              className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white font-semibold text-xs px-4 py-2.5 shadow-sm"
            >
              Sign in with GitHub (OAuth)
            </Button>
            <Button
              to="/repositories"
              variant="outline"
              className="text-white border-white/20 hover:bg-white/10 text-xs px-4 py-2.5"
            >
              Enter Token (PAT)
            </Button>
          </div>
        </div>
      )}

      {/* Primary Dashboard Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-[#E2E8F0]">
        <button
          type="button"
          onClick={() => setActiveTab('queue')}
          className={`pb-3 px-3 text-sm font-bold border-b-2 transition-all flex items-center gap-2 ${
            activeTab === 'queue'
              ? 'border-[#2563EB] text-[#2563EB]'
              : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
          }`}
        >
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span>Multi-Repo Auto-Repair Queue</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('overview')}
          className={`pb-3 px-3 text-sm font-bold border-b-2 transition-all flex items-center gap-2 ${
            activeTab === 'overview'
              ? 'border-[#2563EB] text-[#2563EB]'
              : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
          }`}
        >
          <span>Workspace Overview & Metrics</span>
        </button>
      </div>

      {activeTab === 'queue' ? (
        <MultiRepoQueueDashboard />
      ) : (
        <>
          {/* 5 Stats Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {stats.map((stat, idx) => (
              <StatCard
                key={idx}
                title={stat.title}
                value={stat.value}
                subtitle={stat.subtitle}
                change={stat.change}
                changeType={stat.changeType}
                icon={stat.icon}
              />
            ))}
          </div>

      {/* Visual Charts: Investigation Activity & Fix Success Rate */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Chart: Activity Bar Chart (7 Cols) */}
        <div className="lg:col-span-7 bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-sm font-bold text-[#0F172A]">
                Investigation Activity
              </h3>
              <p className="text-xs text-[#64748B] mt-0.5">
                Number of autonomous triage orders executed
              </p>
            </div>
            <div className="flex items-center gap-1 p-1 bg-[#F1F5F9] rounded-lg text-xs font-medium">
              <button
                type="button"
                onClick={() => setTimeRange('7d')}
                className={`px-2.5 py-1 rounded transition-colors ${
                  timeRange === '7d' ? 'bg-white text-[#2563EB] shadow-xs' : 'text-[#64748B]'
                }`}
              >
                7 Days
              </button>
              <button
                type="button"
                onClick={() => setTimeRange('30d')}
                className={`px-2.5 py-1 rounded transition-colors ${
                  timeRange === '30d' ? 'bg-white text-[#2563EB] shadow-xs' : 'text-[#64748B]'
                }`}
              >
                30 Days
              </button>
            </div>
          </div>

          {/* Clean Subtle Blue Bar Chart */}
          <div className="h-44 flex items-end justify-between gap-3 pt-4 px-2 border-b border-[#E2E8F0]">
            {activityData.map((d, i) => (
              <div key={i} className="flex-1 flex flex-col items-center gap-2 h-full justify-end group">
                <span className="text-[11px] font-mono text-[#64748B] opacity-0 group-hover:opacity-100 transition-opacity">
                  {d.count}
                </span>
                <div
                  className="w-full max-w-[38px] bg-[#EFF6FF] group-hover:bg-[#2563EB] border border-[#BFDBFE] group-hover:border-[#1D4ED8] rounded-t-md transition-all duration-200"
                  style={{ height: d.height }}
                />
              </div>
            ))}
          </div>

          <div className="flex justify-between items-center text-xs text-[#64748B] pt-3 px-2">
            {activityData.map((d, i) => (
              <span key={i} className="flex-1 text-center font-medium">
                {d.day}
              </span>
            ))}
          </div>
        </div>

        {/* Right Chart: Fix Success Rate & Agent Performance (5 Cols) */}
        <div className="lg:col-span-5 bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-[#0F172A]">
                  Fix Success Rate
                </h3>
                <p className="text-xs text-[#64748B] mt-0.5">
                  Resolution and verification breakdown
                </p>
              </div>
              <span className="text-sm font-extrabold text-[#16A34A] bg-[#DCFCE7] px-2.5 py-1 rounded-full">
                87.5%
              </span>
            </div>

            {/* Visual Bars Breakdown */}
            <div className="space-y-4 pt-2">
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-[#0F172A] font-medium">First-Pass Resolution</span>
                  <span className="text-[#64748B]">9 / 12 (75%)</span>
                </div>
                <div className="w-full bg-[#E2E8F0] h-2 rounded-full overflow-hidden">
                  <div className="bg-[#2563EB] h-full rounded-full" style={{ width: '75%' }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-[#0F172A] font-medium">Resolved on Test Retry</span>
                  <span className="text-[#64748B]">2 / 12 (17%)</span>
                </div>
                <div className="w-full bg-[#E2E8F0] h-2 rounded-full overflow-hidden">
                  <div className="bg-[#60A5FA] h-full rounded-full" style={{ width: '17%' }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-[#0F172A] font-medium">Requires Human Triage</span>
                  <span className="text-[#64748B]">1 / 12 (8%)</span>
                </div>
                <div className="w-full bg-[#E2E8F0] h-2 rounded-full overflow-hidden">
                  <div className="bg-[#F87171] h-full rounded-full" style={{ width: '8%' }} />
                </div>
              </div>
            </div>
          </div>

          <div className="p-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg mt-6 flex items-center justify-between text-xs">
            <span className="text-[#64748B]">Avg autonomous repair latency</span>
            <span className="font-semibold text-[#0F172A]">2 minutes 14 seconds</span>
          </div>
        </div>
      </div>

      {/* Two Columns: Recent Investigations & Connected Repositories */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Recent Investigations Table (7 Cols) */}
        <div className="lg:col-span-7 bg-white border border-[#E2E8F0] rounded-xl shadow-sm overflow-hidden flex flex-col justify-between">
          <div>
            <div className="p-5 border-b border-[#E2E8F0] flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-[#0F172A]">
                  Recent Investigations
                </h3>
                <p className="text-xs text-[#64748B] mt-0.5">
                  Latest autonomous bug diagnoses and repairs
                </p>
              </div>
              <Link
                to="/history"
                className="text-xs font-semibold text-[#2563EB] hover:text-[#1D4ED8] flex items-center gap-1"
              >
                <span>View All</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            {investigations.length === 0 ? (
              <div className="p-8 text-center space-y-3">
                <div className="w-12 h-12 rounded-xl bg-blue-50 text-[#2563EB] flex items-center justify-center mx-auto">
                  <Activity className="w-6 h-6" />
                </div>
                <h4 className="text-sm font-bold text-[#0F172A]">No Investigations Yet</h4>
                <p className="text-xs text-[#64748B] max-w-sm mx-auto">
                  Select an issue from your connected GitHub repository to launch autonomous root cause analysis and verified code repair.
                </p>
                <div className="pt-2">
                  <PrimaryButton to="/investigations/new" size="sm" icon={PlusCircle}>
                    Start First Investigation
                  </PrimaryButton>
                </div>
              </div>
            ) : (
              <div className="divide-y divide-[#E2E8F0]">
                {investigations.slice(0, 5).map((inv) => {
                  const invLink = `/investigations/${inv.id}`;
                  const repoLabel = inv.repo || inv.repository || 'Repository';
                  const titleLabel = inv.issue_title || inv.issueTitle || inv.title || `Investigation #${inv.id}`;

                  return (
                    <div
                      key={inv.id}
                      className="p-4 hover:bg-[#F8FAFC] transition-colors flex items-center justify-between gap-4"
                    >
                      <div className="space-y-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <Link
                            to={invLink}
                            className="text-sm font-semibold text-[#0F172A] hover:text-[#2563EB] truncate block"
                          >
                            {titleLabel}
                          </Link>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-[#64748B]">
                          <span className="font-mono text-slate-500">{repoLabel}</span>
                          <span>·</span>
                          <span>Issue #{inv.issue_number || inv.issueNumber || 1}</span>
                          {inv.status && (
                            <>
                              <span>·</span>
                              <span className="uppercase text-[10px] font-mono">{inv.status}</span>
                            </>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-3 flex-shrink-0">
                        <StatusBadge status={inv.status || 'ANALYZING'} />
                        <Link
                          to={invLink}
                          className="p-1 text-slate-400 hover:text-[#2563EB] rounded transition-colors"
                          title="Open investigation"
                        >
                          <ArrowUpRight className="w-4 h-4" />
                        </Link>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="p-3 bg-[#F8FAFC] border-t border-[#E2E8F0] text-center">
            <Link
              to="/investigations/new"
              className="text-xs font-semibold text-[#2563EB] hover:underline"
            >
              + Launch New Autonomous Investigation
            </Link>
          </div>
        </div>

        {/* Connected Repositories (5 Cols) */}
        <div className="lg:col-span-5 bg-white border border-[#E2E8F0] rounded-xl shadow-sm overflow-hidden flex flex-col justify-between">
          <div>
            <div className="p-5 border-b border-[#E2E8F0] flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-[#0F172A]">
                  Connected Repositories
                </h3>
                <p className="text-xs text-[#64748B] mt-0.5">
                  {repositories.length} {repositories.length === 1 ? 'repository' : 'repositories'} ready for AI triage
                </p>
              </div>
              <Link
                to="/repositories"
                className="text-xs font-semibold text-[#2563EB] hover:text-[#1D4ED8]"
              >
                Manage
              </Link>
            </div>

            {repositories.length === 0 ? (
              <div className="p-8 text-center space-y-3">
                <div className="w-10 h-10 rounded-xl bg-slate-100 text-slate-500 flex items-center justify-center mx-auto">
                  <FolderGit2 className="w-5 h-5" />
                </div>
                <h4 className="text-sm font-bold text-[#0F172A]">No Repositories Connected</h4>
                <p className="text-xs text-[#64748B] max-w-xs mx-auto">
                  Connect your GitHub account to access your repositories and open issues.
                </p>
                <div className="pt-1">
                  <Button to="/repositories" variant="outline" size="sm">
                    Connect GitHub
                  </Button>
                </div>
              </div>
            ) : (
              <div className="divide-y divide-[#E2E8F0]">
                {repositories.slice(0, 5).map((repo) => {
                  const repoFullName = repo.full_name || repo.name;
                  const repoLang = repo.language || 'Repository';
                  const issuesCount = repo.open_issues_count || repo.openIssuesCount || 0;

                  return (
                    <div
                      key={repo.id || repoFullName}
                      className="p-4 hover:bg-[#F8FAFC] transition-colors flex items-center justify-between gap-3"
                    >
                      <div className="min-w-0 space-y-1">
                        <div className="flex items-center gap-2">
                          <FolderGit2 className="w-4 h-4 text-[#2563EB] flex-shrink-0" />
                          <Link
                            to="/repositories"
                            className="text-sm font-semibold text-[#0F172A] hover:text-[#2563EB] truncate"
                          >
                            {repoFullName}
                          </Link>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-[#64748B]">
                          <span>{repoLang}</span>
                          <span>·</span>
                          <span>{issuesCount} open {issuesCount === 1 ? 'issue' : 'issues'}</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 flex-shrink-0">
                        <Button
                          to={`/investigations/new?repo=${encodeURIComponent(repoFullName)}`}
                          variant="outline"
                          size="sm"
                          className="text-xs py-1 px-2.5"
                        >
                          Investigate
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="p-3 bg-[#F8FAFC] border-t border-[#E2E8F0] text-center">
            <Link
              to="/repositories"
              className="text-xs font-semibold text-[#2563EB] hover:underline"
            >
              + Connect Another Repository
            </Link>
          </div>
        </div>
      </div>
        </>
      )}
    </div>
  );
}
