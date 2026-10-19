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
  ArrowUpRight
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import Button, { PrimaryButton } from '../../components/common/Button';
import { StatusBadge } from '../../components/common/Badge';
import StatCard from '../../components/common/StatCard';
import MultiRepoQueueDashboard from '../../components/dashboard/MultiRepoQueueDashboard';

export default function Dashboard() {
  const { repositories } = useApp();
  const [activeTab, setActiveTab] = useState('queue');
  const [timeRange, setTimeRange] = useState('7d');

  // Realistic metrics matching Section 9
  const stats = [
    { title: 'Repositories', value: repositories.length || 4, subtitle: 'Active in workspace', icon: FolderGit2 },
    { title: 'Investigations', value: 12, subtitle: '+3 from last week', icon: Activity, change: '+25%', changeType: 'positive' },
    { title: 'Bugs Fixed', value: 9, subtitle: 'Autonomous resolution', icon: CheckCircle2, change: '+18%', changeType: 'positive' },
    { title: 'Success Rate', value: '87%', subtitle: 'Deterministic pass rate', icon: TrendingUp, change: '+4.2%', changeType: 'positive' },
    { title: 'Average Fix Time', value: '2m 14s', subtitle: 'Target: < 5m', icon: Clock },
  ];

  // Specific recent investigations requested in Section 9
  const recentInvestigationsList = [
    {
      id: '1',
      title: 'Login authentication bug',
      repo: 'demo-react-app',
      status: 'FIXED',
      statusLabel: 'Fixed',
      time: '12m ago',
      tests: '14/14 Passed',
      link: '/investigations/1'
    },
    {
      id: '2',
      title: 'API timeout issue',
      repo: 'api-service',
      status: 'TESTING',
      statusLabel: 'Testing',
      time: '1h ago',
      tests: '26/28 Running',
      link: '/investigations/2'
    },
    {
      id: '3',
      title: 'Navbar rendering issue',
      repo: 'dashboard-ui',
      status: 'PR_READY',
      statusLabel: 'PR Ready',
      time: '3h ago',
      tests: '19/19 Passed',
      link: '/investigations/3/review'
    },
    {
      id: '4',
      title: 'Database connection error',
      repo: 'ml-models',
      status: 'FAILED',
      statusLabel: 'Failed',
      time: 'Yesterday',
      tests: '4 Failed',
      link: '/investigations/4'
    }
  ];

  // Subtle blue activity chart data
  const activityData = [
    { day: 'Mon', count: 4, height: '40%' },
    { day: 'Tue', count: 7, height: '70%' },
    { day: 'Wed', count: 5, height: '50%' },
    { day: 'Thu', count: 9, height: '90%' },
    { day: 'Fri', count: 8, height: '80%' },
    { day: 'Sat', count: 3, height: '30%' },
    { day: 'Sun', count: 6, height: '60%' },
  ];

  return (
    <div className="space-y-8">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-[#E2E8F0]">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#0F172A]">
            Welcome back, Ansh
          </h1>
          <p className="text-sm text-[#64748B] mt-1">
            Investigate a GitHub issue and let DevRescue verify the fix.
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
        <div className="lg:col-span-7 bg-white border border-[#E2E8F0] rounded-xl shadow-sm overflow-hidden">
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

          <div className="divide-y divide-[#E2E8F0]">
            {recentInvestigationsList.map((inv) => (
              <div
                key={inv.id}
                className="p-4 hover:bg-[#F8FAFC] transition-colors flex items-center justify-between gap-4"
              >
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <Link
                      to={inv.link}
                      className="text-sm font-semibold text-[#0F172A] hover:text-[#2563EB] truncate block"
                    >
                      {inv.title}
                    </Link>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-[#64748B]">
                    <span className="font-mono text-slate-500">{inv.repo}</span>
                    <span>·</span>
                    <span>{inv.tests}</span>
                    <span>·</span>
                    <span>{inv.time}</span>
                  </div>
                </div>

                <div className="flex items-center gap-3 flex-shrink-0">
                  <StatusBadge status={inv.status} />
                  <Link
                    to={inv.link}
                    className="p-1 text-slate-400 hover:text-[#2563EB] rounded transition-colors"
                    title="Open investigation"
                  >
                    <ArrowUpRight className="w-4 h-4" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Connected Repositories (5 Cols) */}
        <div className="lg:col-span-5 bg-white border border-[#E2E8F0] rounded-xl shadow-sm overflow-hidden">
          <div className="p-5 border-b border-[#E2E8F0] flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-[#0F172A]">
                Connected Repositories
              </h3>
              <p className="text-xs text-[#64748B] mt-0.5">
                4 repositories ready for AI triage
              </p>
            </div>
            <Link
              to="/repositories"
              className="text-xs font-semibold text-[#2563EB] hover:text-[#1D4ED8]"
            >
              Manage
            </Link>
          </div>

          <div className="divide-y divide-[#E2E8F0]">
            {repositories.slice(0, 4).map((repo) => (
              <div
                key={repo.id}
                className="p-4 hover:bg-[#F8FAFC] transition-colors flex items-center justify-between gap-3"
              >
                <div className="min-w-0 space-y-1">
                  <div className="flex items-center gap-2">
                    <FolderGit2 className="w-4 h-4 text-[#2563EB] flex-shrink-0" />
                    <Link
                      to="/repositories"
                      className="text-sm font-semibold text-[#0F172A] hover:text-[#2563EB] truncate"
                    >
                      {repo.name}
                    </Link>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-[#64748B]">
                    <span>{repo.language}</span>
                    <span>·</span>
                    <span>{repo.openIssuesCount} open issues</span>
                  </div>
                </div>

                <div className="flex items-center gap-2 flex-shrink-0">
                  <Button
                    to={`/investigations/new?repo=${encodeURIComponent(repo.name)}`}
                    variant="outline"
                    size="sm"
                    className="text-xs py-1 px-2.5"
                  >
                    Investigate
                  </Button>
                </div>
              </div>
            ))}
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
