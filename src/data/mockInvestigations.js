/**
 * DevRescue AI - Mock Investigations Data
 * Realistically simulates the 5-agent pipeline and autonomous bug investigation.
 */

export const MOCK_INVESTIGATIONS = [
  {
    id: '1',
    number: 1,
    title: 'Login button not working',
    issueTitle: 'Login button not working',
    repo: 'demo-react-app',
    branch: 'main',
    issueNumber: 42,
    status: 'IN_PROGRESS',
    progress: 68,
    estimatedTime: '~1 minute',
    startedAt: 'Today, 14:32 UTC',
    duration: '1m 14s',
    riskLevel: 'Low Risk',
    rootCause: {
      summary: 'authenticateUser is referenced without the required import.',
      explanation: 'The issue occurred because authenticateUser was referenced from the wrong module. In src/components/Login.jsx, the component imported only login from "./auth". When the user submits the form, handleLogin attempts to invoke authenticateUser directly, causing a fatal ReferenceError at runtime.',
      targetFile: 'src/components/Login.jsx',
      targetLine: 12
    },
    filesAnalyzed: [
      'src/components/Login.jsx',
      'src/services/authService.js'
    ],
    testSummary: {
      total: 14,
      passed: 12,
      pending: 2,
      failed: 0,
      details: [
        { name: 'Unit: Render Login Form component', status: 'PASSED', duration: '14ms' },
        { name: 'Unit: Email input field validation', status: 'PASSED', duration: '22ms' },
        { name: 'Unit: Password obscuring & length check', status: 'PASSED', duration: '19ms' },
        { name: 'Integration: Invoke authenticateUser on click', status: 'PASSED', duration: '45ms' },
        { name: 'Regression: Error banner when credentials invalid', status: 'PASSED', duration: '34ms' },
        { name: 'Regression: Token storage in localStorage', status: 'PASSED', duration: '28ms' },
        { name: 'End-to-End: Complete auth flow mock', status: 'PENDING', duration: 'Running' },
        { name: 'End-to-End: Session expiration redirect', status: 'PENDING', duration: 'Queued' }
      ]
    },
    securitySummary: {
      level: 'Low Risk',
      noSecretsDetected: true,
      noDependencyChanges: true,
      changesLimitedToRequestedFiles: true,
      advisoryNotes: 'Verified clean AST modification. No environment variables exposed, no external network requests introduced, and patch is strictly confined to local module resolution.'
    },
    agents: [
      {
        id: 'agent-1',
        step: 1,
        name: 'Repository Analyzer',
        shortName: 'Analyzer',
        status: 'COMPLETE',
        time: '4s',
        summary: 'Scanned 142 files and identified dependency graph for auth components.'
      },
      {
        id: 'agent-2',
        step: 2,
        name: 'Bug Investigator',
        shortName: 'Investigator',
        status: 'COMPLETE',
        time: '8s',
        summary: 'Reproduced ReferenceError in isolated sandbox container.'
      },
      {
        id: 'agent-3',
        step: 3,
        name: 'Code Repair Agent',
        shortName: 'Repair',
        status: 'IN_PROGRESS',
        time: 'Active',
        summary: 'Synthesizing minimal import patch for authService module.'
      },
      {
        id: 'agent-4',
        step: 4,
        name: 'Testing Agent',
        shortName: 'Testing',
        status: 'PENDING',
        time: 'Pending',
        summary: 'Queued to run 14 automated unit and regression tests.'
      },
      {
        id: 'agent-5',
        step: 5,
        name: 'Security Reviewer',
        shortName: 'Security',
        status: 'PENDING',
        time: 'Pending',
        summary: 'Queued for secret detection and dependency safety audit.'
      }
    ],
    logs: [
      { time: '14:32:04', agent: 'Analyzer', message: 'Scanning repository structure...' },
      { time: '14:32:08', agent: 'Analyzer', message: 'Found 142 relevant files.' },
      { time: '14:32:12', agent: 'Investigator', message: 'Reproducing the bug...' },
      { time: '14:32:15', agent: 'Investigator', message: 'ReferenceError detected in Login.jsx:38.' },
      { time: '14:32:20', agent: 'Repair', message: 'Generating minimal patch...' }
    ],
    diff: {
      file: 'src/components/Login.jsx',
      additions: 1,
      deletions: 1,
      lines: [
        { type: 'context', oldLine: 1, newLine: 1, text: "import React, { useState } from 'react';" },
        { type: 'remove', oldLine: 2, newLine: null, text: '- import { login } from "./auth";' },
        { type: 'add', oldLine: null, newLine: 2, text: '+ import { login, authenticateUser } from "./services/authService";' },
        { type: 'context', oldLine: 3, newLine: 3, text: '' },
        { type: 'context', oldLine: 4, newLine: 4, text: 'export function LoginModal({ isOpen, onClose }) {' },
        { type: 'context', oldLine: 5, newLine: 5, text: '  const [email, setEmail] = useState("");' },
        { type: 'context', oldLine: 6, newLine: 6, text: '  const [password, setPassword] = useState("");' },
        { type: 'context', oldLine: 7, newLine: 7, text: '' },
        { type: 'context', oldLine: 8, newLine: 8, text: '  const handleLoginClick = async (e) => {' },
        { type: 'context', oldLine: 9, newLine: 9, text: '    e.preventDefault();' },
        { type: 'context', oldLine: 10, newLine: 10, text: '    // authenticateUser is now properly imported from authService' },
        { type: 'context', oldLine: 11, newLine: 11, text: '    await authenticateUser(email, password);' },
        { type: 'context', oldLine: 12, newLine: 12, text: '    onClose();' },
        { type: 'context', oldLine: 13, newLine: 13, text: '  };' }
      ]
    }
  },
  {
    id: '2',
    number: 2,
    title: 'API timeout issue',
    issueTitle: 'API timeout issue under concurrent upstream gateway calls',
    repo: 'api-service',
    branch: 'main',
    issueNumber: 88,
    status: 'TESTING',
    progress: 85,
    estimatedTime: '~30 seconds',
    startedAt: 'Today, 14:15 UTC',
    duration: '2m 10s',
    riskLevel: 'Low Risk',
    rootCause: {
      summary: 'Connection pool lacks circuit breaker and fallback retry limits.',
      explanation: 'Requests to /v1/checkout hung indefinitely because HTTP client sockets had no socket read timeout configured when downstream aggregators experienced high packet loss.',
      targetFile: 'app/core/http_client.py',
      targetLine: 45
    },
    filesAnalyzed: [
      'app/routers/checkout.py',
      'app/core/http_client.py'
    ],
    testSummary: {
      total: 28,
      passed: 26,
      pending: 2,
      failed: 0
    },
    securitySummary: {
      level: 'Low Risk',
      noSecretsDetected: true,
      noDependencyChanges: true,
      changesLimitedToRequestedFiles: true,
      advisoryNotes: 'Applied standard 5-second socket timeout configuration.'
    },
    agents: [
      { id: 'agent-1', step: 1, name: 'Repository Analyzer', shortName: 'Analyzer', status: 'COMPLETE', time: '5s', summary: 'Scanned 89 python files.' },
      { id: 'agent-2', step: 2, name: 'Bug Investigator', shortName: 'Investigator', status: 'COMPLETE', time: '12s', summary: 'Reproduced hanging socket connection.' },
      { id: 'agent-3', step: 3, name: 'Code Repair Agent', shortName: 'Repair', status: 'COMPLETE', time: '14s', summary: 'Added httpx.Timeout(5.0) configuration.' },
      { id: 'agent-4', step: 4, name: 'Testing Agent', shortName: 'Testing', status: 'IN_PROGRESS', time: 'Active', summary: 'Running timeout simulation test suite.' },
      { id: 'agent-5', step: 5, name: 'Security Reviewer', shortName: 'Security', status: 'PENDING', time: 'Pending', summary: 'Awaiting test completion.' }
    ],
    logs: [
      { time: '14:15:02', agent: 'Analyzer', message: 'Analyzing FastAPI route definitions...' },
      { time: '14:15:07', agent: 'Investigator', message: 'Socket connection simulated with 30s latency...' },
      { time: '14:15:19', agent: 'Repair', message: 'Injecting timeout parameters into client factory...' },
      { time: '14:15:33', agent: 'Testing', message: 'Simulating concurrent requests under upstream latency...' }
    ],
    diff: {
      file: 'app/core/http_client.py',
      additions: 4,
      deletions: 1,
      lines: [
        { type: 'context', oldLine: 40, newLine: 40, text: 'def get_http_client():' },
        { type: 'remove', oldLine: 41, newLine: null, text: '-     return httpx.AsyncClient()' },
        { type: 'add', oldLine: null, newLine: 41, text: '+     timeout_config = httpx.Timeout(5.0, connect=2.0)' },
        { type: 'add', oldLine: null, newLine: 42, text: '+     return httpx.AsyncClient(timeout=timeout_config)' },
        { type: 'context', oldLine: 43, newLine: 43, text: '     # Client configured with bounded connection limits' }
      ]
    }
  },
  {
    id: '3',
    number: 3,
    title: 'Navbar rendering issue',
    issueTitle: 'Navbar rendering issue on viewport resize below 768px',
    repo: 'dashboard-ui',
    branch: 'main',
    issueNumber: 63,
    status: 'PR_READY',
    progress: 100,
    estimatedTime: 'Done',
    startedAt: 'Today, 13:40 UTC',
    duration: '1m 58s',
    riskLevel: 'Low Risk',
    rootCause: {
      summary: 'Missing dependency array in useResize hook causing state flicker.',
      explanation: 'ResizeObserver listener caused repetitive state invalidation when transitioning between screen breakpoints.',
      targetFile: 'src/components/Navigation.tsx',
      targetLine: 28
    },
    filesAnalyzed: [
      'src/components/Navigation.tsx'
    ],
    testSummary: {
      total: 19,
      passed: 19,
      pending: 0,
      failed: 0
    },
    securitySummary: {
      level: 'Low Risk',
      noSecretsDetected: true,
      noDependencyChanges: true,
      changesLimitedToRequestedFiles: true,
      advisoryNotes: 'No security risks identified.'
    },
    agents: [
      { id: 'agent-1', step: 1, name: 'Repository Analyzer', shortName: 'Analyzer', status: 'COMPLETE', time: '6s', summary: 'Scanned 210 files.' },
      { id: 'agent-2', step: 2, name: 'Bug Investigator', shortName: 'Investigator', status: 'COMPLETE', time: '10s', summary: 'Reproduced flicker on 768px resize.' },
      { id: 'agent-3', step: 3, name: 'Code Repair Agent', shortName: 'Repair', status: 'COMPLETE', time: '15s', summary: 'Added debounce guard to ResizeObserver.' },
      { id: 'agent-4', step: 4, name: 'Testing Agent', shortName: 'Testing', status: 'COMPLETE', time: '20s', summary: '19/19 tests passed.' },
      { id: 'agent-5', step: 5, name: 'Security Reviewer', shortName: 'Security', status: 'COMPLETE', time: '8s', summary: 'Security checks passed.' }
    ],
    logs: [
      { time: '13:40:01', agent: 'Analyzer', message: 'Scanned component directory...' },
      { time: '13:40:07', agent: 'Investigator', message: 'Re-render loop verified at 768px viewport breakpoint.' },
      { time: '13:40:17', agent: 'Repair', message: 'Debounce wrapper applied to window resize listener.' },
      { time: '13:40:37', agent: 'Testing', message: 'Component rendering tests PASSED.' },
      { time: '13:40:45', agent: 'Security', message: 'Security scan complete with 0 warnings.' }
    ],
    diff: {
      file: 'src/components/Navigation.tsx',
      additions: 3,
      deletions: 1,
      lines: [
        { type: 'context', oldLine: 25, newLine: 25, text: 'useEffect(() => {' },
        { type: 'remove', oldLine: 26, newLine: null, text: '-   window.addEventListener("resize", handleResize);' },
        { type: 'add', oldLine: null, newLine: 26, text: '+   const debounced = debounce(handleResize, 150);' },
        { type: 'add', oldLine: null, newLine: 27, text: '+   window.addEventListener("resize", debounced);' },
        { type: 'add', oldLine: null, newLine: 28, text: '+   return () => window.removeEventListener("resize", debounced);' },
        { type: 'context', oldLine: 29, newLine: 29, text: '}, []);' }
      ]
    }
  },
  {
    id: '4',
    number: 4,
    title: 'Database connection error',
    issueTitle: 'Database connection error during batch inference pool recycling',
    repo: 'ml-models',
    branch: 'main',
    issueNumber: 29,
    status: 'FAILED',
    progress: 42,
    estimatedTime: 'Failed',
    startedAt: 'Yesterday, 18:20 UTC',
    duration: '3m 12s',
    riskLevel: 'Medium Risk',
    rootCause: {
      summary: 'Unmanaged threadpool connection release deadlock.',
      explanation: 'The background thread pool terminated abruptly while postgres connections remained checked out, creating database deadlock.',
      targetFile: 'pipeline/db_pool.py',
      targetLine: 82
    },
    filesAnalyzed: [
      'pipeline/db_pool.py'
    ],
    testSummary: {
      total: 10,
      passed: 6,
      pending: 0,
      failed: 4
    },
    securitySummary: {
      level: 'Medium Risk',
      noSecretsDetected: true,
      noDependencyChanges: true,
      changesLimitedToRequestedFiles: true,
      advisoryNotes: 'Deadlock reproduction failed in mock environment. Human investigation required.'
    },
    agents: [
      { id: 'agent-1', step: 1, name: 'Repository Analyzer', shortName: 'Analyzer', status: 'COMPLETE', time: '4s', summary: 'Scanned 64 python files.' },
      { id: 'agent-2', step: 2, name: 'Bug Investigator', shortName: 'Investigator', status: 'FAILED', time: '48s', summary: 'Unable to deterministically reproduce deadlock.' },
      { id: 'agent-3', step: 3, name: 'Code Repair Agent', shortName: 'Repair', status: 'PENDING', time: 'Aborted', summary: 'Aborted due to non-reproducible condition.' },
      { id: 'agent-4', step: 4, name: 'Testing Agent', shortName: 'Testing', status: 'PENDING', time: 'Aborted', summary: 'Skipped.' },
      { id: 'agent-5', step: 5, name: 'Security Reviewer', shortName: 'Security', status: 'PENDING', time: 'Aborted', summary: 'Skipped.' }
    ],
    logs: [
      { time: '18:20:05', agent: 'Analyzer', message: 'Scanning database pool configurations...' },
      { time: '18:20:12', agent: 'Investigator', message: 'Spawning 100 concurrent inference workers...' },
      { time: '18:21:00', agent: 'Investigator', message: 'Timeout: could not induce deadlock deterministically after 5 attempts.' },
      { time: '18:21:05', agent: 'Investigator', message: 'Investigation marked as requiring manual engineer triage.' }
    ],
    diff: null
  }
];
