import React from 'react';
import { Sparkles } from 'lucide-react';
import { PrimaryButton } from '../../components/common/Button';
import Card from '../../components/common/Card';
import Badge from '../../components/common/Badge';

export default function About() {
  const principles = [
    {
      title: 'Empirical Verification Over Generative Guesswork',
      desc: 'We never guess diffs blindly. Every proposal must pass reproduction in an isolated microVM sandbox and prove green test execution.',
    },
    {
      title: 'Minimal Surgical Footprint',
      desc: 'The best patch is the smallest patch. We reject large unwanted refactorings, modifying only the minimal viable lines to fix the defect.',
    },
    {
      title: 'Absolute Transparency & Human Gateways',
      desc: 'Maintainers maintain full control. Detailed AST root cause analyses and test suites accompany every synthesized pull request.',
    },
  ];

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-20 space-y-16">
      {/* Hero */}
      <div className="space-y-4 max-w-3xl">
        <Badge variant="blue" size="sm">
          ABOUT DEVRESCUE AI
        </Badge>
        <h1 className="text-3xl sm:text-5xl font-extrabold text-[#0F172A] tracking-tight leading-tight">
          Quiet code and empirical software reliability.
        </h1>
        <p className="text-base sm:text-lg text-[#64748B] leading-relaxed">
          DevRescue AI was created to solve the fatigue of chasing production stack traces. We build autonomous agents that triage issues, reproduce crashes, write minimal fixes, run tests, and prepare verified pull requests.
        </p>
      </div>

      {/* Core Principles */}
      <div className="space-y-6">
        <h2 className="text-xl font-bold text-[#0F172A]">Core Engineering Principles</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {principles.map((p, i) => (
            <Card key={i} className="p-6 space-y-3 border-[#E2E8F0]">
              <span className="text-xs font-bold text-[#2563EB] bg-[#EFF6FF] px-2.5 py-1 rounded-full border border-[#BFDBFE]">
                Principle 0{i + 1}
              </span>
              <h3 className="text-base font-bold text-[#0F172A]">{p.title}</h3>
              <p className="text-xs text-[#64748B] leading-relaxed">{p.desc}</p>
            </Card>
          ))}
        </div>
      </div>

      {/* Product Mission Box */}
      <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-2xl p-8 space-y-4">
        <div className="flex items-center gap-2 text-xs font-bold text-[#2563EB] uppercase tracking-wider">
          <Sparkles className="w-4 h-4" />
          <span>The DevRescue Mission</span>
        </div>
        <h3 className="text-xl font-bold text-[#0F172A]">
          From GitHub Issue to Verified Pull Request
        </h3>
        <p className="text-sm text-[#64748B] leading-relaxed">
          Modern engineering teams lose hundreds of hours to context switching when production errors arise. By pairing targeted AST code repair with automated reproduction and adversarial testing, DevRescue delivers ready-to-merge fixes that give engineers peace of mind.
        </p>
        <div className="pt-2">
          <PrimaryButton to="/dashboard" size="md" arrow={true}>
            Explore Developer Console
          </PrimaryButton>
        </div>
      </div>
    </div>
  );
}
