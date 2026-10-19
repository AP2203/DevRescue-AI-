import React from 'react';
import ProgressBar from '../common/ProgressBar';

export default function InvestigationProgress({
  progress = 68,
  isComplete = false,
  isStopped = false,
  isFailed = false
}) {
  return (
    <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-sm space-y-2">
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-[#0F172A]">Investigation Status:</span>
          {isComplete ? (
            <span className="font-bold text-[#16A34A] bg-[#DCFCE7] px-2.5 py-0.5 rounded-full">
              Investigation Complete
            </span>
          ) : isStopped ? (
            <span className="font-bold text-[#DC2626] bg-[#FEE2E2] px-2.5 py-0.5 rounded-full">
              Investigation Stopped
            </span>
          ) : isFailed ? (
            <span className="font-bold text-[#DC2626] bg-[#FEE2E2] px-2.5 py-0.5 rounded-full flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#DC2626]" />
              FAILED
            </span>
          ) : (
            <span className="font-bold text-[#2563EB] bg-[#EFF6FF] px-2.5 py-0.5 rounded-full flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#2563EB] animate-ping" />
              IN PROGRESS
            </span>
          )}
        </div>

        <div className={`font-bold ${isFailed ? 'text-[#DC2626]' : 'text-[#2563EB]'}`}>
          {progress}%
        </div>
      </div>

      <ProgressBar progress={progress} height="h-2.5" />
    </div>
  );
}
