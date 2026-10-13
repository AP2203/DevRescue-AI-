import React from 'react';

export default function RomanNumeralList({
  items = [],
  columns = 3,
  className = '',
}) {
  const colClasses = {
    1: 'grid-cols-1',
    2: 'grid-cols-1 md:grid-cols-2',
    3: 'grid-cols-1 md:grid-cols-3',
    4: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-4',
  };

  return (
    <div className={`grid ${colClasses[columns] || colClasses[3]} gap-6 ${className}`}>
      {items.map((item, index) => {
        const num = String(index + 1).padStart(2, '0');
        return (
          <div
            key={index}
            className="flex flex-col rounded-xl border border-[#E2E8F0] bg-white hover:border-[#CBD5E1] p-6 transition-all shadow-xs group"
          >
            {/* Top index badge */}
            <div className="flex items-center justify-between mb-4">
              <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-[#EFF6FF] text-[#2563EB] border border-[#BFDBFE]">
                MODULE [{num}]
              </span>
              <span className="w-1.5 h-1.5 rounded-full bg-[#2563EB]/40 group-hover:bg-[#2563EB] transition-colors" />
            </div>

            <h4 className="text-base font-bold text-[#0F172A] mb-2 group-hover:text-[#2563EB] transition-colors">
              {item.title}
            </h4>

            <p className="text-xs text-[#64748B] leading-relaxed">
              {item.description || item.meta}
            </p>
          </div>
        );
      })}
    </div>
  );
}
