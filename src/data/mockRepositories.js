/**
 * DevRescue AI - Mock Repositories Data
 * Realistic developer demo datasets without external API dependencies.
 */

export const MOCK_REPOSITORIES = [
  {
    id: 'repo-1',
    name: 'demo-react-app',
    fullName: 'acme-corp/demo-react-app',
    owner: 'acme-corp',
    language: 'React · JavaScript',
    filterCategory: 'React',
    filesCount: 142,
    openIssuesCount: 2,
    defaultBranch: 'main',
    branches: ['main', 'develop', 'release/v1.2', 'fix/auth-handler'],
    lastActivity: '12 minutes ago',
    lastUpdated: 'Today at 14:32 UTC',
    description: 'React front-end application with component routing and interactive user authentication.',
    issues: [
      {
        id: 'issue-42',
        number: 42,
        title: 'Login button not working',
        description: 'Login button throws ReferenceError when clicked.',
        detailedError: 'Clicking the "Sign In" button triggers ReferenceError: authenticateUser is not defined. The handler in Login.jsx attempts to invoke authenticateUser directly from "./auth" instead of "./services/authService".',
        status: 'Open',
        author: 'sarah-dev',
        createdAt: '1 hour ago',
        labels: ['bug', 'p0', 'auth'],
        targetFiles: ['src/components/Login.jsx', 'src/services/authService.js'],
        rootCause: 'authenticateUser is referenced without the required import.',
      },
      {
        id: 'issue-55',
        number: 55,
        title: 'State persistence bug on page refresh in cart dropdown',
        description: 'Selected items reset to default state when browser window reload occurs before sync.',
        detailedError: 'LocalStorage sync handler in useCart.js lacks hydration guard on window.beforeunload event.',
        status: 'Open',
        author: 'frontend-team',
        createdAt: '4 hours ago',
        labels: ['bug', 'state'],
        targetFiles: ['src/hooks/useCart.js'],
        rootCause: 'Unmounted event listener clears sessionStorage on route change.',
      }
    ]
  },
  {
    id: 'repo-2',
    name: 'api-service',
    fullName: 'acme-corp/api-service',
    owner: 'acme-corp',
    language: 'Python',
    filterCategory: 'Python',
    filesCount: 89,
    openIssuesCount: 1,
    defaultBranch: 'main',
    branches: ['main', 'staging', 'feat/async-worker'],
    lastActivity: '2 hours ago',
    lastUpdated: 'Today at 11:15 UTC',
    description: 'High-throughput async Python service powering checkout webhooks and background task queues.',
    issues: [
      {
        id: 'issue-88',
        number: 88,
        title: 'API timeout issue under concurrent upstream gateway calls',
        description: 'Requests to /v1/checkout timeout after 30s when upstream payment processor has high latency.',
        detailedError: 'Missing asynchronous timeout guard causes worker threads to block on unresponsive socket connections.',
        status: 'Open',
        author: 'alex-backend',
        createdAt: '2 hours ago',
        labels: ['performance', 'timeout', 'p1'],
        targetFiles: ['app/routers/checkout.py', 'app/core/http_client.py'],
        rootCause: 'Connection pool lacks circuit breaker and fallback retry limits.',
      }
    ]
  },
  {
    id: 'repo-3',
    name: 'dashboard-ui',
    fullName: 'acme-corp/dashboard-ui',
    owner: 'acme-corp',
    language: 'React · TypeScript',
    filterCategory: 'React',
    filesCount: 210,
    openIssuesCount: 2,
    defaultBranch: 'main',
    branches: ['main', 'release/v2.0'],
    lastActivity: '5 hours ago',
    lastUpdated: 'Yesterday at 18:40 UTC',
    description: 'Enterprise operations analytics dashboard with real-time charts and telemetry views.',
    issues: [
      {
        id: 'issue-63',
        number: 63,
        title: 'Navbar rendering issue on viewport resize below 768px',
        description: 'Mobile navigation drawer fails to close when switching orientation or viewport width.',
        detailedError: 'ResizeObserver event listener causes infinite re-render loop on tablet breakpoint.',
        status: 'Open',
        author: 'jordan-ui',
        createdAt: '5 hours ago',
        labels: ['ui', 'responsive'],
        targetFiles: ['src/components/Navigation.tsx'],
        rootCause: 'Missing dependency array in useResize hook causing state flicker.',
      },
      {
        id: 'issue-71',
        number: 71,
        title: 'Table sorting indicator misaligned in dark mode',
        description: 'Header sort icons overlap table text on low-density displays.',
        detailedError: 'CSS flexbox justification collides with absolute-positioned sort chevron.',
        status: 'Open',
        author: 'qa-lead',
        createdAt: '1 day ago',
        labels: ['styling', 'minor'],
        targetFiles: ['src/components/DataTable.tsx'],
        rootCause: 'Unset CSS box-sizing in child header container.',
      }
    ]
  },
  {
    id: 'repo-4',
    name: 'ml-models',
    fullName: 'acme-corp/ml-models',
    owner: 'acme-corp',
    language: 'Python',
    filterCategory: 'Python',
    filesCount: 64,
    openIssuesCount: 1,
    defaultBranch: 'main',
    branches: ['main', 'experiment/transformer'],
    lastActivity: '1 day ago',
    lastUpdated: '2 days ago at 09:20 UTC',
    description: 'Machine learning inference pipeline for automated log classification and anomalous telemetry.',
    issues: [
      {
        id: 'issue-29',
        number: 29,
        title: 'Database connection error during batch inference pool recycling',
        description: 'Deadlock encountered when threadpool terminates before connection pool release.',
        detailedError: 'Threaded executor exits while active cursors hold transactional locks on inference table.',
        status: 'Open',
        author: 'data-eng',
        createdAt: '1 day ago',
        labels: ['database', 'deadlock', 'p0'],
        targetFiles: ['pipeline/db_pool.py'],
        rootCause: 'Unmanaged connection context manager in background thread worker.',
      }
    ]
  }
];
