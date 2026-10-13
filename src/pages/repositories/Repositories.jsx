import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  FolderGit2,
  Plus,
  AlertCircle,
  RefreshCw,
  ExternalLink,
  Lock,
  Star,
  GitFork,
  GitBranch,
  CheckCircle2,
  LogOut
} from 'lucide-react';
import GithubIcon from '../../components/common/GithubIcon';
import { useApp } from '../../context/AppContext';
import Button, { PrimaryButton } from '../../components/common/Button';
import Card from '../../components/common/Card';
import Modal from '../../components/common/Modal';
import { SearchInput } from '../../components/common/FormInputs';
import EmptyState from '../../components/common/EmptyState';
import api from '../../services/api';

const LANGUAGE_COLORS = {
  JavaScript: '#F7DF1E',
  TypeScript: '#3178C6',
  Python: '#3572A5',
  Go: '#00ADD8',
  Rust: '#DEA584',
  HTML: '#E34F26',
  CSS: '#563D7C',
  Java: '#B07219',
  Ruby: '#701516',
  PHP: '#4F5D95',
  'C++': '#F34B7D',
  'C#': '#178600',
  Shell: '#89E051',
  React: '#61DAFB'
};

export default function Repositories() {
  const {
    appMode,
    githubUser,
    githubConnected,
    githubLoading,
    checkGithubStatus,
    disconnectGithub,
    repositories: demoRepositories,
    connectRepository,
    addNotification
  } = useApp();

  const [searchParams, setSearchParams] = useSearchParams();

  // URL query parameter handling (from GitHub OAuth redirect)
  useEffect(() => {
    const isConnected = searchParams.get('github_connected');
    const githubError = searchParams.get('github_error');

    if (isConnected === 'true') {
      checkGithubStatus();
      addNotification('✓ GitHub connected successfully!', 'success');
      searchParams.delete('github_connected');
      setSearchParams(searchParams, { replace: true });
    } else if (githubError) {
      addNotification(`GitHub connection error: ${githubError}`, 'error');
      searchParams.delete('github_error');
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, checkGithubStatus, addNotification, setSearchParams]);

  // Real Mode state
  const [realRepos, setRealRepos] = useState([]);
  const [loadingRealRepos, setLoadingRealRepos] = useState(false);
  const [realRepoError, setRealRepoError] = useState(null);

  // Search & Filter
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('All');

  // Modal State
  const [selectedRepo, setSelectedRepo] = useState(null);
  const [selectedRepoIssues, setSelectedRepoIssues] = useState([]);
  const [loadingIssues, setLoadingIssues] = useState(false);
  const [issuesError, setIssuesError] = useState(null);

  // Demo connect modal state
  const [connectModalOpen, setConnectModalOpen] = useState(false);
  const [newRepoName, setNewRepoName] = useState('');
  const [newRepoLang, setNewRepoLang] = useState('React');
  const [newRepoDesc, setNewRepoDesc] = useState('');

  // Fetch real repositories from GitHub API
  const fetchRealRepositories = useCallback(async () => {
    if (!githubConnected) return;
    setLoadingRealRepos(true);
    setRealRepoError(null);
    try {
      const repos = await api.getGithubRepositories();
      setRealRepos(repos || []);
    } catch (err) {
      setRealRepoError(err.message || 'Failed to fetch repositories from GitHub.');
      addNotification(`Failed to load GitHub repositories: ${err.message}`, 'error');
    } finally {
      setLoadingRealRepos(false);
    }
  }, [githubConnected, addNotification]);

  useEffect(() => {
    if (appMode === 'REAL' && githubConnected) {
      fetchRealRepositories();
    }
  }, [appMode, githubConnected, fetchRealRepositories]);

  // Fetch issues when viewing issues modal
  const handleOpenIssues = async (repo) => {
    setSelectedRepo(repo);
    if (appMode === 'REAL') {
      setLoadingIssues(true);
      setIssuesError(null);
      setSelectedRepoIssues([]);
      try {
        const owner = repo.owner?.login || repo.owner || repo.full_name?.split('/')[0];
        const repoName = repo.name || repo.full_name?.split('/')[1];
        const issues = await api.getGithubIssues(owner, repoName, 'open');
        setSelectedRepoIssues(issues || []);
      } catch (err) {
        setIssuesError(err.message || 'Failed to load issues from GitHub.');
      } finally {
        setLoadingIssues(false);
      }
    }
  };

  // Connect GitHub trigger
  const handleConnectGithub = () => {
    api.githubLogin();
  };

  // Demo connect submit
  const handleDemoConnectSubmit = (e) => {
    e.preventDefault();
    if (!newRepoName) return;
    connectRepository({
      name: newRepoName,
      language: newRepoLang,
      filterCategory: newRepoLang,
      description: newRepoDesc || 'Custom connected repository via DevRescue AI demo.',
      filesCount: Math.floor(Math.random() * 80) + 50
    });
    setNewRepoName('');
    setNewRepoDesc('');
    setConnectModalOpen(false);
  };

  // Derive filter categories
  const currentRepositories = appMode === 'REAL' ? realRepos : demoRepositories;

  const dynamicLanguages = Array.from(
    new Set(
      currentRepositories
        .map((r) => r.language)
        .filter(Boolean)
    )
  ).slice(0, 5);

  const filterOptions = ['All', ...dynamicLanguages];

  // Filter repositories
  const filtered = currentRepositories.filter((repo) => {
    const nameMatch =
      (repo.name && repo.name.toLowerCase().includes(search.toLowerCase())) ||
      (repo.full_name && repo.full_name.toLowerCase().includes(search.toLowerCase())) ||
      (repo.description && repo.description.toLowerCase().includes(search.toLowerCase()));

    if (filter === 'All') return nameMatch;
    return nameMatch && repo.language === filter;
  });

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-[#E2E8F0]">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#0F172A]">
              Repositories
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
            {appMode === 'REAL'
              ? 'Browse and select repositories connected via your authenticated GitHub account.'
              : 'Manage prototype repositories available for simulated investigations.'}
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          {appMode === 'REAL' ? (
            githubConnected ? (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={fetchRealRepositories}
                  loading={loadingRealRepos}
                  icon={RefreshCw}
                >
                  Refresh
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={disconnectGithub}
                  icon={LogOut}
                  className="text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
                >
                  Disconnect
                </Button>
              </>
            ) : (
              <PrimaryButton onClick={handleConnectGithub} icon={GithubIcon} size="sm">
                Connect GitHub
              </PrimaryButton>
            )
          ) : (
            <PrimaryButton
              onClick={() => setConnectModalOpen(true)}
              icon={Plus}
              size="sm"
            >
              Add Demo Repo
            </PrimaryButton>
          )}
        </div>
      </div>

      {/* REAL MODE: GitHub User Profile Banner (when connected) */}
      {appMode === 'REAL' && githubConnected && githubUser && (
        <div className="p-4 sm:p-5 rounded-2xl bg-gradient-to-r from-[#F8FAFC] via-[#EFF6FF]/40 to-white border border-[#E2E8F0] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            {githubUser.avatar_url ? (
              <img
                src={githubUser.avatar_url}
                alt={githubUser.login}
                className="w-12 h-12 rounded-full ring-2 ring-[#2563EB]/20 border border-white object-cover"
              />
            ) : (
              <div className="w-12 h-12 rounded-full bg-[#2563EB] text-white flex items-center justify-center font-bold">
                {githubUser.login?.[0]?.toUpperCase() || 'U'}
              </div>
            )}
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-[#0F172A] text-base">
                  {githubUser.name || githubUser.login}
                </span>
                <span className="text-xs text-[#64748B] font-mono">
                  @{githubUser.login}
                </span>
                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#16A34A] bg-[#DCFCE7] px-2 py-0.5 rounded-full">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#16A34A]" />
                  Connected
                </span>
              </div>
              <p className="text-xs text-[#64748B] mt-0.5">
                {githubUser.bio || `${githubUser.public_repos || 0} public repositories accessible`}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 text-xs">
            {githubUser.html_url && (
              <a
                href={githubUser.html_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-[#2563EB] hover:text-[#1D4ED8] font-medium"
              >
                <span>View GitHub Profile</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            )}
          </div>
        </div>
      )}

      {/* REAL MODE: Not Connected State Banner */}
      {appMode === 'REAL' && !githubConnected && (
        <Card className="p-8 border-[#BFDBFE] bg-gradient-to-b from-[#F8FAFC] to-[#EFF6FF]/30 text-center">
          <div className="max-w-xl mx-auto space-y-4">
            <div className="w-14 h-14 rounded-2xl bg-[#0F172A] text-white flex items-center justify-center mx-auto shadow-md">
              <GithubIcon className="w-8 h-8" />
            </div>

            <h2 className="text-xl sm:text-2xl font-bold text-[#0F172A]">
              Connect Your GitHub Account
            </h2>

            <p className="text-sm text-[#64748B]">
              DevRescue AI communicates with the official GitHub REST API to list your repositories,
              inspect open bug issues, clone target branches, and prepare verified pull requests.
            </p>

            <div className="pt-2">
              <PrimaryButton
                onClick={handleConnectGithub}
                loading={githubLoading}
                icon={GithubIcon}
                size="lg"
              >
                Connect with GitHub
              </PrimaryButton>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-6 text-xs text-[#64748B] text-left border-t border-[#E2E8F0]">
              <div className="flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-[#16A34A] flex-shrink-0 mt-0.5" />
                <span>Zero token exposure to frontend (secure HTTP-only session)</span>
              </div>
              <div className="flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-[#16A34A] flex-shrink-0 mt-0.5" />
                <span>Access user-owned public and private repositories</span>
              </div>
              <div className="flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-[#16A34A] flex-shrink-0 mt-0.5" />
                <span>Inspect issue descriptions, branches, and codebases</span>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Repositories Explorer (Active when Real + Connected OR Demo Mode) */}
      {(appMode === 'DEMO' || githubConnected) && (
        <>
          {/* Search & Filter Toolbar */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
            <div className="w-full sm:w-80">
              <SearchInput
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search repositories..."
              />
            </div>

            {/* Filter Pills */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
              {filterOptions.map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => setFilter(f)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap cursor-pointer ${
                    filter === f
                      ? 'bg-[#2563EB] text-white shadow-xs font-semibold'
                      : 'bg-white text-[#64748B] border border-[#E2E8F0] hover:text-[#0F172A] hover:bg-[#F8FAFC]'
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          {/* Error Banner in Real Mode */}
          {appMode === 'REAL' && realRepoError && (
            <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 flex items-center justify-between gap-4">
              <div className="flex items-center gap-3 text-xs">
                <AlertCircle className="w-4 h-4 flex-shrink-0 text-red-600" />
                <span>{realRepoError}</span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={fetchRealRepositories}
                className="text-xs border-red-300 text-red-700 hover:bg-red-100"
              >
                Retry
              </Button>
            </div>
          )}

          {/* Loading Skeletons */}
          {appMode === 'REAL' && loadingRealRepos ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {[1, 2, 3, 4].map((i) => (
                <div
                  key={i}
                  className="p-6 rounded-2xl bg-white border border-[#E2E8F0] animate-pulse space-y-4"
                >
                  <div className="flex items-center justify-between">
                    <div className="h-5 w-48 bg-slate-200 rounded" />
                    <div className="h-4 w-16 bg-slate-200 rounded" />
                  </div>
                  <div className="h-4 w-full bg-slate-100 rounded" />
                  <div className="grid grid-cols-3 gap-2 pt-4 border-t border-[#E2E8F0]">
                    <div className="h-4 bg-slate-100 rounded" />
                    <div className="h-4 bg-slate-100 rounded" />
                    <div className="h-4 bg-slate-100 rounded" />
                  </div>
                </div>
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={FolderGit2}
              title={appMode === 'REAL' ? 'No repositories found' : 'No demo repositories found'}
              description={
                search
                  ? `No repositories matched "${search}". Try a different search query.`
                  : appMode === 'REAL'
                  ? 'No repositories were returned from your GitHub account. Check permissions or create a repository on GitHub.'
                  : 'Restore the standard mock workspace to explore autonomous investigations.'
              }
              actionLabel={appMode === 'REAL' ? 'Refresh Repositories' : 'Load Demo Repository'}
              onAction={
                appMode === 'REAL'
                  ? fetchRealRepositories
                  : () => {
                      connectRepository({
                        name: 'demo-react-app',
                        language: 'React · JavaScript',
                        filterCategory: 'React',
                        description: 'Customer-facing frontend application with state management.',
                        filesCount: 142
                      });
                    }
              }
            />
          ) : (
            /* Cards Grid */
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {filtered.map((repo) => {
                const repoFullName = repo.full_name || repo.name;
                const isPrivate = Boolean(repo.private);
                const defaultBranch = repo.default_branch || repo.defaultBranch || 'main';
                const langColor = LANGUAGE_COLORS[repo.language] || '#94A3B8';
                const openIssues = repo.open_issues !== undefined ? repo.open_issues : (repo.openIssuesCount || repo.issues?.length || 0);

                return (
                  <Card
                    key={repo.id || repoFullName}
                    className="p-6 flex flex-col justify-between border-[#E2E8F0] hover:border-[#CBD5E1] transition-all"
                  >
                    <div className="space-y-4">
                      {/* Top Row: Name, visibility badge, branch */}
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <FolderGit2 className="w-5 h-5 text-[#2563EB] flex-shrink-0" />
                            <h3 className="text-base font-bold text-[#0F172A] truncate">
                              {repoFullName}
                            </h3>
                            {isPrivate ? (
                              <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                                <Lock className="w-2.5 h-2.5" />
                                Private
                              </span>
                            ) : (
                              <span className="text-[10px] font-semibold text-[#16A34A] bg-[#DCFCE7] px-2 py-0.5 rounded border border-[#BBF7D0]">
                                Public
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-[#64748B] line-clamp-2">
                            {repo.description || 'No description provided.'}
                          </p>
                        </div>

                        <span className="text-xs font-mono bg-[#F8FAFC] text-[#0F172A] border border-[#E2E8F0] px-2 py-0.5 rounded flex items-center gap-1 flex-shrink-0">
                          <GitBranch className="w-3 h-3 text-[#64748B]" />
                          {defaultBranch}
                        </span>
                      </div>

                      {/* Meta details */}
                      <div className="grid grid-cols-3 gap-2 pt-2 border-t border-[#E2E8F0] text-xs text-[#64748B]">
                        <div>
                          <span className="block text-[11px] text-[#94A3B8]">Language</span>
                          <span className="font-semibold text-[#0F172A] mt-0.5 flex items-center gap-1.5 truncate">
                            <span
                              className="w-2 h-2 rounded-full flex-shrink-0"
                              style={{ backgroundColor: langColor }}
                            />
                            {repo.language || 'Unknown'}
                          </span>
                        </div>
                        <div>
                          <span className="block text-[11px] text-[#94A3B8]">Stars / Forks</span>
                          <span className="font-semibold text-[#0F172A] mt-0.5 flex items-center gap-2">
                            <span className="flex items-center gap-0.5">
                              <Star className="w-3 h-3 text-amber-500 fill-amber-500" />
                              {repo.stars || repo.stargazers_count || 0}
                            </span>
                            <span className="flex items-center gap-0.5">
                              <GitFork className="w-3 h-3 text-slate-400" />
                              {repo.forks || repo.forks_count || 0}
                            </span>
                          </span>
                        </div>
                        <div>
                          <span className="block text-[11px] text-[#94A3B8]">Open Issues</span>
                          <span className="font-semibold text-[#2563EB] mt-0.5 block">
                            {openIssues} issues
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="pt-4 mt-4 border-t border-[#E2E8F0] flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {repo.html_url && (
                          <a
                            href={repo.html_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-[#64748B] hover:text-[#0F172A] inline-flex items-center gap-1"
                          >
                            <span>GitHub</span>
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </div>

                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleOpenIssues(repo)}
                        >
                          View Issues
                        </Button>
                        <Button
                          to={`/investigations/new?repo=${encodeURIComponent(repoFullName)}`}
                          variant="primary"
                          size="sm"
                        >
                          Investigate
                        </Button>
                      </div>
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* Repository Detail & Issues Modal */}
      {selectedRepo && (
        <Modal
          isOpen={!!selectedRepo}
          onClose={() => setSelectedRepo(null)}
          title={selectedRepo.full_name || selectedRepo.name}
          subtitle={`Default branch: ${selectedRepo.default_branch || selectedRepo.defaultBranch || 'main'} · Open Issues: ${selectedRepo.open_issues !== undefined ? selectedRepo.open_issues : (selectedRepo.openIssuesCount || 0)}`}
          maxWidth="max-w-2xl"
          footer={
            <>
              <Button variant="outline" size="sm" onClick={() => setSelectedRepo(null)}>
                Close
              </Button>
              <Button
                variant="primary"
                size="sm"
                to={`/investigations/new?repo=${encodeURIComponent(selectedRepo.full_name || selectedRepo.name)}`}
              >
                Launch Investigation →
              </Button>
            </>
          }
        >
          <div className="space-y-5">
            <p className="text-sm text-[#64748B]">
              {selectedRepo.description || 'No description provided for this repository.'}
            </p>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-xs">
              <div>
                <span className="text-[#64748B] block">Language</span>
                <span className="font-semibold text-[#0F172A] text-sm mt-0.5 block truncate">
                  {selectedRepo.language || 'Unknown'}
                </span>
              </div>
              <div>
                <span className="text-[#64748B] block">Visibility</span>
                <span className="font-semibold text-[#0F172A] text-sm mt-0.5 block">
                  {selectedRepo.private ? 'Private' : 'Public'}
                </span>
              </div>
              <div>
                <span className="text-[#64748B] block">Branch</span>
                <span className="font-semibold text-[#0F172A] text-sm mt-0.5 block font-mono">
                  {selectedRepo.default_branch || selectedRepo.defaultBranch || 'main'}
                </span>
              </div>
              <div>
                <span className="text-[#64748B] block">Stars</span>
                <span className="font-semibold text-[#0F172A] text-sm mt-0.5 block">
                  {selectedRepo.stars || selectedRepo.stargazers_count || 0}
                </span>
              </div>
            </div>

            {/* Issues Section */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-[#0F172A]">
                  Open Issues Available for Investigation
                </h4>
                {appMode === 'REAL' && (
                  <span className="text-[11px] text-[#64748B]">
                    Fetched from real GitHub repository
                  </span>
                )}
              </div>

              {loadingIssues ? (
                <div className="p-8 text-center text-xs text-[#64748B] space-y-2">
                  <div className="w-5 h-5 border-2 border-[#2563EB] border-t-transparent rounded-full animate-spin mx-auto" />
                  <span>Loading open issues from GitHub...</span>
                </div>
              ) : issuesError ? (
                <div className="p-4 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">
                  {issuesError}
                </div>
              ) : (appMode === 'REAL' ? selectedRepoIssues : selectedRepo.issues || []).length === 0 ? (
                <div className="p-6 text-center bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl space-y-2">
                  <CheckCircle2 className="w-6 h-6 text-[#16A34A] mx-auto" />
                  <p className="text-xs font-semibold text-[#0F172A]">
                    No open issues found in this repository
                  </p>
                  <p className="text-[11px] text-[#64748B]">
                    You can still configure an investigation order by specifying a custom issue description.
                  </p>
                  <div className="pt-2">
                    <Button
                      to={`/investigations/new?repo=${encodeURIComponent(selectedRepo.full_name || selectedRepo.name)}`}
                      variant="primary"
                      size="sm"
                    >
                      Specify Custom Issue
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                  {(appMode === 'REAL' ? selectedRepoIssues : selectedRepo.issues || []).map((iss) => {
                    const issNumber = iss.number;
                    const issTitle = iss.title;
                    const issAuthor = iss.user?.login || iss.author || 'maintainer';
                    const issLabels = iss.labels || [];

                    return (
                      <div
                        key={iss.id || issNumber}
                        className="p-3 bg-white border border-[#E2E8F0] hover:border-slate-300 rounded-xl flex items-center justify-between gap-3 text-xs transition-colors"
                      >
                        <div className="space-y-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-bold text-[#2563EB]">
                              #{issNumber}
                            </span>
                            <span className="font-semibold text-[#0F172A] truncate">
                              {issTitle}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-[11px] text-[#64748B]">
                            <span>Opened by @{issAuthor}</span>
                            {issLabels.length > 0 && (
                              <div className="flex items-center gap-1">
                                {issLabels.slice(0, 2).map((lbl, idx) => (
                                  <span
                                    key={idx}
                                    className="px-1.5 py-0.2 rounded bg-slate-100 text-slate-600 text-[10px] font-medium"
                                  >
                                    {typeof lbl === 'string' ? lbl : lbl.name}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>

                        <Button
                          to={`/investigations/new?repo=${encodeURIComponent(selectedRepo.full_name || selectedRepo.name)}&issue=${issNumber}`}
                          variant="outline"
                          size="sm"
                          className="text-xs py-1 px-3 flex-shrink-0"
                        >
                          Select →
                        </Button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </Modal>
      )}

      {/* Demo Connect Repository Modal */}
      <Modal
        isOpen={connectModalOpen}
        onClose={() => setConnectModalOpen(false)}
        title="Add Demo Repository"
        subtitle="Add a simulated repository to the local DevRescue prototype environment"
        maxWidth="max-w-md"
        footer={
          <>
            <Button variant="outline" size="sm" onClick={() => setConnectModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" size="sm" onClick={handleDemoConnectSubmit}>
              Add Repository
            </Button>
          </>
        }
      >
        <form onSubmit={handleDemoConnectSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-[#0F172A] uppercase tracking-wider mb-1.5">
              Repository Name *
            </label>
            <input
              type="text"
              value={newRepoName}
              onChange={(e) => setNewRepoName(e.target.value)}
              placeholder="e.g. auth-gateway or frontend-web"
              required
              className="w-full rounded-lg bg-white border border-[#E2E8F0] px-3.5 py-2 text-sm text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB]"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#0F172A] uppercase tracking-wider mb-1.5">
              Language / Framework
            </label>
            <select
              value={newRepoLang}
              onChange={(e) => setNewRepoLang(e.target.value)}
              className="w-full rounded-lg bg-white border border-[#E2E8F0] px-3.5 py-2 text-sm text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB]"
            >
              <option value="React">React · TypeScript</option>
              <option value="Python">Python · FastAPI</option>
              <option value="Node.js">Node.js · Express</option>
              <option value="Go">Go · Gin</option>
              <option value="Other">Other</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#0F172A] uppercase tracking-wider mb-1.5">
              Description
            </label>
            <textarea
              rows={3}
              value={newRepoDesc}
              onChange={(e) => setNewRepoDesc(e.target.value)}
              placeholder="Brief description of the service..."
              className="w-full rounded-lg bg-white border border-[#E2E8F0] px-3.5 py-2 text-sm text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB]"
            />
          </div>

          <div className="p-3 bg-[#EFF6FF] border border-[#BFDBFE] rounded-lg text-xs text-[#2563EB]">
            Demo Mode: Repository will be added to your local prototype environment.
          </div>
        </form>
      </Modal>
    </div>
  );
}
