import React from 'react';
import { Check, AlertTriangle } from 'lucide-react';

export default function AgentStatus({
  step,
  name,
  role,
  status = 'PENDING', // PENDING | IN_PROGRESS | COMPLETE | FAILED
  time,
  summary,
  className = '',
}) {
  const normStatus = String(status).toUpperCase();

  const isComplete = normStatus === 'COMPLETE' || normStatus === 'PASSED';
  const isInProgress = normStatus === 'IN_PROGRESS' || normStatus === 'RUNNING';
  const isFailed = normStatus === 'FAILED' || normStatus === 'ERROR';
  const isPending = !isComplete && !isInProgress && !isFailed;

  return (
    <div
      className={`p-3.5 rounded-xl border transition-all duration-200 flex items-start gap-3.5 ${
        isInProgress
          ? 'bg-[#EFF6FF] border-[#BFDBFE] shadow-xs'
          : isComplete
          ? 'bg-white border-[#E2E8F0]'
          : isFailed
          ? 'bg-[#FEF2F2] border-[#FECACA]'
          : 'bg-[#F8FAFC] border-[#E2E8F0]/80 opacity-75'
      } ${className}`}
    >
      {/* Icon Indicator */}
      <div className="flex-shrink-0 mt-0.5">
        {isComplete && (
          <div className="w-6 h-6 rounded-full bg-[#16A34A] text-white flex items-center justify-center shadow-xs">
            <Check className="w-3.5 h-3.5 stroke-[2.5]" />
          </div>
        )}

        {isInProgress && (
          <div className="relative w-6 h-6 flex items-center justify-center">
            <span className="absolute w-6 h-6 rounded-full bg-[#2563EB]/20 animate-ping" />
            <span className="w-4 h-4 rounded-full bg-[#2563EB] flex items-center justify-center">
              <span className="w-1.5 h-1.5 rounded-full bg-white" />
            </span>
          </div>
        )}

        {isFailed && (
          <div className="w-6 h-6 rounded-full bg-[#DC2626] text-white flex items-center justify-center shadow-xs">
            <AlertTriangle className="w-3.5 h-3.5 stroke-[2.5]" />
          </div>
        )}

        {isPending && (
          <div className="w-6 h-6 rounded-full border-2 border-slate-300 bg-white flex items-center justify-center">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-300" />
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            {step && (
              <span className="text-[11px] font-semibold text-[#64748B]">
                {step}.
              </span>
            )}
            <h4
              className={`text-sm font-semibold truncate ${
                isInProgress
                  ? 'text-[#1E3A8A]'
                  : isComplete
                  ? 'text-[#0F172A]'
                  : isFailed
                  ? 'text-[#991B1B]'
                  : 'text-[#64748B]'
              }`}
            >
              {name}
            </h4>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            {time && (
              <span className="text-xs text-[#64748B] font-mono">{time}</span>
            )}
            <span
              className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${
                isComplete
                  ? 'bg-[#DCFCE7] text-[#16A34A]'
                  : isInProgress
                  ? 'bg-[#DBEAFE] text-[#1D4ED8] font-semibold animate-pulse'
                  : isFailed
                  ? 'bg-[#FEE2E2] text-[#DC2626]'
                  : 'bg-slate-100 text-slate-500'
              }`}
            >
              {isComplete
                ? 'Complete'
                : isInProgress
                ? 'In Progress'
                : isFailed
                ? 'Failed'
                : 'Pending'}
            </span>
          </div>
        </div>

        {role && (
          <p className="text-xs text-[#64748B] mt-0.5 truncate">{role}</p>
        )}

        {summary && (
          <p className="text-xs text-slate-600 mt-1 leading-relaxed bg-white/60 p-2 rounded border border-slate-200/60">
            {summary}
          </p>
        )}
      </div>
    </div>
  );
}
