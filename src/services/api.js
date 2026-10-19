/**
 * DevRescue AI - Frontend API Client
 * Interfaces directly with FastAPI backend.
 * Uses VITE_API_URL environment variable (never hardcoded).
 * Includes credentials for secure HTTP-only session cookies.
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

// Request timeouts. Long-running AI/Docker operations get a larger budget so a
// slow-but-healthy operation is not misreported as a network failure.
const DEFAULT_TIMEOUT_MS = 120000;
const AI_TIMEOUT_MS = 420000;      // Nemotron (up to 3 attempts) + GitHub retrieval
const SANDBOX_TIMEOUT_MS = 900000; // Docker image build + dependency prep + test run

export const ERROR_CODES = {
  NETWORK_ERROR: 'NETWORK_ERROR',
  REQUEST_TIMEOUT: 'REQUEST_TIMEOUT',
  REQUEST_ABORTED: 'REQUEST_ABORTED'
};

async function request(endpoint, options = {}) {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, signal: externalSignal, ...fetchOptions } = options;
  const url = `${API_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(fetchOptions.headers || {})
  };

  const controller = new AbortController();
  let timedOut = false;
  const timer = timeoutMs > 0
    ? setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs)
    : null;

  // Link an optional external cancellation signal to our controller.
  let onExternalAbort = null;
  if (externalSignal) {
    if (externalSignal.aborted) {
      controller.abort();
    } else {
      onExternalAbort = () => controller.abort();
      externalSignal.addEventListener('abort', onExternalAbort);
    }
  }

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      headers,
      credentials: 'include', // Sends session cookie securely across origins
      signal: controller.signal
    });

    if (!response.ok) {
      let errorMessage = `API error: ${response.status} ${response.statusText}`;
      let errorData = null;
      try {
        errorData = await response.json();
        errorMessage = errorData.message || errorData.detail?.message || errorData.detail || errorMessage;
      } catch {
        // use default error message
      }
      const err = new Error(errorMessage);
      err.status = response.status;
      err.data = errorData;
      err.errorCode = (errorData && (errorData.error_code || errorData.error)) || null;
      err.isHttpError = true;
      throw err;
    }

    return await response.json();
  } catch (error) {
    // 1. Client-side timeout: the request did not complete within the budget.
    if (timedOut) {
      const err = new Error(`Request to ${endpoint} timed out after ${Math.round(timeoutMs / 1000)}s. The backend may still be processing; this operation is NOT confirmed and must be retried.`);
      err.status = null;
      err.errorCode = ERROR_CODES.REQUEST_TIMEOUT;
      err.isTimeout = true;
      console.error(`[DevRescue API Timeout] ${endpoint}:`, err);
      throw err;
    }

    // 2. Explicit cancellation (e.g. a superseded run) — surface distinctly.
    if (error?.name === 'AbortError') {
      const err = new Error('Request was cancelled.');
      err.status = null;
      err.errorCode = ERROR_CODES.REQUEST_ABORTED;
      err.isAborted = true;
      throw err;
    }

    // 3. Transport-level failure: server down, connection reset, DNS, or CORS
    //    (this is what the browser reports as "Failed to fetch"). Never treat
    //    this as a successful result.
    if (error?.name === 'TypeError') {
      const err = new Error(`Cannot reach the DevRescue backend at ${API_URL}. The request to ${endpoint} failed at the network layer (server not running, connection reset, or blocked by CORS).`);
      err.status = null;
      err.errorCode = ERROR_CODES.NETWORK_ERROR;
      err.isNetworkError = true;
      err.cause = error;
      console.error(`[DevRescue API Network Error] ${endpoint}:`, error);
      throw err;
    }

    // 4. Already-classified HTTP error, or anything else — rethrow unchanged.
    console.error(`[DevRescue API Error] ${endpoint}:`, error);
    throw error;
  } finally {
    if (timer) clearTimeout(timer);
    if (externalSignal && onExternalAbort) {
      externalSignal.removeEventListener('abort', onExternalAbort);
    }
  }
}

// -------------------------------------------------------------
// 1. Health & Status
// -------------------------------------------------------------
export async function healthCheck() {
  return request('/api/health');
}

export async function getRiskHealth() {
  return request('/api/risk/health');
}

// -------------------------------------------------------------
// 2. ML XGBoost Risk Prediction
// -------------------------------------------------------------
export async function predictRisk(features) {
  return request('/api/risk/predict', {
    method: 'POST',
    body: JSON.stringify(features)
  });
}

// -------------------------------------------------------------
// 3. Autonomous Multi-Agent Investigations
// -------------------------------------------------------------
export async function createInvestigation(data) {
  // Support both GitHub-connected metadata and legacy payload
  const payload = data.issue_url || data.repository || data.owner
    ? {
        repository: data.repository || data.repo,
        owner: data.owner,
        repo: data.repo,
        branch: data.branch || 'main',
        issue_number: Number(data.issue_number || data.issueNumber),
        issue_title: data.issue_title || data.issueTitle || data.title,
        issue_url: data.issue_url || data.issueUrl,
        error_description: data.error_description || data.errorDescription || '',
        mode: data.mode || 'real'
      }
    : {
        repo: data.repo,
        issue_title: data.issueTitle || data.title,
        error_description: data.errorDescription || data.description || '',
        branch: data.branch || 'main',
        issue_number: Number(data.issueNumber) || 42,
        mode: data.mode || 'real'
      };

  return request('/api/investigations', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export async function getInvestigations() {
  return request('/api/investigations');
}

export async function getInvestigation(id) {
  return request(`/api/investigations/${id}`);
}

export async function getInvestigationLogs(id) {
  return request(`/api/investigations/${id}/logs`);
}

export async function approveInvestigation(id) {
  return request(`/api/investigations/${id}/approve`, {
    method: 'POST'
  });
}

export async function rejectInvestigation(id, reason = '') {
  return request(`/api/investigations/${id}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason })
  });
}

export async function syncInvestigation(id, data) {
  return request(`/api/investigations/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data)
  });
}

export async function listRuns(id) {
  return request(`/api/investigations/${id}/runs`);
}

export async function startRun(id, data = {}) {
  return request(`/api/investigations/${id}/runs`, {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

export async function getRun(id, runId) {
  return request(`/api/investigations/${id}/runs/${runId}`);
}

export async function approveRun(id, runId, payload = {}) {
  return request(`/api/investigations/${id}/runs/${runId}/approve`, {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

// -------------------------------------------------------------
// 3b. Real NVIDIA Nemotron Investigation API
// -------------------------------------------------------------
export async function investigateNemotron(payload, options = {}) {
  console.log('[REAL INVESTIGATION] POST /api/ai/nemotron/investigate', payload);
  return request('/api/ai/nemotron/investigate', {
    method: 'POST',
    body: JSON.stringify(payload),
    timeoutMs: AI_TIMEOUT_MS,
    ...options
  });
}

export async function generateNemotronPatch(payload, options = {}) {
  return request('/api/ai/nemotron/generate-patch', {
    method: 'POST',
    body: JSON.stringify(payload),
    timeoutMs: AI_TIMEOUT_MS,
    ...options
  });
}

export async function generatePatch(payload, options = {}) {
  console.log('[REAL PATCH] POST /api/ai/nemotron/patch', payload);
  return request('/api/ai/nemotron/patch', {
    method: 'POST',
    body: JSON.stringify(payload),
    timeoutMs: AI_TIMEOUT_MS,
    ...options
  });
}

export async function runSandboxTest(payload, options = {}) {
  console.log('[REAL SANDBOX TEST] POST /api/ai/sandbox/test', payload);
  return request('/api/ai/sandbox/test', {
    method: 'POST',
    body: JSON.stringify(payload),
    timeoutMs: SANDBOX_TIMEOUT_MS,
    ...options
  });
}

export async function getSandboxStatus() {
  return request('/api/ai/sandbox/status');
}

export async function scanSecurity(patch) {
  console.log('[SECURITY SCAN] POST /api/ai/sandbox/security-scan');
  return request('/api/ai/sandbox/security-scan', {
    method: 'POST',
    body: JSON.stringify({ patch })
  });
}



// -------------------------------------------------------------
// 4. GitHub Real Integration APIs
// -------------------------------------------------------------
export function githubLogin() {
  window.location.href = `${import.meta.env.VITE_API_URL || API_URL}/api/github/login?redirect=true`;
}

export async function getGithubUser() {
  return request('/api/github/me');
}

export async function disconnectGithub() {
  return request('/api/github/disconnect', {
    method: 'POST'
  });
}

export async function getGithubRepositories(page = 1, perPage = 30) {
  return request(`/api/github/repositories?page=${page}&per_page=${perPage}`);
}

export async function getGithubRepository(owner, repo) {
  return request(`/api/github/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`);
}

export async function getGithubBranches(owner, repo) {
  return request(`/api/github/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/branches`);
}

export async function getGithubIssues(owner, repo, state = 'open') {
  return request(`/api/github/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/issues?state=${state}`);
}

export async function getGithubIssue(owner, repo, issueNumber) {
  return request(`/api/github/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/issues/${issueNumber}`);
}

export async function getGithubTree(owner, repo, branch) {
  return request(`/api/github/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/tree?branch=${encodeURIComponent(branch)}`);
}

export async function getGithubFile(owner, repo, path, ref) {
  const query = ref ? `?path=${encodeURIComponent(path)}&ref=${encodeURIComponent(ref)}` : `?path=${encodeURIComponent(path)}`;
  return request(`/api/github/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/file${query}`);
}

export async function getGithubLanguages(owner, repo) {
  return request(`/api/github/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/languages`);
}

export async function getGithubCommits(owner, repo, branch) {
  const query = branch ? `?branch=${encodeURIComponent(branch)}` : '';
  return request(`/api/github/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/commits${query}`);
}

// -------------------------------------------------------------
// 5. Repositories & Pull Requests
// -------------------------------------------------------------
export async function getRepositories() {
  return request('/api/repositories');
}

export async function getPullRequests() {
  return request('/api/pull-requests');
}

export async function createPullRequest(data) {
  const payload = {
    ...data,
    approved: data.approved !== undefined ? data.approved : (data.human_approved !== undefined ? data.human_approved : true)
  };
  return request('/api/pull-requests', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

// -------------------------------------------------------------
// 7. Multi-Repository Discovery & Auto-Repair Queue
// -------------------------------------------------------------
export async function discoverRepositoriesAndIssues(options = {}) {
  return request('/api/queue/discover', {
    method: 'POST',
    body: JSON.stringify(options)
  });
}

export async function getQueueRepositories() {
  return request('/api/queue/repositories');
}

export async function getQueueIssues(params = {}) {
  const query = new URLSearchParams();
  if (params.repo) query.set('repo', params.repo);
  if (params.severity) query.set('severity', params.severity);
  if (params.triage_status) query.set('triage_status', params.triage_status);
  if (params.search) query.set('search', params.search);
  const qStr = query.toString();
  return request(`/api/queue/issues${qStr ? `?${qStr}` : ''}`);
}

export async function enqueueIssues(issueKeys, priorityOverride = null) {
  return request('/api/queue/enqueue', {
    method: 'POST',
    body: JSON.stringify({
      issue_keys: issueKeys,
      priority_override: priorityOverride
    })
  });
}

export async function getQueueJobs(params = {}) {
  const query = new URLSearchParams();
  if (params.status) query.set('status', params.status);
  if (params.repo) query.set('repo', params.repo);
  const qStr = query.toString();
  return request(`/api/queue/jobs${qStr ? `?${qStr}` : ''}`);
}

export async function getQueueJob(jobId) {
  return request(`/api/queue/jobs/${encodeURIComponent(jobId)}`);
}

export async function cancelQueueJob(jobId) {
  return request(`/api/queue/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: 'POST'
  });
}

export async function retryQueueJob(jobId, force = false) {
  return request(`/api/queue/jobs/${encodeURIComponent(jobId)}/retry`, {
    method: 'POST',
    body: JSON.stringify({ force })
  });
}

export async function approveQueueJob(jobId, patchHash = null, comment = null) {
  return request(`/api/queue/jobs/${encodeURIComponent(jobId)}/approve`, {
    method: 'POST',
    body: JSON.stringify({ patch_hash: patchHash, comment })
  });
}

export async function startQueueProcessing() {
  return request('/api/queue/start', { method: 'POST' });
}

export async function pauseQueueProcessing() {
  return request('/api/queue/pause', { method: 'POST' });
}

export async function getQueueStats() {
  return request('/api/queue/stats');
}

export async function updateQueueConfig(config) {
  return request('/api/queue/config', {
    method: 'PUT',
    body: JSON.stringify(config)
  });
}

const api = {
  healthCheck,
  getRiskHealth,
  predictRisk,
  createInvestigation,
  getInvestigations,
  getInvestigation,
  getInvestigationLogs,
  approveInvestigation,
  rejectInvestigation,
  syncInvestigation,
  listRuns,
  startRun,
  getRun,
  approveRun,
  investigateNemotron,
  generateNemotronPatch,
  generatePatch,
  runSandboxTest,
  getSandboxStatus,
  scanSecurity,
  githubLogin,
  getGithubUser,
  disconnectGithub,
  getGithubRepositories,
  getGithubRepository,
  getGithubBranches,
  getGithubIssues,
  getGithubIssue,
  getGithubTree,
  getGithubFile,
  getGithubLanguages,
  getGithubCommits,
  getRepositories,
  getPullRequests,
  createPullRequest,
  discoverRepositoriesAndIssues,
  getQueueRepositories,
  getQueueIssues,
  enqueueIssues,
  getQueueJobs,
  getQueueJob,
  cancelQueueJob,
  retryQueueJob,
  approveQueueJob,
  startQueueProcessing,
  pauseQueueProcessing,
  getQueueStats,
  updateQueueConfig
};

export { api };
export default api;

