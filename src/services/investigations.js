/**
 * DevRescue AI - Investigations Service
 */

const STORAGE_KEY = 'devrescue_investigations_v1';

const INITIAL_INVESTIGATIONS = [
  {
    id: 'inv-47',
    number: 47,
    repo: 'acme-corp/payment-gateway',
    branch: 'main',
    issueNumber: 109,
    issueTitle: 'Race condition in idempotency ledger during concurrent capture calls',
    errorDescription: 'When two concurrent webhook events attempt to capture the same settlement ledger row, isolation level permits duplicate transaction credit records.',
    status: 'READY_FOR_REVIEW',
    startedAt: 'Today, 14:22 UTC',
    duration: '3m 21s',
    cost: '$0.42',
    currentAgentIndex: 4,
    agents: [
      { id: '1', name: 'Detective', role: 'Telemetry Triaging', status: 'PASSED', time: '44s', summary: 'Isolated bug to concurrent INSERT without FOR UPDATE lock in idempotency session.' },
      { id: '2', name: 'Analyst', role: 'Root Cause & AST', status: 'PASSED', time: '45s', summary: 'Discovered missing optimistic lock token check in PostgreSQL capture pipeline.' },
      { id: '3', name: 'Coder', role: 'Patch Synthesis', status: 'PASSED', time: '48s', summary: 'Added atomic UPSERT with SELECT FOR UPDATE NOWAIT and transaction isolation.' },
      { id: '4', name: 'Tester', role: 'CI Emulation', status: 'PASSED', time: '47s', summary: '5/5 unit tests passed. 2 new concurrency regression tests written & passed.' },
      { id: '5', name: 'Reporter', role: 'PR Explanation', status: 'PASSED', time: '17s', summary: 'Drafted semantic pull request body, changelog entry, and security advisory note.' },
    ],
    logs: [
      { time: '14:22:01', agent: 'SYS', message: 'Task initialized. Spinning ephemeral sandbox container [node:22-alpine]...' },
      { time: '14:22:06', agent: 'DETECTIVE', message: 'Cloned acme-corp/payment-gateway at commit 8f9b1c2 on branch main.' },
      { time: '14:22:15', agent: 'DETECTIVE', message: 'Reproduced stacktrace from Sentry issue #IDEM-992.' },
      { time: '14:22:38', agent: 'DETECTIVE', message: 'Stacktrace locates failure at src/ledger/capture_guard.ts:89.' },
      { time: '14:22:45', agent: 'ANALYST', message: 'Beginning AST analysis on src/ledger/capture_guard.ts.' },
      { time: '14:23:05', agent: 'ANALYST', message: 'Identified non-atomic read-then-write pattern in checkExistingSettlement().' },
      { time: '14:23:30', agent: 'CODER', message: 'Synthesizing patch using atomic SELECT ... FOR UPDATE query builder.' },
      { time: '14:23:55', agent: 'CODER', message: 'Patch created: +28 lines, -12 lines. Applying to local git working tree.' },
      { time: '14:24:18', agent: 'TESTER', message: 'Executing pnpm test:integration --filter=payment-gateway...' },
      { time: '14:24:32', agent: 'TESTER', message: 'Generated 2 new concurrent stress tests (100 simultaneous workers).' },
      { time: '14:25:05', agent: 'TESTER', message: 'All 7 test suites succeeded with 0 race condition anomalies.' },
      { time: '14:25:12', agent: 'REPORTER', message: 'Compiling investigation dossier and verified patch manifest.' },
      { time: '14:25:22', agent: 'REPORTER', message: 'Ready for human engineer review and pull request dispatch.' },
    ],
    rootCause: {
      file: 'src/ledger/capture_guard.ts',
      lineRange: 'L84-L112',
      summary: 'Non-atomic existence verification allows concurrent requests to simultaneously validate and commit duplicate ledger entries.',
      explanation: 'In the existing implementation, checkExistingSettlement() executes a non-locking SELECT query. In high-frequency webhook bursts from payment aggregators, two identical capture notifications arrive within 12 milliseconds of each other. Both read the absence of a settlement record simultaneously, pass validation, and subsequently invoke executeSettlement(), creating double ledger entries. The fix wraps the query in an atomic transaction with pessimistic row locking (`FOR UPDATE NOWAIT`) and an explicit idempotency key UNIQUE constraint handle.',
    },
    patch: {
      file: 'src/ledger/capture_guard.ts',
      originalCode: `export async function recordSettlement(
  client: DatabaseClient,
  idempotencyKey: string,
  amount: bigint
): Promise<SettlementResult> {
  // Vulnerable: non-atomic check allows duplicate settlement
  const existing = await client.query(
    'SELECT id, status FROM settlements WHERE idempotency_key = $1',
    [idempotencyKey]
  );

  if (existing.rows.length > 0) {
    return { status: 'DUPLICATE', id: existing.rows[0].id };
  }

  const result = await client.query(
    'INSERT INTO settlements (idempotency_key, amount, status) VALUES ($1, $2, $3) RETURNING id',
    [idempotencyKey, amount, 'CAPTURED']
  );

  return { status: 'SUCCESS', id: result.rows[0].id };
}`,
      modifiedCode: `export async function recordSettlement(
  client: DatabaseClient,
  idempotencyKey: string,
  amount: bigint
): Promise<SettlementResult> {
  // Rescued: Atomic transaction with row-level pessimistic locking
  return await client.transaction(async (tx) => {
    const existing = await tx.query(
      'SELECT id, status FROM settlements WHERE idempotency_key = $1 FOR UPDATE NOWAIT',
      [idempotencyKey]
    );

    if (existing.rows.length > 0) {
      return { status: 'DUPLICATE', id: existing.rows[0].id };
    }

    const result = await tx.query(
      'INSERT INTO settlements (idempotency_key, amount, status) VALUES ($1, $2, $3) ON CONFLICT (idempotency_key) DO NOTHING RETURNING id',
      [idempotencyKey, amount, 'CAPTURED']
    );

    if (result.rows.length === 0) {
      // Caught edge case race condition gracefully
      const recheck = await tx.query(
        'SELECT id FROM settlements WHERE idempotency_key = $1',
        [idempotencyKey]
      );
      return { status: 'DUPLICATE', id: recheck.rows[0].id };
    }

    return { status: 'SUCCESS', id: result.rows[0].id };
  });
}`,
    },
    testResults: [
      { name: 'settlement.test.ts > should succeed for first-time capture', status: 'PASSED', duration: '14ms' },
      { name: 'settlement.test.ts > should reject duplicate capture key cleanly', status: 'PASSED', duration: '19ms' },
      { name: 'concurrency.test.ts > 50 parallel capture workers on same key', status: 'PASSED', duration: '312ms' },
      { name: 'concurrency.test.ts > row-lock release after transaction abort', status: 'PASSED', duration: '45ms' },
      { name: 'ledger_audit.test.ts > zero discrepancy balance invariant', status: 'PASSED', duration: '88ms' },
    ],
    prNumber: null,
    prUrl: null,
  },
  {
    id: 'inv-46',
    number: 46,
    repo: 'hyperion/kernel-indexer',
    branch: 'master',
    issueNumber: 88,
    issueTitle: 'Panic on AST parsing of unterminated macro invocations in Rust 2024',
    errorDescription: 'Parser fails to recover token stream boundaries when encountering unclosed delimiters inside procedural attribute macros.',
    status: 'PR_OPENED',
    startedAt: 'Yesterday, 19:10 UTC',
    duration: '4m 12s',
    cost: '$0.58',
    currentAgentIndex: 4,
    agents: [
      { id: '1', name: 'Detective', role: 'Telemetry Triaging', status: 'PASSED', time: '52s', summary: 'Trace identified index-out-of-bounds in TokenCursor::peek().' },
      { id: '2', name: 'Analyst', role: 'Root Cause & AST', status: 'PASSED', time: '1m 05s', summary: 'Missing boundary check when stream terminates prematurely.' },
      { id: '3', name: 'Coder', role: 'Patch Synthesis', status: 'PASSED', time: '58s', summary: 'Added Option<Token> guard with graceful EOF token synthesis.' },
      { id: '4', name: 'Tester', role: 'CI Emulation', status: 'PASSED', time: '55s', summary: 'cargo test passed with 14 fuzzed test cases.' },
      { id: '5', name: 'Reporter', role: 'PR Explanation', status: 'PASSED', time: '22s', summary: 'PR #89 opened on hyperion/kernel-indexer.' },
    ],
    logs: [
      { time: '19:10:02', agent: 'SYS', message: 'Investigation #46 initiated.' },
      { time: '19:10:54', agent: 'DETECTIVE', message: 'Reproduced panic in syntax/lexer.rs:312.' },
      { time: '19:11:59', agent: 'ANALYST', message: 'Root cause verified: unchecked cursor advance on unterminated delimiter.' },
      { time: '19:12:57', agent: 'CODER', message: 'Patch written and formatted with rustfmt.' },
      { time: '19:13:52', agent: 'TESTER', message: 'All 14 rust test suites green.' },
      { time: '19:14:14', agent: 'REPORTER', message: 'Dispatched pull request #89.' }
    ],
    rootCause: {
      file: 'src/syntax/lexer.rs',
      lineRange: 'L310-L325',
      summary: 'TokenCursor::advance() unwrap() on None during sudden EOF inside attribute macro delimiter.',
      explanation: 'When macro delimiter parsing encounters EOF without closing brace, the cursor advances blindly past buffer length. Refactored into safe Option match with Diagnostic recovery error.',
    },
    patch: {
      file: 'src/syntax/lexer.rs',
      originalCode: `pub fn next_token(&mut self) -> Token {
    let raw = self.stream.get(self.cursor).unwrap();
    self.cursor += 1;
    raw.into()
}`,
      modifiedCode: `pub fn next_token(&mut self) -> Option<Token> {
    let raw = self.stream.get(self.cursor)?;
    self.cursor += 1;
    Some(raw.into())
}`,
    },
    testResults: [
      { name: 'parser_macro_unclosed_brace_test', status: 'PASSED', duration: '8ms' },
      { name: 'fuzz_syntax_tree_random_inputs', status: 'PASSED', duration: '142ms' },
    ],
    prNumber: 89,
    prUrl: 'https://github.com/hyperion/kernel-indexer/pull/89',
  },
  {
    id: 'inv-45',
    number: 45,
    repo: 'meridian/identity-service',
    branch: 'main',
    issueNumber: 54,
    issueTitle: 'JWT exp validation clock drift edge case permits expired refresh tokens',
    errorDescription: 'Negative skew offset calculation allows reuse of revoked refresh tokens within 60 second window.',
    status: 'PR_OPENED',
    startedAt: '2 days ago',
    duration: '2m 45s',
    cost: '$0.34',
    currentAgentIndex: 4,
    agents: [
      { id: '1', name: 'Detective', role: 'Telemetry Triaging', status: 'PASSED', time: '30s', summary: 'Clock drift offset verified.' },
      { id: '2', name: 'Analyst', role: 'Root Cause & AST', status: 'PASSED', time: '40s', summary: 'Leeway sign inversion in time comparison.' },
      { id: '3', name: 'Coder', role: 'Patch Synthesis', status: 'PASSED', time: '40s', summary: 'Fixed math clamp and added revoked token check.' },
      { id: '4', name: 'Tester', role: 'CI Emulation', status: 'PASSED', time: '35s', summary: 'Go test passed.' },
      { id: '5', name: 'Reporter', role: 'PR Explanation', status: 'PASSED', time: '20s', summary: 'PR #55 opened.' },
    ],
    logs: [
      { time: '11:00:00', agent: 'SYS', message: 'Investigation #45 started.' },
      { time: '11:02:45', agent: 'REPORTER', message: 'PR #55 merged.' }
    ],
    rootCause: {
      file: 'internal/auth/jwt.go',
      lineRange: 'L42-L55',
      summary: 'Time subtraction inverted resulting in negative skew acceptance.',
      explanation: 'Inverted skew parameter allowed expired tokens up to 60s in the past to validate.',
    },
    patch: {
      file: 'internal/auth/jwt.go',
      originalCode: `if now.Add(-leeway).After(claims.ExpiresAt.Time) { return ErrTokenExpired }`,
      modifiedCode: `if now.Add(leeway).After(claims.ExpiresAt.Time) { return ErrTokenExpired }`,
    },
    testResults: [
      { name: 'TestJWTExpirySkewEdgeCases', status: 'PASSED', duration: '4ms' }
    ],
    prNumber: 55,
    prUrl: 'https://github.com/meridian/identity-service/pull/55',
  }
];

