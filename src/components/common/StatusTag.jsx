import React from 'react';

export default function StatusTag({ status, label = null, className = '' }) {
  const norm = String(status || '').toUpperCase();

  let dotColor = 'bg-slate-400';
  let badgeStyle = 'text-[#64748B] bg-[#F1F5F9] border-[#E2E8F0]';
  let displayLabel = label || norm;

  if (norm === 'RUNNING' || norm === 'IN_PROGRESS' || norm === 'ACTIVE') {
    dotColor = 'bg-[#2563EB]';
    badgeStyle = 'text-[#2563EB] bg-[#EFF6FF] border-[#BFDBFE]';
    if (!label && norm === 'IN_PROGRESS') displayLabel = 'ACTIVE DISPATCH';
  } else if (norm === 'FAILED' || norm === 'CRITICAL' || norm === 'REJECTED') {
    dotColor = 'bg-[#DC2626]';
    badgeStyle = 'text-[#DC2626] bg-[#FEE2E2] border-[#FECACA]';
  } else if (
    norm === 'PASSED' ||
    norm === 'SUCCESS' ||
    norm === 'HEALTHY' ||
    norm === 'READY_FOR_REVIEW' ||
    norm === 'COMPLETE' ||
    norm === 'READY'
  ) {
    dotColor = 'bg-[#16A34A]';
    badgeStyle = 'text-[#16A34A] bg-[#DCFCE7] border-[#86EFAC]';
    if (!label && norm === 'READY_FOR_REVIEW') displayLabel = 'PATCH READY';
  } else if (norm === 'MERGED' || norm === 'OPEN' || norm === 'PR_OPENED') {
    dotColor = 'bg-[#2563EB]';
    badgeStyle = 'text-[#2563EB] bg-[#EFF6FF] border-[#BFDBFE]';
    if (!label && norm === 'PR_OPENED') displayLabel = 'PR DEPLOYED';
  } else if (norm === 'PENDING' || norm === 'WAITING') {
    dotColor = 'bg-slate-400';
    badgeStyle = 'text-[#64748B] bg-[#F8FAFC] border-[#E2E8F0]';
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-mono text-[11px] font-semibold tracking-wider uppercase px-2.5 py-0.5 rounded-full border ${badgeStyle} ${className}`}
    >
      <span className="relative flex h-2 w-2">
        {(norm === 'RUNNING' || norm === 'IN_PROGRESS' || norm === 'ACTIVE') && (
          <span
            className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${dotColor}`}
          />
        )}
        <span className={`relative inline-flex rounded-full h-2 w-2 ${dotColor}`} />
      </span>
      <span>{displayLabel}</span>
    </span>
  );
}
