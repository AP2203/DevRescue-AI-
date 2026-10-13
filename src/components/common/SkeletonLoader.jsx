import React from 'react';

export default function SkeletonLoader({ className = '', height = 'h-4', width = 'w-full' }) {
  return (
    <div
      className={`rounded bg-slate-200/70 animate-pulse ${height} ${width} ${className}`}
    />
  );
}

export function SkeletonCard() {
  return (
    <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 space-y-4">
      <div className="flex items-center justify-between">
        <SkeletonLoader width="w-1/3" height="h-5" />
        <SkeletonLoader width="w-16" height="h-4" />
      </div>
      <SkeletonLoader width="w-3/4" height="h-4" />
      <div className="flex items-center gap-3 pt-2">
        <SkeletonLoader width="w-20" height="h-6" className="rounded-full" />
        <SkeletonLoader width="w-24" height="h-6" className="rounded-full" />
      </div>
    </div>
  );
}

export function SkeletonTable({ rows = 4 }) {
  return (
    <div className="bg-white border border-[#E2E8F0] rounded-xl overflow-hidden">
      <div className="p-4 bg-[#F8FAFC] border-b border-[#E2E8F0] flex gap-4">
        <SkeletonLoader width="w-1/4" height="h-4" />
        <SkeletonLoader width="w-1/3" height="h-4" />
        <SkeletonLoader width="w-1/6" height="h-4" />
      </div>
      <div className="divide-y divide-[#E2E8F0]">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="p-4 flex gap-4 items-center">
            <SkeletonLoader width="w-1/4" height="h-4" />
            <SkeletonLoader width="w-1/2" height="h-4" />
            <SkeletonLoader width="w-1/6" height="h-4" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function SkeletonDiff() {
  return (
    <div className="bg-[#0F172A] rounded-xl border border-slate-800 p-6 space-y-3 font-mono">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="h-4 bg-slate-700/60 rounded w-48 animate-pulse" />
        <div className="h-4 bg-slate-700/60 rounded w-20 animate-pulse" />
      </div>
      <div className="h-4 bg-slate-800 rounded w-3/4 animate-pulse" />
      <div className="h-4 bg-red-950/60 rounded w-5/6 animate-pulse" />
      <div className="h-4 bg-emerald-950/60 rounded w-4/5 animate-pulse" />
      <div className="h-4 bg-slate-800 rounded w-2/3 animate-pulse" />
      <div className="h-4 bg-slate-800 rounded w-1/2 animate-pulse" />
    </div>
  );
}
