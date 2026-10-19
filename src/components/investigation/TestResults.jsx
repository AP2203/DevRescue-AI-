import React, { useState } from 'react';
import { ShieldCheck, ShieldAlert, AlertTriangle, Terminal, CheckCircle2, XCircle, Box, RefreshCw, Copy, Check, Sliders, Sparkles } from 'lucide-react';

export default function TestResults({
  testSummary,
  isComplete = false,
  isRealMode = false,
  sandboxResult = null,
  isTestingRunning = false,
  onRerunSandbox = null,
  hasPatch = false,
}) {
  const [copied, setCopied] = useState(false);
  const [overrideWorkdir, setOverrideWorkdir] = useState('');
  const [overrideCommand, setOverrideCommand] = useState('');
  const [isRerunning, setIsRerunning] = useState(false);
  const [overrideError, setOverrideError] = useState('');

  // REAL MODE RENDERING
  if (isRealMode) {
    if (isTestingRunning) {
      return (
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm space-y-5">
          <div className="flex items-center justify-between pb-3 border-b border-[#E2E8F0]">
            <div>
              <h3 className="text-sm font-bold text-[#0F172A] flex items-center gap-2">
                <Box className="w-4 h-4 text-[#2563EB]" />
                Docker Sandbox Test Runner
              </h3>
              <p className="text-xs text-[#64748B] mt-0.5">
                Executing patched repository tests in isolated container
              </p>
            </div>
            <span className="text-xs font-bold text-[#2563EB] bg-[#EFF6FF] border border-[#BFDBFE] px-2.5 py-1 rounded-full flex items-center gap-1.5 animate-pulse">
              <RefreshCw className="w-3 h-3 animate-spin" />
              RUNNING
            </span>
          </div>

          <div className="p-8 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-center space-y-4">
            <Box className="w-10 h-10 text-[#2563EB] mx-auto animate-bounce" />
            <div className="space-y-1">
              <h4 className="text-sm font-bold text-[#0F172A]">Docker Sandbox: RUNNING</h4>
              <p className="text-xs text-[#64748B] max-w-md mx-auto leading-relaxed">
                Applying unified diff to repository source and executing test suite inside an isolated Docker container.
              </p>
            </div>

            <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
              <span className="text-[11px] font-mono bg-white px-2.5 py-1 rounded border border-[#E2E8F0] text-[#475569]">
                --network none
              </span>
              <span className="text-[11px] font-mono bg-white px-2.5 py-1 rounded border border-[#E2E8F0] text-[#475569]">
                --cpus 2.0
              </span>
              <span className="text-[11px] font-mono bg-white px-2.5 py-1 rounded border border-[#E2E8F0] text-[#475569]">
                --memory 2g
              </span>
              <span className="text-[11px] font-mono bg-white px-2.5 py-1 rounded border border-[#E2E8F0] text-[#475569]">
                --pids-limit 100
              </span>
            </div>
          </div>
        </div>
      );
    }

    if (!sandboxResult) {
      return (
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#E2E8F0]">
            <div>
              <h3 className="text-sm font-bold text-[#0F172A] flex items-center gap-2">
                <Box className="w-4 h-4 text-[#64748B]" />
                Docker Sandbox Test Runner
              </h3>
              <p className="text-xs text-[#64748B] mt-0.5">
                Isolated container sandbox test runner
              </p>
            </div>
            <span className="text-xs font-bold text-[#64748B] bg-slate-100 px-2.5 py-1 rounded-full">
              AWAITING EXECUTION
            </span>
          </div>

          <div className="p-8 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-center space-y-3">
            <Box className="w-10 h-10 text-[#94A3B8] mx-auto" />
            <h4 className="text-sm font-bold text-[#0F172A]">No Sandbox Tests Run Yet</h4>
            <p className="text-xs text-[#64748B] max-w-md mx-auto leading-relaxed">
              Once Nemotron generates and validates a unified diff, the Testing Agent will automatically launch an isolated Docker sandbox to verify the patch.
            </p>
          </div>
        </div>
      );
    }

    // Status styling configuration
    const isPassed = sandboxResult.status === 'PASSED';
    const isSynthesizedTest = Boolean(sandboxResult.verified_via_synthesized_test || sandboxResult.verifiedViaSynthesizedTest);
    const isFailed = sandboxResult.status === 'FAILED' || sandboxResult.status === 'TESTS_FAILED';
    const isNoTestsFound = sandboxResult.status === 'NO_TESTS_FOUND';
    const isNotConfigured = sandboxResult.status === 'TESTS_NOT_CONFIGURED';
    const isUnsupported = sandboxResult.status === 'UNSUPPORTED_PROJECT';
    const isCollectionError = sandboxResult.status === 'TEST_COLLECTION_ERROR';
    const isTimeout = sandboxResult.status === 'TIMEOUT';
    const isDepsUnavailable = sandboxResult.status === 'DEPENDENCIES_UNAVAILABLE';
    const isEnvError = sandboxResult.status === 'ENVIRONMENT_ERROR';
    const isDockerUnavailable = sandboxResult.status === 'DOCKER_UNAVAILABLE';
    const isPatchFailed = sandboxResult.status === 'PATCH_FAILED';
    const isGenericError = sandboxResult.status === 'ERROR';

    const statusBadge = isPassed ? (
      <div className="flex items-center gap-2">
        <span className="text-xs font-bold text-[#16A34A] bg-[#DCFCE7] border border-[#86EFAC] px-2.5 py-1 rounded-full flex items-center gap-1.5">
          <CheckCircle2 className="w-3.5 h-3.5" />
          PASSED
        </span>
        {isSynthesizedTest && (
          <span className="text-xs font-bold text-[#7C3AED] bg-[#F5F3FF] border border-[#DDD6FE] px-2.5 py-1 rounded-full flex items-center gap-1.5 shadow-xs">
            <Sparkles className="w-3.5 h-3.5 text-[#7C3AED]" />
            AI-Synthesized Test Verified
          </span>
        )}
      </div>
    ) : isNoTestsFound ? (
      <span className="text-xs font-bold text-[#D97706] bg-[#FEF3C7] border border-[#FCD34D] px-2.5 py-1 rounded-full flex items-center gap-1.5">
        <AlertTriangle className="w-3.5 h-3.5" />
        NO_TESTS_FOUND
      </span>
    ) : isNotConfigured ? (
      <span className="text-xs font-bold text-[#D97706] bg-[#FEF3C7] border border-[#FCD34D] px-2.5 py-1 rounded-full flex items-center gap-1.5">
        <AlertTriangle className="w-3.5 h-3.5" />
        TESTS_NOT_CONFIGURED
      </span>
    ) : isUnsupported ? (
      <span className="text-xs font-bold text-[#6D28D9] bg-[#F5F3FF] border border-[#DDD6FE] px-2.5 py-1 rounded-full flex items-center gap-1.5">
        <AlertTriangle className="w-3.5 h-3.5 text-[#6D28D9]" />
        UNSUPPORTED_PROJECT
      </span>
    ) : isCollectionError ? (
      <span className="text-xs font-bold text-[#DC2626] bg-[#FEF2F2] border border-[#FECACA] px-2.5 py-1 rounded-full flex items-center gap-1.5">
        <AlertTriangle className="w-3.5 h-3.5 text-[#DC2626]" />
        TEST_COLLECTION_ERROR
      </span>
    ) : isTimeout ? (
      <span className="text-xs font-bold text-[#EA580C] bg-[#FFEDD5] border border-[#FDBA74] px-2.5 py-1 rounded-full flex items-center gap-1.5">
        <AlertTriangle className="w-3.5 h-3.5" />
        TIMEOUT
      </span>
    ) : isDepsUnavailable ? (
      <span className="text-xs font-bold text-[#D97706] bg-[#FEF3C7] border border-[#FCD34D] px-2.5 py-1 rounded-full flex items-center gap-1.5">
        <AlertTriangle className="w-3.5 h-3.5" />
        DEPENDENCIES_UNAVAILABLE
      </span>
    ) : isEnvError ? (
      <span className="text-xs font-bold text-[#DC2626] bg-[#FEF2F2] border border-[#FECACA] px-2.5 py-1 rounded-full flex items-center gap-1.5">
        <AlertTriangle className="w-3.5 h-3.5 text-[#DC2626]" />
        ENVIRONMENT_ERROR
      </span>
    ) : isDockerUnavailable ? (
      <span className="text-xs font-bold text-[#EA580C] bg-[#FFEDD5] border border-[#FDBA74] px-2.5 py-1 rounded-full flex items-center gap-1.5">
        <ShieldAlert className="w-3.5 h-3.5" />
        DOCKER_UNAVAILABLE
      </span>
    ) : isPatchFailed ? (
      <span className="text-xs font-bold text-[#DC2626] bg-[#FEF2F2] border border-[#FECACA] px-2.5 py-1 rounded-full flex items-center gap-1.5">
        <AlertTriangle className="w-3.5 h-3.5 text-[#DC2626]" />
        PATCH_FAILED
      </span>
    ) : isGenericError ? (
      <span className="text-xs font-bold text-[#DC2626] bg-[#FEF2F2] border border-[#FECACA] px-2.5 py-1 rounded-full flex items-center gap-1.5">
        <XCircle className="w-3.5 h-3.5" />
        ERROR
      </span>
    ) : (
      <span className="text-xs font-bold text-[#DC2626] bg-[#FEE2E2] border border-[#FCA5A5] px-2.5 py-1 rounded-full flex items-center gap-1.5">
        <XCircle className="w-3.5 h-3.5" />
        {sandboxResult.status || 'FAILED'}
      </span>
    );

    const handleCopy = () => {
      const text = `${sandboxResult.stdout || ''}\n${sandboxResult.stderr || ''}`.trim();
      navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    };

    // Client-side validation mirroring backend override guards. The backend remains
    // authoritative; this avoids obvious invalid submissions and surfaces errors in the UI.
    const validateOverrides = (workdir, command) => {
      const wd = (workdir || '').trim();
      if (wd) {
        const normalized = wd.replace(/\\/g, '/');
        if (normalized.split('/').filter(Boolean).includes('..')) {
          return 'Working directory must not contain ".." path traversal.';
        }
        if (/^[a-zA-Z]:/.test(normalized)) {
          return 'Working directory must be a relative path inside the repository.';
        }
        if (normalized.startsWith('/workspace') && normalized.slice('/workspace'.length).split('/').includes('..')) {
          return 'Working directory must stay inside /workspace.';
        }
        if (normalized.startsWith('/') && !normalized.startsWith('/workspace')) {
          return 'Working directory must stay inside /workspace.';
        }
      }
      const cmd = (command || '').trim();
      if (cmd) {
        const dangerous = /(^|[;&|])\s*(rm|rmdir|curl|wget|sudo|chmod|dd|shutdown|reboot|nc|ncat|netcat|eval|exec)\b/i;
        if (dangerous.test(cmd) || /\/dev\/tcp/.test(cmd)) {
          return 'Test command contains a forbidden or unsafe token.';
        }
        const approved = ['pytest', 'py.test', 'python', 'python3', 'npm', 'npx', 'yarn', 'pnpm', 'mvn', './mvnw', 'gradle', './gradlew', 'go', 'cargo', 'tox', 'poetry', 'pipenv'];
        const subs = cmd.split(/[;&|]+/).map((s) => s.trim()).filter(Boolean);
        for (const sub of subs) {
          if (!approved.some((p) => sub === p || sub.startsWith(`${p} `))) {
            return `"${sub}" is not an approved test runner command.`;
          }
        }
      }
      return '';
    };

    const handleRerunClick = async () => {
      if (!onRerunSandbox || isRerunning) return;
      const validationError = validateOverrides(overrideWorkdir, overrideCommand);
      if (validationError) {
        setOverrideError(validationError);
        return;
      }
      setOverrideError('');
      setIsRerunning(true);
      try {
        await onRerunSandbox({
          working_directory: overrideWorkdir.trim() || undefined,
          test_command: overrideCommand.trim() || undefined
        });
      } finally {
        setIsRerunning(false);
      }
    };

    return (
      <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-[#E2E8F0]">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-[#0F172A] flex items-center gap-2">
                <Box className="w-4 h-4 text-[#2563EB]" />
                Automated Docker Sandbox Test Results
              </h3>
              <span className="text-[10px] font-bold text-[#2563EB] bg-[#EFF6FF] px-2 py-0.5 rounded border border-[#BFDBFE]">
                REAL DOCKER RUNNER
              </span>
            </div>
            <p className="text-xs text-[#64748B] mt-0.5">
              Executed inside ephemeral container with network isolation
            </p>
          </div>
          {statusBadge}
        </div>

        {/* Numerical Summary Metrics Cards */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-center">
          <div className="p-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg">
            <span className="text-xs font-mono font-bold text-[#0F172A] block truncate" title={sandboxResult.test_command || 'None'}>
              {sandboxResult.test_command || 'None'}
            </span>
            <span className="text-[11px] text-[#64748B]">Command</span>
          </div>

          <div className="p-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg">
            <span className="text-lg font-bold text-[#0F172A] block">
              {sandboxResult.tests_run ?? '—'}
            </span>
            <span className="text-[11px] text-[#64748B]">Tests Run</span>
          </div>

          <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
            <span className="text-lg font-bold text-[#16A34A] block">
              {sandboxResult.tests_passed ?? (isPassed ? 'All' : '0')}
            </span>
            <span className="text-[11px] text-[#16A34A] font-medium">Passed</span>
          </div>

          <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg">
            <span className="text-lg font-bold text-[#DC2626] block">
              {sandboxResult.tests_failed ?? (isFailed ? '1+' : '0')}
            </span>
            <span className="text-[11px] text-[#DC2626] font-medium">Failed</span>
          </div>

          <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <span className="text-lg font-bold text-[#2563EB] block">
              {sandboxResult.duration_seconds ? `${sandboxResult.duration_seconds}s` : '—'}
            </span>
            <span className="text-[11px] text-[#2563EB] font-medium">Duration</span>
          </div>
        </div>

        {/* AI-Synthesized Test Fallback Banner */}
        {isSynthesizedTest && (
          <div className="bg-[#FAF5FF] border border-[#E9D5FF] rounded-lg p-3.5 flex items-start gap-3 shadow-xs">
            <div className="w-7 h-7 rounded-lg bg-[#7C3AED]/10 text-[#7C3AED] flex items-center justify-center shrink-0 mt-0.5">
              <Sparkles className="w-4 h-4" />
            </div>
            <div className="space-y-0.5">
              <h4 className="text-xs font-bold text-[#6B21A8] flex items-center gap-1.5">
                AI Test Synthesis Fallback Activated
                <span className="text-[10px] font-mono bg-[#EDE9FE] text-[#6D28D9] px-2 py-0.5 rounded-full font-semibold">
                  Zero-Test Fallback
                </span>
              </h4>
              <p className="text-xs text-[#7E22CE] leading-relaxed">
                This repository initially contained zero matching test files (<code className="font-mono text-[11px] bg-[#EDE9FE] px-1 py-0.5 rounded">NO_TESTS_FOUND</code>).
                DevRescue AI automatically synthesized a minimal unit test to reproduce the bug and verify the fix inside the isolated Docker sandbox (<code className="font-mono text-[11px] bg-[#EDE9FE] px-1 py-0.5 rounded">--network none</code>).
              </p>
            </div>
          </div>
        )}

        {/* Security / Sandbox Guarantees Banner */}
        <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg p-3 flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex items-center gap-2 text-[#475569]">
            <ShieldCheck className="w-4 h-4 text-[#16A34A]" />
            <span className="font-semibold text-[#0F172A]">Security Guarantees:</span>
            <span>Network disabled (<code className="text-[#2563EB] font-mono text-[11px]">--network none</code>)</span>
            <span>•</span>
            <span>Ephemeral workspace destroyed</span>
            <span>•</span>
            <span>No host credentials exposed</span>
          </div>
          <div className="flex items-center gap-2 font-mono text-[11px] text-[#64748B]">
            <span>Exit Code: {sandboxResult.exit_code !== null && sandboxResult.exit_code !== undefined ? sandboxResult.exit_code : 'N/A'}</span>
          </div>
        </div>

        {/* Framework & Working Directory Info */}
        {(sandboxResult.framework || sandboxResult.working_directory || sandboxResult.test_strategy) && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-3 text-xs bg-slate-50 border border-slate-200 px-3 py-2 rounded-lg text-slate-700">
              {sandboxResult.framework && (
                <span className="flex items-center gap-1.5">
                  <span className="text-slate-500 font-medium">Framework:</span>
                  <span className="font-mono font-semibold text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-200">
                    {sandboxResult.framework}
                  </span>
                </span>
              )}
              {sandboxResult.working_directory && (
                <span className="flex items-center gap-1.5">
                  <span className="text-slate-500 font-medium">Working Dir:</span>
                  <span className="font-mono font-semibold text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-200">
                    {sandboxResult.working_directory.startsWith('/') ? sandboxResult.working_directory : `/${sandboxResult.working_directory}`}
                  </span>
                </span>
              )}
              {sandboxResult.docker_image && (
                <span className="flex items-center gap-1.5">
                  <span className="text-slate-500 font-medium">Image:</span>
                  <span className="font-mono text-slate-700 bg-white px-2 py-0.5 rounded border border-slate-200">
                    {sandboxResult.docker_image}
                  </span>
                </span>
              )}
            </div>

            {/* Test Strategy Contract Details */}
            {sandboxResult.test_strategy && (
              <div className="p-3 bg-blue-50/50 border border-blue-100 rounded-lg text-xs space-y-1.5">
                <div className="flex items-center justify-between font-semibold text-[#1E3A8A]">
                  <span>Test Strategy Contract:</span>
                  <span className="font-mono text-[11px] font-normal text-blue-700 bg-white px-2 py-0.5 rounded border border-blue-200">
                    Status: {sandboxResult.test_strategy.status} • Confidence: {Math.round((sandboxResult.test_strategy.confidence || 1) * 100)}%
                  </span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 font-mono text-[11px]">
                  <div className="bg-white p-1.5 rounded border border-blue-100">
                    <span className="text-slate-400 block text-[10px]">Language</span>
                    <span className="text-slate-800 font-medium">{sandboxResult.test_strategy.language} {sandboxResult.test_strategy.runtime_version ? `(${sandboxResult.test_strategy.runtime_version})` : ''}</span>
                  </div>
                  <div className="bg-white p-1.5 rounded border border-blue-100">
                    <span className="text-slate-400 block text-[10px]">Package Manager</span>
                    <span className="text-slate-800 font-medium">{sandboxResult.test_strategy.package_manager || 'None'}</span>
                  </div>
                  <div className="bg-white p-1.5 rounded border border-blue-100">
                    <span className="text-slate-400 block text-[10px]">Discovered Tests</span>
                    <span className="text-slate-800 font-medium">{sandboxResult.test_strategy.test_files_count} test file(s)</span>
                  </div>
                  <div className="bg-white p-1.5 rounded border border-blue-100">
                    <span className="text-slate-400 block text-[10px]">Test Command</span>
                    <span className="text-slate-800 font-medium truncate block">{sandboxResult.test_strategy.test_command || 'None'}</span>
                  </div>
                </div>
                {sandboxResult.test_strategy.env_var_names && sandboxResult.test_strategy.env_var_names.length > 0 && (
                  <div className="text-[11px] text-blue-800 pt-1 flex flex-wrap items-center gap-1.5">
                    <span className="font-semibold text-blue-900">Injected Runtime Env:</span>
                    <span className="bg-white px-2 py-0.5 rounded border border-blue-200 font-mono text-[10px]">
                      {sandboxResult.test_strategy.env_var_names.length} non-sensitive dummy var(s) (.env.example / CI)
                    </span>
                  </div>
                )}
                {sandboxResult.test_strategy.supporting_evidence && sandboxResult.test_strategy.supporting_evidence.length > 0 && (
                  <div className="text-[11px] text-slate-600 pt-1">
                    <span className="font-semibold text-slate-700">Profiling Evidence: </span>
                    {sandboxResult.test_strategy.supporting_evidence.slice(0, 3).join(' • ')}
                  </div>
                )}
                {(sandboxResult.retry_history?.length > 0 || sandboxResult.repair_retries > 0) && (
                  <div className="text-[11px] text-purple-700 pt-1 flex items-center gap-1.5 font-medium">
                    <span className="bg-purple-100 text-purple-800 px-2 py-0.5 rounded border border-purple-200">
                      Self-Healing Retries: {sandboxResult.repair_retries || sandboxResult.retry_history.length} attempt(s)
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Message / Notice if TESTS_NOT_CONFIGURED, DEPENDENCIES_UNAVAILABLE, or DOCKER_UNAVAILABLE */}
        {sandboxResult.message && (
          <div className={`p-3.5 rounded-lg border text-xs ${
            isPassed
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : (isNotConfigured || isNoTestsFound || isDepsUnavailable)
              ? 'bg-amber-50 border-amber-200 text-amber-900'
              : 'bg-rose-50 border-rose-200 text-rose-900'
          }`}>
            <div className="font-semibold mb-0.5">Execution Details:</div>
            <div className="whitespace-pre-wrap font-mono">{sandboxResult.message}</div>
          </div>
        )}

        {/* Manual Override & Rerun Controls */}
        {onRerunSandbox && (
          <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-[#0F172A] flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5 text-[#2563EB]" />
                Manual Test Strategy Override & Rerun
              </span>
              <span className="text-[11px] text-[#64748B]">
                Specify custom path or test command
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div>
                <label className="block text-[11px] font-medium text-[#475569] mb-1">
                  Working Directory Override
                </label>
                <input
                  type="text"
                  value={overrideWorkdir}
                  onChange={(e) => { setOverrideWorkdir(e.target.value); setOverrideError(''); }}
                  placeholder={sandboxResult.working_directory || "e.g. backend or src"}
                  className="w-full px-2.5 py-1.5 text-xs font-mono bg-white border border-[#CBD5E1] rounded-md focus:ring-1 focus:ring-[#2563EB] focus:border-[#2563EB] outline-none"
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-[#475569] mb-1">
                  Test Command Override
                </label>
                <input
                  type="text"
                  value={overrideCommand}
                  onChange={(e) => { setOverrideCommand(e.target.value); setOverrideError(''); }}
                  placeholder={sandboxResult.test_command || "e.g. pytest tests/ -v or npm test"}
                  className="w-full px-2.5 py-1.5 text-xs font-mono bg-white border border-[#CBD5E1] rounded-md focus:ring-1 focus:ring-[#2563EB] focus:border-[#2563EB] outline-none"
                />
              </div>
            </div>

            {overrideError && (
              <div className="text-[11px] font-medium text-[#DC2626] bg-[#FEF2F2] border border-[#FECACA] rounded-md px-2.5 py-1.5">
                {overrideError}
              </div>
            )}

            <div className="flex items-center justify-between pt-1">
              <p className="text-[11px] text-[#64748B]">
                Applies current patch and executes inside isolated container (<code className="font-mono text-[#2563EB]">--network none</code>).
              </p>
              <button
                type="button"
                disabled={isTestingRunning || isRerunning || !hasPatch}
                onClick={handleRerunClick}
                className="px-3 py-1.5 text-xs font-semibold text-white bg-[#2563EB] hover:bg-[#1D4ED8] disabled:bg-[#94A3B8] rounded-md flex items-center gap-1.5 cursor-pointer transition-colors"
              >
                <RefreshCw className={`w-3 h-3 ${isRerunning ? 'animate-spin' : ''}`} />
                {isRerunning ? 'Executing Sandbox...' : 'Rerun in Docker Sandbox'}
              </button>
            </div>
          </div>
        )}

        {/* Terminal Output Viewer (stdout / stderr) */}
        {(sandboxResult.stdout || sandboxResult.stderr) && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-[#0F172A] flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5 text-[#64748B]" />
                Sandbox Console Output
              </span>
              <button
                type="button"
                onClick={handleCopy}
                className="text-[11px] text-[#64748B] hover:text-[#0F172A] flex items-center gap-1 cursor-pointer transition-colors"
              >
                {copied ? <Check className="w-3 h-3 text-[#16A34A]" /> : <Copy className="w-3 h-3" />}
                {copied ? 'Copied' : 'Copy Output'}
              </button>
            </div>

            <div className="bg-[#0F172A] text-[#F8FAFC] rounded-lg p-4 font-mono text-xs overflow-x-auto max-h-80 border border-[#334155] leading-relaxed">
              {sandboxResult.stdout && (
                <div className="whitespace-pre-wrap">{sandboxResult.stdout}</div>
              )}
              {sandboxResult.stderr && (
                <div className="text-rose-400 mt-2 whitespace-pre-wrap border-t border-[#334155] pt-2">
                  <div className="text-[11px] font-bold text-rose-300">STDERR:</div>
                  {sandboxResult.stderr}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    );
  }

  // DEMO MODE RENDERING
  const total = testSummary?.total || 14;
  const passed = isComplete ? total : (testSummary?.passed || 12);
  const pending = isComplete ? 0 : (testSummary?.pending || (total - passed));

  const testList = [
    { name: 'Unit: Render Login Form component', status: 'Passed' },
    { name: 'Unit: Input field validation & state updates', status: 'Passed' },
    { name: 'Integration: Invoke authenticateUser with credentials', status: 'Passed' },
    { name: 'Regression: Verify error banner handling & boundary', status: 'Passed' },
    { name: 'End-to-End: Full authentication session lifecycle', status: isComplete ? 'Passed' : 'Pending' },
  ];

  return (
    <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm space-y-5">
      <div className="flex items-center justify-between pb-3 border-b border-[#E2E8F0]">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-[#0F172A]">
              Automated Test Suite Execution
            </h3>
            <span className="text-[10px] font-bold text-[#2563EB] bg-[#EFF6FF] px-2 py-0.5 rounded border border-[#BFDBFE]">
              SIMULATED DEMO RESULT
            </span>
          </div>
          <p className="text-xs text-[#64748B] mt-0.5">
            Synthetic test proof synthesized for interactive prototype demo
          </p>
        </div>
        <span className="text-xs font-bold text-[#16A34A] bg-[#DCFCE7] px-2.5 py-1 rounded-full">
          {passed}/{total} Passed
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="p-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg">
          <span className="text-lg font-bold text-[#0F172A] block">{total}</span>
          <span className="text-[11px] text-[#64748B]">Total Tests</span>
        </div>
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
          <span className="text-lg font-bold text-[#16A34A] block">{passed}</span>
          <span className="text-[11px] text-[#16A34A] font-medium">Passed</span>
        </div>
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <span className="text-lg font-bold text-[#2563EB] block">{pending}</span>
          <span className="text-[11px] text-[#2563EB] font-medium">Pending</span>
        </div>
      </div>

      <div className="space-y-2 text-xs">
        {testList.map((t, idx) => (
          <div
            key={idx}
            className="p-3 bg-white border border-[#E2E8F0] rounded-lg flex items-center justify-between hover:bg-[#F8FAFC] transition-colors"
          >
            <span className="font-mono text-[#0F172A]">{t.name}</span>
            <span
              className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                t.status === 'Passed'
                  ? 'bg-[#DCFCE7] text-[#16A34A]'
                  : 'bg-[#DBEAFE] text-[#2563EB] animate-pulse'
              }`}
            >
              {t.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
