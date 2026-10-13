import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Check,
  AlertTriangle,
  ShieldCheck,
  Bug,
  Sparkles,
  Code2,
  FileCheck,
  Clock,
  ChevronRight
} from 'lucide-react';
import Button, { PrimaryButton } from '../../components/common/Button';
import Badge from '../../components/common/Badge';
import Card from '../../components/common/Card';
import { WORKFLOW_PIPELINE_STEPS, MOCK_AGENTS } from '../../data/mockAgents';

export default function Landing() {
  const [activeTab, setActiveTab] = useState(0);

  return (
    <div className="space-y-24 py-10 sm:py-16">
      {/* 1. HERO SECTION */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-center">
          {/* Left Column: Headings & CTAs */}
          <div className="lg:col-span-6 space-y-6 text-left">
            {/* Small Badge */}
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#EFF6FF] border border-[#BFDBFE] text-xs font-semibold text-[#2563EB]">
              <Sparkles className="w-3.5 h-3.5" />
              <span>AI-Powered Software Engineering</span>
            </div>

            {/* Headline */}
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-[#0F172A] tracking-tight leading-[1.08]">
              From GitHub Issue <br />
              to <span className="text-[#2563EB]">Verified Pull Request</span>
            </h1>

            {/* Description */}
            <p className="text-base sm:text-lg text-[#64748B] leading-relaxed max-w-xl">
              DevRescue AI autonomously investigates bugs, generates fixes, runs tests, performs security checks, and prepares pull requests — so developers can focus on building.
            </p>

            {/* Primary CTA */}
            <div className="pt-2">
              <PrimaryButton
                to="/investigations/new"
                size="lg"
                arrow={true}
                className="w-full sm:w-auto shadow-sm text-sm sm:text-base px-7 py-3.5 font-semibold"
              >
                Start Investigation
              </PrimaryButton>
            </div>

            {/* Highlights */}
            <div className="pt-4 flex flex-wrap items-center gap-6 text-xs text-[#64748B]">
              <div className="flex items-center gap-2">
                <Check className="w-4 h-4 text-[#16A34A]" />
                <span>Simulated MicroVM Sandbox</span>
              </div>
              <div className="flex items-center gap-2">
                <Check className="w-4 h-4 text-[#16A34A]" />
                <span>Minimal Surgical Diffs</span>
              </div>
              <div className="flex items-center gap-2">
                <Check className="w-4 h-4 text-[#16A34A]" />
                <span>Human-in-the-Loop Review</span>
              </div>
            </div>
          </div>

          {/* Right Column: Sophisticated Hero Visual Preview */}
          <div className="lg:col-span-6">
            <div className="relative rounded-2xl bg-white border border-[#E2E8F0] shadow-card overflow-hidden">
              {/* Card Header Bar */}
              <div className="px-5 py-3.5 bg-[#F8FAFC] border-b border-[#E2E8F0] flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-red-400" />
                    <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
                  </div>
                  <span className="text-xs font-semibold text-[#0F172A] pl-2 border-l border-[#E2E8F0]">
                    DevRescue Live Pipeline Preview
                  </span>
                </div>

                <Badge variant="demo" size="sm">
                  Frontend Demo
                </Badge>
              </div>

              {/* Investigation Header */}
              <div className="p-5 border-b border-[#E2E8F0] bg-white">
                <div className="flex items-center justify-between text-xs text-[#64748B] mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-[#0F172A]">demo-react-app</span>
                    <span>·</span>
                    <span className="font-mono text-slate-500">branch: main</span>
                  </div>
                  <span className="font-semibold text-[#2563EB] bg-[#EFF6FF] px-2 py-0.5 rounded border border-[#BFDBFE]">
                    Issue #42
                  </span>
                </div>
                <h3 className="text-base font-bold text-[#0F172A]">
                  Login button not working
                </h3>
                <p className="text-xs text-[#64748B] mt-1">
                  ReferenceError: authenticateUser is not defined in Login.jsx:38
                </p>
              </div>

              {/* Agent Pipeline Progress View */}
              <div className="p-5 space-y-3 bg-[#F8FAFC]/50">
                <div className="flex items-center justify-between text-xs font-semibold text-[#0F172A] mb-1">
                  <span>Autonomous Agent Pipeline</span>
                  <span className="text-[#2563EB]">68% Completed</span>
                </div>

                {/* Agent 1 */}
                <div className="flex items-center justify-between p-2.5 rounded-lg bg-white border border-[#E2E8F0]">
                  <div className="flex items-center gap-2.5">
                    <div className="w-5 h-5 rounded-full bg-[#16A34A] text-white flex items-center justify-center">
                      <Check className="w-3 h-3 stroke-[3]" />
                    </div>
                    <span className="text-xs font-semibold text-[#0F172A]">
                      Repository Analyzer
                    </span>
                  </div>
                  <span className="text-[11px] text-[#16A34A] font-medium bg-[#DCFCE7] px-2 py-0.5 rounded-full">
                    Complete
                  </span>
                </div>

                {/* Agent 2 */}
                <div className="flex items-center justify-between p-2.5 rounded-lg bg-white border border-[#E2E8F0]">
                  <div className="flex items-center gap-2.5">
                    <div className="w-5 h-5 rounded-full bg-[#16A34A] text-white flex items-center justify-center">
                      <Check className="w-3 h-3 stroke-[3]" />
                    </div>
                    <span className="text-xs font-semibold text-[#0F172A]">
                      Bug Investigator
                    </span>
                  </div>
                  <span className="text-[11px] text-[#16A34A] font-medium bg-[#DCFCE7] px-2 py-0.5 rounded-full">
                    Complete
                  </span>
                </div>

                {/* Agent 3 */}
                <div className="flex items-center justify-between p-2.5 rounded-lg bg-white border border-[#E2E8F0]">
                  <div className="flex items-center gap-2.5">
                    <div className="w-5 h-5 rounded-full bg-[#16A34A] text-white flex items-center justify-center">
                      <Check className="w-3 h-3 stroke-[3]" />
                    </div>
                    <span className="text-xs font-semibold text-[#0F172A]">
                      Code Repair Agent
                    </span>
                  </div>
                  <span className="text-[11px] text-[#16A34A] font-medium bg-[#DCFCE7] px-2 py-0.5 rounded-full">
                    Complete
                  </span>
                </div>

                {/* Agent 4 */}
                <div className="flex items-center justify-between p-2.5 rounded-lg bg-[#EFF6FF] border border-[#BFDBFE]">
                  <div className="flex items-center gap-2.5">
                    <div className="relative w-5 h-5 flex items-center justify-center">
                      <span className="w-5 h-5 rounded-full bg-[#2563EB]/20 animate-ping absolute" />
                      <span className="w-3.5 h-3.5 rounded-full bg-[#2563EB] flex items-center justify-center">
                        <span className="w-1.5 h-1.5 rounded-full bg-white" />
                      </span>
                    </div>
                    <span className="text-xs font-bold text-[#1E3A8A]">
                      Testing Agent
                    </span>
                  </div>
                  <span className="text-[11px] text-[#2563EB] font-semibold bg-[#DBEAFE] px-2 py-0.5 rounded-full animate-pulse">
                    ● In Progress
                  </span>
                </div>

                {/* Agent 5 */}
                <div className="flex items-center justify-between p-2.5 rounded-lg bg-white border border-[#E2E8F0] opacity-60">
                  <div className="flex items-center gap-2.5">
                    <div className="w-5 h-5 rounded-full border border-slate-300 flex items-center justify-center text-slate-400">
                      <span className="w-1.5 h-1.5 rounded-full bg-slate-300" />
                    </div>
                    <span className="text-xs font-medium text-[#64748B]">
                      Security Reviewer
                    </span>
                  </div>
                  <span className="text-[11px] text-slate-500 font-medium bg-slate-100 px-2 py-0.5 rounded-full">
                    Pending
                  </span>
                </div>
              </div>

              {/* Bottom Quick Action */}
              <div className="p-4 bg-white border-t border-[#E2E8F0] flex items-center justify-between">
                <span className="text-xs text-[#64748B]">
                  Estimated remaining: <strong className="text-[#0F172A]">~45s</strong>
                </span>
                <Link
                  to="/investigations/1"
                  className="text-xs font-semibold text-[#2563EB] hover:text-[#1D4ED8] flex items-center gap-1"
                >
                  <span>Open Live War Room</span>
                  <span>→</span>
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 2. PROBLEM SECTION */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8">
        <div className="text-center max-w-3xl mx-auto mb-16 space-y-3">
          <span className="text-xs font-semibold uppercase tracking-wider text-[#2563EB]">
            The Challenge
          </span>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-[#0F172A] tracking-tight">
            Developers spend 40% of their time chasing stack traces.
          </h2>
          <p className="text-base text-[#64748B] leading-relaxed">
            Diagnosing runtime bugs, reproducing edge cases in local branches, testing for regressions, and creating clean pull requests interrupts core product engineering.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card className="p-6 space-y-3 border-[#E2E8F0]">
            <div className="w-10 h-10 rounded-xl bg-red-50 text-[#DC2626] flex items-center justify-center">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-[#0F172A]">Context Switching Fatigue</h3>
            <p className="text-sm text-[#64748B] leading-relaxed">
              Engineers drop active roadmap features to reproduce obscure production bugs across microservices.
            </p>
          </Card>

          <Card className="p-6 space-y-3 border-[#E2E8F0]">
            <div className="w-10 h-10 rounded-xl bg-amber-50 text-[#D97706] flex items-center justify-center">
              <Bug className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-[#0F172A]">Hidden Regressions</h3>
            <p className="text-sm text-[#64748B] leading-relaxed">
              Quick fixes often break adjacent modules because edge-case stress tests are rarely synthesized under pressure.
            </p>
          </Card>

          <Card className="p-6 space-y-3 border-[#E2E8F0]">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-[#2563EB] flex items-center justify-center">
              <Clock className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-[#0F172A]">Slow Resolution Time</h3>
            <p className="text-sm text-[#64748B] leading-relaxed">
              From issue report to code review to merge takes hours or days when maintainers are backlogged.
            </p>
          </Card>
        </div>
      </section>

      {/* 3. SOLUTION SECTION */}
      <section className="bg-[#F7F9FC] py-16 border-y border-[#E2E8F0]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-16 space-y-3">
            <span className="text-xs font-semibold uppercase tracking-wider text-[#2563EB]">
              The Autonomous Solution
            </span>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-[#0F172A] tracking-tight">
              An autonomous engineering team dedicated to your repo.
            </h2>
            <p className="text-base text-[#64748B] leading-relaxed">
              DevRescue AI doesn’t just guess completions. It spins an isolated microVM, reproduces the bug, proves root cause, writes minimal code, runs tests, and prepares a verified PR for your sign-off.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="bg-white border border-[#E2E8F0] p-6 rounded-xl space-y-3 shadow-xs">
              <div className="w-8 h-8 rounded-lg bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center font-bold text-sm">
                01
              </div>
              <h4 className="text-base font-bold text-[#0F172A]">Automatic Reproduction</h4>
              <p className="text-xs text-[#64748B] leading-relaxed">
                Reproduces exceptions in isolated sandbox environments with exact node/python versions.
              </p>
            </div>

            <div className="bg-white border border-[#E2E8F0] p-6 rounded-xl space-y-3 shadow-xs">
              <div className="w-8 h-8 rounded-lg bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center font-bold text-sm">
                02
              </div>
              <h4 className="text-base font-bold text-[#0F172A]">AST Invariant Analysis</h4>
              <p className="text-xs text-[#64748B] leading-relaxed">
                Traces call graphs, variable bindings, and concurrency race conditions across files.
              </p>
            </div>

            <div className="bg-white border border-[#E2E8F0] p-6 rounded-xl space-y-3 shadow-xs">
              <div className="w-8 h-8 rounded-lg bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center font-bold text-sm">
                03
              </div>
              <h4 className="text-base font-bold text-[#0F172A]">Minimal Surgical Patches</h4>
              <p className="text-xs text-[#64748B] leading-relaxed">
                Generates precise 1-to-10 line patches conforming to existing repo formatting and style rules.
              </p>
            </div>

            <div className="bg-white border border-[#E2E8F0] p-6 rounded-xl space-y-3 shadow-xs">
              <div className="w-8 h-8 rounded-lg bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center font-bold text-sm">
                04
              </div>
              <h4 className="text-base font-bold text-[#0F172A]">Verified Test Proofs</h4>
              <p className="text-xs text-[#64748B] leading-relaxed">
                Proves 100% green test passes with synthesized regression tests before preparing the PR.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 4. HOW IT WORKS — THE 8-STEP PIPELINE */}
      <section id="how-it-works" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16 space-y-3">
          <span className="text-xs font-semibold uppercase tracking-wider text-[#2563EB]">
            End-to-End Pipeline
          </span>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-[#0F172A] tracking-tight">
            How DevRescue AI Works
          </h2>
          <p className="text-base text-[#64748B] leading-relaxed">
            From ingestion of a raw GitHub issue through autonomous repair, rigorous verification, human approval, and pull request dispatch.
          </p>
        </div>

        {/* Pipeline Step-by-Step Flow Graphic */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
          {WORKFLOW_PIPELINE_STEPS.map((step, idx) => (
            <div
              key={step.step}
              className="relative bg-white border border-[#E2E8F0] rounded-xl p-3.5 text-center flex flex-col justify-between hover:border-[#2563EB] transition-all group"
            >
              <div>
                <span className="text-[10px] font-bold text-[#2563EB] bg-[#EFF6FF] px-2 py-0.5 rounded-full">
                  0{step.step}
                </span>
                <h4 className="text-xs font-bold text-[#0F172A] mt-2 group-hover:text-[#2563EB] transition-colors leading-tight">
                  {step.title}
                </h4>
              </div>
              <p className="text-[11px] text-[#64748B] mt-2 leading-tight">
                {step.desc}
              </p>
              {idx < WORKFLOW_PIPELINE_STEPS.length - 1 && (
                <div className="hidden lg:block absolute -right-2 top-1/2 -translate-y-1/2 text-slate-300 pointer-events-none z-10">
                  <ChevronRight className="w-4 h-4 text-slate-300" />
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* 5. THE 5 AI AGENTS */}
      <section id="agents" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16 space-y-3">
          <span className="text-xs font-semibold uppercase tracking-wider text-[#2563EB]">
            Specialized Roles
          </span>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-[#0F172A] tracking-tight">
            The 5 Autonomous AI Agents
          </h2>
          <p className="text-base text-[#64748B] leading-relaxed">
            Rather than relying on a single generic model, DevRescue orchestrates five fine-tuned agents with deterministic AST tools and validation sandboxes.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {MOCK_AGENTS.map((agent) => (
            <Card key={agent.id} className="p-6 flex flex-col justify-between border-[#E2E8F0]">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[#2563EB] bg-[#EFF6FF] px-2.5 py-1 rounded-full border border-[#BFDBFE]">
                    {agent.badge}
                  </span>
                  <span className="text-xs font-mono text-[#64748B]">
                    avg ~{agent.metrics.averageTime}
                  </span>
                </div>

                <div>
                  <h3 className="text-lg font-bold text-[#0F172A]">{agent.name}</h3>
                  <span className="text-xs font-medium text-[#2563EB] block mt-0.5">
                    {agent.role}
                  </span>
                </div>

                <p className="text-xs text-[#64748B] leading-relaxed">
                  {agent.description}
                </p>

                <div className="pt-2 border-t border-[#E2E8F0]">
                  <span className="text-[11px] font-semibold text-[#0F172A] block mb-2">
                    Key Tools:
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {agent.tools.map((t) => (
                      <span
                        key={t}
                        className="text-[11px] bg-[#F1F5F9] text-[#475569] px-2 py-0.5 rounded font-mono"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="pt-5 mt-4 border-t border-[#E2E8F0] flex items-center justify-between text-xs text-[#64748B]">
                <span>Status: <strong className="text-[#16A34A]">Operational</strong></span>
                <Link to="/agents" className="text-[#2563EB] hover:underline font-medium">
                  View Specs →
                </Link>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* 6. WHY DEVRESCUE */}
      <section className="bg-[#F7F9FC] py-16 border-y border-[#E2E8F0]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-16 space-y-3">
            <span className="text-xs font-semibold uppercase tracking-wider text-[#2563EB]">
              Why DevRescue AI
            </span>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-[#0F172A] tracking-tight">
              Designed for Senior Engineers and Maintainers
            </h2>
            <p className="text-base text-[#64748B] leading-relaxed">
              We eliminate hallucinations, bloated diffs, and unwanted library upgrades.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-xl bg-blue-50 text-[#2563EB] flex items-center justify-center">
                <Code2 className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-bold text-[#0F172A]">Zero Rewrite Philosophy</h3>
              <p className="text-sm text-[#64748B] leading-relaxed">
                DevRescue only touches the specific lines causing the error. No unsolicited architectural refactorings or stylistic disruptions.
              </p>
            </div>

            <div className="space-y-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-50 text-[#16A34A] flex items-center justify-center">
                <FileCheck className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-bold text-[#0F172A]">Deterministic Verification</h3>
              <p className="text-sm text-[#64748B] leading-relaxed">
                Every patch must run your existing test suite plus new generated regression stress tests in an ephemeral sandbox.
              </p>
            </div>

            <div className="space-y-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-50 text-[#4F46E5] flex items-center justify-center">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-bold text-[#0F172A]">Human Review Gateway</h3>
              <p className="text-sm text-[#64748B] leading-relaxed">
                Nothing is merged automatically without human verification. You examine diffs, test logs, and security scores with one click.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 7. SECURITY ARCHITECTURE */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-8 sm:p-12 shadow-sm">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
            <div className="lg:col-span-7 space-y-4">
              <span className="text-xs font-semibold uppercase tracking-wider text-[#2563EB]">
                Enterprise Security
              </span>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-[#0F172A]">
                Isolated microVM execution with strict zero-leakage policies
              </h2>
              <p className="text-sm text-[#64748B] leading-relaxed">
                DevRescue runs every investigation in an ephemeral, single-use container sandbox. Code is discarded immediately after patch synthesis and PR delivery.
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4">
                <div className="flex items-start gap-2.5 text-xs text-[#0F172A]">
                  <Check className="w-4 h-4 text-[#16A34A] flex-shrink-0 mt-0.5" />
                  <span>No secrets or env variables stored in training logs</span>
                </div>
                <div className="flex items-start gap-2.5 text-xs text-[#0F172A]">
                  <Check className="w-4 h-4 text-[#16A34A] flex-shrink-0 mt-0.5" />
                  <span>No write permissions to primary branch</span>
                </div>
                <div className="flex items-start gap-2.5 text-xs text-[#0F172A]">
                  <Check className="w-4 h-4 text-[#16A34A] flex-shrink-0 mt-0.5" />
                  <span>Static analysis blocks malicious dependencies</span>
                </div>
                <div className="flex items-start gap-2.5 text-xs text-[#0F172A]">
                  <Check className="w-4 h-4 text-[#16A34A] flex-shrink-0 mt-0.5" />
                  <span>Simulated prototype with zero external leak</span>
                </div>
              </div>
            </div>

            <div className="lg:col-span-5 bg-[#0F172A] p-6 rounded-xl text-slate-200 font-mono text-xs space-y-2 border border-slate-800">
              <div className="text-slate-400 border-b border-slate-800 pb-2 flex items-center justify-between">
                <span>security_policy.json</span>
                <span className="text-emerald-400">ENFORCED</span>
              </div>
              <div className="text-slate-300">
                <span className="text-purple-400">"network_egress"</span>: <span className="text-amber-400">"RESTRICTED"</span>,<br />
                <span className="text-purple-400">"ephemeral_runtime"</span>: <span className="text-blue-400">true</span>,<br />
                <span className="text-purple-400">"allow_dependency_change"</span>: <span className="text-blue-400">false</span>,<br />
                <span className="text-purple-400">"git_permission"</span>: <span className="text-amber-400">"BRANCH_WRITE_ONLY"</span>,<br />
                <span className="text-purple-400">"human_gate_required"</span>: <span className="text-blue-400">true</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 8. INTERACTIVE DEMO WORKFLOW */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-12 space-y-3">
          <span className="text-xs font-semibold uppercase tracking-wider text-[#2563EB]">
            Interactive Demo
          </span>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-[#0F172A] tracking-tight">
            See the Autonomous Resolution Journey
          </h2>
          <p className="text-base text-[#64748B] leading-relaxed">
            Click through the stages to inspect how DevRescue progresses from issue to pull request.
          </p>
        </div>

        <div className="bg-white border border-[#E2E8F0] rounded-2xl overflow-hidden shadow-card">
          <div className="flex border-b border-[#E2E8F0] bg-[#F8FAFC] overflow-x-auto">
            {['1. Issue Ingestion', '2. Live Investigation', '3. Code Diff Review', '4. Verified Pull Request'].map(
              (title, index) => (
                <button
                  key={title}
                  type="button"
                  onClick={() => setActiveTab(index)}
                  className={`px-6 py-4 text-xs font-semibold border-b-2 whitespace-nowrap cursor-pointer transition-colors ${
                    activeTab === index
                      ? 'border-[#2563EB] text-[#2563EB] bg-white'
                      : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
                  }`}
                >
                  {title}
                </button>
              )
            )}
          </div>

          <div className="p-6 sm:p-8">
            {activeTab === 0 && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono text-[#64748B]">Repository: demo-react-app</span>
                  <Badge variant="blue">Open Issue #42</Badge>
                </div>
                <h3 className="text-xl font-bold text-[#0F172A]">Login button not working</h3>
                <p className="text-sm text-[#64748B]">
                  User reported: "Clicking 'Sign In' triggers a ReferenceError in the console. The user remains stuck on the modal without an error toast."
                </p>
                <div className="p-4 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl font-mono text-xs text-red-600">
                  ReferenceError: authenticateUser is not defined at Login.jsx:38
                </div>
                <div className="pt-2">
                  <Button to="/investigations/new" variant="primary" size="sm" arrow={true}>
                    Launch Investigation Order
                  </Button>
                </div>
              </div>
            )}

            {activeTab === 1 && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono text-[#64748B]">Live Agent Telemetry</span>
                  <Badge variant="blue">In Progress · 68%</Badge>
                </div>
                <div className="p-4 bg-[#0F172A] rounded-xl text-slate-200 font-mono text-xs space-y-1.5 border border-slate-800">
                  <div className="text-slate-400">[14:32:04] Analyzer: Scanning repository structure...</div>
                  <div className="text-blue-400">[14:32:08] Analyzer: Found 142 relevant files in dependency graph.</div>
                  <div className="text-amber-400">[14:32:12] Investigator: Reproducing the bug in sandbox container...</div>
                  <div className="text-rose-400">[14:32:15] Investigator: ReferenceError detected at Login.jsx:38.</div>
                  <div className="text-emerald-400">[14:32:20] Repair: Generating minimal patch for authService.js...</div>
                </div>
                <div className="pt-2">
                  <Button to="/investigations/1" variant="primary" size="sm" arrow={true}>
                    View Full Live Console
                  </Button>
                </div>
              </div>
            )}

            {activeTab === 2 && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono text-[#64748B]">Proposed Diff (src/components/Login.jsx)</span>
                  <Badge variant="success">Tests Passed 14/14</Badge>
                </div>
                <div className="p-4 bg-[#0F172A] rounded-xl text-xs font-mono border border-slate-800 space-y-1">
                  <div className="text-slate-400">@@ -2,3 +2,3 @@ import React from 'react';</div>
                  <div className="bg-red-950/40 text-red-300 px-2 py-0.5 rounded border-l-2 border-red-500">
                    - import &#123; login &#125; from "./auth";
                  </div>
                  <div className="bg-emerald-950/40 text-emerald-300 px-2 py-0.5 rounded border-l-2 border-emerald-500">
                    + import &#123; login, authenticateUser &#125; from "./services/authService";
                  </div>
                </div>
                <div className="pt-2">
                  <Button to="/investigations/1/review" variant="primary" size="sm" arrow={true}>
                    Open Code Review Desk
                  </Button>
                </div>
              </div>
            )}

            {activeTab === 3 && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono text-[#64748B]">Synthesized Pull Request</span>
                  <Badge variant="blue">PR #128 Ready for Review</Badge>
                </div>
                <h3 className="text-lg font-bold text-[#0F172A]">
                  Fix authentication crash on login submit
                </h3>
                <p className="text-xs text-[#64748B]">
                  Branch: <span className="font-mono text-[#0F172A]">devrescue/fix-auth-crash-42</span> into <span className="font-mono text-[#0F172A]">main</span>
                </p>
                <div className="flex items-center gap-4 text-xs">
                  <span className="text-[#16A34A] font-semibold">✓ 14 Tests Passed</span>
                  <span className="text-[#16A34A] font-semibold">✓ Security Audit Passed</span>
                  <span className="text-[#64748B]">+14 / -4 lines</span>
                </div>
                <div className="pt-2">
                  <Button to="/pull-requests" variant="primary" size="sm" arrow={true}>
                    View Pull Request Register
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* 9. BOTTOM CALL TO ACTION */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="bg-[#0F172A] rounded-2xl p-8 sm:p-14 text-center text-white relative overflow-hidden shadow-xl">
          <div className="max-w-2xl mx-auto space-y-6 relative z-10">
            <span className="text-xs font-bold text-[#60A5FA] uppercase tracking-wider bg-blue-950 px-3 py-1 rounded-full border border-blue-800">
              Autonomous Software Engineering
            </span>
            <h2 className="text-3xl sm:text-5xl font-extrabold tracking-tight">
              Turn GitHub Issues into Verified PRs in Minutes.
            </h2>
            <p className="text-slate-300 text-sm sm:text-base leading-relaxed">
              Explore the interactive frontend console today. Connect demo repositories, watch live agent telemetry, and approve verified patches.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3.5 pt-2">
              <PrimaryButton
                to="/dashboard"
                size="lg"
                arrow={true}
                className="w-full sm:w-auto text-sm py-3 px-8"
              >
                Launch Developer Console
              </PrimaryButton>
              <Button
                to="/investigations/new"
                variant="outline"
                size="lg"
                className="w-full sm:w-auto text-sm py-3 px-8 bg-transparent text-white border-slate-700 hover:bg-slate-800 hover:text-white"
              >
                New Investigation
              </Button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
