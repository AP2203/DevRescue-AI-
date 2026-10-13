
import React from 'react';
import { Check } from 'lucide-react';
import { MOCK_AGENTS } from '../../data/mockAgents';
import { PrimaryButton } from '../../components/common/Button';
import Card from '../../components/common/Card';
import Badge from '../../components/common/Badge';

export default function Agents() {
  return (
    <div className="space-y-8">
      {/* Title */}
      <div className="pb-6 border-b border-[#E2E8F0]">
        <div className="flex items-center gap-2 mb-2">
          <Badge variant="blue" size="sm">
            AI COLLECTIVE
          </Badge>
          <span className="text-xs text-[#64748B]">5 Specialized Runtimes</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#0F172A]">
          The 5 Autonomous AI Agents
        </h1>
        <p className="text-sm text-[#64748B] max-w-3xl mt-1 leading-relaxed">
          Monolithic models try to solve bugs by guessing code changes directly from conversational prompts. DevRescue separates triage into five specialized intelligences, each constrained by formal contracts and adversarial verification.
        </p>
      </div>

      {/* Agents List */}
      <div className="space-y-6">
        {MOCK_AGENTS.map((agent) => (
          <Card key={agent.id} className="p-6 md:p-8 border-[#E2E8F0] shadow-sm">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              {/* Left Column: Number & Role */}
              <div className="lg:col-span-4 space-y-3">
                <span className="text-xs font-bold text-[#2563EB] bg-[#EFF6FF] px-2.5 py-1 rounded-full border border-[#BFDBFE]">
                  {agent.badge}
                </span>

                <h2 className="text-xl font-bold text-[#0F172A]">{agent.name}</h2>
                <p className="text-xs font-semibold text-[#2563EB]">{agent.role}</p>

                <div className="pt-3 border-t border-[#E2E8F0] space-y-1.5 text-xs text-[#64748B]">
                  <div className="flex justify-between">
                    <span>Average Execution:</span>
                    <span className="font-semibold text-[#0F172A]">{agent.metrics.averageTime}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Status:</span>
                    <span className="font-semibold text-[#16A34A]">Operational</span>
                  </div>
                </div>
              </div>

              {/* Right Column: Capabilities & Tools */}
              <div className="lg:col-span-8 space-y-4">
                <p className="text-sm text-[#64748B] leading-relaxed">
                  {agent.description}
                </p>

                <div className="space-y-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-[#0F172A] block">
                    Core Capabilities
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                    {agent.capabilities.map((cap, i) => (
                      <div key={i} className="flex items-start gap-2 text-[#0F172A]">
                        <Check className="w-3.5 h-3.5 text-[#16A34A] flex-shrink-0 mt-0.5" />
                        <span>{cap}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="pt-3 border-t border-[#E2E8F0]">
                  <span className="text-xs font-bold uppercase tracking-wider text-[#0F172A] block mb-2">
                    Deterministic Tools
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {agent.tools.map((tool) => (
                      <span
                        key={tool}
                        className="text-xs bg-[#F8FAFC] border border-[#E2E8F0] px-2.5 py-1 rounded-md text-[#475569] font-mono"
                      >
                        {tool}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Bottom CTA */}
      <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 sm:p-8 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-sm">
        <div>
          <h3 className="text-lg font-bold text-[#0F172A]">
            Deploy the 5 agents against your open issues
          </h3>
          <p className="text-xs text-[#64748B] mt-0.5">
            Assemble an ephemeral sandbox and launch autonomous verification.
          </p>
        </div>
        <PrimaryButton to="/investigations/new" size="md" arrow={true}>
          Commission Investigation
        </PrimaryButton>
      </div>
    </div>
  );
}
