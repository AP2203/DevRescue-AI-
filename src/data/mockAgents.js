/**
 * DevRescue AI - Mock AI Agents Registry
 * Defines the 5 specialized autonomous software engineering agents.
 */

export const MOCK_AGENTS = [
  {
    id: 'analyzer',
    step: 1,
    name: 'Repository Analyzer',
    shortName: 'Analyzer',
    badge: 'Step 01',
    role: 'Codebase Topology & Dependency Mapping',
    description: 'Scans the repository structure, traces abstract syntax trees (AST), inspects git history, and isolates files relevant to the reported issue.',
    capabilities: [
      'Multi-language AST indexing (JS, TS, Python, Go)',
      'Cross-file import & dependency graph reconstruction',
      'Git blame & recent commit delta attribution',
      'Targeted file identification'
    ],
    tools: ['Tree-Sitter Parser', 'LSP Indexer', 'Git Graph Walker', 'Module Resolver'],
    metrics: {
      averageTime: '4.2s',
      filesPerSec: '850 files/s',
      relevanceScore: '99.4%'
    }
  },
  {
    id: 'investigator',
    step: 2,
    name: 'Bug Investigator',
    shortName: 'Investigator',
    badge: 'Step 02',
    role: 'Root Cause Isolation & Reproduction',
    description: 'Reproduces the reported bug in an isolated runtime environment, parses stack traces, and detects the exact broken invariant or missing reference.',
    capabilities: [
      'Deterministic crash reproduction in sandboxed microVM',
      'Stack trace decompilation & frame isolation',
      'Runtime state inspection & variable dump',
      'Invariant validation and failure diagnosis'
    ],
    tools: ['Sandbox Container', 'Debugger Inspector', 'Crash Replay Engine', 'Stack Decoupler'],
    metrics: {
      averageTime: '8.6s',
      reproducibilityRate: '94.2%',
      falsePositiveRate: '0.6%'
    }
  },
  {
    id: 'repair',
    step: 3,
    name: 'Code Repair Agent',
    shortName: 'Repair Agent',
    badge: 'Step 03',
    role: 'Surgical Patch Synthesis',
    description: 'Generates minimal, clean code fixes conforming to existing repo conventions, lint rules, and formatting styles without unwanted refactoring.',
    capabilities: [
      'Minimal line-delta patch generation',
      'Style & convention conformity (ESLint, Prettier, Black)',
      'Multi-file atomic patch bundling',
      'Context-aware syntax validation'
    ],
    tools: ['AST Transformer', 'Idiomatic Synthesizer', 'Diff Minimizer', 'Formatter Guard'],
    metrics: {
      averageTime: '12.4s',
      medianDiffSize: '+6 / -2 lines',
      lintCompliance: '100%'
    }
  },
  {
    id: 'testing',
    step: 4,
    name: 'Testing Agent',
    shortName: 'Testing Agent',
    badge: 'Step 04',
    role: 'Automated Test Execution & Regression Proving',
    description: 'Executes existing unit, integration, and end-to-end tests against the synthesized patch, plus generates regression tests to ensure no regressions.',
    capabilities: [
      'Execution of Jest, Vitest, PyTest test suites',
      'Automated new regression test case synthesis',
      'Flaky test detection and isolation',
      '100% green test verification proof'
    ],
    tools: ['Test Harness Runner', 'Coverage Evaluator', 'Mutation Tester', 'Regression Guard'],
    metrics: {
      averageTime: '18.1s',
      testsVerified: '100%',
      regressionRate: '0.0%'
    }
  },
  {
    id: 'security',
    step: 5,
    name: 'Security Reviewer',
    shortName: 'Security Reviewer',
    badge: 'Step 05',
    role: 'Static Security & Dependency Analysis',
    description: 'Performs automated security review of the proposed patch, checking for secret leakage, insecure deserialization, dependency tampering, and privilege escalations.',
    capabilities: [
      'High-entropy secret and credential scanning',
      'Supply-chain & package.json modification check',
      'OWASP Top 10 pattern matching',
      'Automated security advisory note generation'
    ],
    tools: ['Secret Hunter', 'SAST Engine', 'Dependency Lock Auditor', 'Permissive Scope Checker'],
    metrics: {
      averageTime: '5.8s',
      secretsCaught: '100%',
      riskClassification: 'Accurate'
    }
  }
];

export const WORKFLOW_PIPELINE_STEPS = [
  { step: 1, title: 'GitHub Issue', desc: 'Ingest bug report or stacktrace' },
  { step: 2, title: 'Repository Analysis', desc: 'Scan codebase & identify target modules' },
  { step: 3, title: 'Bug Investigation', desc: 'Reproduce bug & isolate root cause' },
  { step: 4, title: 'Code Repair', desc: 'Synthesize minimal surgical patch' },
  { step: 5, title: 'Testing', desc: 'Run existing test suite & regression checks' },
  { step: 6, title: 'Security Review', desc: 'Scan for secrets & vulnerability risks' },
  { step: 7, title: 'Human Approval', desc: 'Maintainer reviews and signs off fix' },
  { step: 8, title: 'Pull Request', desc: 'Synthesize verified PR with changelog' }
];
