import React from 'react';

export default function Footnote({ children, className = '' }) {
  return (
    <p className={`font-mono text-xs text-[#64748B] flex items-center gap-1.5 leading-normal ${className}`}>
      <span className="text-[#2563EB] font-bold">//</span>
      <span>
        {children || (
          <>
            Isolated demo sandbox runtime. <span className="text-[#0F172A]">All patch trials synthesized with simulated test verification.</span>
          </>
        )}
      </span>
    </p>
  );
}
