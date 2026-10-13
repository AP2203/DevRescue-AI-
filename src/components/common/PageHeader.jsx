import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Bug } from 'lucide-react';

export default function PageHeader({
  leftTitle = 'DevRescue AI',
  leftLink = null,
  centerMeta = 'AUTONOMOUS BUG DISPATCH & INVESTIGATION CLUSTER',
}) {
  const [time, setTime] = useState(() => new Date().toUTCString().slice(17, 25));

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date().toUTCString().slice(17, 25));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="w-full bg-white border-b border-[#E2E8F0] sticky top-0 z-40 shadow-xs">
      <div className="max-w-[1400px] mx-auto px-4 md:px-8 py-3.5 flex flex-col md:flex-row items-center justify-between gap-3">
        {/* Left: Brand */}
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-[#2563EB] text-white flex items-center justify-center">
            <Bug className="w-4 h-4" />
          </div>
          {leftLink ? (
            <Link
              to={leftLink}
              className="font-bold text-base tracking-tight text-[#0F172A] hover:text-[#2563EB] transition-colors"
            >
              <span>{leftTitle}</span>
            </Link>
          ) : (
            <span className="font-bold text-base tracking-tight text-[#0F172A]">
              {leftTitle}
            </span>
          )}
        </div>

        {/* Center: Meta Description */}
        <div className="text-[11px] font-mono uppercase tracking-wider text-[#64748B] text-center">
          {centerMeta}
        </div>

        {/* Right: Live UTC Clock */}
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#16A34A]" />
          <span className="font-mono text-xs font-semibold text-[#0F172A] tabular-nums">
            {time} UTC
          </span>
        </div>
      </div>
    </header>
  );
}
