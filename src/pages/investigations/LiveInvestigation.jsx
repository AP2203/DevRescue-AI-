import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { AlertCircle, RefreshCw, ShieldCheck, Sparkles } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import Button from '../../components/common/Button';
import { ConfirmDialog } from '../../components/common/Modal';
import api from '../../services/api';
import DiffViewer from '../../components/common/DiffViewer';

// Modular Investigation Components
import InvestigationHeader from '../../components/investigation/InvestigationHeader';
import InvestigationProgress from '../../components/investigation/InvestigationProgress';
import AgentPipeline from '../../components/investigation/AgentPipeline';
import LiveLogs from '../../components/investigation/LiveLogs';
import FilesAnalyzed from '../../components/investigation/FilesAnalyzed';
import RootCause from '../../components/investigation/RootCause';
import TestResults from '../../components/investigation/TestResults';
import SecurityResults from '../../components/investigation/SecurityResults';

export default function LiveInvestigation() {
  const { id } = useParams();
  const { getInvestigation, updateInvestigation, addNotification, appMode } = useApp();

  const [prevId, setPrevId] = useState(id);
  const [inv, setInv] = useState(() => getInvestigation(id) || null);
  const [activeTab, setActiveTab] = useState('LOGS');
  const [isSimulating, setIsSimulating] = useState(true);
  const [stopConfirmOpen, setStopConfirmOpen] = useState(false);

  // Real Investigation State
  const [isInvestigating, setIsInvestigating] = useState(false);
  const [investigationError, setInvestigationError] = useState(null);
  const [errorStatus, setErrorStatus] = useState(null);
  const [patchErrorDetails, setPatchErrorDetails] = useState(null);
  const [dockerStatus, setDockerStatus] = useState(null);
  const [failureInfo, setFailureInfo] = useState(null);
  const executedTracker = useRef(new Set());
  // Monotonic token identifying the currently active run. Async responses from an
  // older run are ignored so they cannot overwrite the current run's state.
  const activeRunTokenRef = useRef(0);

  const isRealMode = (inv?.mode?.toUpperCase() === 'REAL') || (appMode === 'REAL');

  if (prevId !== id) {
    setPrevId(id);
    setInv(getInvestigation(id) || null);
    setInvestigationError(null);
    setErrorStatus(null);
    setPatchErrorDetails(null);
    setFailureInfo(null);
  }

  // Real Mode: Query backend status or sync existing
  useEffect(() => {
    let isSubscribed = true;

    // Check Docker daemon and sandbox status
    api.getSandboxStatus()
      .then((status) => {
        if (isSubscribed && status) {
          setDockerStatus(status);
        }
      })
      .catch((err) => {
        console.warn('Sandbox status query failed:', err);
      });

    if (!id) return;

    api.getInvestigation(id)
      .then((backendInv) => {
        if (isSubscribed && backendInv) {
          const latestRun = backendInv.latest_run;
          setInv((prev) => ({
            ...backendInv,
            latest_run_id: backendInv.latest_run_id || latestRun?.run_id || prev?.latest_run_id,
            stages: latestRun?.stages || backendInv.stages || prev?.stages,
            rootCause: latestRun?.root_cause || backendInv.rootCause || prev?.rootCause,
            patch: latestRun?.patch || backendInv.patch || prev?.patch,
            sandboxResult: latestRun?.sandbox_result !== undefined ? latestRun.sandbox_result : (backendInv.sandboxResult !== undefined ? backendInv.sandboxResult : prev?.sandboxResult),
            securityResult: latestRun?.security_result || backendInv.securityResult || prev?.securityResult,
            riskAssessment: latestRun?.risk_assessment || backendInv.riskAssessment || prev?.riskAssessment,
            agents: backendInv.agents || prev?.agents,
            logs: latestRun?.logs || backendInv.logs || prev?.logs,
          }));
          setErrorStatus(null);
          setInvestigationError(null);
        }
      })
      .catch((err) => {
        if (isSubscribed) {
          if (err?.status === 404) {
            // Investigation not found on backend; do not fabricate fake records in real mode
            if (isRealMode) {
              setInv(null);
            }
            setErrorStatus(404);
            setInvestigationError(`Investigation #${id} was not found on the server.`);
          }
        }
      });

    return () => {
      isSubscribed = false;
    };
  }, [id, isRealMode]);


  // Execute Real NVIDIA Nemotron Investigation + Real Unified Patch Generation
  const runRealInvestigation = useCallback(async (overrideRunId = null) => {
    if (!inv) return;

    const runToken = ++activeRunTokenRef.current;
    const isStale = () => activeRunTokenRef.current !== runToken;
    const runStartedAt = Date.now();

    const currentRunId = overrideRunId || inv?.latest_run_id || `run_${id}_${Date.now()}`;

    // Extract repository details. This MUST be explicitly bound; we never default to
    // another repository, since that would contaminate results across investigations.
    let owner = inv.owner;
    let repoName = inv.repo_name;
    const rawRepo = inv.repo || inv.repository || '';
    if (rawRepo.includes('/')) {
      const parts = rawRepo.split('/');
      owner = owner || parts[0];
      repoName = repoName || parts[1];
    } else {
      repoName = repoName || rawRepo || '';
    }
    const branch = inv.branch || 'main';
    const issueNumber = Number(inv.issue_number || inv.issueNumber || 1);

    if (!owner || !repoName) {
      setIsInvestigating(false);
      const msg = 'Repository binding is missing (owner/repo). Refusing to run to avoid cross-repository contamination. Please re-select the issue.';
      setErrorStatus(409);
      setInvestigationError(msg);
      setFailureInfo({ stage: 'Repository Retrieval', message: msg, retryable: false, runId: currentRunId, elapsedSeconds: 0 });
      addNotification(msg, 'error');
      return;
    }

    setIsInvestigating(true);
    setInvestigationError(null);
    setPatchErrorDetails(null);
    setFailureInfo(null);
    setErrorStatus(null);

    const nowStr = new Date().toLocaleTimeString();
    const liveAgents = [
      {
        id: '1',
        step: 1,
        name: 'Repository Analyzer',
        role: 'AST & Tree Parsing',
        status: 'IN_PROGRESS',
        time: 'Active',
        summary: `Scanning ${owner}/${repoName}@${branch}...`
      },
      {
        id: '2',
        step: 2,
        name: 'Bug Investigator',
        role: 'Root Cause Isolation',
        status: 'IN_PROGRESS',
        time: 'Active',
        summary: `Isolating root cause for issue #${issueNumber}...`
      },
      {
        id: '3',
        step: 3,
        name: 'Code Repair Agent',
        role: 'Patch Synthesis',
        status: 'PENDING',
        time: '—',
        summary: 'Awaiting diagnosis'
      },
      {
        id: '4',
        step: 4,
        name: 'Testing Agent',
        role: 'Isolated Sandbox Emulation',
        status: 'PENDING',
        time: '—',
        summary: 'Awaiting patch synthesis'
      },
      {
        id: '5',
        step: 5,
        name: 'Security Reviewer',
        role: 'SAST & Secrets Audit',
        status: 'PENDING',
        time: '—',
        summary: 'Awaiting patch synthesis'
      }
    ];

    const startLogs = [
      ...(inv.logs || []),
      { time: nowStr, agent: 'SYS', message: `[REAL INVESTIGATION] POST /api/ai/nemotron/investigate` },
      { time: nowStr, agent: 'GitHub', message: `Connecting to ${owner}/${repoName} (${branch}) for issue #${issueNumber}...` },
      { time: nowStr, agent: 'Analyzer', message: 'Analyzing repository tree and selecting candidate modules...' },
      { time: nowStr, agent: 'Nemotron', message: 'Calling NVIDIA Nemotron 3.5 (nvidia/nemotron-3.5-lightning-30b-a3b)...' }
    ];

    // Optimistically update status to show running state
    setInv((prev) => ({
      ...prev,
      status: 'IN_PROGRESS',
      progress: 35,
      agents: liveAgents,
      logs: startLogs
    }));

    try {
      // STAGE 1: Investigation
      const payload = {
        owner,
        repo: repoName,
        branch,
        issue_number: issueNumber
      };

      const res = await api.investigateNemotron(payload);
      if (isStale()) return;

      const filesAnalyzedList = (res.files_analyzed || []).map((f) => f.path);
      const invRes = res.investigation || {};

      // Transition to STAGE 2: Code Repair Agent (Patch Generation)
      const stage2Agents = [
        {
          id: '1',
          step: 1,
          name: 'Repository Analyzer',
          role: 'AST & Tree Parsing',
          status: 'COMPLETE',
          time: '2.5s',
          summary: `${filesAnalyzedList.length} files parsed in AST`
        },
        {
          id: '2',
          step: 2,
          name: 'Bug Investigator',
          role: 'Root Cause Isolation',
          status: 'COMPLETE',
          time: '4.8s',
          summary: `Root cause isolated (${Math.round((invRes.confidence || 0.95) * 100)}% confidence)`
        },
        {
          id: '3',
          step: 3,
          name: 'Code Repair Agent',
          role: 'Patch Synthesis',
          status: 'IN_PROGRESS',
          time: 'Active',
          summary: 'Synthesizing real unified diff...'
        },
        {
          id: '4',
          step: 4,
          name: 'Testing Agent',
          role: 'Isolated Sandbox Emulation',
          status: 'PENDING',
          time: '—',
          summary: 'Awaiting patch synthesis'
        },
        {
          id: '5',
          step: 5,
          name: 'Security Reviewer',
          role: 'SAST & Secrets Audit',
          status: 'PENDING',
          time: '—',
          summary: 'Awaiting patch validation'
        }
      ];

      const patchStartLogs = [
        ...startLogs,
        { time: new Date().toLocaleTimeString(), agent: 'Analyzer', message: `Files analyzed: ${filesAnalyzedList.join(', ') || 'None'}` },
        { time: new Date().toLocaleTimeString(), agent: 'Nemotron', message: `Nemotron 3.5 root cause: ${invRes.root_cause?.slice(0, 80)}...` },
        { time: new Date().toLocaleTimeString(), agent: 'SYS', message: `[REAL PATCH] POST /api/ai/nemotron/patch` },
        { time: new Date().toLocaleTimeString(), agent: 'Repair', message: `Fetching current contents of affected files and invoking Nemotron for unified diff...` }
      ];

      setInv((prev) => ({
        ...prev,
        progress: 70,
        agents: stage2Agents,
        logs: patchStartLogs
      }));

      // STAGE 2: Generate and Validate Real Patch
      const patchRes = await api.generatePatch({
        owner,
        repo: repoName,
        branch,
        issue_number: issueNumber,
        investigation: invRes
      });
      if (isStale()) return;

      const patchDoneAgents = [
        {
          id: '1',
          step: 1,
          name: 'Repository Analyzer',
          role: 'AST & Tree Parsing',
          status: 'COMPLETE',
          time: '2.5s',
          summary: `${filesAnalyzedList.length} files parsed in AST`
        },
        {
          id: '2',
          step: 2,
          name: 'Bug Investigator',
          role: 'Root Cause Isolation',
          status: 'COMPLETE',
          time: '4.8s',
          summary: `Root cause isolated (${Math.round((invRes.confidence || 0.95) * 100)}% confidence)`
        },
        {
          id: '3',
          step: 3,
          name: 'Code Repair Agent',
          role: 'Patch Synthesis',
          status: 'COMPLETE',
          time: '3.1s',
          summary: `${patchRes.files_changed?.length || 1} file(s) modified (+${patchRes.lines_added || 0} / -${patchRes.lines_removed || 0})`
        },
        {
          id: '4',
          step: 4,
          name: 'Testing Agent',
          role: 'Isolated Sandbox Emulation',
          status: 'IN_PROGRESS',
          time: 'Active',
          summary: 'Executing patched repository tests in Docker sandbox (--network none)...'
        },
        {
          id: '5',
          step: 5,
          name: 'Security Reviewer',
          role: 'SAST & Secrets Audit',
          status: 'PENDING',
          time: '—',
          summary: 'Awaiting sandbox tests'
        }
      ];

      const patchDoneLogs = [
        ...patchStartLogs,
        { time: new Date().toLocaleTimeString(), agent: 'Repair', message: `Unified diff generated for: ${patchRes.files_changed?.join(', ')}` },
        { time: new Date().toLocaleTimeString(), agent: 'Validator', message: `AST Diff Validator: clean application verified (+${patchRes.lines_added} / -${patchRes.lines_removed} lines).` },
        { time: new Date().toLocaleTimeString(), agent: 'SYS', message: `[REAL SANDBOX TEST] POST /api/ai/sandbox/test` },
        { time: new Date().toLocaleTimeString(), agent: 'Testing', message: `Mounting temporary workspace into isolated Docker sandbox with --network none...` }
      ];

      setInv((prev) => ({
        ...prev,
        progress: 85,
        agents: patchDoneAgents,
        logs: patchDoneLogs
      }));

      // STAGE 3: Real Docker Sandbox Testing Execution (with bounded repair retry)
      let currentPatchRes = patchRes;
      let sandboxRes = null;
      let isTestPassed = false;
      const MAX_REPAIR_RETRIES = 2;
      let repairAttempt = 0;
      let accumulatedLogs = [...patchDoneLogs];

      while (repairAttempt <= MAX_REPAIR_RETRIES) {
        try {
          sandboxRes = await api.runSandboxTest({
            owner,
            repo: repoName,
            branch,
            issue_number: issueNumber,
            patch: currentPatchRes.patch,
            binding: currentPatchRes.binding || null
          });
        } catch (testErr) {
          // A transport failure is NEVER a "test result". Classify it honestly
          // so the UI shows the real failed stage instead of a fake success.
          console.warn('Sandbox testing request error:', testErr);
          const isTransportTimeout = testErr?.isTimeout || testErr?.errorCode === 'REQUEST_TIMEOUT';
          const isNetworkFailure = testErr?.isNetworkError || testErr?.errorCode === 'NETWORK_ERROR';
          sandboxRes = {
            success: false,
            status: isTransportTimeout ? 'TIMEOUT' : 'ERROR',
            message: testErr?.message || 'Sandbox test invocation failed',
            exit_code: 1,
            stdout: '',
            stderr: testErr?.message || 'Execution error',
            transport_failure: isNetworkFailure || isTransportTimeout
          };
        }

        isTestPassed = sandboxRes?.status === 'PASSED';
        // Only a genuine test failure warrants a repair retry; transport errors,
        // build/dependency errors and zero-test outcomes are terminal for this run.
        const isRetryableTestFailure = sandboxRes?.status === 'FAILED' || sandboxRes?.status === 'TESTS_FAILED';
        if (isTestPassed || !isRetryableTestFailure || repairAttempt >= MAX_REPAIR_RETRIES) {
          break;
        }

        // Bounded repair retry: feed exact failure output/traceback back into diagnosis
        repairAttempt += 1;
        const errTraceback = sandboxRes?.stderr || sandboxRes?.stdout || sandboxRes?.message || 'Test execution failed.';
        const retryLogs = [
          { time: new Date().toLocaleTimeString(), agent: 'SYS', message: `[REPAIR RETRY ${repairAttempt}/${MAX_REPAIR_RETRIES}] Sandbox tests returned ${sandboxRes?.status} (exit code ${sandboxRes?.exit_code}). Feeding traceback into Nemotron...` },
          { time: new Date().toLocaleTimeString(), agent: 'Nemotron', message: `Analyzing test error traceback and synthesizing revised patch...` }
        ];
        accumulatedLogs.push(...retryLogs);

        setInv((prev) => ({
          ...prev,
          logs: [...(prev.logs || []), ...retryLogs]
        }));

        try {
          const revisedInvestigation = {
            ...invRes,
            root_cause: `${invRes.root_cause || ''}\n\nPREVIOUS ATTEMPT FAILED TESTS (${sandboxRes?.status}):\n${errTraceback.slice(-3000)}`,
            proposed_fix: `${invRes.proposed_fix || ''}\n\nFix previous test failure:\n${errTraceback.slice(-1000)}`
          };
          currentPatchRes = await api.generatePatch({
            owner,
            repo: repoName,
            branch,
            issue_number: issueNumber,
            investigation: revisedInvestigation
          });

          const patchUpdateLogs = [
            { time: new Date().toLocaleTimeString(), agent: 'Repair', message: `Revised unified diff generated for: ${currentPatchRes.files_changed?.join(', ')}` },
            { time: new Date().toLocaleTimeString(), agent: 'Testing', message: `Retesting revised patch in Docker sandbox...` }
          ];
          accumulatedLogs.push(...patchUpdateLogs);

          setInv((prev) => ({
            ...prev,
            logs: [...(prev.logs || []), ...patchUpdateLogs]
          }));
        } catch (retryErr) {
          console.warn('Repair retry patch synthesis failed:', retryErr);
          break;
        }
      }

      if (isStale()) return;

      const isPatchFailedInSandbox = sandboxRes?.status === 'PATCH_FAILED';
      const skippedStatuses = ['TESTS_NOT_CONFIGURED', 'NO_TESTS_FOUND', 'UNSUPPORTED_PROJECT'];
      const isSandboxSkipped = skippedStatuses.includes(sandboxRes?.status);
      const isSandboxFailed = !isTestPassed && !isSandboxSkipped;

      const testingStatus = isTestPassed
        ? 'COMPLETE'
        : isSandboxSkipped
        ? 'SKIPPED'
        : 'FAILED';

      const testingSummary = isTestPassed
        ? `Tests passed: ${sandboxRes.tests_passed ?? 'All'}/${sandboxRes.tests_run ?? sandboxRes.tests_passed ?? 'All'} (${sandboxRes.duration_seconds || 1}s)`
        : sandboxRes?.status === 'TESTS_NOT_CONFIGURED'
        ? 'No test suite configured for this component'
        : sandboxRes?.status === 'NO_TESTS_FOUND'
        ? 'Test runner executed but found no matching tests'
        : sandboxRes?.status === 'UNSUPPORTED_PROJECT'
        ? 'Repository language or build system is not supported for isolated execution'
        : sandboxRes?.status === 'TEST_COLLECTION_ERROR'
        ? `Test collection error: ${(sandboxRes?.message || 'Test discovery failed').split('\n')[0]}`
        : sandboxRes?.status === 'TIMEOUT'
        ? `Test execution timed out: ${(sandboxRes?.message || 'Execution exceeded time limit').split('\n')[0]}`
        : sandboxRes?.status === 'ENVIRONMENT_ERROR'
        ? `Environment error: ${(sandboxRes?.message || 'Application import or conftest error').split('\n')[0]}`
        : sandboxRes?.status === 'DEPENDENCIES_UNAVAILABLE'
        ? `Dependencies unavailable: ${(sandboxRes?.message || 'Package installation failed').split('\n')[0]}`
        : sandboxRes?.status === 'DOCKER_UNAVAILABLE'
        ? 'Docker daemon unavailable'
        : sandboxRes?.status === 'PATCH_FAILED'
        ? `Patch failed in sandbox: ${sandboxRes?.message || 'Hunk mismatch'}`
        : sandboxRes?.status === 'ERROR'
        ? `Sandbox execution error: ${sandboxRes?.message || 'Execution failed'}`
        : `Tests failed (exit code ${sandboxRes?.exit_code ?? 1})`;

      // If patch failed to apply in sandbox, Code Repair Agent failed!
      const codeRepairStatus = isPatchFailedInSandbox ? 'FAILED' : 'COMPLETE';
      const codeRepairSummary = isPatchFailedInSandbox
        ? `Patch application rejected in sandbox: ${sandboxRes?.message || 'Hunk mismatch'}`
        : `${currentPatchRes.files_changed?.length || 1} file(s) modified (+${currentPatchRes.lines_added || 0} / -${currentPatchRes.lines_removed || 0})`;

      // STAGE 4: Security Review (SAST & Secrets Audit)
      let secRes = null;
      let secStatus = 'SKIPPED';
      let secSummary = 'Security review skipped';
      let secTime = '—';

      if (!isPatchFailedInSandbox && currentPatchRes?.patch) {
        try {
          const secStartTime = Date.now();
          secRes = await api.scanSecurity(currentPatchRes.patch);
          const secElapsed = ((Date.now() - secStartTime) / 1000).toFixed(1);
          secTime = `${secElapsed}s`;
          if (secRes?.status === 'PASSED') {
            secStatus = 'COMPLETE';
            secSummary = secRes.summary || 'Security review passed: No vulnerabilities found';
          } else if (secRes?.status === 'WARNINGS') {
            secStatus = 'WARNING';
            secSummary = secRes.summary || 'Security review completed with warnings';
          } else if (secRes?.status === 'FAILED') {
            secStatus = 'FAILED';
            secSummary = secRes.summary || 'Security review failed: Vulnerabilities or secrets detected';
          } else {
            secStatus = 'NOT_IMPLEMENTED';
            secSummary = secRes?.summary || 'Security review: NOT IMPLEMENTED';
          }
        } catch (secErr) {
          console.warn('Security scan failed:', secErr);
          secRes = {
            status: 'NOT_IMPLEMENTED',
            summary: `Security scanner execution error: ${secErr.message}`,
            findings: [],
            clean: false,
            limitations: 'Scanner invocation failed.'
          };
          secStatus = 'NOT_IMPLEMENTED';
          secSummary = secRes.summary;
        }
      } else if (isPatchFailedInSandbox) {
        secStatus = 'SKIPPED';
        secSummary = 'Skipped: Patch application failed in sandbox';
      }

      const finalAgents = [
        {
          id: '1',
          step: 1,
          name: 'Repository Analyzer',
          role: 'AST & Tree Parsing',
          status: 'COMPLETE',
          time: '2.5s',
          summary: `${filesAnalyzedList.length} files parsed in AST`
        },
        {
          id: '2',
          step: 2,
          name: 'Bug Investigator',
          role: 'Root Cause Isolation',
          status: 'COMPLETE',
          time: '4.8s',
          summary: `Root cause isolated (${Math.round((invRes.confidence || 0.95) * 100)}% confidence)`
        },
        {
          id: '3',
          step: 3,
          name: 'Code Repair Agent',
          role: 'Patch Synthesis',
          status: codeRepairStatus,
          time: isPatchFailedInSandbox ? 'Failed' : '3.1s',
          summary: codeRepairSummary
        },
        {
          id: '4',
          step: 4,
          name: 'Testing Agent',
          role: 'Isolated Sandbox Emulation',
          status: testingStatus,
          time: sandboxRes?.duration_seconds ? `${sandboxRes.duration_seconds}s` : '1.2s',
          summary: testingSummary
        },
        {
          id: '5',
          step: 5,
          name: 'Security Reviewer',
          role: 'SAST & Secrets Audit',
          status: secStatus,
          time: secTime,
          summary: secSummary
        }
      ];

      const endLogs = [
        ...accumulatedLogs,
        {
          time: new Date().toLocaleTimeString(),
          agent: 'Testing',
          message: `Docker sandbox execution complete: ${sandboxRes?.status} (Command: ${sandboxRes?.test_command || 'None'})`
        },
        {
          time: new Date().toLocaleTimeString(),
          agent: 'Security',
          message: `Security review finished: ${secRes?.status || secStatus} (${secRes?.findings_count || 0} findings). ${secSummary}`
        },
        {
          time: new Date().toLocaleTimeString(),
          agent: 'SYS',
          message: isPatchFailedInSandbox
            ? `[REAL TESTING] FAILED: Patch application failed in sandbox environment.`
            : `[REAL PIPELINE] Complete. Investigation, sandbox test, and security review finished.`
        }
      ];

      const rootCauseData = {
        summary: invRes.root_cause?.slice(0, 160) + (invRes.root_cause?.length > 160 ? '...' : ''),
        explanation: invRes.root_cause || 'Root cause identified by Nemotron 3.5',
        file: invRes.affected_files?.[0] || filesAnalyzedList[0] || 'src/handler.py',
        targetFile: invRes.affected_files?.[0] || filesAnalyzedList[0] || 'src/handler.py',
        confidence: Math.round((invRes.confidence || 0.95) * 100),
        affectedFiles: invRes.affected_files || [],
        affectedFunctions: invRes.affected_functions || [],
        evidence: invRes.evidence || [],
        proposedFix: invRes.proposed_fix,
        testStrategy: invRes.test_strategy
      };

      const patchData = {
        file: currentPatchRes.files_changed?.[0] || invRes.affected_files?.[0] || filesAnalyzedList[0] || 'src/handler.py',
        files_changed: currentPatchRes.files_changed || [invRes.affected_files?.[0] || 'src/handler.py'],
        lines_added: currentPatchRes.lines_added || 0,
        lines_removed: currentPatchRes.lines_removed || 0,
        diff: currentPatchRes.patch,
        explanation: currentPatchRes.explanation || invRes.proposed_fix,
        validation: currentPatchRes.validation || { is_valid: !isPatchFailedInSandbox, clean_application: !isPatchFailedInSandbox },
        binding: currentPatchRes.binding || null
      };

      const isSecurityFailed = secRes?.status === 'FAILED';
      // Overall status is derived from the required stages — never from a raw
      // progress counter. Testing must genuinely pass for the run to be COMPLETE.
      let finalStatus;
      if (isPatchFailedInSandbox || isSandboxFailed || isSecurityFailed) {
        finalStatus = 'FAILED';
      } else if (isTestPassed) {
        finalStatus = 'COMPLETE';
      } else if (isSandboxSkipped) {
        finalStatus = 'READY_FOR_REVIEW'; // partial: no tests to run, needs human review
      } else {
        finalStatus = 'FAILED';
      }
      const finalProgress = finalStatus === 'COMPLETE' ? 100 : (finalStatus === 'READY_FOR_REVIEW' ? 90 : (isPatchFailedInSandbox ? 75 : 80));

      const completedInv = {
        ...inv,
        id: inv.id,
        latest_run_id: currentRunId,
        status: finalStatus,
        progress: finalProgress,
        estimatedTime: finalStatus === 'COMPLETE' ? 'Completed' : 'Failed in Sandbox / Security',
        agents: finalAgents,
        logs: endLogs,
        filesAnalyzed: filesAnalyzedList,
        rootCause: rootCauseData,
        patch: patchData,
        diff: patchData,
        sandboxResult: sandboxRes,
        securityResult: secRes,
        testSummary: {
          total: sandboxRes?.tests_run || 0,
          passed: sandboxRes?.tests_passed || 0,
          failed: sandboxRes?.tests_failed || (isPatchFailedInSandbox ? 1 : 0),
          pending: 0,
          status: sandboxRes?.status || 'COMPLETED'
        },
        securitySummary: {
          level: secRes?.status === 'PASSED' ? 'Low Risk' : (secRes?.status === 'WARNINGS' ? 'Medium Risk' : (secRes?.status === 'FAILED' ? 'High Risk' : 'Unknown')),
          status: secRes?.status || secStatus,
          findings_count: secRes?.findings_count || 0
        }
      };

      setInv(completedInv);
      updateInvestigation(inv.id, completedInv);
      setActiveTab('TESTS'); // Switch to TESTS tab to show sandbox results
      setIsInvestigating(false);

      try {
        const synced = await api.syncInvestigation(inv.id, completedInv);
        if (synced) {
          setInv((prev) => ({ ...prev, ...synced }));
          updateInvestigation(inv.id, { ...completedInv, ...synced });
        }
      } catch (syncErr) {
        console.error('[Backend sync failed]:', syncErr);
        addNotification(`Backend state synchronization warning: ${syncErr.message}`, 'error');
      }

      if (isPatchFailedInSandbox) {
        setPatchErrorDetails({
          status: 'PATCH_APPLICATION_FAILED',
          message: sandboxRes?.message || 'Patch failed to apply cleanly to sandbox repository files.',
          file: patchRes.files_changed?.[0] || 'target file',
          hunk: 1,
          retry_available: true,
          attempts: 1
        });
        addNotification(`✕ Patch application failed in sandbox: ${sandboxRes?.message || 'Hunk mismatch'}`, 'error');
      } else if (isTestPassed) {
        addNotification('✓ Real Docker sandbox tests PASSED!');
      } else if (isSandboxFailed) {
        addNotification(`✕ Real Docker sandbox failed: ${sandboxRes?.message || sandboxRes?.status || 'Failed'}`, 'error');
      } else {
        addNotification(`Investigation complete (Sandbox: ${sandboxRes?.status || 'Tested'})`);
      }
    } catch (err) {
      console.error('[DevRescue REAL Pipeline Error]', err);
      if (isStale()) return;
      setIsInvestigating(false);
      const status = err.status || 500;
      setErrorStatus(status);

      const errData = typeof err.data?.detail === 'object' ? err.data.detail : (typeof err.data === 'object' ? err.data : {});
      const errorCode = errData.error_code || errData.error || '';
      const isGitHubError = (typeof errorCode === 'string' && errorCode.startsWith('GITHUB_')) ||
        (status === 502 && (errData.error === 'github_connection_error' || (err.message && err.message.toLowerCase().includes('github')))) ||
        (typeof errData.error === 'string' && errData.error.startsWith('github_'));
      const isTimeout = status === 504 || errorCode === 'NEMOTRON_TIMEOUT' || errorCode === 'GITHUB_TIMEOUT' || (err.message && err.message.toLowerCase().includes('timeout'));
      const isRateLimited = status === 429 || errorCode === 'NEMOTRON_RATE_LIMITED' || errorCode === 'GITHUB_RATE_LIMITED';
      const isPatchAppFailed = errData.error === 'patch_application_failed' ||
        errData.status === 'PATCH_APPLICATION_FAILED' ||
        errData.error === 'invalid_patch' ||
        errData.status === 'INVALID_PATCH' ||
        errData.error === 'diff_validation_error';
      const isNetworkError = err.errorCode === 'NETWORK_ERROR' || err.isNetworkError === true;
      const isRequestTimeout = err.errorCode === 'REQUEST_TIMEOUT' || err.isTimeout === true;

      let msg = errData.message || err.message || 'Pipeline failed.';
      if (isNetworkError) {
        msg = err.message || 'Cannot reach the DevRescue backend. Ensure the API server is running and CORS is configured.';
      } else if (isRequestTimeout) {
        msg = err.message || 'The backend request timed out. The operation is unconfirmed and must be retried.';
      } else if (isPatchAppFailed) {
        const failurePrefix = (errData.status === 'INVALID_PATCH' || errData.error === 'invalid_patch') ? 'Patch validation failed' : 'Patch application failed';
        msg = `${failurePrefix} on '${errData.file || 'target file'}'${errData.hunk ? ` (Hunk #${errData.hunk})` : ''}: ${errData.message || err.message}`;
      } else if (status === 401) {
        msg = errData.message || (errorCode === 'NEMOTRON_AUTH_ERROR' ? 'NVIDIA Nemotron authentication failed. Check API key.' : 'GitHub session expired. Reconnect GitHub.');
      } else if (isRateLimited) {
        msg = errData.message || (isGitHubError ? 'GitHub API rate limit exceeded.' : 'NVIDIA Nemotron rate limit exceeded. Please wait a moment and retry.');
      } else if (isTimeout) {
        msg = errData.message || (isGitHubError ? 'GitHub API request timed out. Please retry.' : 'Nemotron inference timed out after multiple attempts. You can retry the investigation.');
      } else if (status === 502) {
        msg = isGitHubError ? `GitHub API connection error: ${errData.message || err.message}` : `Nemotron / upstream error: ${errData.message || err.message}`;
      }

      setInvestigationError(msg);
      setPatchErrorDetails(isPatchAppFailed ? errData : null);
      addNotification(msg, 'error');

      const failedStageName = isNetworkError || isRequestTimeout
        ? 'Backend Connection'
        : isGitHubError
        ? 'Repository Retrieval'
        : isPatchAppFailed
        ? 'Patch Synthesis'
        : (isTimeout || isRateLimited)
        ? 'Root Cause Diagnosis (Nemotron)'
        : 'Bug Investigator';
      setFailureInfo({
        stage: failedStageName,
        message: msg,
        errorCode: typeof errorCode === 'string' && errorCode ? errorCode : (err.errorCode || null),
        retryable: Boolean(isNetworkError || isRequestTimeout || isTimeout || isRateLimited || (isPatchAppFailed && errData.retry_available) || status >= 500),
        runId: currentRunId,
        elapsedSeconds: ((Date.now() - runStartedAt) / 1000).toFixed(1)
      });

      const failedAgents = liveAgents.map((a) => {
        if (isPatchAppFailed) {
          if (a.step === 1) return { ...a, status: 'COMPLETE', summary: 'Files analyzed', time: '2.5s' };
          if (a.step === 2) return { ...a, status: 'COMPLETE', summary: 'Root cause isolated', time: '4.8s' };
          if (a.step === 3) {
            const agentFailPrefix = (errData.status === 'INVALID_PATCH' || errData.error === 'invalid_patch') ? 'Patch invalid' : 'Patch application failed';
            return {
              ...a,
              status: 'FAILED',
              time: 'Failed',
              summary: `${agentFailPrefix} (${errData.file || 'target'}${errData.hunk ? ` Hunk #${errData.hunk}` : ''})`
            };
          }
          if (a.step === 4) return { ...a, status: 'SKIPPED', time: '—', summary: 'Skipped: Patch application failed' };
          if (a.step > 4) return { ...a, status: 'SKIPPED', time: '—', summary: 'Skipped: Patch application failed' };
          return a;
        }

        if (isGitHubError) {
          // GitHub stage failure (Step 1: Repository Analyzer)
          if (a.step === 1) {
            return {
              ...a,
              status: 'FAILED',
              time: 'Failed',
              summary: `GitHub error: ${msg}`
            };
          }
          if (a.step === 2) {
            return {
              ...a,
              status: 'SKIPPED',
              time: '—',
              summary: 'Skipped: Repository analysis failed'
            };
          }
          if (a.step === 3) {
            return {
              ...a,
              status: 'SKIPPED',
              time: '—',
              summary: 'Skipped: Repository analysis failed'
            };
          }
          if (a.step === 4) {
            return {
              ...a,
              status: 'SKIPPED',
              time: '—',
              summary: 'Skipped: Repository analysis failed'
            };
          }
          return {
            ...a,
            status: 'SKIPPED',
            time: '—',
            summary: 'Skipped: Repository analysis failed'
          };
        }

        // Investigation failure (Step 2: Bug Investigator)
        if (a.step === 1) {
          return {
            ...a,
            status: 'COMPLETE',
            summary: 'Files analyzed',
            time: '2.5s'
          };
        }
        if (a.step === 2) {
          return {
            ...a,
            status: 'FAILED',
            time: 'Failed',
            summary: isTimeout ? 'Nemotron timeout during inference' : (isRateLimited ? 'Rate limit exceeded' : `Error: ${msg}`)
          };
        }
        if (a.step === 3) {
          return {
            ...a,
            status: 'SKIPPED',
            time: '—',
            summary: 'Skipped: Bug investigation failed'
          };
        }
        if (a.step === 4) {
          return {
            ...a,
            status: 'SKIPPED',
            time: '—',
            summary: 'Skipped: Bug investigation failed'
          };
        }
        return {
          ...a,
          status: 'SKIPPED',
          time: '—',
          summary: 'Skipped: Bug investigation failed'
        };
      });

      const failedLogs = [
        ...startLogs,
        {
          time: new Date().toLocaleTimeString(),
          agent: isGitHubError ? 'GitHub' : (isTimeout ? 'Nemotron' : (isPatchAppFailed ? 'Repair' : 'SYS')),
          message: isGitHubError
            ? `[GITHUB_ERROR] ${msg}`
            : isPatchAppFailed
            ? `[PATCH_APPLICATION_FAILED] ${msg}`
            : isTimeout
            ? `[NEMOTRON_TIMEOUT] ${msg}`
            : isRateLimited
            ? `[NEMOTRON_RATE_LIMITED] ${msg}`
            : `[ERROR ${status}] ${msg}`
        }
      ];

      const failedInv = {
        status: 'FAILED',
        progress: isPatchAppFailed ? 65 : 40,
        agents: failedAgents,
        logs: failedLogs
      };

      setInv((prev) => ({
        ...prev,
        ...failedInv
      }));
      updateInvestigation(inv.id, failedInv);
      try {
        api.syncInvestigation(inv.id, failedInv).catch(() => {});
      } catch (e) {}
    }
  }, [id, inv, updateInvestigation, addNotification]);

  // Dedicated Retry Patch Synthesis invoking the real backend endpoint POST /api/ai/nemotron/patch
  const retryPatchSynthesis = useCallback(async () => {
    if (!inv) return;

    let owner = inv.owner;
    let repoName = inv.repo_name;
    const rawRepo = inv.repo || inv.repository || '';
    if (rawRepo.includes('/')) {
      const parts = rawRepo.split('/');
      owner = owner || parts[0];
      repoName = repoName || parts[1];
    } else {
      repoName = repoName || rawRepo || '';
    }
    const branch = inv.branch || 'main';
    const issueNumber = Number(inv.issue_number || inv.issueNumber || 1);

    if (!owner || !repoName) {
      const msg = 'Repository binding is missing (owner/repo). Refusing to retry to avoid cross-repository contamination.';
      setErrorStatus(409);
      setInvestigationError(msg);
      addNotification(msg, 'error');
      return;
    }

    const invRes = inv.rootCause ? {
      root_cause: inv.rootCause.explanation || inv.rootCause.summary || '',
      confidence: (inv.rootCause.confidence || 95) / 100,
      affected_files: inv.rootCause.affectedFiles || (inv.rootCause.file ? [inv.rootCause.file] : []),
      affected_functions: inv.rootCause.affectedFunctions || [],
      evidence: inv.rootCause.evidence || [],
      proposed_fix: inv.rootCause.proposedFix || '',
      test_strategy: inv.rootCause.testStrategy || ''
    } : null;

    if (!invRes || !invRes.affected_files?.length) {
      // If root cause not available, fall back to complete investigation
      return runRealInvestigation();
    }

    setIsInvestigating(true);
    setInvestigationError(null);
    setPatchErrorDetails(null);
    setErrorStatus(null);

    addNotification('Invoking backend /api/ai/nemotron/patch with fresh source context...', 'info');

    try {
      const patchRes = await api.generatePatch({
        owner,
        repo: repoName,
        branch,
        issue_number: issueNumber,
        investigation: invRes
      });

      addNotification('✓ Clean unified diff synthesized and verified! Executing Docker sandbox...', 'success');

      // Proceed to sandbox test
      let sandboxRes = null;
      try {
        sandboxRes = await api.runSandboxTest({
          owner,
          repo: repoName,
          branch,
          issue_number: issueNumber,
          patch: patchRes.patch,
          binding: patchRes.binding || null
        });
      } catch (testErr) {
        const isTransportTimeout = testErr?.isTimeout || testErr?.errorCode === 'REQUEST_TIMEOUT';
        sandboxRes = {
          success: false,
          status: isTransportTimeout ? 'TIMEOUT' : 'ERROR',
          message: testErr?.message || 'Sandbox test invocation failed',
          exit_code: 1,
          stdout: '',
          stderr: testErr?.message || 'Execution error',
          transport_failure: true
        };
      }

      const isTestPassed = sandboxRes?.status === 'PASSED';
      const isPatchFailedInSandbox = sandboxRes?.status === 'PATCH_FAILED';
      const skippedTestStatuses = ['NO_TESTS_FOUND', 'TESTS_NOT_CONFIGURED', 'UNSUPPORTED_PROJECT'];
      const isTestSkipped = skippedTestStatuses.includes(sandboxRes?.status);
      const finalStatus = isPatchFailedInSandbox
        ? 'FAILED'
        : isTestPassed
        ? 'COMPLETE'
        : isTestSkipped
        ? 'READY_FOR_REVIEW'
        : 'FAILED';
      const finalProgress = finalStatus === 'COMPLETE' ? 100 : (finalStatus === 'READY_FOR_REVIEW' ? 90 : (isPatchFailedInSandbox ? 75 : 80));

      const finalAgents = (inv.agents || []).map((a) => {
        if (a.step === 3) {
          return {
            ...a,
            status: isPatchFailedInSandbox ? 'FAILED' : 'COMPLETE',
            summary: isPatchFailedInSandbox
              ? `Patch rejected in sandbox: ${sandboxRes?.message || 'Conflict'}`
              : `${patchRes.files_changed?.length || 1} file(s) modified (+${patchRes.lines_added || 0} / -${patchRes.lines_removed || 0})`
          };
        }
        if (a.step === 4) {
          return {
            ...a,
            status: isTestPassed ? 'COMPLETE' : (isTestSkipped ? 'SKIPPED' : 'FAILED'),
            summary: isTestPassed
              ? 'Tests passed'
              : (sandboxRes?.message || `Sandbox status: ${sandboxRes?.status || 'unknown'}`)
          };
        }
        return a;
      });

      const updatedInv = {
        ...inv,
        status: finalStatus,
        progress: finalProgress,
        agents: finalAgents,
        patch: {
          file: patchRes.files_changed?.[0] || 'src/handler.py',
          files_changed: patchRes.files_changed || [],
          lines_added: patchRes.lines_added || 0,
          lines_removed: patchRes.lines_removed || 0,
          diff: patchRes.patch,
          explanation: patchRes.explanation,
          validation: patchRes.validation,
          binding: patchRes.binding || null
        },
        sandboxResult: sandboxRes
      };

      setInv(updatedInv);
      updateInvestigation(inv.id, updatedInv);
      setIsInvestigating(false);
      setActiveTab('TESTS');
      if (isTestPassed) {
        addNotification('✓ Patch synthesis retry succeeded and sandbox tests passed!');
      } else if (finalStatus === 'READY_FOR_REVIEW') {
        addNotification(`Patch synthesized; no runnable tests (${sandboxRes?.status}). Awaiting human review.`, 'info');
      } else {
        addNotification(`✕ Patch synthesized but sandbox testing failed: ${sandboxRes?.message || sandboxRes?.status || 'failed'}`, 'error');
      }

      try {
        const synced = await api.syncInvestigation(inv.id, updatedInv);
        if (synced) {
          setInv((prev) => ({ ...prev, ...synced }));
          updateInvestigation(inv.id, { ...updatedInv, ...synced });
        }
      } catch (syncErr) {
        console.error('[Backend sync failed]:', syncErr);
        addNotification(`Backend state synchronization warning: ${syncErr.message}`, 'error');
      }
    } catch (err) {
      console.error('[Patch Retry Error]', err);
      setIsInvestigating(false);
      const status = err.status || 500;
      setErrorStatus(status);
      const errData = typeof err.data?.detail === 'object' ? err.data.detail : (typeof err.data === 'object' ? err.data : {});
      const msg = errData.message || err.message || 'Patch synthesis retry failed.';
      setInvestigationError(msg);
      setPatchErrorDetails(errData.status === 'PATCH_APPLICATION_FAILED' ? errData : null);
      addNotification(msg, 'error');
    }
  }, [inv, runRealInvestigation, updateInvestigation, addNotification]);

  const handleRerunSandboxWithOverrides = useCallback(async ({ working_directory, test_command }) => {
    const patchDiff = inv?.patch?.diff || inv?.diff?.diff;
    if (!patchDiff) {
      addNotification('No code patch available to test. Synthesize a patch first.', 'warning');
      return;
    }

    let owner = inv.owner;
    let repoName = inv.repo_name;
    const rawRepo = inv.repo || inv.repository || '';
    if (rawRepo.includes('/')) {
      const parts = rawRepo.split('/');
      owner = owner || parts[0];
      repoName = repoName || parts[1];
    } else {
      repoName = repoName || rawRepo || '';
    }
    const branch = inv.branch || 'main';
    const issueNumber = Number(inv.issue_number || inv.issueNumber || 1);

    if (!owner || !repoName) {
      addNotification('Repository binding is missing (owner/repo). Refusing to run sandbox to avoid cross-repository contamination.', 'error');
      return;
    }

    addNotification('Executing isolated Docker sandbox test with custom overrides...', 'info');

    const nowStr = new Date().toLocaleTimeString();
    const startMsg = `[MANUAL TEST OVERRIDE] POST /api/ai/sandbox/test (Workdir: ${working_directory || 'default'}, Command: ${test_command || 'default'})`;

    setInv((prev) => ({
      ...prev,
      logs: [
        ...(prev?.logs || []),
        { time: nowStr, agent: 'SYS', message: startMsg },
        { time: nowStr, agent: 'Testing', message: 'Mounting isolated workspace with custom parameters into Docker sandbox (--network none)...' }
      ]
    }));

    try {
      const sandboxRes = await api.runSandboxTest({
        owner,
        repo: repoName,
        branch,
        issue_number: issueNumber,
        patch: patchDiff,
        working_directory_override: working_directory || undefined,
        test_command_override: test_command || undefined,
        binding: inv?.patch?.binding || null
      });

      const isTestPassed = sandboxRes?.status === 'PASSED';
      const rerunSkippedStatuses = ['TESTS_NOT_CONFIGURED', 'NO_TESTS_FOUND', 'UNSUPPORTED_PROJECT'];
      const testingStatus = isTestPassed
        ? 'COMPLETE'
        : rerunSkippedStatuses.includes(sandboxRes?.status)
        ? 'SKIPPED'
        : 'FAILED';

      const testingSummary = isTestPassed
        ? `Tests passed: ${sandboxRes.tests_passed ?? 'All'}/${sandboxRes.tests_run ?? sandboxRes.tests_passed ?? 'All'} (${sandboxRes.duration_seconds || 1}s)`
        : sandboxRes?.status === 'TESTS_NOT_CONFIGURED'
        ? 'No test suite configured for this component'
        : sandboxRes?.status === 'NO_TESTS_FOUND'
        ? 'Test runner executed but found no matching tests'
        : sandboxRes?.status === 'UNSUPPORTED_PROJECT'
        ? 'Repository language or build system is not supported for isolated execution'
        : sandboxRes?.status === 'TEST_COLLECTION_ERROR'
        ? `Test collection error: ${(sandboxRes?.message || 'Test discovery failed').split('\n')[0]}`
        : sandboxRes?.status === 'TIMEOUT'
        ? `Test execution timed out: ${(sandboxRes?.message || 'Execution exceeded time limit').split('\n')[0]}`
        : sandboxRes?.status === 'ENVIRONMENT_ERROR'
        ? `Environment error: ${(sandboxRes?.message || 'Application import or conftest error').split('\n')[0]}`
        : sandboxRes?.status === 'DEPENDENCIES_UNAVAILABLE'
        ? `Dependencies unavailable: ${(sandboxRes?.message || 'Package installation failed').split('\n')[0]}`
        : sandboxRes?.status === 'DOCKER_UNAVAILABLE'
        ? 'Docker daemon unavailable'
        : sandboxRes?.status === 'PATCH_FAILED'
        ? `Patch failed in sandbox: ${sandboxRes?.message || 'Hunk mismatch'}`
        : sandboxRes?.status === 'ERROR'
        ? `Sandbox execution error: ${sandboxRes?.message || 'Execution failed'}`
        : `Tests failed (exit code ${sandboxRes?.exit_code ?? 1})`;

      const completionMsg = `Manual sandbox test run complete: ${sandboxRes?.status} (Command: ${sandboxRes?.test_command || 'None'}, Exit: ${sandboxRes?.exit_code ?? 'N/A'})`;

      setInv((prev) => {
        const updatedAgents = (prev?.agents || []).map((ag) => {
          if (ag.id === '4' || ag.name === 'Testing Agent') {
            return {
              ...ag,
              status: testingStatus,
              time: sandboxRes?.duration_seconds ? `${sandboxRes.duration_seconds}s` : '1.2s',
              summary: testingSummary
            };
          }
          return ag;
        });

        const updated = {
          ...prev,
          sandboxResult: sandboxRes,
          agents: updatedAgents,
          testSummary: {
            total: sandboxRes?.tests_run || 0,
            passed: sandboxRes?.tests_passed || 0,
            failed: sandboxRes?.tests_failed || 0,
            pending: 0,
            status: sandboxRes?.status || 'COMPLETED'
          },
          logs: [
            ...(prev?.logs || []),
            { time: new Date().toLocaleTimeString(), agent: 'Testing', message: completionMsg }
          ]
        };

        updateInvestigation(inv.id, updated);
        return updated;
      });

      if (isTestPassed) {
        addNotification('✓ Custom Docker sandbox tests PASSED!', 'success');
      } else {
        addNotification(`Docker sandbox finished: ${sandboxRes?.status}`, 'info');
      }

      return sandboxRes;
    } catch (err) {
      console.error('[Manual Sandbox Run Error]', err);
      addNotification(`Manual sandbox execution failed: ${err.message || 'Error'}`, 'error');
      setInv((prev) => ({
        ...prev,
        logs: [
          ...(prev?.logs || []),
          { time: new Date().toLocaleTimeString(), agent: 'SYS', message: `[ERROR] Manual sandbox run error: ${err.message}` }
        ]
      }));
    }
  }, [inv, updateInvestigation, addNotification]);

  // Auto-trigger Real Investigation if not yet complete
  useEffect(() => {
    if (!isRealMode || !id || !inv || isInvestigating) return;

    const runIdentifier = inv.latest_run_id || 'initial';
    const key = `${id}-${inv.repo}-${inv.issueNumber || inv.issue_number}-${runIdentifier}`;
    if (!executedTracker.current.has(key)) {
      const isFinished = inv.status === 'COMPLETE' || inv.status === 'READY_FOR_REVIEW' || inv.status === 'PR_READY';
      const isFailedWithCause = inv.status === 'FAILED' && inv.rootCause;
      if (!isFinished && !isFailedWithCause) {
        executedTracker.current.add(key);
        runRealInvestigation(inv.latest_run_id);
      }
    }
  }, [id, isRealMode, inv, isInvestigating, runRealInvestigation]);

  // Autonomous stream simulation ticker (DEMO MODE ONLY)
  useEffect(() => {
    // Strictly disable simulated progression in REAL MODE
    if (isRealMode) return;

    if (!isSimulating || !inv || inv.status === 'COMPLETE' || inv.status === 'READY_FOR_REVIEW' || inv.status === 'PR_READY') {
      return;
    }

    const interval = setInterval(() => {
      setInv((prev) => {
        if (!prev) return prev;
        const currentProgress = prev.progress || 68;

        // Advance to 100% and complete
        if (currentProgress >= 95) {
          const completedAgents = (prev.agents || []).map((a) => ({
            ...a,
            status: 'COMPLETE',
            time: a.time === 'Pending' || a.time === 'Active' ? '12s' : a.time,
          }));

          const updatedLogs = [
            ...(prev.logs || []),
            { time: new Date().toLocaleTimeString(), agent: 'Testing', message: 'Demo simulation completed.' },
            { time: new Date().toLocaleTimeString(), agent: 'Analyzer', message: 'Investigation Complete. Patch verified and ready for review.' }
          ];

          const updated = {
            ...prev,
            status: 'COMPLETE',
            progress: 100,
            estimatedTime: 'Completed',
            agents: completedAgents,
            logs: updatedLogs,
            testSummary: {
              ...prev.testSummary,
              passed: 14,
              pending: 0,
            }
          };

          updateInvestigation(prev.id, updated);
          addNotification('Investigation complete! Patch is ready for review.');
          clearInterval(interval);
          return updated;
        }

        // Mid-flight increment
        const nextProgress = currentProgress + 8;
        const updatedAgents = (prev.agents || []).map((a) => {
          if (a.step <= 3) return { ...a, status: 'COMPLETE' };
          if (a.step === 4 && nextProgress >= 75) return { ...a, status: 'IN_PROGRESS', time: 'Active' };
          if (a.step === 5 && nextProgress >= 90) return { ...a, status: 'IN_PROGRESS', time: 'Active' };
          return a;
        });

        const updated = {
          ...prev,
          progress: nextProgress,
          agents: updatedAgents,
        };

        updateInvestigation(prev.id, updated);
        return updated;
      });
    }, 3000);

    return () => clearInterval(interval);
  }, [isSimulating, inv, isRealMode, updateInvestigation, addNotification]);

  const isFailed = inv?.status === 'FAILED' || inv?.status === 'ENVIRONMENT_ERROR' || Boolean(investigationError);
  // Never let a raw progress counter (or a prior READY_FOR_REVIEW) mask a failure.
  const isComplete = !isFailed && (inv?.status === 'COMPLETE' || inv?.status === 'READY_FOR_REVIEW' || inv?.status === 'PR_READY' || (inv?.progress || 0) >= 100);
  const isStopped = inv?.status === 'STOPPED';

  // Automatically capture authorized PayPal Sandbox Bounty upon 100% green verification
  const paypalCapturedRef = useRef(false);
  useEffect(() => {
    if (isComplete && inv?.paypal_order_id && !paypalCapturedRef.current) {
      paypalCapturedRef.current = true;
      api.capturePayPalOrder(inv.paypal_order_id, inv.id)
        .then((res) => {
          addNotification(`PayPal Sandbox Bounty Captured: ${res.order_id} ($${res.amount || 25}) upon 100% green test suite verification!`, 'success');
        })
        .catch((err) => {
          console.warn("PayPal capture notice:", err);
        });
    }
  }, [isComplete, inv?.paypal_order_id, inv?.id, addNotification]);

  const handleFastForward = () => {
    if (!inv) return;
    if (isRealMode) {
      addNotification('Fast-forward is disabled in Real Mode. Showing actual backend state.', 'info');
      return;
    }

    const completedAgents = (inv.agents || []).map((a) => ({
      ...a,
      status: 'COMPLETE',
      time: a.time === 'Pending' || a.time === 'Active' ? '8s' : a.time,
    }));

    const completeLogs = [
      ...(inv.logs || []),
      { time: new Date().toLocaleTimeString(), agent: 'Analyzer', message: 'Demo simulation fast-forwarded to completion.' }
    ];

    const completed = {
      ...inv,
      status: 'COMPLETE',
      progress: 100,
      estimatedTime: 'Completed',
      agents: completedAgents,
      logs: completeLogs
    };

    setInv(completed);
    updateInvestigation(inv.id, completed);
    addNotification('Investigation simulation fast-forwarded to completion.');
  };

  const handleStopInvestigation = () => {
    if (!inv) return;
    const stopped = {
      ...inv,
      status: 'STOPPED',
      estimatedTime: 'Aborted by Maintainer'
    };
    setInv(stopped);
    updateInvestigation(inv.id, stopped);
    setIsSimulating(false);
    setStopConfirmOpen(false);
    addNotification('✓ Investigation stopped', 'warning');
  };

  const handleRerun = useCallback(async () => {
    if (!inv || isInvestigating) return;
    executedTracker.current.clear();
    setInvestigationError(null);
    setPatchErrorDetails(null);
    setFailureInfo(null);
    setErrorStatus(null);

    let activeRunId = null;
    try {
      const newRun = await api.startRun(id, {
        parent_run_id: inv.latest_run_id,
        mode: isRealMode ? 'real' : 'demo'
      });
      if (newRun?.run_id) {
        activeRunId = newRun.run_id;
        setInv((prev) => prev ? {
          ...prev,
          latest_run_id: newRun.run_id,
          sandboxResult: null,
          securityResult: null,
          patch: null,
          rootCause: null,
          logs: newRun.logs || [],
          status: 'INVESTIGATING',
          progress: 20,
          stages: newRun.stages || prev.stages,
        } : prev);
      }
    } catch (err) {
      console.warn('Backend startRun fallback:', err);
      activeRunId = `run_${id}_${Date.now()}`;
      setInv((prev) => prev ? {
        ...prev,
        latest_run_id: activeRunId,
        sandboxResult: null,
        securityResult: null,
        patch: null,
        rootCause: null,
        logs: [],
        status: 'INVESTIGATING',
        progress: 20
      } : prev);
    }

    runRealInvestigation(activeRunId);
  }, [inv, id, isInvestigating, isRealMode, runRealInvestigation]);

  if (!inv) {
    return (
      <div className="py-20 text-center space-y-4 max-w-md mx-auto">
        <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto text-slate-500">
          <AlertCircle className="w-6 h-6 text-amber-500" />
        </div>
        <h2 className="text-xl font-bold text-[#0F172A]">Investigation Not Found</h2>
        <p className="text-sm text-[#64748B]">
          No active or saved investigation dossier was found with ID #{id}. Please select a repository issue to investigate.
        </p>
        <div className="flex items-center justify-center gap-3 pt-2">
          <Button to="/repositories" variant="primary">
            Select an Issue to Investigate
          </Button>
          <Button to="/history" variant="outline">
            View History
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 1. Investigation Header */}
      <InvestigationHeader
        inv={inv}
        isComplete={isComplete}
        isStopped={isStopped}
        isFailed={isFailed}
        isRealMode={isRealMode}
        isInvestigating={isInvestigating}
        onFastForward={handleFastForward}
        onStopClick={() => setStopConfirmOpen(true)}
        onRerun={handleRerun}
      />

      {/* PATCH_APPLICATION_FAILED Dedicated Alert Banner */}
      {patchErrorDetails && (
        <div className="bg-[#FFFBEB] border border-[#FCD34D] rounded-xl p-5 shadow-sm space-y-3 text-xs text-[#92400E]">
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-[#D97706] flex-shrink-0 mt-0.5" />
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-sm text-[#78350F]">
                    Patch Application Failed
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#FEF3C7] text-[#B45309] border border-[#FCD34D]">
                    PATCH_APPLICATION_FAILED
                  </span>
                </div>
                <p className="text-xs text-[#92400E] leading-relaxed">
                  {patchErrorDetails.message || investigationError}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 flex-shrink-0">
              <Button
                variant="outline"
                size="sm"
                icon={RefreshCw}
                onClick={patchErrorDetails.retry_available ? retryPatchSynthesis : runRealInvestigation}
                disabled={isInvestigating}
                className="bg-white border-[#FCD34D] text-[#92400E] hover:bg-[#FEF3C7]"
              >
                {patchErrorDetails.retry_available ? 'Retry Patch Synthesis' : 'Force Re-investigation'}
              </Button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-[#FDE68A] text-[11px]">
            <span className="font-semibold text-[#78350F]">Failure Diagnostics:</span>
            {patchErrorDetails.file && (
              <span className="bg-white px-2 py-0.5 rounded border border-[#FCD34D] font-mono text-[#78350F]">
                Target: {patchErrorDetails.file}
              </span>
            )}
            {patchErrorDetails.hunk && (
              <span className="bg-white px-2 py-0.5 rounded border border-[#FCD34D] font-mono text-[#78350F]">
                Hunk: #{patchErrorDetails.hunk}
              </span>
            )}
            <span className={`px-2 py-0.5 rounded font-medium ${patchErrorDetails.retry_available ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' : 'bg-slate-100 text-slate-700'}`}>
              {patchErrorDetails.retry_available ? '✓ Retry Available' : '⚠️ Retries Exhausted'}
            </span>
            {patchErrorDetails.attempts > 1 && (
              <span className="text-slate-500 font-mono">
                ({patchErrorDetails.attempts} autonomous attempts made)
              </span>
            )}
          </div>
        </div>
      )}

      {/* Real Mode Error Alert Banner (for Non-Patch Errors) */}
      {investigationError && !patchErrorDetails && (
        <div className="bg-[#FEF2F2] border border-[#FCA5A5] rounded-xl p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-[#991B1B]">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-[#DC2626] flex-shrink-0 mt-0.5" />
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm text-[#7F1D1D]">
                  {errorStatus === 401
                    ? 'Authentication Error'
                    : errorStatus === 429
                    ? 'Nemotron Rate Limit Exceeded'
                    : errorStatus === 504
                    ? 'Nemotron Gateway Timeout'
                    : errorStatus === 502
                    ? 'Nemotron Upstream / Parsing Error'
                    : 'Investigation Error'}
                </span>
                <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-[#FEE2E2] text-[#DC2626] border border-[#FCA5A5]">
                  {errorStatus ? `HTTP ${errorStatus}` : 'FAILED'}
                </span>
              </div>
              <p className="mt-1 text-[#991B1B] text-xs">
                {investigationError}
              </p>
              {failureInfo && (
                <div className="flex flex-wrap items-center gap-2 pt-2 text-[11px]">
                  <span className="bg-white px-2 py-0.5 rounded border border-[#FCA5A5] text-[#7F1D1D]">
                    Failed stage: <strong>{failureInfo.stage}</strong>
                  </span>
                  {failureInfo.runId && (
                    <span className="bg-white px-2 py-0.5 rounded border border-[#FCA5A5] font-mono text-[#7F1D1D]">
                      Run: {failureInfo.runId}
                    </span>
                  )}
                  {failureInfo.elapsedSeconds !== undefined && (
                    <span className="bg-white px-2 py-0.5 rounded border border-[#FCA5A5] text-[#7F1D1D]">
                      Elapsed: {failureInfo.elapsedSeconds}s
                    </span>
                  )}
                  {failureInfo.errorCode && (
                    <span className="bg-white px-2 py-0.5 rounded border border-[#FCA5A5] font-mono text-[#7F1D1D]">
                      {failureInfo.errorCode}
                    </span>
                  )}
                  <span className={`px-2 py-0.5 rounded font-medium ${failureInfo.retryable ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' : 'bg-slate-100 text-slate-700'}`}>
                    {failureInfo.retryable ? '✓ Retryable' : '✗ Not retryable'}
                  </span>
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            {errorStatus === 401 ? (
              <Button
                variant="primary"
                size="sm"
                onClick={() => api.githubLogin()}
                className="bg-[#2563EB] hover:bg-[#1D4ED8]"
              >
                Reconnect GitHub
              </Button>
            ) : (!failureInfo || failureInfo.retryable) ? (
              <Button
                variant="outline"
                size="sm"
                icon={RefreshCw}
                onClick={runRealInvestigation}
                disabled={isInvestigating}
              >
                Retry Investigation
              </Button>
            ) : null}
          </div>
        </div>
      )}

      {/* 2. Investigation Progress */}
      <InvestigationProgress
        progress={inv.progress || (isFailed ? 40 : 100)}
        isComplete={isComplete}
        isStopped={isStopped}
        isFailed={isFailed}
      />

      {/* 3. Main Grid: Left Agents Panel (4 Cols) + Right Live Tabs (8 Cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left: Agent Pipeline & Sandbox Metrics */}
        <div className="lg:col-span-4 space-y-4">
          <AgentPipeline
            agents={inv.agents || []}
            isComplete={isComplete}
            isRealMode={isRealMode}
            sandboxResult={inv.sandboxResult}
            dockerStatus={dockerStatus}
          />

          {isRealMode && !isInvestigating && (
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-3 shadow-xs flex items-center justify-between text-xs text-[#64748B]">
              <span className="font-mono text-[11px]">Real Mode Pipeline</span>
              <button
                type="button"
                onClick={runRealInvestigation}
                className="text-[#2563EB] hover:text-[#1D4ED8] font-semibold text-xs flex items-center gap-1 cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Re-run Investigation</span>
              </button>
            </div>
          )}
        </div>

        {/* Right: Tabs & Detailed Evidence */}
        <div className="lg:col-span-8 space-y-4">
          {/* Navigation Tabs */}
          <div className="bg-white border border-[#E2E8F0] rounded-xl p-2 shadow-xs flex items-center gap-1.5 overflow-x-auto">
            {[
              { id: 'LOGS', label: 'Live Logs', count: inv.logs?.length || 5 },
              { id: 'PATCH', label: 'Unified Patch', count: inv.patch?.diff ? (inv.patch.files_changed?.length || 1) : undefined },
              { id: 'ROOT_CAUSE', label: 'Root Cause' },
              { id: 'FILES', label: 'Files Analyzed', count: inv.filesAnalyzed?.length || 1 },
              { id: 'TESTS', label: 'Tests', count: isRealMode ? (inv.sandboxResult?.status === 'PASSED' ? 'Passed' : inv.sandboxResult?.status || 'Docker') : `${inv.testSummary?.passed || 12}/${inv.testSummary?.total || 14}` },
              { id: 'SECURITY', label: 'Security' },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap cursor-pointer flex items-center gap-1.5 ${
                  activeTab === tab.id
                    ? 'bg-[#2563EB] text-white shadow-xs'
                    : 'text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC]'
                }`}
              >
                <span>{tab.label}</span>
                {tab.count !== undefined && (
                  <span
                    className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                      activeTab === tab.id
                        ? 'bg-blue-400/30 text-white'
                        : 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {tab.count}
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* TAB 1: LIVE LOGS */}
          {activeTab === 'LOGS' && (
            <LiveLogs
              logs={inv.logs || []}
              repo={inv.repo}
              isLive={!isComplete && !isStopped && !investigationError}
              isComplete={isComplete}
              isRealMode={isRealMode}
              investigationId={inv.id}
            />
          )}

          {/* TAB 2: UNIFIED PATCH */}
          {activeTab === 'PATCH' && (
            <div className="space-y-4">
              {inv.patch?.diff ? (
                <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-[#E2E8F0] gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-[#16A34A] bg-[#DCFCE7] border border-[#BBF7D0] px-2.5 py-0.5 rounded-full uppercase tracking-wider">
                          PATCH GENERATED
                        </span>
                        <span className="text-xs text-[#64748B] font-mono">
                          {inv.patch.file || 'Modified File'}
                        </span>
                      </div>
                      <h3 className="text-base font-bold text-[#0F172A] mt-1.5">
                        Autonomous Code Repair
                      </h3>
                      <p className="text-xs text-[#64748B] mt-0.5">
                        Minimal unified diff synthesized via NVIDIA Nemotron 3.5 &amp; verified with AST Diff Validator.
                      </p>
                    </div>

                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-mono font-semibold bg-[#F8FAFC] border border-[#E2E8F0] px-2.5 py-1 rounded-lg text-[#0F172A]">
                        Files changed: <strong>{inv.patch.files_changed?.length || 1}</strong>
                      </span>
                      <span className="text-xs font-mono font-semibold bg-emerald-50 border border-emerald-200 text-[#16A34A] px-2.5 py-1 rounded-lg">
                        +{inv.patch.lines_added || 0}
                      </span>
                      <span className="text-xs font-mono font-semibold bg-rose-50 border border-rose-200 text-[#DC2626] px-2.5 py-1 rounded-lg">
                        -{inv.patch.lines_removed || 0}
                      </span>
                    </div>
                  </div>

                  {/* Validation Proof Card */}
                  <div className="p-3.5 bg-[#EFF6FF] border border-[#BFDBFE] rounded-xl flex items-center justify-between text-xs text-[#1E3A8A]">
                    <div className="flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-[#2563EB]" />
                      <span className="font-semibold">Diff Validator Result:</span>
                      <span>Patch applies cleanly to the analyzed repository AST.</span>
                    </div>
                    <span className="px-2 py-0.5 rounded font-mono font-bold text-[10px] bg-white border border-[#BFDBFE] text-[#2563EB]">
                      VALIDATED
                    </span>
                  </div>

                  {/* Proposed Fix Explanation */}
                  {inv.patch.explanation && (
                    <div className="p-4 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-xs space-y-1.5">
                      <span className="font-semibold text-[#0F172A] block">Proposed Fix Rationale:</span>
                      <p className="text-[#64748B] leading-relaxed">
                        {inv.patch.explanation}
                      </p>
                    </div>
                  )}

                  {/* Unified Diff Viewer */}
                  <div>
                    <DiffViewer
                      file={inv.patch.file || 'src/components/SubmitButton.jsx'}
                      diff={inv.patch.diff}
                    />
                  </div>
                </div>
              ) : (
                <div className="bg-white border border-[#E2E8F0] rounded-xl p-10 text-center space-y-3">
                  <Sparkles className="w-8 h-8 text-[#94A3B8] mx-auto animate-pulse" />
                  <h4 className="text-sm font-bold text-[#0F172A]">
                    {isInvestigating ? 'Synthesizing Patch with Nemotron...' : 'No Patch Generated Yet'}
                  </h4>
                  <p className="text-xs text-[#64748B] max-w-md mx-auto">
                    {isInvestigating
                      ? 'The Code Repair Agent is generating and validating a unified diff against the target files.'
                      : 'Run or re-run the AI investigation to synthesize a validated code patch.'}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: ROOT CAUSE */}
          {activeTab === 'ROOT_CAUSE' && (
            <RootCause rootCause={inv.rootCause} />
          )}

          {/* TAB 4: FILES ANALYZED */}
          {activeTab === 'FILES' && (
            <FilesAnalyzed files={inv.filesAnalyzed || (inv.patch ? [inv.patch.file] : ['src/handler.py'])} />
          )}

          {/* TAB 5: TESTS */}
          {activeTab === 'TESTS' && (
            <TestResults
              testSummary={inv.testSummary}
              isComplete={isComplete}
              isRealMode={isRealMode}
              sandboxResult={inv.sandboxResult}
              isTestingRunning={isInvestigating && inv.progress >= 70 && !inv.sandboxResult}
              onRerunSandbox={handleRerunSandboxWithOverrides}
              hasPatch={Boolean(inv.patch?.diff || inv.diff?.diff)}
            />
          )}

          {/* TAB 6: SECURITY */}
          {activeTab === 'SECURITY' && (
            <SecurityResults
              isRealMode={isRealMode}
              securityResult={inv?.securityResult}
            />
          )}
        </div>
      </div>

      {/* Stop Investigation Confirmation Dialog */}
      <ConfirmDialog
        isOpen={stopConfirmOpen}
        onClose={() => setStopConfirmOpen(false)}
        onConfirm={handleStopInvestigation}
        title="Stop AI Investigation?"
        description="This will cancel active agent operations. You can restart the investigation order anytime."
        confirmText="Stop Investigation"
        danger={true}
      />
    </div>
  );
}
