import React from 'react';

export default function RuledList({ items = [], renderItem, className = '' }) {
  return (
    <ul className={`divide-y divide-[#E2E8F0] rounded-xl border border-[#E2E8F0] bg-white overflow-hidden shadow-xs ${className}`}>
      {items.map((item, idx) => (
        <li key={item.id || idx} className="py-3 px-4 flex items-start gap-4 hover:bg-[#F8FAFC] transition-colors">
          {renderItem ? (
            renderItem(item, idx)
          ) : (
            <>
              <span className="font-mono text-xs font-semibold text-[#2563EB] select-none pt-0.5">
                // {String(idx + 1).padStart(2, '0')}
              </span>
              <div className="flex-1 min-w-0">
                <span className="text-sm text-[#0F172A] font-semibold block">
                  {item.text || item.title}
                </span>
                {item.subtitle && (
                  <p className="text-xs text-[#64748B] mt-0.5">
                    {item.subtitle}
                  </p>
                )}
              </div>
              {item.timestamp && (
                <span className="font-mono text-xs text-[#94A3B8] font-medium">
                  {item.timestamp}
                </span>
              )}
            </>
          )}
        </li>
      ))}
    </ul>
  );
}
