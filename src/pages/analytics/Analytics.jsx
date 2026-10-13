import React from 'react';
import {
  TrendingUp,
  Clock,
  CheckCircle2,
  DollarSign
} from 'lucide-react';
import { ANALYTICS_DATA } from '../../services/analytics';
import Badge from '../../components/common/Badge';
import StatCard from '../../components/common/StatCard';

export default function Analytics() {
  const { weeklyTrend, languageDistribution, failureCategories } = ANALYTICS_DATA;

  const stats = [
    { title: 'Repair Success Rate', value: '87.5%', subtitle: 'Bugs patched without regression', icon: TrendingUp, change: '+4.2%', changeType: 'positive' },
    { title: 'Avg. Triage Latency', value: '2m 14s', subtitle: 'Target: < 5 minutes', icon: Clock },
    { title: 'Tests Certified', value: '14,892', subtitle: 'Simulated runner executions', icon: CheckCircle2, change: '+12%', changeType: 'positive' },
    { title: 'Avg. Compute Cost', value: '$0.34', subtitle: 'Per verified pull request', icon: DollarSign },
  ];

  return (
    <div className="space-y-8">
      {/* Title */}
      <div className="pb-6 border-b border-[#E2E8F0]">
        <div className="flex items-center gap-2 mb-2">
          <Badge variant="blue" size="sm">
            METRICS &amp; TELEMETRY
          </Badge>
          <span className="text-xs text-[#64748B]">Updated 12m ago</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#0F172A]">
          System Analytics
        </h1>
        <p className="text-sm text-[#64748B] max-w-3xl mt-1 leading-relaxed">
          Empirical measurements of bug reproduction latency, AST verification fidelity, and pull request acceptance ratios across all connected codebases.
        </p>
      </div>

      {/* 4 Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
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

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Weekly Trend (8 Cols) */}
        <div className="lg:col-span-8 bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-[#0F172A]">
                Weekly Investigation Volume &amp; Resolution
              </h3>
              <p className="text-xs text-[#64748B] mt-0.5">
                Resolved vs Dispatched orders across 6 weeks
              </p>
            </div>
            <div className="flex items-center gap-4 text-xs">
              <span className="flex items-center gap-1.5 text-[#0F172A] font-medium">
                <span className="w-2.5 h-2.5 rounded-full bg-[#2563EB]" />
                Resolved
              </span>
              <span className="flex items-center gap-1.5 text-[#64748B]">
                <span className="w-2.5 h-2.5 rounded-full bg-[#E2E8F0]" />
                Dispatched
              </span>
            </div>
          </div>

          <div className="h-52 flex items-end justify-between gap-4 pt-6 px-4 border-b border-[#E2E8F0]">
            {weeklyTrend.map((w, idx) => (
              <div key={idx} className="flex-1 flex flex-col items-center gap-2 h-full justify-end group">
                <span className="text-[10px] font-mono text-[#64748B]">
                  {w.resolved}
                </span>
                <div className="w-full flex items-end justify-center gap-1">
                  <div
                    className="w-1/2 max-w-[20px] bg-[#2563EB] rounded-t-sm transition-all"
                    style={{ height: `${(w.resolved / 40) * 160}px` }}
                  />
                  <div
                    className="w-1/2 max-w-[20px] bg-[#E2E8F0] rounded-t-sm transition-all"
                    style={{ height: `${(w.total / 40) * 160}px` }}
                  />
                </div>
              </div>
            ))}
          </div>

          <div className="flex justify-between items-center text-xs text-[#64748B] px-4">
            {weeklyTrend.map((w, idx) => (
              <span key={idx} className="flex-1 text-center font-medium">
                {w.week}
              </span>
            ))}
          </div>
        </div>

        {/* Language Distribution (4 Cols) */}
        <div className="lg:col-span-4 bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm space-y-4">
          <div>
            <h3 className="text-sm font-bold text-[#0F172A]">
              Language Breakdown
            </h3>
            <p className="text-xs text-[#64748B] mt-0.5">
              Target repository languages
            </p>
          </div>

          <div className="space-y-3 pt-2">
            {languageDistribution.map((lang, idx) => (
              <div key={idx} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="font-semibold text-[#0F172A]">{lang.language}</span>
                  <span className="text-[#64748B] font-mono">{lang.share}%</span>
                </div>
                <div className="w-full bg-[#E2E8F0] h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-[#2563EB] h-full rounded-full"
                    style={{ width: `${lang.share}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Failure Categories Breakdown */}
      <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm space-y-4">
        <div>
          <h3 className="text-sm font-bold text-[#0F172A]">
            Bug Categories Resolved by AI
          </h3>
          <p className="text-xs text-[#64748B] mt-0.5">
            Distribution of root causes identified by Bug Investigator
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {failureCategories.map((cat, idx) => (
            <div key={idx} className="p-4 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-[#0F172A]">{cat.category}</span>
                <span className="text-xs font-bold text-[#2563EB]">{cat.count}</span>
              </div>
              <p className="text-xs text-[#64748B] leading-relaxed">{cat.example}</p>
              <div className="pt-2 flex justify-between text-[11px] text-[#64748B] border-t border-[#E2E8F0]">
                <span>Resolution Rate</span>
                <strong className="text-[#16A34A]">{cat.resolutionRate}</strong>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
