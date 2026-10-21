import React, { useState } from 'react';
import {
  TrendingUp,
  Clock,
  CheckCircle2,
  DollarSign,
  Info
} from 'lucide-react';
import { ANALYTICS_DATA } from '../../services/analytics';
import Badge from '../../components/common/Badge';
import StatCard from '../../components/common/StatCard';

export default function Analytics() {
  const { weeklyTrend, languageDistribution, failureCategories, overview } = ANALYTICS_DATA;
  const [hoveredWeek, setHoveredWeek] = useState(null);

  const stats = [
    {
      title: 'Repair Success Rate',
      value: overview?.successRate || '87.5%',
      subtitle: 'Bugs patched without regression',
      icon: TrendingUp,
      change: '+4.2%',
      changeType: 'positive'
    },
    {
      title: 'Avg. Triage Latency',
      value: overview?.avgTime || '2m 14s',
      subtitle: 'Target: < 5 minutes',
      icon: Clock
    },
    {
      title: 'Tests Certified',
      value: overview?.testsPassed || '14,892',
      subtitle: 'Simulated runner executions',
      icon: CheckCircle2,
      change: '+12%',
      changeType: 'positive'
    },
    {
      title: 'Avg. Compute Cost',
      value: overview?.avgCostPerPatch || '$0.34',
      subtitle: 'Per verified pull request',
      icon: DollarSign
    },
  ];

  // Calculate maximum value for weekly chart normalization
  const maxWeekly = Math.max(
    ...weeklyTrend.map((w) => Math.max(w.dispatched || w.total || 0, w.resolved || 0)),
    1
  );

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
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-bold text-[#0F172A]">
                Weekly Investigation Volume &amp; Resolution
              </h3>
              <p className="text-xs text-[#64748B] mt-0.5">
                Resolved vs Dispatched orders across 7 consecutive release cycles
              </p>
            </div>
            <div className="flex items-center gap-4 text-xs">
              <span className="flex items-center gap-1.5 text-[#0F172A] font-medium">
                <span className="w-2.5 h-2.5 rounded-sm bg-[#2563EB]" />
                Resolved
              </span>
              <span className="flex items-center gap-1.5 text-[#64748B]">
                <span className="w-2.5 h-2.5 rounded-sm bg-[#E2E8F0]" />
                Dispatched
              </span>
            </div>
          </div>

          {/* Chart Graphic Area */}
          <div className="relative pt-6 pb-2">
            {/* Background horizontal guidelines */}
            <div className="absolute inset-x-0 top-8 bottom-6 flex flex-col justify-between pointer-events-none opacity-40">
              <div className="border-b border-dashed border-[#CBD5E1] w-full" />
              <div className="border-b border-dashed border-[#CBD5E1] w-full" />
              <div className="border-b border-dashed border-[#CBD5E1] w-full" />
            </div>

            {/* Bars Container */}
            <div className="h-44 flex items-end justify-between gap-3 px-3 relative border-b border-[#E2E8F0]">
              {weeklyTrend.map((w, idx) => {
                const resolvedPct = Math.min(100, Math.max(8, Math.round(((w.resolved || 0) / (maxWeekly * 1.15)) * 100)));
                const dispatchedPct = Math.min(100, Math.max(8, Math.round(((w.dispatched || w.total || w.resolved || 0) / (maxWeekly * 1.15)) * 100)));
                const isHovered = hoveredWeek === idx;

                return (
                  <div
                    key={idx}
                    className="flex-1 flex flex-col items-center justify-end h-full group relative cursor-pointer"
                    onMouseEnter={() => setHoveredWeek(idx)}
                    onMouseLeave={() => setHoveredWeek(null)}
                  >
                    {/* Hover Tooltip */}
                    {isHovered && (
                      <div className="absolute -top-12 z-20 bg-[#0F172A] text-white text-[11px] rounded-lg px-2.5 py-1.5 shadow-lg whitespace-nowrap pointer-events-none transform -translate-x-1/2 left-1/2 animate-in fade-in zoom-in-95 duration-150">
                        <div className="font-semibold">{w.week}: {w.resolved} resolved</div>
                        <div className="text-slate-300 text-[10px]">
                          {w.dispatched || w.total} dispatched ({w.rate}% rate)
                        </div>
                      </div>
                    )}

                    {/* Numeric Count Label */}
                    <span className={`text-[10px] font-mono mb-1.5 transition-colors ${isHovered ? 'text-[#2563EB] font-bold' : 'text-[#64748B]'}`}>
                      {w.resolved}
                    </span>

                    {/* Bar Columns */}
                    <div className="w-full h-32 flex items-end justify-center gap-1 sm:gap-1.5">
                      {/* Resolved Bar */}
                      <div
                        className="w-1/2 max-w-[16px] sm:max-w-[20px] bg-[#2563EB] group-hover:bg-[#1D4ED8] rounded-t transition-all duration-300 shadow-sm"
                        style={{ height: `${resolvedPct}%` }}
                        title={`${w.week}: ${w.resolved} resolved`}
                      />
                      {/* Dispatched Bar */}
                      <div
                        className="w-1/2 max-w-[16px] sm:max-w-[20px] bg-[#E2E8F0] group-hover:bg-[#CBD5E1] rounded-t transition-all duration-300"
                        style={{ height: `${dispatchedPct}%` }}
                        title={`${w.week}: ${w.dispatched || w.total} dispatched`}
                      />
                    </div>
                  </div>
                );
              })}
            </div>

            {/* X-Axis Labels */}
            <div className="flex justify-between items-center text-xs text-[#64748B] px-3 pt-2">
              {weeklyTrend.map((w, idx) => (
                <span
                  key={idx}
                  className={`flex-1 text-center font-medium transition-colors ${
                    hoveredWeek === idx ? 'text-[#0F172A] font-bold' : ''
                  }`}
                >
                  {w.week}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Language Distribution (4 Cols) */}
        <div className="lg:col-span-4 bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-[#0F172A]">
                Language Breakdown
              </h3>
              <span className="text-[11px] text-[#64748B] font-mono">
                {languageDistribution.reduce((acc, item) => acc + (item.count || 0), 0)} tracked
              </span>
            </div>
            <p className="text-xs text-[#64748B] mt-0.5">
              Target repository languages patched
            </p>
          </div>

          <div className="space-y-3.5 py-1">
            {languageDistribution.map((lang, idx) => {
              const share = lang.percentage ?? lang.share ?? 0;
              return (
                <div key={idx} className="space-y-1.5">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-semibold text-[#0F172A] flex items-center gap-2">
                      <span
                        className="w-2.5 h-2.5 rounded-full"
                        style={{ backgroundColor: lang.color || '#2563EB' }}
                      />
                      {lang.language}
                    </span>
                    <div className="flex items-center gap-2 font-mono text-[11px]">
                      {lang.count && (
                        <span className="text-[#64748B]">{lang.count} files</span>
                      )}
                      <span className="font-bold text-[#0F172A]">{share}%</span>
                    </div>
                  </div>
                  <div className="w-full bg-[#F1F5F9] h-2 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${share}%`,
                        backgroundColor: lang.color || '#2563EB'
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          <div className="pt-2 border-t border-[#E2E8F0] flex items-center gap-1.5 text-[11px] text-[#64748B]">
            <Info className="w-3.5 h-3.5 text-[#2563EB] shrink-0" />
            <span>Multi-language AST parser dynamically maps symbol boundaries.</span>
          </div>
        </div>
      </div>

      {/* Failure Categories Breakdown */}
      <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
          <div>
            <h3 className="text-sm font-bold text-[#0F172A]">
              Bug Categories Resolved by AI
            </h3>
            <p className="text-xs text-[#64748B] mt-0.5">
              Distribution of root causes identified and patched by autonomous agents
            </p>
          </div>
          <span className="text-xs font-mono text-[#64748B]">
            {failureCategories.reduce((acc, cat) => acc + (cat.count || 0), 0)} Total Cases
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
          {failureCategories.map((cat, idx) => (
            <div
              key={idx}
              className="p-4 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl flex flex-col justify-between space-y-3 hover:border-[#CBD5E1] hover:bg-white transition-all shadow-sm group"
            >
              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-1">
                  <span
                    className="text-xs font-bold text-[#0F172A] line-clamp-1"
                    title={cat.category}
                  >
                    {cat.category}
                  </span>
                  <span className="text-xs font-mono font-bold text-[#2563EB] bg-[#EFF6FF] px-1.5 py-0.5 rounded">
                    {cat.count}
                  </span>
                </div>
                <p className="text-[11px] text-[#64748B] leading-relaxed line-clamp-2 min-h-[32px]">
                  {cat.example || 'Pattern match via AST verification engine.'}
                </p>
              </div>

              <div className="pt-2 flex justify-between items-center text-[11px] text-[#64748B] border-t border-[#E2E8F0]">
                <span>Resolution Rate</span>
                <strong className="text-[#16A34A] font-mono font-bold">
                  {cat.resolutionRate || cat.pct || '96%'}
                </strong>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
