import React from 'react';
import TerminalLog from '../common/TerminalLog';
import Button from '../common/Button';

export default function LiveLogs({
  logs = [],
  repo = 'demo-react-app',
  isLive = true,
  isComplete = false,
  isRealMode = false,
  investigationId = '1',
}) {
  return (
    <div className="space-y-3">
      <TerminalLog
        logs={logs}
        isLive={isLive}
        maxHeight="440px"
        title={`TELEMETRY LOGS · ${repo}`}
      />

      <div className="p-3 bg-white border border-[#E2E8F0] rounded-xl flex items-center justify-between text-xs text-[#64748B]">
        <span>
          {isRealMode
            ? 'Live Backend Telemetry Stream · NVIDIA Nemotron 3.5'
            : 'Telemetry stream synced via local state'}
        </span>
        {isComplete && (
          <Button
            to={`/investigations/${investigationId}/review`}
            variant="primary"
            size="sm"
            arrow={true}
          >
            Proceed to Code Review
          </Button>
        )}
      </div>
    </div>
  );
}
