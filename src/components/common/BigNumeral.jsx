import React from 'react';

export default function BigNumeral({
  children,
  size = 'hero',
  accent = false,
  caption = null,
  trend = null,
  className = '',
}) {
  const sizeClasses = {
    hero: 'text-5xl sm:text-6xl md:text-7xl',
    xl: 'text-4xl sm:text-5xl',
    lg: 'text-3xl sm:text-4xl',
    md: 'text-2xl sm:text-3xl',
    sm: 'text-xl sm:text-2xl',
  };

  const selectedSize = sizeClasses[size] || sizeClasses.hero;
  const textColor = accent ? 'text-[#2563EB]' : 'text-[#0F172A]';

  return (
    <div className={`flex flex-col items-start ${className}`}>
      <div className="flex items-baseline gap-2">
        <span
          className={`font-sans font-extrabold tracking-tight ${selectedSize} ${textColor} tabular-nums`}
        >
          {children}
        </span>
        {trend && (
          <span className="font-mono text-xs font-semibold text-[#16A34A] bg-[#DCFCE7] px-2 py-0.5 rounded border border-[#86EFAC]">
            {trend}
          </span>
        )}
      </div>
      {caption && (
        <span className="mt-1.5 uppercase text-[11px] font-semibold tracking-wider text-[#64748B] flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-[#2563EB]" />
          {caption}
        </span>
      )}
    </div>
  );
}
