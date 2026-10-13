import { FastForward, StopCircle, RefreshCw } from 'lucide-react';
import Button, { PrimaryButton } from '../common/Button';
import Badge from '../common/Badge';

export default function InvestigationHeader({
  inv,
  isComplete,
  isStopped,
  isRealMode = false,
  isInvestigating = false,
  onFastForward,
  onStopClick,
  onRerun,
}) {
  const isReal = isRealMode || (inv?.mode?.toUpperCase() === 'REAL') || (inv?.mode === 'real');

  return (
    <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div className="space-y-1.5 min-w-0">
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="text-xs font-mono font-semibold text-[#2563EB] bg-[#EFF6FF] px-2.5 py-0.5 rounded border border-[#BFDBFE]">
            Issue #{inv?.issueNumber || inv?.issue_number || 42}
          </span>
          <span className="text-xs text-[#64748B] font-mono">
            repo: <strong className="text-[#0F172A]">{inv?.repo}</strong>
          </span>
          <span className="text-slate-300">·</span>
          <span className="text-xs text-[#64748B] font-mono">
            branch: <span className="text-[#0F172A]">{inv?.branch || 'main'}</span>
          </span>
          {(inv?.latest_run_id || inv?.latest_run?.run_id) && (
            <span className="text-[10px] font-mono font-bold text-[#334155] bg-[#F8FAFC] px-2 py-0.5 rounded border border-[#CBD5E1]" title="Current Execution Run ID">
              Run: <span className="text-[#2563EB]">{inv?.latest_run_id || inv?.latest_run?.run_id}</span>
            </span>
          )}
          {inv?.status && (
            <span className={`text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded border ${
              inv.status === 'COMPLETE' || inv.status === 'READY_FOR_REVIEW'
                ? 'bg-[#F0FDF4] text-[#16A34A] border-[#BBF7D0]'
                : inv.status === 'FAILED' || inv.status === 'ENVIRONMENT_ERROR'
                ? 'bg-[#FEF2F2] text-[#DC2626] border-[#FECACA]'
                : 'bg-[#EFF6FF] text-[#2563EB] border-[#BFDBFE]'
            }`}>
              {inv.status}
            </span>
          )}
          {isReal ? (
            <span className="text-[10px] font-bold tracking-wider uppercase px-2 py-0.5 rounded border bg-[#EFF6FF] text-[#2563EB] border-[#BFDBFE]">
              NVIDIA NEMOTRON 3.5 REAL
            </span>
          ) : (
            <Badge variant="demo" size="sm">
              SIMULATED DEMO RESULT
            </Badge>
          )}
        </div>

        <h1 className="text-xl sm:text-2xl font-extrabold tracking-tight text-[#0F172A] truncate">
          Investigating: {inv?.issue_title || inv?.title || inv?.issueTitle || 'Target Bug'}
        </h1>
      </div>

      {/* Status + Time Remaining + CTAs */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="text-right hidden sm:block">
          <div className="text-xs font-semibold text-[#0F172A]">
            Estimated time:{' '}
            <span className="text-[#2563EB]">
              {isComplete ? '0s' : inv?.estimatedTime || '~1 minute'}
            </span>
          </div>
          <div className="text-[11px] text-[#64748B]">
            Started {inv?.startedAt || 'Today, 14:32 UTC'}
          </div>
        </div>

        {isReal && onRerun && (
          <Button
            variant="outline"
            size="sm"
            icon={RefreshCw}
            onClick={onRerun}
            disabled={isInvestigating}
            className={isInvestigating ? 'opacity-50' : ''}
            title="Re-run real investigation and tests"
          >
            {isInvestigating ? 'Running...' : 'Re-run'}
          </Button>
        )}

        {isComplete ? (
          <PrimaryButton
            to={`/investigations/${inv?.id}/review`}
            arrow={true}
            size="md"
            className="bg-[#16A34A] hover:bg-[#15803D]"
          >
            Review Fix →
          </PrimaryButton>
        ) : isStopped ? (
          <span className="text-xs font-semibold text-[#DC2626] bg-[#FEE2E2] px-3 py-1.5 rounded-lg border border-[#FECACA]">
            Investigation Aborted
          </span>
        ) : (
          <div className="flex items-center gap-2">
            {!isReal && (
              <Button
                variant="outline"
                size="sm"
                icon={FastForward}
                onClick={onFastForward}
                title="Fast forward simulation to complete"
              >
                Complete Simulation
              </Button>
            )}
            <Button
              variant="danger"
              size="sm"
              icon={StopCircle}
              onClick={onStopClick}
            >
              Stop
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
