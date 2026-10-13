import React from 'react';
import { ShieldCheck, ShieldAlert, AlertTriangle, CheckCircle2, XCircle, Info, Lock } from 'lucide-react';

export default function SecurityResults({ isRealMode = false, securityResult = null }) {
  if (isRealMode) {
    if (!securityResult || securityResult.status === 'NOT_IMPLEMENTED') {
      return (
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#E2E8F0]">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-[#0F172A]">
                  Automated Security Review
                </h3>
                <span className="text-[10px] font-bold text-[#64748B] bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                  REAL MODE
                </span>
              </div>
              <p className="text-xs text-[#64748B] mt-0.5">
                AST vulnerability inspection &amp; secret scanner
              </p>
            </div>
            <span className="text-xs font-bold text-[#64748B] bg-slate-100 px-2.5 py-1 rounded-full">
              NOT IMPLEMENTED
            </span>
          </div>

          <div className="p-8 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-center space-y-3">
            <ShieldAlert className="w-10 h-10 text-[#94A3B8] mx-auto" />
            <h4 className="text-sm font-bold text-[#0F172A]">Security Review: Awaiting Execution / Not Configured</h4>
            <p className="text-xs text-[#64748B] max-w-md mx-auto leading-relaxed">
              DevRescue AI never claims &quot;No secrets detected&quot; unless the scanner has actually executed.
              {securityResult?.message ? ` ${securityResult.message}` : ' A patch diff must be generated and submitted to trigger the security audit.'}
            </p>
            <div className="pt-2">
              <span className="text-[11px] font-mono bg-white px-3 py-1 rounded border border-[#E2E8F0] text-[#64748B]">
                status: NOT_IMPLEMENTED
              </span>
            </div>
          </div>

          {securityResult?.limitations && (
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-600 flex items-start gap-2">
              <Info className="w-4 h-4 text-slate-400 flex-shrink-0 mt-0.5" />
              <span><strong>Scanner Note:</strong> {securityResult.limitations}</span>
            </div>
          )}
        </div>
      );
    }

    const isPassed = securityResult.status === 'PASSED';
    const isWarnings = securityResult.status === 'WARNINGS';
    const isFailed = securityResult.status === 'FAILED';

    const statusBadge = isPassed ? (
      <span className="text-xs font-bold text-[#16A34A] bg-[#DCFCE7] border border-[#86EFAC] px-2.5 py-1 rounded-full flex items-center gap-1.5">
        <CheckCircle2 className="w-3.5 h-3.5" />
        PASSED
      </span>
    ) : isWarnings ? (
      <span className="text-xs font-bold text-[#D97706] bg-[#FEF3C7] border border-[#FCD34D] px-2.5 py-1 rounded-full flex items-center gap-1.5">
        <AlertTriangle className="w-3.5 h-3.5" />
        WARNINGS
      </span>
    ) : (
      <span className="text-xs font-bold text-[#DC2626] bg-[#FEE2E2] border border-[#FCA5A5] px-2.5 py-1 rounded-full flex items-center gap-1.5">
        <XCircle className="w-3.5 h-3.5" />
        FAILED
      </span>
    );

    const findings = securityResult.findings || [];

    return (
      <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-[#E2E8F0]">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-[#0F172A] flex items-center gap-2">
                <Lock className="w-4 h-4 text-[#2563EB]" />
                Automated Security Review (SAST &amp; Secrets)
              </h3>
              <span className="text-[10px] font-bold text-[#2563EB] bg-[#EFF6FF] px-2 py-0.5 rounded border border-[#BFDBFE]">
                REAL SAST SCANNER
              </span>
            </div>
            <p className="text-xs text-[#64748B] mt-0.5">
              Analyzes patch diff additions for leaked credentials, unsafe execution, and SQL injection
            </p>
          </div>
          {statusBadge}
        </div>

        {/* Summary Banner */}
        <div className={`p-4 rounded-xl border text-xs ${
          isPassed
            ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
            : isWarnings
            ? 'bg-amber-50 border-amber-200 text-amber-900'
            : 'bg-rose-50 border-rose-200 text-rose-900'
        }`}>
          <div className="flex items-start gap-2.5">
            {isPassed ? (
              <ShieldCheck className="w-5 h-5 text-[#16A34A] flex-shrink-0 mt-0.5" />
            ) : isWarnings ? (
              <AlertTriangle className="w-5 h-5 text-[#D97706] flex-shrink-0 mt-0.5" />
            ) : (
              <ShieldAlert className="w-5 h-5 text-[#DC2626] flex-shrink-0 mt-0.5" />
            )}
            <div>
              <span className="font-bold block text-sm">
                {isPassed ? 'Patch Security Verification Passed' : (isWarnings ? 'Security Notice: Warnings Detected' : 'Security Verification Failed')}
              </span>
              <p className="text-xs mt-1 leading-relaxed opacity-90">
                {securityResult.summary || 'Security analysis complete.'}
              </p>
            </div>
          </div>
        </div>

        {/* Metric Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-center">
          <div className="p-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg">
            <span className="text-lg font-bold text-[#0F172A] block">
              {securityResult.findings_count ?? findings.length}
            </span>
            <span className="text-[11px] text-[#64748B]">Total Findings</span>
          </div>

          <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg">
            <span className="text-lg font-bold text-[#DC2626] block">
              {securityResult.critical_count ?? findings.filter(f => f.severity === 'CRITICAL').length}
            </span>
            <span className="text-[11px] text-[#DC2626] font-medium">Critical</span>
          </div>

          <div className="p-3 bg-orange-50 border border-orange-200 rounded-lg">
            <span className="text-lg font-bold text-[#EA580C] block">
              {securityResult.high_count ?? findings.filter(f => f.severity === 'HIGH').length}
            </span>
            <span className="text-[11px] text-[#EA580C] font-medium">High</span>
          </div>

          <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
            <span className="text-lg font-bold text-[#D97706] block">
              {(securityResult.medium_count ?? findings.filter(f => f.severity === 'MEDIUM').length) +
               (securityResult.low_count ?? findings.filter(f => f.severity === 'LOW').length)}
            </span>
            <span className="text-[11px] text-[#D97706] font-medium">Medium / Low</span>
          </div>
        </div>

        {/* Passed Verification Checks List */}
        {isPassed && (
          <div className="space-y-2.5">
            <h4 className="text-xs font-bold uppercase tracking-wider text-[#475569]">
              Verified SAST Security Invariants
            </h4>
            <div className="p-3.5 rounded-xl border border-emerald-200 bg-emerald-50/40 flex items-start gap-3 text-xs text-[#0F172A]">
              <CheckCircle2 className="w-4 h-4 text-[#16A34A] flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold block text-[#16A34A]">No Leaked Secrets or Credentials Detected</span>
                <span className="text-[#64748B] text-[11px] block mt-0.5">
                  Pattern entropy scan found 0 API keys, personal access tokens, private keys, or passwords.
                </span>
              </div>
            </div>
            <div className="p-3.5 rounded-xl border border-emerald-200 bg-emerald-50/40 flex items-start gap-3 text-xs text-[#0F172A]">
              <CheckCircle2 className="w-4 h-4 text-[#16A34A] flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold block text-[#16A34A]">No Unsafe Command or Shell Execution</span>
                <span className="text-[#64748B] text-[11px] block mt-0.5">
                  No direct invocations of <code>os.system()</code>, <code>subprocess</code> with <code>shell=True</code>, or interactive shell spawning.
                </span>
              </div>
            </div>
            <div className="p-3.5 rounded-xl border border-emerald-200 bg-emerald-50/40 flex items-start gap-3 text-xs text-[#0F172A]">
              <CheckCircle2 className="w-4 h-4 text-[#16A34A] flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold block text-[#16A34A]">No Dangerous Dynamic Code Evaluation</span>
                <span className="text-[#64748B] text-[11px] block mt-0.5">
                  No invocations of <code>eval()</code> or <code>exec()</code> on untrusted inputs.
                </span>
              </div>
            </div>
            <div className="p-3.5 rounded-xl border border-emerald-200 bg-emerald-50/40 flex items-start gap-3 text-xs text-[#0F172A]">
              <CheckCircle2 className="w-4 h-4 text-[#16A34A] flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold block text-[#16A34A]">No SQL Injection Patterns</span>
                <span className="text-[#64748B] text-[11px] block mt-0.5">
                  Queries are not constructed via raw f-strings, concatenation, or percent string formatting.
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Detailed Findings List (if any) */}
        {findings.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-[#0F172A]">
              Detected Findings ({findings.length})
            </h4>
            {findings.map((f, idx) => {
              const sev = (f.severity || 'HIGH').toUpperCase();
              const badgeClass =
                sev === 'CRITICAL'
                  ? 'bg-red-100 text-red-800 border-red-300'
                  : sev === 'HIGH'
                  ? 'bg-rose-100 text-rose-800 border-rose-300'
                  : sev === 'MEDIUM'
                  ? 'bg-amber-100 text-amber-800 border-amber-300'
                  : 'bg-blue-100 text-blue-800 border-blue-300';

              return (
                <div
                  key={idx}
                  className="p-3.5 rounded-lg border border-[#E2E8F0] bg-white space-y-2 text-xs shadow-xs"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${badgeClass}`}>
                        {sev}
                      </span>
                      <span className="font-mono font-bold text-[#0F172A]">
                        {f.rule_id}
                      </span>
                    </div>
                    <span className="text-[11px] font-mono text-[#64748B]">
                      {f.file}{f.line_number ? `:${f.line_number}` : ''}
                    </span>
                  </div>
                  <p className="text-[#334155]">{f.description}</p>
                  {f.snippet && (
                    <pre className="font-mono text-[11px] bg-slate-900 text-slate-100 p-2 rounded overflow-x-auto">
                      {f.snippet}
                    </pre>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Scanner Limitations Disclosure */}
        <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-600 flex items-start gap-2">
          <Info className="w-4 h-4 text-slate-400 flex-shrink-0 mt-0.5" />
          <div className="leading-relaxed">
            <span className="font-semibold text-slate-800">Scanner Limitations &amp; Architecture: </span>
            {securityResult.limitations || 'Pattern-based heuristic static analysis. Host does not have native Semgrep binary. Does not replace dynamic taint analysis or runtime container isolation.'}
          </div>
        </div>
      </div>
    );
  }

  // DEMO MODE RENDERING
  const securityChecks = [
    { title: 'No secrets or credentials detected in patch', desc: 'Entropy scanner found 0 API keys or private tokens.' },
    { title: 'No dependency changes or package.json alterations', desc: 'Supply-chain surface area remains strictly unchanged.' },
    { title: 'Changes strictly limited to requested modules', desc: 'Minimal blast radius confined to 2 targeted files.' },
  ];

  return (
    <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-[#E2E8F0]">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-[#0F172A]">
              Automated Security Review
            </h3>
            <span className="text-[10px] font-bold text-[#16A34A] bg-[#DCFCE7] px-2 py-0.5 rounded">
              SIMULATED DEMO RESULT
            </span>
          </div>
          <p className="text-xs text-[#64748B] mt-0.5">
            Pre-commit secret audit and AST vulnerability inspection (Demo Mode)
          </p>
        </div>
        <span className="text-xs font-bold text-[#16A34A] bg-[#DCFCE7] px-2.5 py-1 rounded-full flex items-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5" />
          Low Risk
        </span>
      </div>

      <div className="space-y-3">
        {securityChecks.map((check, idx) => (
          <div
            key={idx}
            className="p-3.5 rounded-xl border border-emerald-200 bg-emerald-50/40 flex items-start gap-3 text-xs text-[#0F172A]"
          >
            <CheckCircle2 className="w-4 h-4 text-[#16A34A] flex-shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold block text-[#16A34A]">{check.title}</span>
              <span className="text-[#64748B] text-[11px] block mt-0.5">{check.desc}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
