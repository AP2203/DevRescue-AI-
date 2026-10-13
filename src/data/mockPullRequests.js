/**
 * DevRescue AI - Mock Pull Requests Data
 * Pull requests synthesized and verified by DevRescue AI.
 */

export const MOCK_PULL_REQUESTS = [
  {
    id: 'pr-128',
    number: 128,
    title: 'Fix authentication crash',
    detailedTitle: 'fix(auth): correct authenticateUser import from authService',
    repo: 'demo-react-app',
    branch: 'devrescue/fix-auth-crash-42',
    baseBranch: 'main',
    issueNumber: 42,
    issueTitle: 'Login button not working',
    status: 'READY_FOR_REVIEW', // Maps to tab "Ready for Review"
    statusLabel: 'Ready for Review',
    testsStatus: 'Passed',
    testsDetail: '14/14 tests passed (100%)',
    securityStatus: 'Passed',
    securityDetail: 'Low Risk · 0 secrets · 0 dependency changes',
    author: 'DevRescue AI [Bot]',
    createdAt: '15 minutes ago',
    filesChangedCount: 2,
    filesChanged: [
      'src/components/Login.jsx',
      'src/services/authService.js'
    ],
    additions: 14,
    deletions: 4,
    aiSummary: 'Resolves ReferenceError when clicking the login button. The component previously attempted to call authenticateUser from an incomplete export. The patch imports authenticateUser from authService and updates the click event dispatcher.',
    investigationId: '1',
    isDemoPr: true
  },
  {
    id: 'pr-124',
    number: 124,
    title: 'Resolve API timeout issue',
    detailedTitle: 'perf(http): configure asynchronous socket timeouts on gateway client',
    repo: 'api-service',
    branch: 'devrescue/fix-timeout-88',
    baseBranch: 'main',
    issueNumber: 88,
    issueTitle: 'API timeout issue under concurrent upstream gateway calls',
    status: 'MERGED', // Maps to tab "Merged"
    statusLabel: 'Merged',
    testsStatus: 'Passed',
    testsDetail: '28/28 tests passed (100%)',
    securityStatus: 'Passed',
    securityDetail: 'Low Risk · Bounded concurrency safety verified',
    author: 'DevRescue AI [Bot]',
    createdAt: '2 hours ago',
    filesChangedCount: 2,
    filesChanged: [
      'app/routers/checkout.py',
      'app/core/http_client.py'
    ],
    additions: 32,
    deletions: 9,
    aiSummary: 'Adds bounded socket timeout and retry backoff jitter to prevent worker pool starvation during upstream payment gateway delays.',
    investigationId: '2',
    isDemoPr: true
  },
  {
    id: 'pr-117',
    number: 117,
    title: 'Fix navbar rendering issue',
    detailedTitle: 'fix(ui): debounce ResizeObserver listener in responsive navbar',
    repo: 'dashboard-ui',
    branch: 'devrescue/fix-nav-collapse-63',
    baseBranch: 'main',
    issueNumber: 63,
    issueTitle: 'Navbar rendering issue on viewport resize below 768px',
    status: 'OPEN', // Maps to tab "Open"
    statusLabel: 'Open',
    testsStatus: 'Passed',
    testsDetail: '19/19 tests passed (100%)',
    securityStatus: 'Passed',
    securityDetail: 'Low Risk · Pure UI layout modification',
    author: 'DevRescue AI [Bot]',
    createdAt: '5 hours ago',
    filesChangedCount: 1,
    filesChanged: [
      'src/components/Navigation.tsx'
    ],
    additions: 8,
    deletions: 2,
    aiSummary: 'Applies debounce wrapper to the window resize listener to stop endless re-render cascades when transitioning across the 768px tablet breakpoint.',
    investigationId: '3',
    isDemoPr: true
  }
];
