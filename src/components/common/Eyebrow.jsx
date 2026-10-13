import React from 'react';

export default function Eyebrow({
  children,
  variant = 'blue',
  prefix = '//',
  className = '',
}) {
  const styles = {
    blue: 'text-[#2563EB] bg-[#EFF6FF] border-[#BFDBFE]',
    green: 'text-[#16A34A] bg-[#DCFCE7] border-[#86EFAC]',
    amber: 'text-[#D97706] bg-[#FEF3C7] border-[#FDE68A]',
    red: 'text-[#DC2626] bg-[#FEE2E2] border-[#FECACA]',
    slate: 'text-[#64748B] bg-[#F1F5F9] border-[#E2E8F0]',
    // legacy mappings
    emerald: 'text-[#16A34A] bg-[#DCFCE7] border-[#86EFAC]',
    cyan: 'text-[#2563EB] bg-[#EFF6FF] border-[#BFDBFE]',
    rose: 'text-[#DC2626] bg-[#FEE2E2] border-[#FECACA]',
  };

  const selected = styles[variant] || styles.blue;

  return (
    <div
      className={`inline-flex items-center gap-1.5 font-mono text-[11px] font-semibold tracking-wider uppercase px-2.5 py-0.5 rounded border ${selected} ${className}`}
    >
      {prefix && <span className="opacity-70">{prefix}</span>}
      <span>{children}</span>
    </div>
  );
}
