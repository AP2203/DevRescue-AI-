/**
 * DevRescue AI - Pull Requests Service
 */

const STORAGE_KEY = 'devrescue_pull_requests_v1';

const INITIAL_PRS = [
  {
    id: 'pr-89',
    number: 89,
    title: 'fix(syntax): recover lexer on unterminated macro delimiter stream',
    repo: 'hyperion/kernel-indexer',
    url: 'https://github.com/hyperion/kernel-indexer/pull/89',
    status: 'MERGED',
    linkedInvestigationId: 'inv-46',
    linkedInvestigationNumber: 46,
    createdAt: 'Yesterday, 19:14 UTC',
    author: 'devrescue-ai[bot]',
    additions: 14,
    deletions: 3,
    testsStatus: '14/14 PASSED',
    branch: 'devrescue/fix-macro-panic-88',
  },
  {
    id: 'pr-55',
    number: 55,
    title: 'security(jwt): correct negative leeway clock drift verification',
    repo: 'meridian/identity-service',
    url: 'https://github.com/meridian/identity-service/pull/55',
    status: 'MERGED',
    linkedInvestigationId: 'inv-45',
    linkedInvestigationNumber: 45,
    createdAt: '2 days ago',
    author: 'devrescue-ai[bot]',
    additions: 8,
    deletions: 4,
    testsStatus: '9/9 PASSED',
    branch: 'devrescue/fix-jwt-skew-54',
  },
  {
    id: 'pr-32',
    number: 32,
    title: 'refactor(async): guard against uncollected Aiohttp ClientSession handles',
    repo: 'devrescue-ai/sdk-python',
    url: 'https://github.com/devrescue-ai/sdk-python/pull/32',
    status: 'OPEN',
    linkedInvestigationId: 'inv-44',
    linkedInvestigationNumber: 44,
    createdAt: '4 days ago',
    author: 'devrescue-ai[bot]',
    additions: 19,
    deletions: 11,
    testsStatus: '6/6 PASSED',
    branch: 'devrescue/fix-session-leak-23',
  }
];

export const pullRequestsService = {
  getPullRequests: () => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) return JSON.parse(stored);
    } catch {
      // ignore
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(INITIAL_PRS));
    return INITIAL_PRS;
  },

  getPullRequest: (id) => {
    const list = pullRequestsService.getPullRequests();
    return list.find((pr) => pr.id === id || String(pr.number) === String(id));
  },

  createPullRequestFromInvestigation: (inv) => {
    const list = pullRequestsService.getPullRequests();
    const nextPrNumber = Math.max(...list.map((p) => p.number || 0), 109) + 1;
    const newPr = {
      id: `pr-${nextPrNumber}`,
      number: nextPrNumber,
      title: `fix(${inv.patch?.file ? inv.patch.file.split('/')[1] || 'core' : 'core'}): resolve #${inv.issueNumber} - ${inv.issueTitle}`,
      repo: inv.repo,
      url: `https://github.com/${inv.repo}/pull/${nextPrNumber}`,
      status: 'OPEN',
      linkedInvestigationId: inv.id,
      linkedInvestigationNumber: inv.number,
      createdAt: 'Just now',
      author: 'devrescue-ai[bot]',
      additions: 28,
      deletions: 12,
      testsStatus: `${inv.testResults?.length || 5}/${inv.testResults?.length || 5} PASSED`,
      branch: `devrescue/patch-issue-${inv.issueNumber}`,
    };

    const updated = [newPr, ...list];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    return newPr;
  },

  updatePullRequestStatus: (id, status) => {
    const list = pullRequestsService.getPullRequests();
    const updated = list.map((pr) => (pr.id === id || String(pr.number) === String(id) ? { ...pr, status } : pr));
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    return updated;
  }
};
