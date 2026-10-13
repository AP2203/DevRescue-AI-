import React from 'react';
import StatusTag from './StatusTag';

export default function Timeline({ agents = [], currentAgentIndex = 0, className = '' }) {
  return (
    <div className={`relative pl-4 space-y-6 ${className}`}>
      {/* Clean vertical connection line */}
      <div className="absolute top-3 bottom-6 left-[23px] w-[2px] bg-[#E2E8F0] -z-0" />

      {agents.map((agent, idx) => {
        const isPast = idx < currentAgentIndex || agent.status === 'COMPLETE' || agent.status === 'PASSED';
        const isCurrent = idx === currentAgentIndex && (agent.status === 'RUNNING' || agent.status === 'IN_PROGRESS');

        let nodeColor = 'bg-[#F8FAFC] border-[#E2E8F0] text-[#64748B]';
        if (isCurrent) nodeColor = 'bg-[#EFF6FF] border-[#2563EB] text-[#2563EB] ring-2 ring-[#2563EB]/20';
        if (isPast) nodeColor = 'bg-[#DCFCE7] border-[#86EFAC] text-[#16A34A]';

        return (
          <div key={agent.id || idx} className="relative z-10 flex items-start gap-4 group">
            {/* Step Node */}
            <div className="pt-0.5 flex items-center justify-center">
              <span
                className={`w-6 h-6 rounded-full border flex items-center justify-center font-mono text-[11px] font-bold transition-all shadow-2xs ${nodeColor}`}
              >
                {isPast ? '✓' : isCurrent ? '●' : String(idx + 1)}
              </span>
            </div>

            {/* Agent Card */}
            <div className="flex-1 rounded-xl border border-[#E2E8F0] bg-white hover:border-[#CBD5E1] p-4 transition-all shadow-xs">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-semibold text-[#2563EB]">
                    [{String(idx + 1).padStart(2, '0')}]
                  </span>
                  <h4 className="text-sm font-bold text-[#0F172A]">
                    {agent.name}
                  </h4>
                  <span className="text-[10px] uppercase font-semibold tracking-wider text-[#64748B] px-2 py-0.5 rounded bg-[#F1F5F9] border border-[#E2E8F0]">
                    {agent.role}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  {agent.time && (
                    <span className="font-mono text-xs text-[#64748B] tabular-nums">
                      ⏱ {agent.time}
                    </span>
                  )}
                  <StatusTag status={agent.status} />
                </div>
              </div>

              {agent.summary && (
                <p className="mt-2 text-xs text-[#0F172A] leading-relaxed bg-[#F8FAFC] p-2.5 rounded-lg border border-[#E2E8F0]">
                  <span className="text-[#2563EB] font-bold mr-1.5">&gt;</span>
                  {agent.summary}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
