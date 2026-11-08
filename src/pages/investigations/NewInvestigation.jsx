import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  FolderGit2,
  CheckCircle2,
  Bot,
  GitBranch,
  Lock,
  RefreshCw,
  Search
} from 'lucide-react';
import GithubIcon from '../../components/common/GithubIcon';
import { useApp } from '../../context/AppContext';
import Button, { PrimaryButton } from '../../components/common/Button';
import PayPalBountyCard from '../../components/common/PayPalBountyCard';
import api from '../../services/api';

export default function NewInvestigation() {
  const {
    appMode,
    githubConnected,
    repositories: demoRepositories,
    createInvestigation,
    addNotification
  } = useApp();

  const navigate = useNavigate();
  const location = useLocation();

  const params = new URLSearchParams(location.search);
  const initialRepoParam = params.get('repo');
  const initialIssueParam = params.get('issue');

  // Multi-step progress
  const [currentStep, setCurrentStep] = useState(initialIssueParam ? 3 : 1);

  // Real Mode repositories & loading
  const [realRepos, setRealRepos] = useState([]);
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [repoError, setRepoError] = useState(null);
  const [repoSearch, setRepoSearch] = useState('');

  // Selected Repository & Branches & Issues
  const [selectedRepo, setSelectedRepo] = useState(initialRepoParam || '');
  const [selectedBranch, setSelectedBranch] = useState('main');
  const [branches, setBranches] = useState(['main']);
  const [loadingBranches, setLoadingBranches] = useState(false);

  const [realIssues, setRealIssues] = useState([]);
  const [loadingIssues, setLoadingIssues] = useState(false);
  const [issuesError, setIssuesError] = useState(null);

  const [selectedIssueNumber, setSelectedIssueNumber] = useState(initialIssueParam ? Number(initialIssueParam) : null);
  const [selectedIssueUrl, setSelectedIssueUrl] = useState('');
  const [issueTitle, setIssueTitle] = useState('');
  const [issueDescription, setIssueDescription] = useState('');

  // Execution options
  const [testingEnabled, setTestingEnabled] = useState(true);
  const [securityEnabled, setSecurityEnabled] = useState(true);
  const [paypalBountyOrder, setPaypalBountyOrder] = useState(null);
  const [loading, setLoading] = useState(false);

  // Fetch real repositories in REAL mode
  const fetchRealRepos = useCallback(async () => {
    if (appMode !== 'REAL' || !githubConnected) return;
    setLoadingRepos(true);
    setRepoError(null);
    try {
      const repos = await api.getGithubRepositories();
      setRealRepos(repos || []);
      if (!selectedRepo && repos && repos.length > 0) {
        const first = repos[0];
        setSelectedRepo(first.full_name || first.name);
        setSelectedBranch(first.default_branch || 'main');
      }
    } catch (err) {
      setRepoError(err.message || 'Failed to fetch repositories from GitHub.');
    } finally {
      setLoadingRepos(false);
    }
  }, [appMode, githubConnected, selectedRepo]);

  useEffect(() => {
    if (appMode === 'REAL' && githubConnected) {
      fetchRealRepos();
    } else if (appMode === 'DEMO') {
      const defaultDemo = demoRepositories[0]?.name || 'demo-react-app';
      if (!selectedRepo) {
        setSelectedRepo(initialRepoParam || defaultDemo);
      }
    }
  }, [appMode, githubConnected, fetchRealRepos, demoRepositories, initialRepoParam, selectedRepo]);

  // When initialRepoParam changes or on mount
  useEffect(() => {
    if (initialRepoParam) {
      setSelectedRepo(initialRepoParam);
    }
  }, [initialRepoParam]);

  // Current active repository object
  const activeRepo =
    appMode === 'REAL'
      ? realRepos.find((r) => r.full_name === selectedRepo || r.name === selectedRepo) || realRepos[0]
      : demoRepositories.find((r) => r.name === selectedRepo) || demoRepositories[0];

  // Fetch branches and issues when selected repository changes
  useEffect(() => {
    if (!selectedRepo) return;

    if (appMode === 'REAL' && githubConnected) {
      const parts = selectedRepo.split('/');
      const owner = parts.length > 1 ? parts[0] : activeRepo?.owner?.login || activeRepo?.owner || 'owner';
      const repoName = parts.length > 1 ? parts[1] : selectedRepo;

      // Fetch branches
      setLoadingBranches(true);
      api.getGithubBranches(owner, repoName)
        .then((branchList) => {
          if (Array.isArray(branchList) && branchList.length > 0) {
            const names = branchList.map((b) => b.name);
            setBranches(names);
            const defaultBranch = activeRepo?.default_branch || 'main';
            setSelectedBranch(names.includes(defaultBranch) ? defaultBranch : names[0]);
          } else {
            setBranches(['main']);
            setSelectedBranch('main');
          }
        })
        .catch(() => {
          setBranches(['main']);
          setSelectedBranch('main');
        })
        .finally(() => setLoadingBranches(false));

      // Fetch issues
      setLoadingIssues(true);
      setIssuesError(null);
      api.getGithubIssues(owner, repoName, 'open')
        .then((issueList) => {
          const filtered = (issueList || []).filter((iss) => !iss.pull_request);
          setRealIssues(filtered);

          if (initialIssueParam) {
            const matched = filtered.find((i) => String(i.number) === String(initialIssueParam));
            if (matched) {
              setSelectedIssueNumber(matched.number);
              setIssueTitle(matched.title);
              setIssueDescription(matched.body || '');
              setSelectedIssueUrl(matched.html_url || '');
            }
          }
        })
        .catch((err) => {
          setIssuesError(err.message || 'Failed to fetch issues.');
          setRealIssues([]);
        })
        .finally(() => setLoadingIssues(false));
    } else if (appMode === 'DEMO') {
      const demoRepo = demoRepositories.find((r) => r.name === selectedRepo) || demoRepositories[0];
      setSelectedBranch(demoRepo?.defaultBranch || 'main');
      setBranches([demoRepo?.defaultBranch || 'main']);

      if (initialIssueParam && demoRepo?.issues) {
        const matched = demoRepo.issues.find((i) => String(i.number) === String(initialIssueParam));
        if (matched) {
          setSelectedIssueNumber(matched.number);
          setIssueTitle(matched.title);
          setIssueDescription(matched.description || '');
        }
      }
    }
  }, [selectedRepo, appMode, githubConnected, activeRepo, demoRepositories, initialIssueParam]);

  // Handle selecting an issue
  const handleSelectIssue = (iss) => {
    setSelectedIssueNumber(iss.number);
    setIssueTitle(iss.title);
    setIssueDescription(iss.body || iss.description || '');
    setSelectedIssueUrl(iss.html_url || '');
    setCurrentStep(3);
  };

  // Launch Investigation
  const handleStartInvestigation = async () => {
    setLoading(true);
    addNotification('Initializing agent sandbox and AST indexer...', 'info');

    try {
      const parts = selectedRepo.split('/');
      const owner = parts.length > 1 ? parts[0] : activeRepo?.owner?.login || activeRepo?.owner || 'owner';
      const repoName = parts.length > 1 ? parts[1] : selectedRepo;

      const newInv = await createInvestigation({
        repository: selectedRepo,
        owner,
        repo: repoName,
        branch: selectedBranch,
        issue_number: selectedIssueNumber || 42,
        issueNumber: selectedIssueNumber || 42,
        issue_title: issueTitle || `Issue #${selectedIssueNumber || 42}`,
        issueTitle: issueTitle || `Issue #${selectedIssueNumber || 42}`,
        issue_url: selectedIssueUrl || `https://github.com/${owner}/${repoName}/issues/${selectedIssueNumber || 42}`,
        error_description: issueDescription || '',
        errorDescription: issueDescription || '',
        mode: appMode === 'REAL' ? 'real' : 'demo',
        paypal_order_id: paypalBountyOrder?.order_id || null,
        paypal_bounty: paypalBountyOrder || null
      });

      setLoading(false);
      navigate(`/investigations/${newInv?.id || '1'}`);
    } catch (err) {
      setLoading(false);
      addNotification(`Failed to start investigation: ${err.message}`, 'error');
    }
  };

  const steps = [
    { num: 1, title: 'Repository', label: '01 Repository' },
    { num: 2, title: 'Issue', label: '02 Issue' },
    { num: 3, title: 'Configuration', label: '03 Review' },
    { num: 4, title: 'Summary', label: '04 Start' },
  ];

  // List of repos to display in Step 1
  const repoList = appMode === 'REAL' ? realRepos : demoRepositories;
  const filteredRepos = repoList.filter((r) => {
    const term = repoSearch.toLowerCase();
    const name = (r.full_name || r.name || '').toLowerCase();
    const desc = (r.description || '').toLowerCase();
    return name.includes(term) || desc.includes(term);
  });

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Page Title */}
      <div className="pb-6 border-b border-[#E2E8F0]">
        <div className="flex items-center gap-2.5">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#0F172A]">
            New Investigation
          </h1>
          <span
            className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border ${
              appMode === 'REAL'
                ? 'bg-[#EFF6FF] text-[#2563EB] border-[#BFDBFE]'
                : 'bg-[#FEF3C7] text-[#B45309] border-[#FDE68A]'
            }`}
          >
            {appMode === 'REAL' ? 'Real GitHub Mode' : 'Demo Mode'}
          </span>
        </div>
        <p className="text-sm text-[#64748B] mt-1">
          Configure an autonomous software engineering investigation order.
        </p>
      </div>

      {/* Step Indicator */}
      <div className="grid grid-cols-4 gap-2 sm:gap-4">
        {steps.map((s) => {
          const isDone = currentStep > s.num;
          const isCurrent = currentStep === s.num;

          return (
            <div
              key={s.num}
              onClick={() => {
                if (isDone) setCurrentStep(s.num);
              }}
              className={`p-3 rounded-xl border transition-all select-none ${
                isCurrent
                  ? 'bg-white border-[#2563EB] shadow-xs'
                  : isDone
                  ? 'bg-[#F8FAFC] border-[#E2E8F0] cursor-pointer hover:border-slate-300'
                  : 'bg-white border-[#E2E8F0] opacity-50'
              }`}
            >
              <div className="flex items-center gap-2">
                <span
                  className={`w-5 h-5 rounded-full text-xs font-bold flex items-center justify-center ${
                    isDone
                      ? 'bg-[#16A34A] text-white'
                      : isCurrent
                      ? 'bg-[#2563EB] text-white'
                      : 'bg-slate-200 text-slate-600'
                  }`}
                >
                  {isDone ? '✓' : s.num}
                </span>
                <span className="text-xs font-semibold text-[#0F172A] hidden sm:inline">
                  {s.label}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* STEP 1: SELECT REPOSITORY */}
      {currentStep === 1 && (
        <div className="space-y-6">
          <div>
            <h2 className="text-lg font-bold text-[#0F172A]">Step 1: Select Repository</h2>
            <p className="text-xs text-[#64748B] mt-0.5">
              Choose the repository where the bug was reported.
            </p>
          </div>

          {/* REAL MODE: GitHub Not Connected */}
          {appMode === 'REAL' && !githubConnected ? (
            <div className="p-8 rounded-2xl bg-gradient-to-b from-[#F8FAFC] to-[#EFF6FF]/40 border border-[#BFDBFE] text-center space-y-4">
              <div className="w-12 h-12 rounded-xl bg-[#0F172A] text-white flex items-center justify-center mx-auto">
                <GithubIcon className="w-6 h-6" />
              </div>
              <h3 className="text-base font-bold text-[#0F172A]">
                Connect GitHub to Select a Repository
              </h3>
              <p className="text-xs text-[#64748B] max-w-md mx-auto">
                In Real Mode, DevRescue AI needs GitHub authorization to fetch your accessible repositories and open bug tickets.
              </p>
              <div>
                <PrimaryButton onClick={() => api.githubLogin()} icon={GithubIcon} size="md">
                  Connect GitHub Account
                </PrimaryButton>
              </div>
            </div>
          ) : (
            <>
              {/* Search input if more than 4 repos */}
              {repoList.length > 4 && (
                <div className="relative">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    value={repoSearch}
                    onChange={(e) => setRepoSearch(e.target.value)}
                    placeholder="Search repositories..."
                    className="w-full pl-10 pr-4 py-2 bg-white border border-[#E2E8F0] rounded-xl text-xs text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB]"
                  />
                </div>
              )}

              {loadingRepos ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {[1, 2, 3, 4].map((i) => (
                    <div
                      key={i}
                      className="p-5 rounded-xl border border-[#E2E8F0] bg-white animate-pulse space-y-3"
                    >
                      <div className="h-4 bg-slate-200 rounded w-1/2" />
                      <div className="h-3 bg-slate-100 rounded w-3/4" />
                      <div className="h-3 bg-slate-100 rounded w-1/3" />
                    </div>
                  ))}
                </div>
              ) : repoError ? (
                <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center justify-between">
                  <span>{repoError}</span>
                  <Button variant="outline" size="sm" onClick={fetchRealRepos}>
                    Retry
                  </Button>
                </div>
              ) : filteredRepos.length === 0 ? (
                <div className="p-8 text-center bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-xs text-[#64748B]">
                  No repositories found matching "{repoSearch}".
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {filteredRepos.map((repo) => {
                    const repoFullName = repo.full_name || repo.name;
                    const isSelected = selectedRepo === repoFullName;
                    const isPrivate = Boolean(repo.private);

                    return (
                      <div
                        key={repo.id || repoFullName}
                        onClick={() => {
                          setSelectedRepo(repoFullName);
                          setSelectedBranch(repo.default_branch || repo.defaultBranch || 'main');
                        }}
                        className={`p-5 rounded-xl border cursor-pointer transition-all ${
                          isSelected
                            ? 'bg-[#EFF6FF] border-[#2563EB] shadow-xs'
                            : 'bg-white border-[#E2E8F0] hover:border-slate-300'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2 min-w-0">
                            <FolderGit2 className={`w-4 h-4 flex-shrink-0 ${isSelected ? 'text-[#2563EB]' : 'text-slate-500'}`} />
                            <h3 className="text-sm font-bold text-[#0F172A] truncate">
                              {repoFullName}
                            </h3>
                          </div>
                          {isSelected ? (
                            <CheckCircle2 className="w-4 h-4 text-[#2563EB] flex-shrink-0" />
                          ) : isPrivate ? (
                            <Lock className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                          ) : null}
                        </div>
                        <p className="text-xs text-[#64748B] line-clamp-2">
                          {repo.description || 'No description provided.'}
                        </p>
                        <div className="flex items-center gap-3 mt-3 text-xs text-[#64748B]">
                          <span>{repo.language || 'Codebase'}</span>
                          <span>·</span>
                          <span className="font-mono">{repo.default_branch || repo.defaultBranch || 'main'}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              <div className="flex justify-end pt-4 border-t border-[#E2E8F0]">
                <PrimaryButton
                  onClick={() => setCurrentStep(2)}
                  disabled={!selectedRepo}
                  arrow={true}
                  size="md"
                >
                  Continue to Issue Selection
                </PrimaryButton>
              </div>
            </>
          )}
        </div>
      )}

      {/* STEP 2: SELECT ISSUE & BRANCH */}
      {currentStep === 2 && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-[#0F172A]">Step 2: Select Issue & Branch</h2>
              <p className="text-xs text-[#64748B] mt-0.5">
                Target codebase: <strong className="text-[#0F172A] font-mono">{selectedRepo}</strong>
              </p>
            </div>
            <button
              type="button"
              onClick={() => setCurrentStep(1)}
              className="text-xs text-[#2563EB] hover:underline"
            >
              Change Repository
            </button>
          </div>

          {/* Branch Selector */}
          <div className="p-4 bg-white border border-[#E2E8F0] rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-xs">
              <GitBranch className="w-4 h-4 text-[#2563EB]" />
              <span className="font-semibold text-[#0F172A]">Target Branch:</span>
              <span className="text-[#64748B]">Investigation will branch off this commit ref</span>
            </div>

            <div className="flex items-center gap-2">
              <select
                value={selectedBranch}
                onChange={(e) => setSelectedBranch(e.target.value)}
                disabled={loadingBranches}
                className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg px-3 py-1.5 text-xs font-mono font-semibold text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB]"
              >
                {branches.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Real Issues List */}
          {appMode === 'REAL' ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-[#0F172A]">
                  Open GitHub Issues
                </span>
                {loadingIssues && (
                  <span className="text-xs text-[#64748B] flex items-center gap-1.5">
                    <RefreshCw className="w-3 h-3 animate-spin text-[#2563EB]" />
                    Fetching issues...
                  </span>
                )}
              </div>

              {loadingIssues ? (
                <div className="p-8 text-center text-xs text-[#64748B] space-y-2">
                  <div className="w-5 h-5 border-2 border-[#2563EB] border-t-transparent rounded-full animate-spin mx-auto" />
                  <span>Loading open issues for {selectedRepo}...</span>
                </div>
              ) : issuesError ? (
                <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-xs text-red-700">
                  {issuesError}
                </div>
              ) : realIssues.length === 0 ? (
                <div className="p-6 text-center bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-xs space-y-1">
                  <CheckCircle2 className="w-5 h-5 text-[#16A34A] mx-auto" />
                  <p className="font-semibold text-[#0F172A]">No open issues found in this repository.</p>
                  <p className="text-[#64748B]">You can manually specify a bug report below to trigger an investigation.</p>
                </div>
              ) : (
                <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                  {realIssues.map((iss) => {
                    const isSelected = selectedIssueNumber === iss.number;
                    return (
                      <div
                        key={iss.id || iss.number}
                        onClick={() => handleSelectIssue(iss)}
                        className={`p-4 rounded-xl border cursor-pointer transition-all flex items-start justify-between gap-4 ${
                          isSelected
                            ? 'bg-[#EFF6FF] border-[#2563EB] shadow-xs'
                            : 'bg-white border-[#E2E8F0] hover:border-slate-300'
                        }`}
                      >
                        <div className="space-y-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs font-bold text-[#2563EB]">
                              #{iss.number}
                            </span>
                            <h4 className="text-sm font-bold text-[#0F172A] truncate">
                              {iss.title}
                            </h4>
                            <span className="text-[10px] font-semibold text-[#16A34A] bg-[#DCFCE7] px-2 py-0.2 rounded-full">
                              Open
                            </span>
                          </div>
                          <p className="text-xs text-[#64748B] line-clamp-2">
                            {iss.body || 'No description provided.'}
                          </p>
                          <div className="text-[11px] text-[#64748B]">
                            Opened by @{iss.user?.login || iss.author || 'maintainer'}
                          </div>
                        </div>

                        <div className="flex-shrink-0 pt-1">
                          <span
                            className={`w-4 h-4 rounded-full border flex items-center justify-center ${
                              isSelected ? 'border-[#2563EB] bg-[#2563EB]' : 'border-slate-300'
                            }`}
                          >
                            {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-white" />}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ) : (
            /* Demo Mode Issues List */
            <div className="space-y-3">
              {(activeRepo?.issues || []).map((iss) => {
                const isSelected = selectedIssueNumber === iss.number;
                return (
                  <div
                    key={iss.id || iss.number}
                    onClick={() => handleSelectIssue(iss)}
                    className={`p-4 rounded-xl border cursor-pointer transition-all flex items-start justify-between gap-4 ${
                      isSelected
                        ? 'bg-[#EFF6FF] border-[#2563EB] shadow-xs'
                        : 'bg-white border-[#E2E8F0] hover:border-slate-300'
                    }`}
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-[#2563EB]">
                          #{iss.number}
                        </span>
                        <h4 className="text-sm font-bold text-[#0F172A]">
                          {iss.title}
                        </h4>
                        <span className="text-[11px] font-semibold text-[#16A34A] bg-[#DCFCE7] px-2 py-0.2 rounded-full">
                          {iss.status || 'Open'}
                        </span>
                      </div>
                      <p className="text-xs text-[#64748B]">
                        {iss.description}
                      </p>
                    </div>

                    <div className="flex-shrink-0 pt-1">
                      <span
                        className={`w-4 h-4 rounded-full border flex items-center justify-center ${
                          isSelected ? 'border-[#2563EB] bg-[#2563EB]' : 'border-slate-300'
                        }`}
                      >
                        {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-white" />}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Or custom issue input */}
          <div className="p-5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-[#0F172A]">
              Or Specify Custom Issue / Bug Report
            </h4>
            <div>
              <label className="block text-xs font-semibold text-[#0F172A] mb-1">
                Issue Title *
              </label>
              <input
                type="text"
                value={issueTitle}
                onChange={(e) => {
                  setIssueTitle(e.target.value);
                  if (!selectedIssueNumber) setSelectedIssueNumber(99);
                }}
                placeholder="e.g. Uncaught TypeError in authenticateUser"
                className="w-full rounded-lg bg-white border border-[#E2E8F0] px-3.5 py-2 text-sm text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB]"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#0F172A] mb-1">
                Error Stacktrace or Description
              </label>
              <textarea
                rows={3}
                value={issueDescription}
                onChange={(e) => setIssueDescription(e.target.value)}
                placeholder="Paste runtime stacktrace, reproduce steps, or log output..."
                className="w-full rounded-lg bg-white border border-[#E2E8F0] px-3.5 py-2 text-sm text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB]"
              />
            </div>
          </div>

          {/* PayPal Bug Bounty Card */}
          <PayPalBountyCard
            repository={selectedRepo}
            issueNumber={selectedIssueNumber}
            issueTitle={issueTitle}
            errorDescription={issueDescription}
            onBountyFunded={(order) => {
              setPaypalBountyOrder(order);
              addNotification(`PayPal Sandbox Bounty Authorized: ${order.order_id} ($${order.amount})`, 'success');
            }}
            fundedOrder={paypalBountyOrder}
          />

          <div className="flex items-center justify-between pt-4 border-t border-[#E2E8F0]">
            <Button variant="outline" size="md" onClick={() => setCurrentStep(1)}>
              Back
            </Button>
            <PrimaryButton
              onClick={() => setCurrentStep(3)}
              disabled={!issueTitle}
              arrow={true}
              size="md"
            >
              Continue to Configuration
            </PrimaryButton>
          </div>
        </div>
      )}

      {/* STEP 3: INVESTIGATION CONFIGURATION */}
      {currentStep === 3 && (
        <div className="space-y-6">
          <div>
            <h2 className="text-lg font-bold text-[#0F172A]">
              Step 3: Investigation Configuration
            </h2>
            <p className="text-xs text-[#64748B] mt-0.5">
              Review parameters and choose execution flags.
            </p>
          </div>

          {/* Target Preview Card */}
          <div className="p-4 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div>
              <span className="text-[#64748B] block">Repository</span>
              <span className="font-semibold text-[#0F172A] mt-0.5 block font-mono truncate">{selectedRepo}</span>
            </div>
            <div>
              <span className="text-[#64748B] block">Target Issue</span>
              <span className="font-semibold text-[#0F172A] mt-0.5 block truncate">
                {selectedIssueNumber ? `#${selectedIssueNumber} ` : ''}{issueTitle}
              </span>
            </div>
            <div>
              <span className="text-[#64748B] block">Branch</span>
              <span className="font-semibold text-[#0F172A] mt-0.5 block font-mono">{selectedBranch}</span>
            </div>
          </div>

          {/* Config Controls */}
          <div className="space-y-4">
            {/* AI Mode */}
            <div className="p-4 bg-white border border-[#E2E8F0] rounded-xl flex items-center justify-between">
              <div>
                <span className="text-sm font-bold text-[#0F172A] block">
                  AI Mode: Standard Investigation
                </span>
                <span className="text-xs text-[#64748B] block mt-0.5">
                  Multi-agent pipeline (Analyzer → Investigator → Repair → Testing → Security)
                </span>
              </div>
              <span className="text-xs font-semibold text-[#2563EB] bg-[#EFF6FF] px-2.5 py-1 rounded-full border border-[#BFDBFE]">
                Active
              </span>
            </div>

            {/* Testing */}
            <div className="p-4 bg-white border border-[#E2E8F0] rounded-xl flex items-center justify-between">
              <div>
                <span className="text-sm font-bold text-[#0F172A] block">
                  Testing: Run existing test suite
                </span>
                <span className="text-xs text-[#64748B] block mt-0.5">
                  Execute unit &amp; regression tests in ephemeral container sandbox
                </span>
              </div>
              <button
                type="button"
                onClick={() => setTestingEnabled(!testingEnabled)}
                className={`w-11 h-6 rounded-full transition-colors relative flex items-center px-0.5 cursor-pointer ${
                  testingEnabled ? 'bg-[#2563EB]' : 'bg-slate-300'
                }`}
              >
                <span
                  className={`w-5 h-5 rounded-full bg-white shadow-xs transform transition-transform ${
                    testingEnabled ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>

            {/* Security */}
            <div className="p-4 bg-white border border-[#E2E8F0] rounded-xl flex items-center justify-between">
              <div>
                <span className="text-sm font-bold text-[#0F172A] block">
                  Security: Full security review
                </span>
                <span className="text-xs text-[#64748B] block mt-0.5">
                  Scan for exposed credentials, secret leakage, and dependency changes
                </span>
              </div>
              <button
                type="button"
                onClick={() => setSecurityEnabled(!securityEnabled)}
                className={`w-11 h-6 rounded-full transition-colors relative flex items-center px-0.5 cursor-pointer ${
                  securityEnabled ? 'bg-[#2563EB]' : 'bg-slate-300'
                }`}
              >
                <span
                  className={`w-5 h-5 rounded-full bg-white shadow-xs transform transition-transform ${
                    securityEnabled ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>
          </div>

          {/* PayPal Bug Bounty Card */}
          <PayPalBountyCard
            repository={selectedRepo}
            issueNumber={selectedIssueNumber}
            issueTitle={issueTitle}
            errorDescription={issueDescription}
            onBountyFunded={(order) => {
              setPaypalBountyOrder(order);
              addNotification(`PayPal Sandbox Bounty Authorized: ${order.order_id} ($${order.amount})`, 'success');
            }}
            fundedOrder={paypalBountyOrder}
          />

          <div className="flex items-center justify-between pt-4 border-t border-[#E2E8F0]">
            <Button variant="outline" size="md" onClick={() => setCurrentStep(2)}>
              Back
            </Button>
            <PrimaryButton onClick={() => setCurrentStep(4)} arrow={true} size="md">
              Review Summary
            </PrimaryButton>
          </div>
        </div>
      )}

      {/* STEP 4: REVIEW SUMMARY & START */}
      {currentStep === 4 && (
        <div className="space-y-6">
          <div>
            <h2 className="text-lg font-bold text-[#0F172A]">
              Step 4: Review Order Summary
            </h2>
            <p className="text-xs text-[#64748B] mt-0.5">
              Verify your order specifications before launching the autonomous agents.
            </p>
          </div>

          <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 divide-y divide-[#E2E8F0] space-y-4">
            <div className="flex items-center justify-between pb-2">
              <span className="text-xs text-[#64748B]">Repository:</span>
              <span className="text-sm font-bold text-[#0F172A] font-mono">
                {selectedRepo}
              </span>
            </div>

            <div className="flex items-center justify-between py-2">
              <span className="text-xs text-[#64748B]">Target Issue:</span>
              <span className="text-sm font-bold text-[#0F172A] truncate max-w-sm">
                {selectedIssueNumber ? `#${selectedIssueNumber} ` : ''}{issueTitle}
              </span>
            </div>

            <div className="flex items-center justify-between py-2">
              <span className="text-xs text-[#64748B]">Branch:</span>
              <span className="text-sm font-bold text-[#0F172A] font-mono">
                {selectedBranch}
              </span>
            </div>

            <div className="flex items-center justify-between py-2">
              <span className="text-xs text-[#64748B]">Agents Commissioned:</span>
              <span className="text-sm font-bold text-[#2563EB]">
                5 Autonomous Agents
              </span>
            </div>

            <div className="flex items-center justify-between py-2">
              <span className="text-xs text-[#64748B]">Testing Sandbox:</span>
              <span className="text-xs font-semibold text-[#16A34A] bg-[#DCFCE7] px-2 py-0.5 rounded-full">
                {testingEnabled ? 'Enabled' : 'Disabled'}
              </span>
            </div>

            <div className="flex items-center justify-between py-2">
              <span className="text-xs text-[#64748B]">Security Review:</span>
              <span className="text-xs font-semibold text-[#16A34A] bg-[#DCFCE7] px-2 py-0.5 rounded-full">
                {securityEnabled ? 'Enabled' : 'Disabled'}
              </span>
            </div>

            {paypalBountyOrder && (
              <div className="flex items-center justify-between py-2 border-t border-[#E2E8F0]">
                <span className="text-xs text-blue-600 font-semibold flex items-center gap-1">
                  <span>PayPal Bounty Escrow:</span>
                </span>
                <div className="text-right">
                  <span className="text-sm font-bold text-emerald-600 font-mono">
                    ${paypalBountyOrder.amount} {paypalBountyOrder.currency}
                  </span>
                  <span className="ml-2 text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-100 text-emerald-700">
                    VERIFICATION-GATED
                  </span>
                </div>
              </div>
            )}
          </div>

          <div className="p-4 bg-[#EFF6FF] border border-[#BFDBFE] rounded-xl flex items-center gap-3 text-xs text-[#2563EB]">
            <Bot className="w-5 h-5 flex-shrink-0" />
            <span>
              DevRescue AI will analyze the repository graph, isolate the root cause, synthesize a minimal patch, and evaluate patch risk.
            </span>
          </div>

          <div className="flex items-center justify-between pt-4 border-t border-[#E2E8F0]">
            <Button variant="outline" size="md" onClick={() => setCurrentStep(3)}>
              Back
            </Button>
            <PrimaryButton
              onClick={handleStartInvestigation}
              loading={loading}
              arrow={true}
              size="lg"
            >
              Start Investigation
            </PrimaryButton>
          </div>
        </div>
      )}
    </div>
  );
}
