import React, { useState } from 'react';
import Badge from '../../components/common/Badge';
import CodeBlock from '../../components/common/CodeBlock';
import { PrimaryButton } from '../../components/common/Button';

const TOC = [
  { id: 'overview', title: 'Platform Overview' },
  { id: 'pipeline', title: '8-Step Autonomous Pipeline' },
  { id: 'agents', title: 'The 5 Specialized Agents' },
  { id: 'verification', title: 'Automated Testing & Security' },
  { id: 'demo', title: 'Prototype Demo Mode' },
];

export default function Documentation() {
  const [activeSection, setActiveSection] = useState('overview');

  const scrollTo = (id) => {
    setActiveSection(id);
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-20 space-y-12">
      {/* Title */}
      <div className="pb-6 border-b border-[#E2E8F0] space-y-3">
        <Badge variant="blue" size="sm">
          DOCUMENTATION
        </Badge>
        <h1 className="text-3xl sm:text-4xl font-extrabold text-[#0F172A] tracking-tight">
          DevRescue AI Technical Documentation
        </h1>
        <p className="text-sm text-[#64748B] max-w-3xl leading-relaxed">
          Comprehensive reference guide to the autonomous bug investigation pipeline, agent coordination protocols, and verification standards.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-start">
        {/* Sticky Sidebar */}
        <aside className="lg:col-span-4 sticky top-24 space-y-2 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-4">
          <span className="text-xs font-bold uppercase tracking-wider text-[#0F172A] block px-3 py-1">
            Table of Contents
          </span>
          <nav className="space-y-1">
            {TOC.map((sec) => (
              <button
                key={sec.id}
                type="button"
                onClick={() => scrollTo(sec.id)}
                className={`w-full text-left px-3 py-2 rounded-lg text-xs font-medium transition-colors cursor-pointer flex items-center justify-between ${
                  activeSection === sec.id
                    ? 'bg-[#2563EB] text-white font-semibold shadow-xs'
                    : 'text-[#64748B] hover:text-[#0F172A] hover:bg-white'
                }`}
              >
                <span>{sec.title}</span>
              </button>
            ))}
          </nav>
        </aside>

        {/* Content Body */}
        <div className="lg:col-span-8 space-y-12 text-sm text-[#0F172A] leading-relaxed">
          {/* Overview */}
          <section id="overview" className="space-y-4 scroll-mt-28">
            <h2 className="text-2xl font-bold text-[#0F172A] border-b border-[#E2E8F0] pb-2">
              Platform Overview
            </h2>
            <p className="text-[#64748B]">
              DevRescue AI is an autonomous software engineering platform that investigates bugs, identifies root causes, generates minimal fixes, runs tests, performs security review, and prepares pull requests.
            </p>
            <p className="text-[#64748B]">
              The core workflow is designed around reproducibility and human confidence. No code is merged directly into production branches; instead, every patch is verified by 100% test proofs and presented to a human engineer for review before a pull request is drafted.
            </p>
          </section>

          {/* Pipeline */}
          <section id="pipeline" className="space-y-4 scroll-mt-28">
            <h2 className="text-2xl font-bold text-[#0F172A] border-b border-[#E2E8F0] pb-2">
              8-Step Autonomous Pipeline
            </h2>
            <p className="text-[#64748B]">
              The DevRescue engine orchestrates an eight-step pipeline from start to finish:
            </p>
            <ol className="list-decimal pl-5 space-y-2 text-[#0F172A] font-medium text-xs">
              <li><strong>GitHub Issue</strong> — Ingestion of bug title, description, and runtime stack trace.</li>
              <li><strong>Repository Analysis</strong> — Scanning codebase topology and dependency graphs.</li>
              <li><strong>Bug Investigation</strong> — Reproducing the bug in an isolated test sandbox.</li>
              <li><strong>Code Repair</strong> — Generating a minimal idiomatic patch conforming to repo lint rules.</li>
              <li><strong>Testing</strong> — Running existing unit suites plus synthesized regression stress tests.</li>
              <li><strong>Security Review</strong> — Scanning for credentials, secrets, and supply-chain vulnerabilities.</li>
              <li><strong>Human Approval</strong> — Maintainer reviews line diff and test proofs in Code Review Desk.</li>
              <li><strong>Pull Request</strong> — Synthesizing the verified GitHub pull request.</li>
            </ol>
          </section>

          {/* 5 Agents */}
          <section id="agents" className="space-y-4 scroll-mt-28">
            <h2 className="text-2xl font-bold text-[#0F172A] border-b border-[#E2E8F0] pb-2">
              The 5 Specialized Agents
            </h2>
            <p className="text-[#64748B]">
              Rather than a monolithic prompt, DevRescue splits work between five specialized agents:
            </p>

            <div className="space-y-3">
              <div className="p-4 bg-white border border-[#E2E8F0] rounded-xl space-y-1">
                <h4 className="font-bold text-[#2563EB]">1. Repository Analyzer</h4>
                <p className="text-xs text-[#64748B]">Maps multi-file dependency trees and targets relevant source files.</p>
              </div>
              <div className="p-4 bg-white border border-[#E2E8F0] rounded-xl space-y-1">
                <h4 className="font-bold text-[#2563EB]">2. Bug Investigator</h4>
                <p className="text-xs text-[#64748B]">Isolates runtime crash conditions and diagnoses AST broken invariants.</p>
              </div>
              <div className="p-4 bg-white border border-[#E2E8F0] rounded-xl space-y-1">
                <h4 className="font-bold text-[#2563EB]">3. Code Repair Agent</h4>
                <p className="text-xs text-[#64748B]">Synthesizes surgical minimal git diffs with zero unsolicited refactoring.</p>
              </div>
              <div className="p-4 bg-white border border-[#E2E8F0] rounded-xl space-y-1">
                <h4 className="font-bold text-[#2563EB]">4. Testing Agent</h4>
                <p className="text-xs text-[#64748B]">Executes existing test suites and proves 100% green test results.</p>
              </div>
              <div className="p-4 bg-white border border-[#E2E8F0] rounded-xl space-y-1">
                <h4 className="font-bold text-[#2563EB]">5. Security Reviewer</h4>
                <p className="text-xs text-[#64748B]">Scans for secret leakage, AST security patterns, and lockfile tampering.</p>
              </div>
            </div>
          </section>

          {/* Verification & Code Example */}
          <section id="verification" className="space-y-4 scroll-mt-28">
            <h2 className="text-2xl font-bold text-[#0F172A] border-b border-[#E2E8F0] pb-2">
              Automated Testing &amp; Security
            </h2>
            <p className="text-[#64748B]">
              Below is an example of an autonomous patch verification spec compiled by the Testing and Security agents:
            </p>

            <CodeBlock
              filename="test_proof_manifest.json"
              language="json"
              code={`{
  "investigationId": "inv-42",
  "issue": "Login button not working",
  "patchConfidence": 0.994,
  "testResults": {
    "total": 14,
    "passed": 14,
    "failed": 0,
    "newRegressionTests": 2
  },
  "securityAudit": {
    "secretLeakDetected": false,
    "dependencyChanges": false,
    "riskLevel": "LOW_RISK"
  }
}`}
            />
          </section>

          {/* Demo Mode */}
          <section id="demo" className="space-y-4 scroll-mt-28">
            <h2 className="text-2xl font-bold text-[#0F172A] border-b border-[#E2E8F0] pb-2">
              Prototype Demo Mode
            </h2>
            <p className="text-[#64748B]">
              This application operates completely as an interactive developer prototype. All agent logs, test simulations, and pull requests run in frontend state and localStorage. You can reset to initial prototype state anytime in <strong>Settings → Reset Demo Data</strong>.
            </p>
            <div className="pt-2">
              <PrimaryButton to="/dashboard" size="md" arrow={true}>
                Go to Developer Console
              </PrimaryButton>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