export const investigationsService = {
  getInvestigations: () => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) return JSON.parse(stored);
    } catch {
      // ignore
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(INITIAL_INVESTIGATIONS));
    return INITIAL_INVESTIGATIONS;
  },

  getInvestigation: (id) => {
    const list = investigationsService.getInvestigations();
    return list.find((inv) => inv.id === id || String(inv.number) === String(id));
  },

  createInvestigation: ({ repo, branch, issueNumber, issueTitle, errorDescription }) => {
    const list = investigationsService.getInvestigations();
    const nextNumber = Math.max(...list.map((i) => i.number || 0), 47) + 1;
    const newId = `inv-${nextNumber}`;

    const newInv = {
      id: newId,
      number: nextNumber,
      repo: repo || 'acme-corp/payment-gateway',
      branch: branch || 'main',
      issueNumber: issueNumber || 104,
      issueTitle: issueTitle || 'Memory leak under sustained WebSocket reconnect churn in connection manager',
      errorDescription: errorDescription || 'Connection pool retains uncollected event listeners leading to heap exhaustion.',
      status: 'IN_PROGRESS',
      startedAt: 'Just now',
      duration: 'In progress',
      cost: '$0.00',
      currentAgentIndex: 0,
      agents: [
        { id: '1', name: 'Detective', role: 'Telemetry Triaging', status: 'RUNNING', time: 'Active', summary: 'Triaging stacktrace and creating reproducer sandbox...' },
        { id: '2', name: 'Analyst', role: 'Root Cause & AST', status: 'PENDING', time: '—', summary: 'Waiting for telemetry confirmation' },
        { id: '3', name: 'Coder', role: 'Patch Synthesis', status: 'PENDING', time: '—', summary: 'Waiting for root cause diagnosis' },
        { id: '4', name: 'Tester', role: 'CI Emulation', status: 'PENDING', time: '—', summary: 'Waiting for patch synthesis' },
        { id: '5', name: 'Reporter', role: 'PR Explanation', status: 'PENDING', time: '—', summary: 'Waiting for test suite run' },
      ],
      logs: [
        { time: new Date().toLocaleTimeString(), agent: 'SYS', message: `Initializing DevRescue agent orchestrator for ${repo}...` },
        { time: new Date().toLocaleTimeString(), agent: 'DETECTIVE', message: 'Checking repository permissions and cloning AST representation...' },
        { time: new Date().toLocaleTimeString(), agent: 'DETECTIVE', message: `Target issue #${issueNumber}: "${issueTitle}"` }
      ],
      rootCause: {
        file: 'src/connection/pool.ts',
        lineRange: 'L142-L178',
        summary: 'EventListener leak during socket reconnect backoff loop.',
        explanation: 'Each reconnection attempt binds an anonymous callback to the heartbeat timer without disposing the previous listener handle upon error.'
      },
      patch: {
        file: 'src/connection/pool.ts',
        originalCode: `export class SocketPool {
  attachHeartbeat(socket: WebSocket) {
    // Uncollected listener on reconnect
    socket.on('ping', () => this.recordActivity());
  }
}`,
        modifiedCode: `export class SocketPool {
  private listenerMap = new WeakMap<WebSocket, () => void>();

  attachHeartbeat(socket: WebSocket) {
    this.detachHeartbeat(socket);
    const cb = () => this.recordActivity();
    this.listenerMap.set(socket, cb);
    socket.on('ping', cb);
  }

  detachHeartbeat(socket: WebSocket) {
    const existing = this.listenerMap.get(socket);
    if (existing) {
      socket.off('ping', existing);
      this.listenerMap.delete(socket);
    }
  }
}`
      },
      testResults: [
        { name: 'pool.test.ts > listener cleanup on abrupt socket drop', status: 'PASSED', duration: '22ms' },
        { name: 'pool.test.ts > sustained 5000 reconnect cycles memory ceiling', status: 'PASSED', duration: '240ms' },
      ],
      prNumber: null,
      prUrl: null
    };

    const updated = [newInv, ...list];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    return newInv;
  },

  updateInvestigation: (id, updates) => {
    const list = investigationsService.getInvestigations();
    const updated = list.map((item) => (item.id === id ? { ...item, ...updates } : item));
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    return updated.find((i) => i.id === id);
  }
};
