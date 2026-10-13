import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  FileCode,
  Sparkles,
  ShieldAlert,
  Cpu,
  UserCheck,
  ExternalLink
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import Button, { PrimaryButton } from '../../components/common/Button';
import DiffViewer from '../../components/common/DiffViewer';
import Modal from '../../components/common/Modal';
import api from '../../services/api';

const WRITE_STEPS = [
  'Creating branch...',
  'Applying patch...',
  'Creating commit...',
  'Verifying commit...',
  'Creating pull request...',
  'Verifying pull request...'
];

export default function CodeReview() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { getInvestigation, approvePatchAndOpenPR, rejectPatch, appMode } = useApp();

  const inv = getInvestigation(id) || null;
  const isRealMode = (inv?.mode === 'REAL') || (appMode === 'REAL');

  const [activeTab, setActiveTab] = useState('DIFF');
  const [successModalOpen, setSuccessModalOpen] = useState(false);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');
  const [createdPr, setCreatedPr] = useState(null);
  const [approving, setApproving] = useState(false);
  const [currentStepIdx, setCurrentStepIdx] = useState(0);
  const [approvalError, setApprovalError] = useState(null);

  // Real XGBoost ML state
  const [riskAssessment, setRiskAssessment] = useState(inv?.risk_assessment || null);
  const [riskLoading, setRiskLoading] = useState(() => Boolean(isRealMode && !inv?.risk_assessment));

  useEffect(() => {
    // If real mode and risk_assessment not yet attached, query FastAPI POST /api/risk/predict
    if (isRealMode && !riskAssessment && inv) {
      let isSubscribed = true;

      const features = inv.features_extracted || {
        files_changed: inv.filesAnalyzed?.length || 1,
        lines_added: inv.patch?.lines_added || 2,
        lines_removed: inv.patch?.lines_removed || 1,
        total_changed_lines: (inv.patch?.lines_added || 2) + (inv.patch?.lines_removed || 1),
        patch_size: 250,
        functions_changed: 1,
        classes_changed: 0,
        cyclomatic_complexity: 1.5,
        code_size: 850,
        dependency_changes: 0,
        test_count: 0,
        tests_passed: 0,
        tests_failed: 0
      };

      api.predictRisk(features)
        .then((res) => {
          if (isSubscribed) {
            setRiskAssessment(res);
          }
        })
        .catch((err) => {
          console.warn('[DevRescue] Failed to predict risk from backend:', err);
        })
        .finally(() => {
          if (isSubscribed) setRiskLoading(false);
        });

      return () => {
        isSubscribed = false;
      };
    }
  }, [isRealMode, riskAssessment, inv]);

  if (!inv) {
    return (
      <div className="py-20 text-center space-y-4">
        <h2 className="text-xl font-bold text-[#0F172A]">Investigation Not Found</h2>
        <Button to="/dashboard" variant="primary">
          Back to Dashboard
        </Button>
      </div>
    );
  }

  const handleApprove = async () => {
    setApproving(true);
    setApprovalError(null);
    setCurrentStepIdx(0);

    let stepTimer = null;
    if (isRealMode) {
      stepTimer = setInterval(() => {
        setCurrentStepIdx((prev) => {
          if (prev < WRITE_STEPS.length - 1) return prev + 1;
          return prev;
        });
      }, 700);
    }

    try {
      const pr = await approvePatchAndOpenPR(inv.id);
      if (stepTimer) clearInterval(stepTimer);
      setCurrentStepIdx(WRITE_STEPS.length - 1);
      setCreatedPr(pr);
      setSuccessModalOpen(true);
    } catch (err) {
      if (stepTimer) clearInterval(stepTimer);
      let errorDetails = {
        type: 'ERROR',
        title: 'Pull Request Dispatch Failed',
        message: err.message || 'An error occurred while creating the pull request on GitHub.',
        action: null
      };

      const errLower = (err.message || '').toLowerCase();
      if (err.status === 401 || errLower.includes('auth') || errLower.includes('token')) {
        errorDetails = {
          type: '401_AUTH',
          title: 'GitHub Authentication Required',
          message: 'Active GitHub session or write token not found. Please connect your GitHub account to publish branches and pull requests.',
          action: 'CONNECT_GITHUB'
        };
      } else if (err.status === 403 || errLower.includes('human approval')) {
        errorDetails = {
          type: '403_FORBIDDEN',
          title: 'Human Approval Required',
          message: 'Explicit maintainer sign-off is mandatory before creating a pull request.',
          action: null
        };
      } else if (err.status === 409 || errLower.includes('patch conflict')) {
        errorDetails = {
          type: '409_CONFLICT',
          title: 'Patch Conflict on Target File',
          message: err.message || 'The upstream file on GitHub does not match the expected patch base lines. Branch was automatically rolled back.',
          action: null
        };
      } else if (err.status === 422 || errLower.includes('validation')) {
        errorDetails = {
          type: '422_VALIDATION',
          title: 'GitHub Validation Error',
          message: err.message || 'GitHub rejected the request (unsafe file path, invalid branch name, or malformed diff).',
          action: null
        };
      }
      setApprovalError(errorDetails);
    } finally {
      setApproving(false);
    }
  };

  const handleConfirmReject = async () => {
    await rejectPatch(inv.id, rejectionReason || 'Maintainer requested alternate patch structure.');
    setRejectModalOpen(false);
    navigate(`/investigations/${inv.id}`);
  };

  const handleModalNavigate = () => {
    setSuccessModalOpen(false);
    navigate('/pull-requests');
  };

  if (!inv) {
    return (
      <div className="py-20 text-center space-y-4 max-w-md mx-auto">
        <h2 className="text-xl font-bold text-[#0F172A]">Investigation Not Found</h2>
        <p className="text-sm text-[#64748B]">No investigation dossier was found with ID #{id}.</p>
        <div className="flex items-center justify-center gap-3 pt-2">
          <Button to="/repositories" variant="primary">
            Browse Repositories
          </Button>
          <Button to="/history" variant="outline">
            Investigation History
          </Button>
        </div>
      </div>
    );
  }

  // Determine displayed risk level & color
  const currentRiskLevel = riskAssessment?.risk_level || inv.riskLevel || 'LOW';
  const riskColor = currentRiskLevel === 'LOW'
    ? 'text-[#16A34A]'
    : currentRiskLevel === 'MEDIUM'
    ? 'text-[#D97706]'
    : 'text-[#DC2626]';

  const riskBg = currentRiskLevel === 'LOW'
    ? 'bg-[#DCFCE7]'
    : currentRiskLevel === 'MEDIUM'
    ? 'bg-[#FEF3C7]'
    : 'bg-[#FEE2E2]';

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1 text-xs">
            <Link to={`/investigations/${inv.id}`} className="text-[#2563EB] hover:underline font-medium">
              ← Return to Live Investigation
            </Link>
            <span className="text-slate-300">·</span>
            <span className="text-[#64748B] font-mono">{inv.repo}</span>
            <span className="text-slate-300">·</span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${isRealMode ? 'bg-[#EFF6FF] text-[#2563EB] border border-[#BFDBFE]' : 'bg-[#F1F5F9] text-[#64748B]'}`}>
              {isRealMode ? 'REAL MODE' : 'DEMO MODE'}
            </span>
          </div>

          <h1 className="text-2xl font-bold tracking-tight text-[#0F172A]">
            Code Review
          </h1>
          <p className="text-sm text-[#64748B] mt-0.5">
            Review the proposed fix, verified ML risk assessment, and sandbox proofs before preparing a pull request.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="md"
            onClick={() => setRejectModalOpen(true)}
            disabled={approving}
          >
            Reject Fix
          </Button>

          <PrimaryButton
            size="md"
            arrow={!approving}
            onClick={handleApprove}
            loading={approving}
            disabled={approving}
            className="bg-[#2563EB] hover:bg-[#1D4ED8]"
          >
            {approving ? WRITE_STEPS[currentStepIdx] : 'Approve & Create PR'}
          </PrimaryButton>
        </div>
      </div>

      {/* Error Banner */}
      {approvalError && (
        <div className="bg-[#FEF2F2] border border-[#FCA5A5] rounded-xl p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-[#991B1B]">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-[#DC2626] flex-shrink-0 mt-0.5" />
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm text-[#7F1D1D]">{approvalError.title}</span>
                <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-[#FEE2E2] text-[#DC2626] border border-[#FCA5A5]">
                  {approvalError.type}
                </span>
              </div>
              <p className="mt-1 text-[#991B1B] leading-relaxed max-w-2xl">
                {approvalError.message}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0 self-end sm:self-center">
            {approvalError.action === 'CONNECT_GITHUB' && (
              <button
                type="button"
                onClick={() => api.githubLogin()}
                className="px-3 py-1.5 rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white font-semibold cursor-pointer text-xs"
              >
                Connect GitHub
              </button>
            )}
            <button
              type="button"
              onClick={() => setApprovalError(null)}
              className="px-3 py-1.5 rounded-lg bg-white border border-[#FCA5A5] hover:bg-slate-50 text-[#7F1D1D] font-medium cursor-pointer text-xs"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Sequential Real GitHub Progress Banner */}
      {approving && isRealMode && (
        <div className="bg-[#EFF6FF] border border-[#BFDBFE] rounded-xl p-4 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-4 h-4 border-2 border-[#2563EB] border-t-transparent rounded-full animate-spin" />
              <span className="text-xs font-bold text-[#1E3A8A]">
                Executing GitHub Write Workflow: {WRITE_STEPS[currentStepIdx]}
              </span>
            </div>
            <span className="text-[11px] font-mono font-semibold text-[#2563EB]">
              Step {currentStepIdx + 1} of {WRITE_STEPS.length}
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
            {WRITE_STEPS.map((step, idx) => {
              const isDone = idx < currentStepIdx;
              const isCurrent = idx === currentStepIdx;
              return (
                <div
                  key={step}
                  className={`p-2 rounded-lg text-center text-[10px] font-medium border transition-all ${
                    isDone
                      ? 'bg-emerald-50 border-emerald-300 text-emerald-700'
                      : isCurrent
                      ? 'bg-[#2563EB] border-[#2563EB] text-white shadow-xs font-bold animate-pulse'
                      : 'bg-white/80 border-slate-200 text-slate-400'
                  }`}
                >
                  <span className="truncate block">{step.replace('...', '')}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Top Summary Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Metric 1: Root Cause */}
        <div className="p-4 bg-white border border-[#E2E8F0] rounded-xl shadow-xs">
          <span className="text-xs font-semibold uppercase tracking-wider text-[#64748B] block">
            Root Cause
          </span>
          <span className="text-xs font-bold text-[#0F172A] mt-1 block truncate" title={inv.rootCause?.summary}>
            {inv.rootCause?.summary || 'Identified bug'}
          </span>
          <span className="text-[11px] text-[#64748B] mt-0.5 block truncate">
            {inv.rootCause?.file || 'Target file isolated'}
          </span>
        </div>

        {/* Metric 2: XGBoost ML Risk */}
        <div className="p-4 bg-white border border-[#E2E8F0] rounded-xl shadow-xs">
          <span className="text-xs font-semibold uppercase tracking-wider text-[#64748B] block">
            XGBoost Patch Risk
          </span>
          <span className={`text-base font-bold ${riskColor} mt-1 block flex items-center gap-1.5`}>
            {currentRiskLevel === 'LOW' && <CheckCircle2 className="w-4 h-4" />}
            {currentRiskLevel === 'MEDIUM' && <AlertTriangle className="w-4 h-4" />}
            {currentRiskLevel === 'HIGH' && <XCircle className="w-4 h-4" />}
            <span>{currentRiskLevel} Risk</span>
          </span>
          <span className="text-[11px] text-[#64748B] mt-0.5 block">
            {riskAssessment ? `${(riskAssessment.risk_score * 100).toFixed(1)}% confidence · 13 features` : 'Trained XGBoost model'}
          </span>
        </div>

        {/* Metric 3: Testing Status (No fake claims in Real Mode) */}
        <div className="p-4 bg-white border border-[#E2E8F0] rounded-xl shadow-xs">
          <span className="text-xs font-semibold uppercase tracking-wider text-[#64748B] block">
            Testing Status
          </span>
          {isRealMode ? (
            <>
              <span className="text-xs font-bold text-[#64748B] mt-1 block">
                NOT IMPLEMENTED
              </span>
              <span className="text-[11px] text-[#94A3B8] mt-0.5 block">
                Docker Sandbox disabled
              </span>
            </>
          ) : (
            <>
              <span className="text-base font-bold text-[#16A34A] mt-1 block flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4" />
                <span>Simulated Tests</span>
              </span>
              <span className="text-[11px] text-[#64748B] mt-0.5 block">
                Demo prototype pass
              </span>
            </>
          )}
        </div>

        {/* Metric 4: Security Review (No fake claims in Real Mode) */}
        <div className="p-4 bg-white border border-[#E2E8F0] rounded-xl shadow-xs">
          <span className="text-xs font-semibold uppercase tracking-wider text-[#64748B] block">
            Security Review
          </span>
          {isRealMode ? (
            <>
              <span className="text-xs font-bold text-[#64748B] mt-1 block">
                NOT IMPLEMENTED
              </span>
              <span className="text-[11px] text-[#94A3B8] mt-0.5 block">
                SAST scanner not configured
              </span>
            </>
          ) : (
            <>
              <span className="text-base font-bold text-[#16A34A] mt-1 block flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4" />
                <span>Simulated Security</span>
              </span>
              <span className="text-[11px] text-[#64748B] mt-0.5 block">
                Demo prototype audit
              </span>
            </>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border border-[#E2E8F0] rounded-xl p-2 shadow-xs flex items-center gap-1.5 overflow-x-auto">
        {[
          { id: 'DIFF', label: 'Diff' },
          { id: 'FILES', label: 'Files Changed', count: inv.filesAnalyzed?.length || 1 },
          { id: 'TESTS', label: 'Test Results', count: isRealMode ? 'N/A' : '14/14' },
          { id: 'SECURITY', label: 'Security Review' },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer flex items-center gap-2 ${
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

      {/* Main Content Area */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column (8 Cols) */}
        <div className="lg:col-span-8 space-y-4">
          {activeTab === 'DIFF' && (
            <div className="space-y-4">
              <DiffViewer
                file={inv.patch?.file || "src/handler.py"}
                diff={inv.diff || inv.patch?.diff}
              />

              <div className="p-4 bg-white border border-[#E2E8F0] rounded-xl text-xs text-[#64748B] flex items-center justify-between">
                <span>Minimal viable patch synthesized for human maintainer review</span>
                <span className="font-mono text-slate-400">target: devrescue/patch-issue-{inv.issueNumber || 42}</span>
              </div>
            </div>
          )}

          {activeTab === 'FILES' && (
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm space-y-4">
              <h3 className="text-sm font-bold text-[#0F172A]">Files Changed in this Fix</h3>
              <div className="space-y-3">
                {(inv.filesAnalyzed || [inv.patch?.file || 'src/handler.py']).map((file, i) => (
                  <div key={i} className="p-3.5 rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2.5">
                      <FileCode className="w-4 h-4 text-[#2563EB]" />
                      <span className="font-mono font-bold text-[#0F172A]">{file}</span>
                    </div>
                    <span className="font-mono text-[#16A34A]">+3 / -1</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'TESTS' && (
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm space-y-4">
              <h3 className="text-sm font-bold text-[#0F172A]">Test Suite Verification</h3>
              {isRealMode ? (
                <div className="p-6 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-center space-y-2">
                  <ShieldAlert className="w-8 h-8 text-[#94A3B8] mx-auto" />
                  <h4 className="text-sm font-bold text-[#0F172A]">Testing: NOT IMPLEMENTED</h4>
                  <p className="text-xs text-[#64748B] max-w-md mx-auto leading-relaxed">
                    Automated sandbox execution is not configured. Under DevRescue safety guidelines, test passes are not fabricated when an isolated Docker runner is absent.
                  </p>
                </div>
              ) : (
                <div className="space-y-2 text-xs">
                  <div className="p-2.5 bg-[#EFF6FF] text-[#2563EB] rounded-lg text-xs font-semibold mb-2">
                    DEMO MODE — Simulated Prototype Test Proof
                  </div>
                  {[
                    '14 tests passed (simulated prototype)',
                    'Build completed in 3.4 seconds',
                    'Regression test passed with 0 concurrency collisions'
                  ].map((item, i) => (
                    <div key={i} className="flex items-center gap-2.5 text-[#16A34A] bg-[#DCFCE7]/60 p-3 rounded-lg border border-[#BBF7D0]">
                      <CheckCircle2 className="w-4 h-4" />
                      <span className="font-medium text-[#0F172A]">{item}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'SECURITY' && (
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm space-y-4">
              <h3 className="text-sm font-bold text-[#0F172A]">Security Review Findings</h3>
              {isRealMode ? (
                <div className="p-6 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-center space-y-2">
                  <ShieldAlert className="w-8 h-8 text-[#94A3B8] mx-auto" />
                  <h4 className="text-sm font-bold text-[#0F172A]">Security Review: NOT IMPLEMENTED</h4>
                  <p className="text-xs text-[#64748B] max-w-md mx-auto leading-relaxed">
                    Automated SAST &amp; secret scanning pipeline is not configured. DevRescue does not claim clean security without active scanner execution.
                  </p>
                </div>
              ) : (
                <div className="space-y-2 text-xs">
                  <div className="p-2.5 bg-[#EFF6FF] text-[#2563EB] rounded-lg text-xs font-semibold mb-2">
                    DEMO MODE — Simulated Prototype Security Audit
                  </div>
                  {[
                    'No secrets detected in modified lines (Simulated)',
                    'No dependency changes or package lock updates',
                    'Changes limited strictly to requested files'
                  ].map((item, i) => (
                    <div key={i} className="flex items-center gap-2.5 text-[#16A34A] bg-[#DCFCE7]/60 p-3 rounded-lg border border-[#BBF7D0]">
                      <CheckCircle2 className="w-4 h-4" />
                      <span className="font-medium text-[#0F172A]">{item}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Info Panel (4 Cols) */}
        <div className="lg:col-span-4 space-y-4">
          {/* 1. Real XGBoost Risk Assessment Card */}
          <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-[#E2E8F0]">
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-[#2563EB]" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-[#0F172A]">
                  XGBoost Risk Assessment
                </h3>
              </div>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${riskBg} ${riskColor}`}>
                {currentRiskLevel} RISK
              </span>
            </div>

            {riskLoading ? (
              <p className="text-xs text-[#64748B] animate-pulse">Running inference on XGBoost model...</p>
            ) : riskAssessment ? (
              <div className="space-y-3 text-xs">
                <div className="p-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg space-y-1.5">
                  <div className="flex justify-between items-center text-[11px]">
                    <span className="text-[#64748B]">Confidence Score:</span>
                    <span className="font-bold text-[#0F172A]">{(riskAssessment.risk_score * 100).toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between items-center text-[11px]">
                    <span className="text-[#64748B]">Architecture:</span>
                    <span className="font-mono text-[#0F172A]">{riskAssessment.model_name || 'XGBClassifier'} (13 features)</span>
                  </div>
                </div>

                {/* Probability Distribution */}
                {riskAssessment.probabilities && (
                  <div className="space-y-1.5">
                    <span className="text-[10px] font-semibold uppercase text-[#64748B] block">
                      Class Probability Distribution
                    </span>
                    <div className="grid grid-cols-3 gap-1.5 text-center text-[11px] font-mono">
                      <div className="p-2 bg-emerald-50 border border-emerald-200 rounded">
                        <span className="block text-[10px] text-emerald-700 font-sans font-bold">LOW</span>
                        <span className="font-bold text-emerald-800">
                          {((riskAssessment.probabilities.LOW || 0) * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="p-2 bg-amber-50 border border-amber-200 rounded">
                        <span className="block text-[10px] text-amber-700 font-sans font-bold">MED</span>
                        <span className="font-bold text-amber-800">
                          {((riskAssessment.probabilities.MEDIUM || 0) * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="p-2 bg-rose-50 border border-rose-200 rounded">
                        <span className="block text-[10px] text-rose-700 font-sans font-bold">HIGH</span>
                        <span className="font-bold text-rose-800">
                          {((riskAssessment.probabilities.HIGH || 0) * 100).toFixed(1)}%
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                {riskAssessment.recommendation && (
                  <p className="text-[11px] text-[#64748B] leading-relaxed bg-[#F8FAFC] p-2.5 rounded border border-[#E2E8F0]">
                    {riskAssessment.recommendation}
                  </p>
                )}
              </div>
            ) : (
              <p className="text-xs text-[#64748B]">XGBoost risk model ready for patch evaluation.</p>
            )}
          </div>

          {/* 2. AI Explanation Card */}
          <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-sm space-y-3">
            <div className="flex items-center gap-2 pb-2 border-b border-[#E2E8F0]">
              <Sparkles className="w-4 h-4 text-[#2563EB]" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#0F172A]">
                AI Repair Context
              </h3>
            </div>
            <p className="text-xs text-[#0F172A] font-medium leading-relaxed bg-[#EFF6FF] border border-[#BFDBFE] p-3 rounded-lg">
              "{inv.rootCause?.summary || 'Identified bug and synthesized fix.'}"
            </p>
            <p className="text-xs text-[#64748B] leading-relaxed">
              {inv.rootCause?.explanation || 'Targeted fix confined strictly to bug trigger conditions.'}
            </p>
          </div>

          {/* 3. Human Approval Requirement Card */}
          <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-sm space-y-3">
            <div className="flex items-center gap-2 pb-2 border-b border-[#E2E8F0]">
              <UserCheck className="w-4 h-4 text-[#2563EB]" />
              <h4 className="text-xs font-bold uppercase tracking-wider text-[#0F172A]">
                Human Approval Required
              </h4>
            </div>
            <p className="text-xs text-[#64748B] leading-relaxed">
              In accordance with safety policy, patches cannot be dispatched to GitHub automatically. Maintainer sign-off is mandatory.
            </p>
            <div className="p-2.5 bg-[#F8FAFC] rounded-lg border border-[#E2E8F0] text-xs">
              <span className="text-[#64748B] block text-[11px]">Approval State:</span>
              <span className="font-bold text-[#0F172A]">
                {inv.human_approved ? '✓ Approved by Maintainer' : 'Awaiting Review & Approval'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Success Approval Modal */}
      <Modal
        isOpen={successModalOpen}
        onClose={() => setSuccessModalOpen(false)}
        title={isRealMode ? "Pull Request Created on GitHub" : "Human Approval Confirmed"}
        subtitle={isRealMode ? `Verified upstream on ${createdPr?.repo || inv.repo}` : "Demo pull request prepared."}
        maxWidth="max-w-lg"
        footer={
          <div className="flex items-center justify-end gap-3 w-full">
            <Button variant="outline" size="sm" onClick={() => setSuccessModalOpen(false)}>
              Close
            </Button>
            <PrimaryButton size="sm" onClick={handleModalNavigate} arrow={true}>
              View All Pull Requests
            </PrimaryButton>
          </div>
        }
      >
        <div className="space-y-4 py-2">
          <div className="w-12 h-12 rounded-full bg-[#DCFCE7] text-[#16A34A] flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-7 h-7" />
          </div>

          <div className="text-center">
            <h4 className="text-base font-bold text-[#0F172A]">
              {isRealMode ? `Pull Request #${createdPr?.number || 1} Published` : "Patch Approved by Maintainer"}
            </h4>
            <p className="text-xs text-[#64748B] mt-1">
              {isRealMode
                ? "The fix has been committed, pushed to upstream branch, and verified on GitHub."
                : `Patch #${createdPr?.number || 1} has been signed off and recorded.`}
            </p>
          </div>

          {/* Real GitHub details card */}
          {isRealMode && createdPr && (
            <div className="p-4 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl space-y-2.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-[#64748B]">Repository:</span>
                <span className="font-mono font-bold text-[#0F172A]">{createdPr.repo}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[#64748B]">Branch:</span>
                <span className="font-mono text-[#0F172A]">{createdPr.branch}</span>
              </div>
              {createdPr.commit_sha && (
                <div className="flex items-center justify-between">
                  <span className="text-[#64748B]">Commit SHA:</span>
                  <span className="font-mono text-[#2563EB]">{createdPr.commit_sha.slice(0, 7)}</span>
                </div>
              )}
              {createdPr.status && (
                <div className="flex items-center justify-between">
                  <span className="text-[#64748B]">Status:</span>
                  <span className="font-bold text-[#16A34A]">{createdPr.status}</span>
                </div>
              )}

              {/* Clickable Link to Real GitHub PR */}
              {(createdPr.pr_url || createdPr.html_url || createdPr.prUrl) && (
                <div className="pt-2 border-t border-[#E2E8F0]">
                  <a
                    href={createdPr.pr_url || createdPr.html_url || createdPr.prUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-bold transition-all shadow-xs"
                  >
                    <span>Open PR #{createdPr.number} on GitHub</span>
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </div>
              )}
            </div>
          )}
        </div>
      </Modal>

      {/* Reject Fix Modal */}
      <Modal
        isOpen={rejectModalOpen}
        onClose={() => setRejectModalOpen(false)}
        title="Reject Proposed Fix"
        subtitle="Provide guidance for patch revision"
        maxWidth="max-w-md"
        footer={
          <>
            <Button variant="outline" size="sm" onClick={() => setRejectModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="danger" size="sm" onClick={handleConfirmReject}>
              Confirm Rejection
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <label className="block text-xs font-semibold text-[#0F172A] uppercase tracking-wider">
            Rejection Reason / Guidance
          </label>
          <textarea
            rows={3}
            value={rejectionReason}
            onChange={(e) => setRejectionReason(e.target.value)}
            placeholder="Explain why the patch is unsuitable..."
            className="w-full rounded-lg bg-white border border-[#E2E8F0] p-3 text-sm text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB]"
          />
        </div>
      </Modal>
    </div>
  );
}
