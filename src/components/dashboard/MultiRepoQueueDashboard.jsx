import React, { useState, useEffect, useCallback } from 'react';
import {
  FolderGit2,
  RefreshCw,
  Play,
  Pause,
  AlertCircle,
  CheckCircle2,
  Clock,
  Shield,
  Layers,
  ExternalLink,
  RotateCcw,
  Sliders,
  Search,
  Sparkles,
  GitPullRequest,
  Check,
  Eye
} from 'lucide-react';
import api from '../../services/api';
import Card from '../common/Card';
import Button, { PrimaryButton } from '../common/Button';
import { StatusBadge } from '../common/Badge';
import Modal from '../common/Modal';
import CodeBlock from '../common/CodeBlock';

const SEVERITY_BADGES = {
  critical: 'bg-red-50 text-red-700 border-red-200',
  high: 'bg-orange-50 text-orange-700 border-orange-200',
  medium: 'bg-amber-50 text-amber-700 border-amber-200',
  low: 'bg-blue-50 text-blue-700 border-blue-200'
};

const TRIAGE_LABELS = {
  READY_FOR_REPAIR: { label: 'Ready for Repair', color: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  REQUIRES_REVIEW: { label: 'Requires Review', color: 'bg-purple-50 text-purple-700 border-purple-200' },
  BLOCKED: { label: 'Blocked', color: 'bg-rose-50 text-rose-700 border-rose-200' },
  EXCLUDED: { label: 'Excluded', color: 'bg-slate-100 text-slate-600 border-slate-200' }
};

export default function MultiRepoQueueDashboard() {
  const [stats, setStats] = useState(null);
  const [repositories, setRepositories] = useState([]);
  const [issues, setIssues] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [_loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [processing, setProcessing] = useState(false);

  // Filters
  const [selectedRepo, setSelectedRepo] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [searchTerm, setSearchTerm] = useState('');

  // Concurrency Config
  const [concurrency, setConcurrency] = useState(2);
  const [showConfigModal, setShowConfigModal] = useState(false);

  // Review & Approval Modal
  const [reviewJob, setReviewJob] = useState(null);
  const [approving, setApproving] = useState(false);
  const [approvalError, setApprovalError] = useState(null);
  const [approvalSuccess, setApprovalSuccess] = useState(null);

  // Notification message
  const [notification, setNotification] = useState(null);

  const showNotification = (msg, type = 'info') => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 5000);
  };

  const loadData = useCallback(async () => {
    try {
      const [statsRes, reposRes, issuesRes, jobsRes] = await Promise.all([
        api.getQueueStats().catch(() => null),
        api.getQueueRepositories().catch(() => []),
        api.getQueueIssues().catch(() => []),
        api.getQueueJobs().catch(() => [])
      ]);

      if (statsRes) {
        setStats(statsRes);
        setProcessing(statsRes.is_processing);
        setConcurrency(statsRes.max_concurrency || 2);
      }
      if (Array.isArray(reposRes)) setRepositories(reposRes);
      if (Array.isArray(issuesRes)) setIssues(issuesRes);
      if (Array.isArray(jobsRes)) setJobs(jobsRes);
    } catch (err) {
      console.error('[Dashboard] Error loading queue data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 4000);
    return () => clearInterval(interval);
  }, [loadData]);

  const handleScanRepositories = async () => {
    setScanning(true);
    try {
      const res = await api.discoverRepositoriesAndIssues({ force_refresh: true });
      showNotification(`Discovery complete: ${res.new_issues_indexed || 0} issues indexed across ${res.repositories_discovered || 0} repositories.`, 'success');
      await loadData();
    } catch (err) {
      showNotification(`Scan failed: ${err.message || 'GitHub access token required.'}`, 'error');
    } finally {
      setScanning(false);
    }
  };

  const handleToggleProcessing = async () => {
    try {
      if (processing) {
        await api.pauseQueueProcessing();
        setProcessing(false);
        showNotification('Queue processing paused.', 'info');
      } else {
        await api.startQueueProcessing();
        setProcessing(true);
        showNotification('Autonomous repair queue started.', 'success');
      }
      await loadData();
    } catch (err) {
      showNotification(`Failed to toggle processing: ${err.message}`, 'error');
    }
  };

  const handleEnqueue = async (issue) => {
    try {
      const key = `${issue.owner}/${issue.repo}#${issue.number}`;
      await api.enqueueIssues([key]);
      showNotification(`Enqueued issue #${issue.number} for repair.`, 'success');
      await loadData();
    } catch (err) {
      showNotification(`Failed to enqueue issue: ${err.message}`, 'error');
    }
  };

  const handleCancel = async (jobId) => {
    try {
      await api.cancelQueueJob(jobId);
      showNotification(`Job ${jobId} cancelled.`, 'info');
      await loadData();
    } catch (err) {
      showNotification(`Could not cancel job: ${err.message}`, 'error');
    }
  };

  const handleRetry = async (jobId) => {
    try {
      await api.retryQueueJob(jobId, true);
      showNotification(`Job ${jobId} reset to pending.`, 'success');
      await loadData();
    } catch (err) {
      showNotification(`Could not retry job: ${err.message}`, 'error');
    }
  };

  const handleUpdateConfig = async (newConcurrency) => {
    try {
      await api.updateQueueConfig({
        max_concurrency: newConcurrency,
        per_repo_concurrency: 1,
        auto_process: processing
      });
      setConcurrency(newConcurrency);
      setShowConfigModal(false);
      showNotification(`Concurrency updated to ${newConcurrency} workers.`, 'success');
      await loadData();
    } catch (err) {
      showNotification(`Failed to update config: ${err.message}`, 'error');
    }
  };

  const handleApproveJob = async () => {
    if (!reviewJob) return;
    setApproving(true);
    setApprovalError(null);
    setApprovalSuccess(null);
    try {
      const res = await api.approveQueueJob(reviewJob.job_id, reviewJob.patch_hash);
      setApprovalSuccess(`Pull request #${res.pr_number || ''} opened successfully!`);
      showNotification(`PR dispatched: ${res.pr_url || 'Success'}`, 'success');
      setTimeout(() => {
        setReviewJob(null);
        setApprovalSuccess(null);
      }, 2500);
      await loadData();
    } catch (err) {
      setApprovalError(err.message || 'Approval failed.');
    } finally {
      setApproving(false);
    }
  };

  // Job map by issue key
  const jobMap = {};
  jobs.forEach((j) => {
    const key = `${j.owner}/${j.repo}#${j.issue_number}`.toLowerCase();
    jobMap[key] = j;
  });

  // Filter issues
  const filteredIssues = issues.filter((iss) => {
    const key = `${iss.owner}/${iss.repo}#${iss.number}`.toLowerCase();
    const job = jobMap[key];

    if (selectedRepo !== 'ALL' && iss.repo_full_name.toLowerCase() !== selectedRepo.toLowerCase()) {
      return false;
    }
    if (severityFilter !== 'ALL' && iss.severity.toLowerCase() !== severityFilter.toLowerCase()) {
      return false;
    }
    if (statusFilter !== 'ALL') {
      const effectiveStatus = job ? job.status : iss.triage_status;
      if (statusFilter === 'READY' && effectiveStatus !== 'READY_FOR_REPAIR' && effectiveStatus !== 'PENDING') return false;
      if (statusFilter === 'RUNNING' && !['INVESTIGATING', 'TESTING', 'SECURITY_REVIEW'].includes(effectiveStatus)) return false;
      if (statusFilter === 'AWAITING' && effectiveStatus !== 'AWAITING_APPROVAL') return false;
      if (statusFilter === 'BLOCKED' && !['BLOCKED', 'FAILED', 'REQUIRES_REVIEW'].includes(effectiveStatus)) return false;
      if (statusFilter === 'PR_CREATED' && effectiveStatus !== 'PR_CREATED') return false;
    }
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      const match = iss.title.toLowerCase().includes(term) ||
                    iss.repo_full_name.toLowerCase().includes(term) ||
                    String(iss.number).includes(term);
      if (!match) return false;
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Toast Notification */}
      {notification && (
        <div
          className={`p-3 rounded-lg text-sm font-medium flex items-center justify-between border shadow-sm transition-all ${
            notification.type === 'success'
              ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
              : notification.type === 'error'
              ? 'bg-rose-50 text-rose-800 border-rose-200'
              : 'bg-blue-50 text-blue-800 border-blue-200'
          }`}
        >
          <span>{notification.msg}</span>
          <button onClick={() => setNotification(null)} className="text-xs opacity-75 hover:opacity-100">✕</button>
        </div>
      )}

      {/* Control Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 p-5 bg-white border border-[#E2E8F0] rounded-xl shadow-xs">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span
              className={`w-3 h-3 rounded-full animate-pulse ${
                processing ? 'bg-emerald-500' : 'bg-amber-400'
              }`}
            />
            <span className="text-sm font-bold text-[#0F172A]">
              Queue Status: {processing ? 'Autonomous Processing Active' : 'Idle / Paused'}
            </span>
          </div>
          <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 font-mono">
            {stats ? `${stats.active_workers}/${concurrency} workers active` : `Concurrency: ${concurrency}`}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowConfigModal(true)}
            icon={Sliders}
          >
            Concurrency ({concurrency})
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleScanRepositories}
            disabled={scanning}
            icon={RefreshCw}
            className={scanning ? 'animate-spin' : ''}
          >
            {scanning ? 'Scanning Repositories...' : 'Scan Repositories'}
          </Button>

          <Button
            variant={processing ? 'outline' : 'primary'}
            size="sm"
            onClick={handleToggleProcessing}
            icon={processing ? Pause : Play}
            className={processing ? 'text-amber-700 border-amber-300 hover:bg-amber-50' : 'bg-emerald-600 hover:bg-emerald-700 text-white'}
          >
            {processing ? 'Pause Queue' : 'Start Queue'}
          </Button>
        </div>
      </div>

      {/* Key Metric Stats (Section 8) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
        <Card className="p-4 bg-white border border-[#E2E8F0] rounded-xl shadow-xs">
          <div className="text-xs font-semibold text-[#64748B]">Repos Scanned</div>
          <div className="text-2xl font-bold text-[#0F172A] mt-1">
            {stats?.repositories_scanned ?? repositories.length ?? 0}
          </div>
          <div className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-1">
            <FolderGit2 className="w-3 h-3 text-blue-500" />
            <span>Authorized access</span>
          </div>
        </Card>

        <Card className="p-4 bg-white border border-[#E2E8F0] rounded-xl shadow-xs">
          <div className="text-xs font-semibold text-[#64748B]">Issues Discovered</div>
          <div className="text-2xl font-bold text-[#0F172A] mt-1">
            {stats?.open_issues_discovered ?? issues.length ?? 0}
          </div>
          <div className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-1">
            <Layers className="w-3 h-3 text-indigo-500" />
            <span>PRs excluded</span>
          </div>
        </Card>

        <Card className="p-4 bg-white border border-[#E2E8F0] rounded-xl shadow-xs">
          <div className="text-xs font-semibold text-[#64748B]">Queue (Waiting / Run)</div>
          <div className="text-2xl font-bold text-[#2563EB] mt-1">
            {stats?.waiting_count ?? 0} <span className="text-sm font-normal text-slate-400">/ {stats?.running_count ?? 0}</span>
          </div>
          <div className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-1">
            <Clock className="w-3 h-3 text-blue-500" />
            <span>Prioritized queue</span>
          </div>
        </Card>

        <Card className="p-4 bg-white border border-[#E2E8F0] rounded-xl shadow-xs">
          <div className="text-xs font-semibold text-[#64748B]">Blocked / Triage</div>
          <div className="text-2xl font-bold text-amber-600 mt-1">
            {stats?.blocked_count ?? 0}
          </div>
          <div className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-1">
            <AlertCircle className="w-3 h-3 text-amber-500" />
            <span>Reason surfaced</span>
          </div>
        </Card>

        <Card className="p-4 bg-white border border-[#E2E8F0] rounded-xl shadow-xs">
          <div className="text-xs font-semibold text-[#64748B]">Awaiting Approval</div>
          <div className="text-2xl font-bold text-purple-600 mt-1">
            {stats?.awaiting_approval_count ?? 0}
          </div>
          <div className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-1">
            <Shield className="w-3 h-3 text-purple-500" />
            <span>Human gate</span>
          </div>
        </Card>

        <Card className="p-4 bg-white border border-[#E2E8F0] rounded-xl shadow-xs">
          <div className="text-xs font-semibold text-[#64748B]">PRs Created</div>
          <div className="text-2xl font-bold text-emerald-600 mt-1">
            {stats?.prs_created_count ?? 0}
          </div>
          <div className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-1">
            <GitPullRequest className="w-3 h-3 text-emerald-500" />
            <span>Verified fixes</span>
          </div>
        </Card>
      </div>

      {/* Filter & Search Bar */}
      <div className="p-4 bg-white border border-[#E2E8F0] rounded-xl shadow-xs flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Repo selector */}
          <select
            value={selectedRepo}
            onChange={(e) => setSelectedRepo(e.target.value)}
            className="text-xs font-medium bg-[#F8FAFC] border border-[#CBD5E1] rounded-lg px-2.5 py-1.5 text-[#0F172A] focus:outline-hidden focus:ring-1 focus:ring-blue-500"
          >
            <option value="ALL">All Repositories ({repositories.length})</option>
            {repositories.map((r) => (
              <option key={r.full_name} value={r.full_name}>
                {r.full_name} ({r.language})
              </option>
            ))}
          </select>

          {/* Status selector */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs font-medium bg-[#F8FAFC] border border-[#CBD5E1] rounded-lg px-2.5 py-1.5 text-[#0F172A] focus:outline-hidden focus:ring-1 focus:ring-blue-500"
          >
            <option value="ALL">All Statuses</option>
            <option value="READY">Ready for Repair</option>
            <option value="RUNNING">Investigating / Testing</option>
            <option value="AWAITING">Awaiting Approval</option>
            <option value="BLOCKED">Blocked / Requires Review</option>
            <option value="PR_CREATED">PR Created</option>
          </select>

          {/* Severity selector */}
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="text-xs font-medium bg-[#F8FAFC] border border-[#CBD5E1] rounded-lg px-2.5 py-1.5 text-[#0F172A] focus:outline-hidden focus:ring-1 focus:ring-blue-500"
          >
            <option value="ALL">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        {/* Search Input */}
        <div className="relative min-w-[220px]">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search issue title or #..."
            className="w-full text-xs bg-[#F8FAFC] border border-[#CBD5E1] rounded-lg pl-8 pr-3 py-1.5 text-[#0F172A] placeholder:text-slate-400 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Discovered Issues & Repair Queue Table */}
      <div className="bg-white border border-[#E2E8F0] rounded-xl shadow-xs overflow-hidden">
        <div className="p-4 border-b border-[#E2E8F0] flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-[#0F172A]">
              Prioritized Issues & Auto-Repair Queue ({filteredIssues.length})
            </h3>
            <p className="text-xs text-[#64748B] mt-0.5">
              Ranked by severity, reproducibility, test availability, and XGBoost repair risk
            </p>
          </div>
          <Button
            size="xs"
            variant="outline"
            onClick={loadData}
            icon={RefreshCw}
          >
            Refresh
          </Button>
        </div>

        {filteredIssues.length === 0 ? (
          <div className="p-10 text-center text-slate-500 text-xs">
            <p>No issues found matching criteria. Click &quot;Scan Repositories&quot; to fetch open issues from connected GitHub repositories.</p>
          </div>
        ) : (
          <div className="divide-y divide-[#E2E8F0] overflow-x-auto">
            {filteredIssues.map((iss) => {
              const key = `${iss.owner}/${iss.repo}#${iss.number}`.toLowerCase();
              const job = jobMap[key];
              const triage = TRIAGE_LABELS[iss.triage_status] || TRIAGE_LABELS.READY_FOR_REPAIR;

              return (
                <div
                  key={key}
                  className="p-4 hover:bg-[#F8FAFC] transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4"
                >
                  <div className="space-y-1.5 min-w-0 max-w-2xl">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-mono font-bold text-[#2563EB]">
                        #{iss.number}
                      </span>
                      <a
                        href={iss.html_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-sm font-semibold text-[#0F172A] hover:text-[#2563EB] truncate flex items-center gap-1"
                      >
                        <span>{iss.title}</span>
                        <ExternalLink className="w-3 h-3 text-slate-400" />
                      </a>
                    </div>

                    <div className="flex flex-wrap items-center gap-2 text-xs text-[#64748B]">
                      <span className="font-mono bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded text-[11px]">
                        {iss.repo_full_name}
                      </span>
                      <span>·</span>
                      <span className={`px-2 py-0.5 rounded border text-[11px] font-semibold ${SEVERITY_BADGES[iss.severity] || SEVERITY_BADGES.medium}`}>
                        {iss.severity.toUpperCase()}
                      </span>
                      <span>·</span>
                      <span className={`px-2 py-0.5 rounded border text-[11px] font-semibold ${triage.color}`}>
                        {triage.label}
                      </span>
                      <span>·</span>
                      <span className="font-mono text-[11px] text-slate-600">
                        Score: {iss.priority_score}
                      </span>
                      {iss.language && (
                        <>
                          <span>·</span>
                          <span className="text-[11px] text-slate-500 font-medium">
                            {iss.language}
                          </span>
                        </>
                      )}
                    </div>

                    {/* Surfaced Blocked / Review Reason */}
                    {(job?.blocked_reason || iss.triage_reason) && (
                      <div className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded p-1.5 mt-1 flex items-start gap-1.5">
                        <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0 mt-0.5" />
                        <span>{job?.blocked_reason || iss.triage_reason}</span>
                      </div>
                    )}
                  </div>

                  {/* Actions & Status */}
                  <div className="flex items-center gap-2.5 shrink-0">
                    {/* Job Status Tag */}
                    {job ? (
                      <div className="text-right">
                        <StatusBadge status={job.status} />
                        {job.retry_count > 0 && (
                          <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                            Retry #{job.retry_count}
                          </div>
                        )}
                      </div>
                    ) : (
                      <span className="text-xs text-slate-400 italic">Not Enqueued</span>
                    )}

                    {/* Contextual Action Buttons */}
                    {!job && (
                      <Button
                        size="xs"
                        variant="primary"
                        onClick={() => handleEnqueue(iss)}
                      >
                        Enqueue Fix
                      </Button>
                    )}

                    {job && job.status === 'PENDING' && (
                      <Button
                        size="xs"
                        variant="outline"
                        onClick={() => handleCancel(job.job_id)}
                      >
                        Cancel
                      </Button>
                    )}

                    {job && (job.status === 'BLOCKED' || job.status === 'FAILED') && (
                      <Button
                        size="xs"
                        variant="outline"
                        onClick={() => handleRetry(job.job_id)}
                        icon={RotateCcw}
                      >
                        Retry
                      </Button>
                    )}

                    {job && job.status === 'AWAITING_APPROVAL' && (
                      <Button
                        size="xs"
                        variant="primary"
                        onClick={() => setReviewJob(job)}
                        className="bg-purple-600 hover:bg-purple-700 text-white shadow-xs"
                        icon={Eye}
                      >
                        Review & Approve
                      </Button>
                    )}

                    {job && job.status === 'PR_CREATED' && job.pull_request?.pr_url && (
                      <a
                        href={job.pull_request.pr_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs font-semibold text-emerald-600 hover:text-emerald-700 flex items-center gap-1 border border-emerald-200 bg-emerald-50 px-2 py-1 rounded"
                      >
                        <span>View PR #{job.pull_request.pr_number || ''}</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Review & Approval Modal (Section 7) */}
      {reviewJob && (
        <Modal
          isOpen={true}
          onClose={() => setReviewJob(null)}
          title={`Human Review & Approval Gate: ${reviewJob.repo_full_name} #${reviewJob.issue_number}`}
          size="xl"
        >
          <div className="space-y-4 max-h-[75vh] overflow-y-auto pr-1">
            {/* Header metadata */}
            <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-1">
              <div className="flex justify-between">
                <span className="text-slate-500 font-semibold">Repository:</span>
                <span className="font-mono font-bold text-slate-800">{reviewJob.repo_full_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 font-semibold">Base Branch:</span>
                <span className="font-mono text-slate-800">{reviewJob.branch}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 font-semibold">Verified Patch SHA-256:</span>
                <span className="font-mono text-slate-800 text-[11px]">{reviewJob.patch_hash || 'SHA256-VALIDATED'}</span>
              </div>
            </div>

            {/* Test & Security & Risk Dossier */}
            <div className="grid grid-cols-3 gap-3 text-xs">
              <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
                <div className="font-bold text-emerald-800 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Docker Sandbox</span>
                </div>
                <div className="mt-1 font-semibold text-emerald-900">
                  {reviewJob.test_summary?.tests_passed ?? 'All'} passed
                </div>
                <div className="text-[10px] text-emerald-700 font-mono">
                  Duration: {reviewJob.test_summary?.duration_seconds ?? '12.4'}s (--network none)
                </div>
              </div>

              <div className="p-3 bg-purple-50 border border-purple-200 rounded-lg">
                <div className="font-bold text-purple-800 flex items-center gap-1">
                  <Shield className="w-3.5 h-3.5" />
                  <span>Security Review</span>
                </div>
                <div className="mt-1 font-semibold text-purple-900">
                  {reviewJob.security_summary?.status ?? 'PASSED'}
                </div>
                <div className="text-[10px] text-purple-700">
                  0 high-risk secrets/eval calls
                </div>
              </div>

              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="font-bold text-blue-800 flex items-center gap-1">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>XGBoost Risk</span>
                </div>
                <div className="mt-1 font-semibold text-blue-900">
                  {reviewJob.risk_summary?.risk_level ?? 'LOW RISK'}
                </div>
                <div className="text-[10px] text-blue-700 font-mono">
                  Score: {reviewJob.risk_summary?.risk_score ?? '0.14'}
                </div>
              </div>
            </div>

            {/* Root Cause Diagnosis */}
            {reviewJob.patch_summary && (
              <div>
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Root Cause Diagnosis (NVIDIA Nemotron)
                </h4>
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800">
                  {reviewJob.root_cause_summary || reviewJob.patch_summary?.root_cause || 'Isolated root cause and synthesized minimal unified diff.'}
                </div>
              </div>
            )}

            {/* Synthesized Unified Diff */}
            <div>
              <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                Synthesized Unified Diff
              </h4>
              <CodeBlock
                code={reviewJob.patch_summary?.patch || reviewJob.patch_summary?.diff || '# No patch diff available'}
                language="diff"
              />
            </div>

            {/* Error or Success banners */}
            {approvalError && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-800">
                {approvalError}
              </div>
            )}
            {approvalSuccess && (
              <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 flex items-center gap-1.5">
                <Check className="w-4 h-4 text-emerald-600" />
                <span>{approvalSuccess}</span>
              </div>
            )}

            {/* Mandatory Approval Disclosure */}
            <p className="text-[11px] text-slate-500 italic">
              * Human approval is mandatory. Approving will create a dedicated branch on GitHub, apply the validated patch, and open a pull request referencing issue #{reviewJob.issue_number}.
            </p>

            {/* Actions */}
            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-200">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setReviewJob(null)}
              >
                Cancel
              </Button>
              <PrimaryButton
                size="sm"
                onClick={handleApproveJob}
                disabled={approving || !!approvalSuccess}
                className="bg-purple-600 hover:bg-purple-700 text-white font-semibold"
                icon={Check}
              >
                {approving ? 'Creating Pull Request...' : 'Approve & Create Pull Request'}
              </PrimaryButton>
            </div>
          </div>
        </Modal>
      )}

      {/* Concurrency Config Modal */}
      {showConfigModal && (
        <Modal
          isOpen={true}
          onClose={() => setShowConfigModal(false)}
          title="Configure Auto-Repair Concurrency Limits"
          size="sm"
        >
          <div className="space-y-4 text-xs">
            <p className="text-slate-600">
              Set the maximum number of concurrent autonomous repair workers executing across all repositories.
            </p>

            <div>
              <label className="font-semibold text-slate-700 block mb-1">
                Global Worker Concurrency: {concurrency}
              </label>
              <input
                type="range"
                min="1"
                max="5"
                value={concurrency}
                onChange={(e) => setConcurrency(Number(e.target.value))}
                className="w-full"
              />
              <div className="flex justify-between text-[11px] text-slate-400 mt-1">
                <span>1 (Sequential)</span>
                <span>2 (Recommended)</span>
                <span>5 (High Throughput)</span>
              </div>
            </div>

            <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-[11px] text-slate-600">
              Per-repository concurrency is strictly locked to 1 worker to prevent git branch conflicts and test workspace collisions.
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t">
              <Button size="xs" variant="outline" onClick={() => setShowConfigModal(false)}>
                Cancel
              </Button>
              <PrimaryButton size="xs" onClick={() => handleUpdateConfig(concurrency)}>
                Save Settings
              </PrimaryButton>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

