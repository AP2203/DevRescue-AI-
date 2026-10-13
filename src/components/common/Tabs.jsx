import React from 'react';

export default function Tabs({
  tabs = [],
  activeTab,
  onChange,
  variant = 'pills', // pills | underline
  className = '',
}) {
  if (variant === 'underline') {
    return (
      <div className={`flex items-center gap-6 border-b border-[#E2E8F0] ${className}`}>
        {tabs.map((tab) => {
          const id = typeof tab === 'object' ? tab.id : tab;
          const label = typeof tab === 'object' ? tab.label : tab;
          const count = typeof tab === 'object' ? tab.count : null;
          const icon = typeof tab === 'object' ? tab.icon : null;
          const isActive = activeTab === id;

          return (
            <button
              key={id}
              type="button"
              onClick={() => onChange(id)}
              className={`pb-3 -mb-px text-sm font-medium transition-colors cursor-pointer flex items-center gap-2 border-b-2 ${
                isActive
                  ? 'border-[#2563EB] text-[#2563EB]'
                  : 'border-transparent text-[#64748B] hover:text-[#0F172A] hover:border-slate-300'
              }`}
            >
              {icon && <span className="w-4 h-4">{icon}</span>}
              <span>{label}</span>
              {count !== null && count !== undefined && (
                <span
                  className={`text-xs px-2 py-0.5 rounded-full ${
                    isActive
                      ? 'bg-[#EFF6FF] text-[#2563EB]'
                      : 'bg-[#F1F5F9] text-[#64748B]'
                  }`}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div
      className={`inline-flex flex-wrap items-center gap-1 p-1 bg-[#F1F5F9] border border-[#E2E8F0] rounded-lg ${className}`}
    >
      {tabs.map((tab) => {
        const id = typeof tab === 'object' ? tab.id : tab;
        const label = typeof tab === 'object' ? tab.label : tab;
        const count = typeof tab === 'object' ? tab.count : null;
        const icon = typeof tab === 'object' ? tab.icon : null;
        const isActive = activeTab === id;

        return (
          <button
            key={id}
            type="button"
            onClick={() => onChange(id)}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-2 cursor-pointer ${
              isActive
                ? 'bg-white text-[#2563EB] shadow-xs font-semibold'
                : 'text-[#64748B] hover:text-[#0F172A]'
            }`}
          >
            {icon && <span className="w-3.5 h-3.5">{icon}</span>}
            <span>{label}</span>
            {count !== null && count !== undefined && (
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                  isActive
                    ? 'bg-[#EFF6FF] text-[#2563EB]'
                    : 'bg-[#E2E8F0] text-[#64748B]'
                }`}
              >
                {count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
