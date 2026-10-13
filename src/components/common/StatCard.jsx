import React from 'react';

export default function StatCard({
  title,
  value,
  change,
  changeType = 'positive', // positive | negative | neutral
  subtitle,
  icon: Icon,
  className = '',
}) {
  return (
    <div
      className={`bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-sm hover:border-[#CBD5E1] transition-all ${className}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
          {title}
        </span>
        {Icon && (
          <div className="w-8 h-8 rounded-lg bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center">
            <Icon className="w-4 h-4" />
          </div>
        )}
      </div>

      <div className="mt-2.5 flex items-baseline gap-2">
        <span className="text-2xl sm:text-3xl font-bold tracking-tight text-[#0F172A]">
          {value}
        </span>
        {change && (
          <span
            className={`text-xs font-semibold px-1.5 py-0.5 rounded ${
              changeType === 'positive'
                ? 'bg-emerald-50 text-[#16A34A]'
                : changeType === 'negative'
                ? 'bg-red-50 text-[#DC2626]'
                : 'bg-slate-100 text-[#64748B]'
            }`}
          >
            {change}
          </span>
        )}
      </div>

      {subtitle && (
        <p className="text-xs text-[#64748B] mt-1.5">{subtitle}</p>
      )}
    </div>
  );
}
