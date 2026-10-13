/**
 * DevRescue AI - AI Agents Registry
 */

export const AGENT_CREW = [
  {
    numeral: '01',
    id: 'detective',
    name: 'The Detective',
    subtitle: 'TELEMETRY & STACKTRACE TRIAGING',
    role: 'Root Failure Isolation',
    accentWord: 'observes',
    description:
      'The Detective ingests production exception logs, Sentry breadcrumbs, and raw GitHub issue dumps. It inspects commit ancestry, maps unhandled runtime exceptions back to exact AST nodes, and generates a minimal reproducible sandbox environment within an ephemeral container.',
    tools: ['Git Log Walker', 'Sentry DSN Parser', 'Docker Ephemeral Sandbox', 'AST Source Locator'],
    metrics: {
      invocations: '1,420',
      avgLatency: '38s',
      isolationAccuracy: '99.1%',
    },
    quote: '"Before altering a single line of grammar, one must observe the exact conditions of failure without speculation."',
  },
  {
    numeral: '02',
    id: 'analyst',
    name: 'The Analyst',
    subtitle: 'ROOT CAUSE & INVARIANT PROVING',
    role: 'Semantic Code Verification',
    accentWord: 'diagnoses',
    description:
      'The Analyst evaluates code invariants, concurrency barriers, and execution lifetimes. It reads control flow graphs across function boundaries, detecting race conditions, negative time offsets, memory leaks, and unchecked null references before proposing structural remedies.',
    tools: ['Tree-Sitter Query Engine', 'Static Call-Graph Tracer', 'Concurrency Race Prover', 'LLVM Invariant Analyzer'],
    metrics: {
      invocations: '1,388',
      avgLatency: '44s',
      falsePositiveRate: '0.8%',
    },
    quote: '"A bug is rarely a flaw of syntax; it is an assumption violated under the weight of unforeseen concurrency."',
  },
  {
    numeral: '03',
    id: 'coder',
    name: 'The Coder',
    subtitle: 'PATCH SYNTHESIS & MINIMAL DIFFS',
    role: 'Targeted Code Repair',
    accentWord: 'restores',
    description:
      'The Coder adheres to the philosophy of surgical minimalism. It synthesizes precise git diffs that respect the repository\'s existing formatting, naming conventions, and idiomatic paradigms. It avoids unnecessary refactorings, modifying only the minimal viable character sequence.',
    tools: ['Language Server Protocol (LSP)', 'Prettier/Rustfmt/gofmt Runner', 'Atomic Diff Generator', 'Semantic Rebaser'],
    metrics: {
      invocations: '1,340',
      avgLatency: '51s',
      medianDiffSize: '+18 / -6',
    },
    quote: '"The finest patch is not the one that rewrites the system, but the one that disappears into the existing rhythm of the prose."',
  },
  {
    numeral: '04',
    id: 'tester',
    name: 'The Tester',
    subtitle: 'STRESS EMULATION & CI VERIFICATION',
    role: 'Adversarial Test Synthesis',
    accentWord: 'challenges',
    description:
      'The Tester writes adversarial regression test cases designed to prove the fix and guard against future regressions. It executes the existing test suite inside isolated sandboxes, runs fuzzing loops, and measures execution overhead before issuing green CI certification.',
    tools: ['Jest / PyTest / Cargo Test Runner', 'Fuzzing Input Generator', 'Isolated MicroVM Runner', 'Coverage Diff Validator'],
    metrics: {
      invocations: '1,290',
      avgLatency: '46s',
      regressionPassRate: '98.7%',
    },
    quote: '"Code without adversarial trials is mere belief; only failing tests turned green constitute empirical proof."',
  },
  {
    numeral: '05',
    id: 'reporter',
    name: 'The Reporter',
    subtitle: 'PR EXPLANATION & CHANGELOG DRAFTING',
    role: 'Pull Request Dispatch',
    accentWord: 'articulates',
    description:
      'The Reporter drafts eloquent, clear pull request descriptions following Conventional Commits and GitHub markdown standards. It details the root cause, links relevant issues, provides benchmark measurements, and notes any architectural considerations for human reviewers.',
    tools: ['GitHub Octokit API', 'Semantic Changelog Generator', 'Markdown Typographer', 'Review Checklist Builder'],
    metrics: {
      invocations: '1,260',
      avgLatency: '19s',
      humanMergeRate: '94.2%',
    },
    quote: '"Clear prose is the final courtesy an engineer owes to those who will read the git history five years hence."',
  },
];
