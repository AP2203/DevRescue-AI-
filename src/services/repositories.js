/**
 * DevRescue AI - Repositories Service
 */

const STORAGE_KEY = 'devrescue_repositories_v1';

const INITIAL_REPOSITORIES = [
  {
    id: 'repo-1',
    name: 'acme-corp/payment-gateway',
    fullName: 'acme-corp/payment-gateway',
    description: 'High-throughput idempotency-backed Stripe and Adyen orchestration microservice.',
    language: 'TypeScript',
    defaultBranch: 'main',
    branches: ['main', 'release/2.4', 'feat/webhooks-v2', 'fix/deadlock-guard'],
    lastSync: '12 minutes ago',
    status: 'HEALTHY',
    openIssuesCount: 4,
    stars: 382,
    issues: [
      {
        id: 'iss-104',
        number: 104,
        title: 'Memory leak under sustained WebSocket reconnect churn in connection manager',
        description: 'Under heavy packet loss, the connection pool retains uncollected listeners leading to process OOM after 6 hours in production cluster.',
        labels: ['bug', 'critical', 'p1'],
        author: 'sre-team',
        created_at: '2 hours ago',
      },
      {
        id: 'iss-109',
        number: 109,
        title: 'Race condition in idempotency ledger during concurrent capture calls',
        description: 'When two concurrent webhook events attempt to capture the same settlement ledger row, isolation level permits duplicate transaction credit records.',
        labels: ['bug', 'concurrency', 'p0'],
        author: 'finance-eng',
        created_at: '5 hours ago',
      },
      {
        id: 'iss-112',
        number: 112,
        title: 'Uncaught Promise rejection on Adyen HMAC signature mismatch',
        description: 'Malformed notification payload throws synchronous validation error before router handler catch block.',
        labels: ['bug', 'error-handling'],
        author: 'gateway-ops',
        created_at: '1 day ago',
      },
      {
        id: 'iss-115',
        number: 115,
        title: 'Stripe webhook retry storm exhausts upstream database connection pool',
        description: 'Exponential backoff jitter missing on secondary queue processor.',
        labels: ['performance'],
        author: 'sre-team',
        created_at: '3 days ago',
      }
    ]
  },
  {
    id: 'repo-2',
    name: 'hyperion/kernel-indexer',
    fullName: 'hyperion/kernel-indexer',
    description: 'Distributed vector embedding generator for code intelligence across git commits.',
    language: 'Rust',
    defaultBranch: 'master',
    branches: ['master', 'v0.9-rc', 'simd-experiments'],
    lastSync: '41 minutes ago',
    status: 'ACTIVE',
    openIssuesCount: 2,
    stars: 1240,
    issues: [
      {
        id: 'iss-201',
        number: 88,
        title: 'Panic on AST parsing of unterminated macro invocations in Rust 2024 edition',
        description: 'Parser fails to recover token stream boundaries when encountering unclosed delimiters inside procedural attribute macros.',
        labels: ['bug', 'parser', 'rust2024'],
        author: 'compiler-fan',
        created_at: '18 hours ago',
      },
      {
        id: 'iss-202',
        number: 92,
        title: 'Deadlock in channel reader during shutdown signal broadcast',
        description: 'Worker thread fails to release atomic lock before joining supervisor thread on SIGTERM.',
        labels: ['bug', 'concurrency'],
        author: 'tokio-maintainer',
        created_at: '2 days ago',
      }
    ]
  },
  {
    id: 'repo-3',
    name: 'meridian/identity-service',
    fullName: 'meridian/identity-service',
    description: 'OpenID Connect provider with biometric Passkey and WebAuthn attestations.',
    language: 'Go',
    defaultBranch: 'main',
    branches: ['main', 'feat/passkeys-v2'],
    lastSync: '2 hours ago',
    status: 'HEALTHY',
    openIssuesCount: 3,
    stars: 610,
    issues: [
      {
        id: 'iss-301',
        number: 54,
        title: 'JWT exp validation clock drift edge case permits expired refresh tokens',
        description: 'Negative skew offset calculation allows reuse of revoked refresh tokens within 60 second window.',
        labels: ['security', 'auth', 'p0'],
        author: 'sec-audit',
        created_at: '3 hours ago',
      },
      {
        id: 'iss-302',
        number: 58,
        title: 'SQL injection risk in custom claims filter expression',
        description: 'Unescaped user input passed to raw SQL builder in administrative claims search.',
        labels: ['security', 'critical'],
        author: 'pentest-bot',
        created_at: '1 day ago',
      }
    ]
  },
  {
    id: 'repo-4',
    name: 'devrescue-ai/sdk-python',
    fullName: 'devrescue-ai/sdk-python',
    description: 'Official Python client for automated bug triage and test orchestrations.',
    language: 'Python',
    defaultBranch: 'main',
    branches: ['main', 'dev'],
    lastSync: 'Just now',
    status: 'HEALTHY',
    openIssuesCount: 1,
    stars: 189,
    issues: [
      {
        id: 'iss-401',
        number: 23,
        title: 'AsyncSession connection pool exhausted when retrying streamed stdout',
        description: 'Aiohttp client session not properly closed on connection reset by peer during agent log stream.',
        labels: ['bug', 'async'],
        author: 'sdk-team',
        created_at: '4 hours ago',
      }
    ]
  }
];

export const repositoriesService = {
  getRepositories: () => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) return JSON.parse(stored);
    } catch {
      // ignore
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(INITIAL_REPOSITORIES));
    return INITIAL_REPOSITORIES;
  },

  getRepository: (id) => {
    const list = repositoriesService.getRepositories();
    return list.find((r) => r.id === id || r.name === id);
  },

  connectRepository: ({ fullName, description, language, defaultBranch }) => {
    const list = repositoriesService.getRepositories();
    const newRepo = {
      id: 'repo-' + Date.now(),
      name: fullName,
      fullName,
      description: description || 'Imported GitHub repository',
      language: language || 'TypeScript',
      defaultBranch: defaultBranch || 'main',
      branches: [defaultBranch || 'main', 'develop'],
      lastSync: 'Just now',
      status: 'HEALTHY',
      openIssuesCount: 1,
      stars: 1,
      issues: [
        {
          id: 'iss-' + Date.now(),
          number: 1,
          title: 'Initial test failure: connection timeout in test suite',
          description: 'Automated test suite timeout during integration stage.',
          labels: ['bug', 'test'],
          author: 'system',
          created_at: 'Just now',
        }
      ]
    };
    const updated = [newRepo, ...list];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    return newRepo;
  },

  syncRepository: (id) => {
    const list = repositoriesService.getRepositories();
    const updated = list.map((r) => (r.id === id ? { ...r, lastSync: 'Just now' } : r));
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    return updated;
  },
};
