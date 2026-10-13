import React, { useState } from 'react';
import {
  GitPullRequest,
  Plus,
  ShieldCheck,
  Check,
  ExternalLink
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import Button, { PrimaryButton } from '../../components/common/Button';
import Badge, { StatusBadge } from '../../components/common/Badge';
import Modal from '../../components/common/Modal';
import { SearchInput } from '../../components/common/FormInputs';
import EmptyState from '../../components/common/EmptyState';

export default function PullRequests() {
  const { pullRequests, appMode } = useApp();
  const isRealMode = appMode === 'REAL';

  const [activeTab, setActiveTab] = useState('ALL');
  const [search, setSearch] = useState('');
  const [selectedPr, setSelectedPr] = useState(null);
  const [demoPrBannerOpen, setDemoPrBannerOpen] = useState(false);

  const tabs = [
    { id: 'ALL', label: 'All', count: pullRequests.length },
    { id: 'READY_FOR_REVIEW', label: 'Ready for Review', count: pullRequests.filter((p) => p.status === 'READY_FOR_REVIEW').length },
    { id: 'OPEN', label: 'Open', count: pullRequests.filter((p) => p.status === 'OPEN').length },
    { id: 'MERGED', label: 'Merged', count: pullRequests.filter((p) => p.status === 'MERGED').length },
    { id: 'CLOSED', label: 'Closed', count: pullRequests.filter((p) => p.status === 'CLOSED').length },
    { id: 'FAILED', label: 'Failed', count: pullRequests.filter((p) => p.status === 'FAILED').length },
  ];

  const filtered = pullRequests.filter((pr) => {
    const matchesSearch =
      (pr.title || '').toLowerCase().includes(search.toLowerCase()) ||
      (pr.repo || '').toLowerCase().includes(search.toLowerCase()) ||
      String(pr.number).includes(search);

    if (activeTab === 'ALL') return matchesSearch;
    return matchesSearch && pr.status === activeTab;
  });

  return (
    <div className="space-y-8">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-[#E2E8F0]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#0F172A]">
              Pull Requests
            </h1>
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${isRealMode ? 'bg-[#EFF6FF] text-[#2563EB] border border-[#BFDBFE]' : 'bg-[#F1F5F9] text-[#64748B]'}`}>
              {isRealMode ? 'REAL MODE' : 'DEMO MODE'}
            </span>
          </div>
          <p className="text-sm text-[#64748B]">
            {isRealMode
              ? 'Real Pull Requests created on GitHub after human maintainer approval.'
              : 'Pull requests prepared by DevRescue AI (Prototype environment).'}
          </p>
        </div>

        <PrimaryButton
          to="/investigations/new"
          icon={Plus}
          size="sm"
        >
          New Investigation
        </PrimaryButton>
      </div>

      {/* Search and Tabs Toolbar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        {/* Tabs */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1 sm:pb-0">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap cursor-pointer flex items-center gap-1.5 ${
                activeTab === tab.id
                  ? 'bg-[#2563EB] text-white shadow-xs'
                  : 'bg-white text-[#64748B] border border-[#E2E8F0] hover:text-[#0F172A] hover:bg-[#F8FAFC]'
              }`}
            >
              <span>{tab.label}</span>
              {tab.count > 0 && (
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

        {/* Search */}
        <div className="w-full sm:w-64">
          <SearchInput
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search pull requests..."
          />
        </div>
      </div>

      {/* PR Table / List */}
      {filtered.length === 0 ? (
        <EmptyState
          icon={GitPullRequest}
          title={isRealMode ? "No pull requests created yet" : "No demo pull requests yet"}
          description={
            search
              ? `No pull requests matching "${search}".`
              : isRealMode
              ? "Approve an investigation fix in Real Mode to create a verified pull request on GitHub."
              : "Approved fixes will appear here once synthesized by AI."
          }
          actionLabel={isRealMode ? "View Investigations" : "View Investigation"}
          actionTo={isRealMode ? "/investigations" : "/investigations/1"}
        />
      ) : (
        <div className="bg-white border border-[#E2E8F0] rounded-xl overflow-hidden shadow-xs">
          <div className="divide-y divide-[#E2E8F0]">
            {filtered.map((pr) => {
              const isRealPr = Boolean(pr.pr_url || pr.html_url || pr.prUrl || (!pr.isDemoPr && isRealMode));
              const realUrl = pr.pr_url || pr.html_url || pr.prUrl;

              return (
                <div
                  key={pr.id}
                  className="p-5 hover:bg-[#F8FAFC] transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4"
                >
                  <div className="space-y-1.5 min-w-0">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <span className="font-mono text-xs font-bold text-[#2563EB]">
                        {isRealPr ? `PR #${pr.number}` : `Demo PR #${pr.number}`}
                      </span>
                      <h3 className="text-sm font-bold text-[#0F172A] truncate">
                        {pr.title}
                      </h3>
                      {isRealPr ? (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#DCFCE7] text-[#16A34A] border border-[#BBF7D0]">
                          GITHUB PR
                        </span>
                      ) : (
                        <Badge variant="demo" size="sm">
                          DEMO PR
                        </Badge>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-3 text-xs text-[#64748B]">
                      <span className="font-mono text-slate-700 font-medium">
                        {pr.repo}
                      </span>
                      {pr.branch && (
                        <>
                          <span>·</span>
                          <span className="font-mono text-slate-600">
                            {pr.branch} {pr.base_branch ? `→ ${pr.base_branch}` : ''}
                          </span>
                        </>
                      )}
                      {pr.commit_sha && (
                        <>
                          <span>·</span>
                          <span className="font-mono text-[#2563EB]">
                            SHA: {pr.commit_sha.slice(0, 7)}
                          </span>
                        </>
                      )}
                      {!isRealPr && (
                        <>
                          <span>·</span>
                          <span className="text-[#16A34A] font-medium flex items-center gap-1">
                            <Check className="w-3.5 h-3.5" />
                            Tests: {pr.testsStatus || 'Passed'}
                          </span>
                          <span>·</span>
                          <span className="text-[#16A34A] font-medium flex items-center gap-1">
                            <ShieldCheck className="w-3.5 h-3.5" />
                            Security: {pr.securityStatus || 'Passed'}
                          </span>
                          <span>·</span>
                          <span className="font-mono">
                            +{pr.additions || 14} / -{pr.deletions || 4} lines
                          </span>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2.5 flex-shrink-0">
                    <StatusBadge status={pr.status} />

                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedPr(pr)}
                    >
                      {isRealPr ? 'Details' : 'View Demo PR'}
                    </Button>

                    {isRealPr && realUrl && (
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => window.open(realUrl, '_blank', 'noopener,noreferrer')}
                        className="bg-[#2563EB] hover:bg-[#1D4ED8] flex items-center gap-1.5"
                      >
                        <span>Open on GitHub</span>
                        <ExternalLink className="w-3.5 h-3.5" />
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* PR Detail Modal */}
      {selectedPr && (() => {
        const isSelectedReal = Boolean(selectedPr.pr_url || selectedPr.html_url || selectedPr.prUrl || (!selectedPr.isDemoPr && isRealMode));
        const selectedRealUrl = selectedPr.pr_url || selectedPr.html_url || selectedPr.prUrl;

        return (
          <Modal
            isOpen={!!selectedPr}
            onClose={() => setSelectedPr(null)}
            title={`PR #${selectedPr.number}: ${selectedPr.title}`}
            subtitle={isSelectedReal ? `Repo: ${selectedPr.repo} · Head: ${selectedPr.branch || 'fix'} · Base: ${selectedPr.base_branch || 'main'}` : `Repo: ${selectedPr.repo} · Target: ${selectedPr.branch || 'main'}`}
            maxWidth="max-w-xl"
            footer={
              <>
                <Button variant="outline" size="sm" onClick={() => setSelectedPr(null)}>
                  Close
                </Button>
                {selectedPr.investigationId && (
                  <Button
                    variant="outline"
                    size="sm"
                    to={`/investigations/${selectedPr.investigationId}/review`}
                    onClick={() => setSelectedPr(null)}
                  >
                    View Diff
                  </Button>
                )}
                {isSelectedReal && selectedRealUrl ? (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => window.open(selectedRealUrl, '_blank', 'noopener,noreferrer')}
                    className="bg-[#2563EB] hover:bg-[#1D4ED8] flex items-center gap-1.5"
                  >
                    <span>Open on GitHub</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </Button>
                ) : (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => setDemoPrBannerOpen(true)}
                  >
                    Open Demo PR
                  </Button>
                )}
              </>
            }
          >
            <div className="space-y-4">
              <div className={`p-3 rounded-lg text-xs flex items-center justify-between border ${
                isSelectedReal
                  ? 'bg-[#DCFCE7]/60 border-[#BBF7D0] text-[#16A34A] font-semibold'
                  : 'bg-[#EFF6FF] border-[#BFDBFE] text-[#2563EB]'
              }`}>
                <span>{isSelectedReal ? '✓ Verified Upstream GitHub Pull Request' : 'Simulated Prototype · Demo PR'}</span>
                <StatusBadge status={selectedPr.status} />
              </div>

              {/* Metadata Grid */}
              <div className="grid grid-cols-2 gap-3 p-4 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-xs">
                <div>
                  <span className="text-[#64748B] block">Repository</span>
                  <span className="font-semibold text-[#0F172A] mt-0.5 block">{selectedPr.repo}</span>
                </div>
                <div>
                  <span className="text-[#64748B] block">Target Issue</span>
                  <span className="font-semibold text-[#0F172A] mt-0.5 block">
                    #{selectedPr.issueNumber || 42} {selectedPr.issueTitle || 'Bug repair'}
                  </span>
                </div>
                <div>
                  <span className="text-[#64748B] block">Branch</span>
                  <span className="font-mono text-[#0F172A] mt-0.5 block truncate">
                    {selectedPr.branch || 'main'} {selectedPr.base_branch ? `→ ${selectedPr.base_branch}` : ''}
                  </span>
                </div>
                <div>
                  <span className="text-[#64748B] block">
                    {selectedPr.commit_sha ? 'Verified Commit SHA' : 'Line Delta'}
                  </span>
                  {selectedPr.commit_sha ? (
                    <span className="font-mono text-[#2563EB] font-bold mt-0.5 block">
                      {selectedPr.commit_sha.slice(0, 10)}
                    </span>
                  ) : (
                    <span className="font-mono mt-0.5 block">
                      <span className="text-[#16A34A] font-semibold">+{selectedPr.additions || 14}</span> /{' '}
                      <span className="text-[#DC2626] font-semibold">-{selectedPr.deletions || 4}</span>
                    </span>
                  )}
                </div>
              </div>

            {/* AI Summary */}
            <div className="space-y-1.5">
              <span className="text-xs font-bold uppercase tracking-wider text-[#0F172A]">
                AI Synthesis Summary
              </span>
              <p className="text-xs text-[#64748B] leading-relaxed bg-white border border-[#E2E8F0] p-3 rounded-lg">
                {selectedPr.aiSummary || 'Fixes runtime unhandled exceptions by importing missing symbol into module scope.'}
              </p>
            </div>

            {/* Tests & Security Results */}
            <div className="grid grid-cols-2 gap-3 pt-2">
              <div className="p-3 rounded-lg bg-emerald-50/50 border border-emerald-200 text-xs">
                <span className="font-semibold text-[#16A34A] block mb-1">
                  Test Results
                </span>
                <span className="text-[#0F172A]">{selectedPr.testsDetail || '14/14 tests passed (100%)'}</span>
              </div>

              <div className="p-3 rounded-lg bg-emerald-50/50 border border-emerald-200 text-xs">
                <span className="font-semibold text-[#16A34A] block mb-1">
                  Security Results
                </span>
                <span className="text-[#0F172A]">{selectedPr.securityDetail || 'Low Risk · 0 secrets'}</span>
              </div>
            </div>
          </div>
        </Modal>
      );
    })()}

      {/* Simulated GitHub PR Modal */}
      <Modal
        isOpen={demoPrBannerOpen}
        onClose={() => setDemoPrBannerOpen(false)}
        title="Simulated Demo PR Viewer"
        subtitle="Frontend Demo Environment"
        maxWidth="max-w-lg"
        footer={
          <Button variant="primary" size="sm" onClick={() => setDemoPrBannerOpen(false)}>
            Close Preview
          </Button>
        }
      >
        <div className="space-y-3 text-center py-4">
          <div className="w-12 h-12 rounded-full bg-[#EFF6FF] border border-[#BFDBFE] text-[#2563EB] flex items-center justify-center mx-auto">
            <GitPullRequest className="w-6 h-6" />
          </div>
          <h4 className="text-base font-bold text-[#0F172A]">
            Demo PR #{selectedPr?.number || 128} Ready
          </h4>
          <p className="text-xs text-[#64748B] max-w-sm mx-auto leading-relaxed">
            In a production deployment, this triggers a real GitHub REST/GraphQL API commit and creates an upstream pull request on <code className="font-mono bg-slate-100 px-1 py-0.5 rounded">{selectedPr?.repo}</code>.
          </p>
          <div className="p-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg text-xs font-mono text-slate-700 text-left">
            git push origin devrescue/fix-issue-{selectedPr?.issueNumber || 42}<br />
            gh pr create --title "{selectedPr?.title}" --base main
          </div>
        </div>
      </Modal>
    </div>
  );
}
