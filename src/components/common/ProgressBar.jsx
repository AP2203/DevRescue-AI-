import React from 'react';

export default function ProgressBar({
  progress = 0,
  showLabel = false,
  label,
  height = 'h-2',
  className = '',
}) {
  const clamped = Math.min(100, Math.max(0, progress));

  return (
    <div className={`w-full ${className}`}>
      {(showLabel || label) && (
        <div className="flex justify-between items-center mb-1.5 text-xs">
          <span className="font-medium text-[#0F172A]">{label || 'Progress'}</span>
          <span className="font-semibold text-[#2563EB]">{clamped}%</span>
        </div>
      )}
      <div className={`w-full bg-[#E2E8F0] rounded-full overflow-hidden ${height}`}>
        <div
          className="bg-[#2563EB] h-full rounded-full transition-all duration-500 ease-out"
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}
