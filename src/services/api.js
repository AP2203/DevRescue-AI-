/**
 * DevRescue AI - Frontend API Client
 * Interfaces directly with FastAPI backend.
 * Uses VITE_API_URL environment variable (never hardcoded).
 * Includes credentials for secure HTTP-only session cookies.
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

async function request(endpoint, options = {}) {
  const url = `${API_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  };

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      credentials: 'include' // Sends session cookie securely across origins
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
      throw err;
    }

    return await response.json();
  } catch (error) {
    console.error(`[DevRescue API Error] ${endpoint}:`, error);
    throw error;
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
export async function investigateNemotron(payload) {
  console.log('[REAL INVESTIGATION] POST /api/ai/nemotron/investigate', payload);
  return request('/api/ai/nemotron/investigate', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export async function generateNemotronPatch(payload) {
  return request('/api/ai/nemotron/generate-patch', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export async function generatePatch(payload) {
  console.log('[REAL PATCH] POST /api/ai/nemotron/patch', payload);
  return request('/api/ai/nemotron/patch', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export async function runSandboxTest(payload) {
  console.log('[REAL SANDBOX TEST] POST /api/ai/sandbox/test', payload);
  return request('/api/ai/sandbox/test', {
    method: 'POST',
    body: JSON.stringify(payload)
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
  createPullRequest
};

export { api };
export default api;

