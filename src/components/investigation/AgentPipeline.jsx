import React from 'react';
import { Bot, AlertCircle } from 'lucide-react';

export default function AgentPipeline({
  agents = [],
  isComplete = false,
  isRealMode = false,
  sandboxResult = null,
  dockerStatus = null
}) {
  const getSandboxEnvLabel = () => {
    if (!isRealMode) return 'node:22-alpine (Simulated)';
    if (sandboxResult?.docker_image) return `${sandboxResult.docker_image} (Docker)`;
    if (sandboxResult?.status === 'DOCKER_UNAVAILABLE') return 'None (Docker unavailable)';
    if (dockerStatus && !dockerStatus.docker_available) return 'None (Docker unavailable)';
    if (dockerStatus?.docker_available) return `${dockerStatus.default_image || 'Docker Desktop'} (Active)`;
    return 'Docker Desktop (Active)';
  };

  const getAgentEvidence = (agent) => {

    if (agent.summary) return agent.summary;
    const step = agent.step;
    const status = agent.status;

    if (status === 'NOT_IMPLEMENTED') {
      return 'NOT IMPLEMENTED';
    }

    if (status === 'SKIPPED' || status === 'TESTS_NOT_CONFIGURED' || status === 'NO_TESTS_FOUND' || status === 'UNSUPPORTED_PROJECT') {
      if (step === 4) return status === 'UNSUPPORTED_PROJECT' ? 'Unsupported project ecosystem' : 'No test suite configured or collected';
      return 'Stage skipped';
    }

    if (status === 'COMPLETE' || status === 'PASSED') {
      if (step === 1) return 'AST dependency graph analyzed';
      if (step === 2) return 'Bug isolated in code graph';
      if (step === 3) return 'Patch synthesized';
      if (step === 4) {
        if (sandboxResult?.verified_via_synthesized_test || sandboxResult?.verifiedViaSynthesizedTest || agent.details?.verified_via_synthesized_test) {
          return 'Docker sandbox verified via AI-synthesized test';
        }
        return isRealMode ? 'Docker sandbox tests passed' : 'Simulated tests passed';
      }
      if (step === 5) return isRealMode ? 'Security audit passed' : 'Simulated audit passed';
      return 'Completed';
    }
    if (status === 'WARNING' || status === 'WARNINGS') {
      if (step === 5) return 'Security review passed with warnings';
      return 'Completed with warnings';
    }
    if (status === 'IN_PROGRESS' || status === 'RUNNING') {
      if (step === 3) return 'Synthesizing patch...';
      if (step === 4) return 'Executing sandbox...';
      if (step === 5) return 'Auditing security...';
      return 'Analyzing...';
    }
    return 'Pending dispatch';
  };

  return (
    <div className="space-y-3">
      <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-sm">
        <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#E2E8F0]">
          <div className="flex items-center gap-2">
            <Bot className="w-4 h-4 text-[#2563EB]" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#0F172A]">
              Autonomous Agents ({agents.length || 5})
            </h3>
          </div>
          <span className="text-[11px] font-mono text-[#64748B]">
            {isComplete ? 'Execution Finished' : 'Active Pipeline'}
          </span>
        </div>

        <div className="space-y-2.5">
          {agents.map((agent, idx) => {
            const isAgentPassed = agent.status === 'COMPLETE' || agent.status === 'PASSED';
            const isAgentWarning = agent.status === 'WARNING' || agent.status === 'WARNINGS';
            const isAgentSkipped = agent.status === 'SKIPPED' || agent.status === 'TESTS_NOT_CONFIGURED' || agent.status === 'NO_TESTS_FOUND' || agent.status === 'UNSUPPORTED_PROJECT';
            const isAgentActive = agent.status === 'IN_PROGRESS' || agent.status === 'RUNNING';
            const isAgentNotImpl = agent.status === 'NOT_IMPLEMENTED';
            const isAgentFailed = agent.status === 'FAILED' || agent.status === 'TESTS_FAILED' || agent.status === 'ENVIRONMENT_ERROR' || agent.status === 'DEPENDENCIES_UNAVAILABLE' || agent.status === 'PATCH_FAILED' || agent.status === 'ERROR';
            const evidence = getAgentEvidence(agent);

            return (
              <div
                key={agent.id || idx}
                className={`p-3 rounded-lg border transition-all ${
                  isAgentActive
                    ? 'bg-[#EFF6FF] border-[#BFDBFE] ring-1 ring-[#2563EB]/20 shadow-xs'
                    : isAgentPassed
                    ? 'bg-[#F8FAFC] border-[#E2E8F0]'
                    : isAgentWarning
                    ? 'bg-[#FFFBEB] border-[#FDE68A]'
                    : isAgentSkipped
                    ? 'bg-[#FFFBEB] border-[#FDE68A]'
                    : isAgentNotImpl
                    ? 'bg-[#F8FAFC] border-[#E2E8F0] opacity-75'
                    : 'bg-white border-[#E2E8F0] opacity-80'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    {/* Status Icon */}
                    <div className="flex-shrink-0">
                      {isAgentPassed && (
                        <div className="w-5 h-5 rounded-full bg-[#DCFCE7] text-[#16A34A] flex items-center justify-center font-bold text-xs">
                          ✓
                        </div>
                      )}
                      {isAgentWarning && (
                        <div className="w-5 h-5 rounded-full bg-[#FEF3C7] text-[#D97706] flex items-center justify-center font-bold text-xs">
                          !
                        </div>
                      )}
                      {isAgentSkipped && (
                        <div className="w-5 h-5 rounded-full bg-[#FEF3C7] text-[#D97706] flex items-center justify-center font-bold text-xs">
                          —
                        </div>
                      )}
                      {isAgentActive && (
                        <div className="relative w-5 h-5 rounded-full bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center border border-[#2563EB]">
                          <span className="w-2 h-2 rounded-full bg-[#2563EB] animate-ping" />
                          <span className="w-1.5 h-1.5 rounded-full bg-[#2563EB] absolute" />
                        </div>
                      )}
                      {isAgentNotImpl && (
                        <div className="w-5 h-5 rounded-full bg-slate-100 text-slate-500 flex items-center justify-center font-bold text-xs">
                          <AlertCircle className="w-3.5 h-3.5" />
                        </div>
                      )}
                      {isAgentFailed && (
                        <div className="w-5 h-5 rounded-full bg-[#FEE2E2] text-[#DC2626] flex items-center justify-center font-bold text-xs">
                          ✕
                        </div>
                      )}
                      {!isAgentPassed && !isAgentWarning && !isAgentSkipped && !isAgentActive && !isAgentNotImpl && !isAgentFailed && (
                        <div className="w-5 h-5 rounded-full border border-slate-300 text-slate-400 flex items-center justify-center font-mono text-[10px]">
                          ○
                        </div>
                      )}
                    </div>

                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-bold text-[#0F172A]">
                          {agent.name}
                        </span>
                        <span className="text-[10px] text-[#64748B] font-mono">
                          ({agent.role || agent.shortName || `Agent ${idx + 1}`})
                        </span>
                      </div>
                      <div className="text-[11px] font-medium text-[#64748B] mt-0.5 line-clamp-1">
                        {evidence}
                      </div>
                    </div>
                  </div>

                  <div className="text-right flex flex-col items-end gap-0.5">
                    <div className="flex items-center gap-1">
                      {agent.step === 4 && (sandboxResult?.verified_via_synthesized_test || sandboxResult?.verifiedViaSynthesizedTest || agent.details?.verified_via_synthesized_test) && (
                        <span className="text-[9px] font-bold text-[#7C3AED] bg-[#F5F3FF] border border-[#DDD6FE] px-1.5 py-0.5 rounded-full shadow-2xs">
                          AI-Synthesized
                        </span>
                      )}
                      <span
                        className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full ${
                          isAgentPassed
                            ? 'bg-[#DCFCE7] text-[#16A34A]'
                            : isAgentWarning
                            ? 'bg-[#FEF3C7] text-[#D97706] border border-[#FCD34D]'
                            : isAgentSkipped
                            ? 'bg-[#FEF3C7] text-[#D97706] border border-[#FCD34D]'
                            : isAgentFailed
                            ? 'bg-[#FEE2E2] text-[#DC2626] font-bold border border-[#FCA5A5]'
                            : isAgentActive
                            ? 'bg-[#DBEAFE] text-[#2563EB]'
                            : isAgentNotImpl
                            ? 'bg-slate-100 text-slate-600 font-mono'
                            : 'bg-slate-100 text-slate-500'
                        }`}
                      >
                        {agent.status}
                      </span>
                    </div>
                    {agent.time && (
                      <div className="text-[10px] text-[#94A3B8] font-mono mt-0.5">
                        {agent.time}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Quick Metrics Subcard */}
      <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-4 text-xs space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-[#64748B]">Sandbox Environment:</span>
          <span className="font-mono text-[#0F172A] bg-white px-2 py-0.5 rounded border border-[#E2E8F0]">
            {getSandboxEnvLabel()}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-[#64748B]">Telemetry Overhead:</span>
          <span className="font-mono text-[#0F172A]">18.4 KB</span>
        </div>
        <div className="pt-2 border-t border-[#E2E8F0] flex justify-between items-center">
          <span className="text-[#64748B]">Pipeline Mode:</span>
          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${isRealMode ? 'bg-[#EFF6FF] text-[#2563EB]' : 'bg-[#DCFCE7] text-[#16A34A]'}`}>
            {isRealMode ? 'FASTAPI + XGBOOST' : 'DEMO MODE'}
          </span>
        </div>
      </div>
    </div>
  );
}
