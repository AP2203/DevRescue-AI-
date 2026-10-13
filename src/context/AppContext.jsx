import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { MOCK_REPOSITORIES } from '../data/mockRepositories';
import { MOCK_INVESTIGATIONS } from '../data/mockInvestigations';
import { MOCK_PULL_REQUESTS } from '../data/mockPullRequests';
import api from '../services/api';

const AppContext = createContext(null);

const STORAGE_KEYS = {
  REPOS: 'devrescue_mock_repos_v2',
  INVESTIGATIONS: 'devrescue_mock_investigations_v2',
  PRS: 'devrescue_mock_prs_v2',
  APP_MODE: 'devrescue_app_mode_v1'
};

export function AppProvider({ children }) {
  // Mode: 'REAL' (uses FastAPI + XGBoost + Real GitHub) vs 'DEMO' (uses local mock data)
  const initialAppMode = (() => {
    try {
      return localStorage.getItem(STORAGE_KEYS.APP_MODE) || 'REAL';
    } catch {
      return 'REAL';
    }
  })();

  const [appMode, setAppModeState] = useState(initialAppMode);

  const [backendHealth, setBackendHealth] = useState({
    status: 'checking',
    mlStatus: null,
    details: null
  });

  // Real GitHub connection state
  const [githubUser, setGithubUser] = useState(null);
  const [githubConnected, setGithubConnected] = useState(false);
  const [githubLoading, setGithubLoading] = useState(false);

  const [repositories, setRepositories] = useState(MOCK_REPOSITORIES);
  const [investigations, setInvestigations] = useState(MOCK_INVESTIGATIONS);
  const [pullRequests, setPullRequests] = useState(() => {
    if (initialAppMode === 'REAL') {
      return [];
    }
    try {
      const saved = localStorage.getItem(STORAGE_KEYS.PRS);
      return saved ? JSON.parse(saved) : MOCK_PULL_REQUESTS;
    } catch {
      return MOCK_PULL_REQUESTS;
    }
  });
  const [notifications, setNotifications] = useState([]);

  const setAppMode = (mode) => {
    setAppModeState(mode);
    try {
      localStorage.setItem(STORAGE_KEYS.APP_MODE, mode);
    } catch {
      // ignore
    }
    if (mode === 'REAL') {
      api.getPullRequests().then((prs) => {
        setPullRequests(Array.isArray(prs) ? prs : []);
      }).catch(() => {
        setPullRequests([]);
      });
    } else {
      try {
        const saved = localStorage.getItem(STORAGE_KEYS.PRS);
        setPullRequests(saved ? JSON.parse(saved) : MOCK_PULL_REQUESTS);
      } catch {
        setPullRequests(MOCK_PULL_REQUESTS);
      }
    }
  };

  const addNotification = useCallback((message, type = 'success') => {
    const id = Date.now() + Math.random().toString();
    setNotifications((prev) => [{ id, message, type }, ...prev].slice(0, 4));
    setTimeout(() => {
      setNotifications((prev) => prev.filter((n) => n.id !== id));
    }, 4500);
  }, []);

  const removeNotification = useCallback((id) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const checkGithubStatus = useCallback(async () => {
    setGithubLoading(true);
    try {
      const res = await api.getGithubUser();
      if (res && res.authenticated && res.user) {
        setGithubUser(res.user);
        setGithubConnected(true);
      } else {
        setGithubUser(null);
        setGithubConnected(false);
      }
    } catch {
      setGithubUser(null);
      setGithubConnected(false);
    } finally {
      setGithubLoading(false);
    }
  }, []);

  const disconnectGithub = useCallback(async () => {
    try {
      await api.disconnectGithub();
      setGithubUser(null);
      setGithubConnected(false);
      addNotification('✓ GitHub disconnected');
    } catch (err) {
      addNotification(`Failed to disconnect GitHub: ${err.message}`, 'error');
    }
  }, [addNotification]);

  // Check backend health & sync data on startup
  useEffect(() => {
    let isMounted = true;

    async function checkBackend() {
      try {
        const health = await api.healthCheck();
        if (!isMounted) return;

        setBackendHealth({
          status: health.status || 'healthy',
          mlStatus: health.components?.ml_risk_model || 'healthy',
          details: health
        });

        // In REAL MODE: check GitHub connection and backend items
        if (appMode === 'REAL') {
          checkGithubStatus();

          try {
            const [backendInvs, backendPrs] = await Promise.allSettled([
              api.getInvestigations(),
              api.getPullRequests()
            ]);

            if (backendInvs.status === 'fulfilled' && Array.isArray(backendInvs.value)) {
              setInvestigations(backendInvs.value);
            }
            if (backendPrs.status === 'fulfilled' && Array.isArray(backendPrs.value)) {
              setPullRequests(backendPrs.value);
            }
          } catch (e) {
            console.warn('[DevRescue] Could not load backend collections:', e);
          }
        }
      } catch (err) {
        if (!isMounted) return;
        setBackendHealth({
          status: 'offline',
          mlStatus: 'offline',
          details: { error: err.message }
        });
      }
    }

    checkBackend();
    return () => {
      isMounted = false;
    };
  }, [appMode, checkGithubStatus]);

  // Demo mode localStorage synchronization
  useEffect(() => {
    if (appMode === 'DEMO') {
      try {
        localStorage.setItem(STORAGE_KEYS.INVESTIGATIONS, JSON.stringify(investigations));
        localStorage.setItem(STORAGE_KEYS.REPOS, JSON.stringify(repositories));
        localStorage.setItem(STORAGE_KEYS.PRS, JSON.stringify(pullRequests));
      } catch {
        // ignore
      }
    }
  }, [investigations, repositories, pullRequests, appMode]);

  const resetDemoData = () => {
    setRepositories(MOCK_REPOSITORIES);
    setInvestigations(MOCK_INVESTIGATIONS);
    setPullRequests(MOCK_PULL_REQUESTS);
    try {
      localStorage.removeItem(STORAGE_KEYS.REPOS);
      localStorage.removeItem(STORAGE_KEYS.INVESTIGATIONS);
      localStorage.removeItem(STORAGE_KEYS.PRS);
    } catch {
      // ignore
    }
    addNotification('✓ Demo data reset');
  };

  const connectRepository = (data) => {
    const newRepo = {
      id: `repo-${Date.now()}`,
      name: data.name || 'custom-app',
      fullName: `acme-corp/${data.name || 'custom-app'}`,
      owner: 'acme-corp',
      language: data.language || 'JavaScript',
      filterCategory: data.filterCategory || 'Other',
      filesCount: data.filesCount || 95,
      openIssuesCount: 1,
      defaultBranch: 'main',
      branches: ['main', 'develop'],
      lastActivity: 'Just now',
      lastUpdated: 'Just now',
      description: data.description || 'Connected repository via DevRescue AI.',
      issues: [
        {
          id: `iss-${Date.now()}`,
          number: 1,
          title: 'Initial reported issue',
          description: 'Example bug reported for this newly registered repository.',
          status: 'Open',
          author: 'maintainer',
          createdAt: 'Just now',
          labels: ['bug']
        }
      ]
    };
    setRepositories((prev) => [newRepo, ...prev]);
    addNotification(`Repository "${newRepo.name}" registered.`);
    return newRepo;
  };

  const createInvestigation = async (params) => {
    if (appMode === 'REAL') {
      // REAL MODE: NEVER silently fall back to mock data
      const realInv = await api.createInvestigation(params);
      setInvestigations((prev) => [realInv, ...prev]);
      addNotification('✓ Investigation created and connected to GitHub');
      return realInv;
    }

    // Demo Mode fallback
    const issueTitle = params.issueTitle || params.issue_title || params.title;
    const repo = params.repo || params.repository || 'demo-react-app';
    const branch = params.branch || 'main';
    const issueNumber = params.issueNumber || params.issue_number || 42;
    const errorDescription = params.errorDescription || params.error_description || '';

    const newId = String(investigations.length + 1);
    const newInv = {
      id: newId,
      number: investigations.length + 1,
      mode: 'DEMO',
      title: issueTitle || 'Issue investigation',
      issueTitle: issueTitle || 'Issue investigation',
      repo: repo,
      branch: branch,
      issueNumber: Number(issueNumber) || 42,
      status: 'IN_PROGRESS',
      progress: 35,
      estimatedTime: '~1 minute',
      startedAt: 'Just now',
      duration: '0m 15s',
      riskLevel: 'Low Risk',
      rootCause: {
        summary: errorDescription ? `Identified cause: ${errorDescription.slice(0, 75)}...` : 'authenticateUser is referenced without the required import.',
        explanation: errorDescription || 'The issue occurred because authenticateUser was referenced from the wrong module.',
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
        failed: 0
      },
      securitySummary: {
        level: 'Low Risk',
        noSecretsDetected: true,
        noDependencyChanges: true,
        changesLimitedToRequestedFiles: true,
        advisoryNotes: 'Verified clean AST modification. Simulated demo checks.'
      },
      agents: [
        { id: 'a1', step: 1, name: 'Repository Analyzer', shortName: 'Analyzer', status: 'COMPLETE', time: '4s', summary: 'Scanned repository structure.' },
        { id: 'a2', step: 2, name: 'Bug Investigator', shortName: 'Investigator', status: 'COMPLETE', time: '8s', summary: 'Reproduced error in sandbox.' },
        { id: 'a3', step: 3, name: 'Code Repair Agent', shortName: 'Repair', status: 'IN_PROGRESS', time: 'Active', summary: 'Generating minimal patch...' },
        { id: 'a4', step: 4, name: 'Testing Agent', shortName: 'Testing', status: 'PENDING', time: 'Pending', summary: 'Queued to run tests.' },
        { id: 'a5', step: 5, name: 'Security Reviewer', shortName: 'Security', status: 'PENDING', time: 'Pending', summary: 'Queued for security review.' }
      ],
      logs: [
        { time: new Date().toLocaleTimeString(), agent: 'Analyzer', message: `Scanning repository ${repo}...` },
        { time: new Date().toLocaleTimeString(), agent: 'Investigator', message: `Reproducing issue #${issueNumber}...` },
        { time: new Date().toLocaleTimeString(), agent: 'Repair', message: 'Generating minimal patch...' }
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
          { type: 'context', oldLine: 5, newLine: 5, text: '  // Updated import allows authenticateUser to resolve' }
        ]
      }
    };

    setInvestigations((prev) => [newInv, ...prev]);
    addNotification('✓ Demo investigation started');
    return newInv;
  };

  const getInvestigation = (id) => {
    return investigations.find((i) => String(i.id) === String(id) || String(i.number) === String(id));
  };

  const updateInvestigation = (id, updates) => {
    let updatedItem = null;
    setInvestigations((prev) =>
      prev.map((item) => {
        if (String(item.id) === String(id) || String(item.number) === String(id)) {
          updatedItem = { ...item, ...updates };
          return updatedItem;
        }
        return item;
      })
    );
    return updatedItem;
  };

  const approvePatchAndOpenPR = async (investigationId) => {
    const inv = getInvestigation(investigationId);
    if (!inv) return null;

    if (appMode === 'REAL') {
      try {
        const result = await api.approveInvestigation(inv.id);
        const pr = result.pull_request || {
          id: `pr-${result.pr_number}`,
          number: result.pr_number,
          repo: inv.repo || inv.repository,
          title: result.investigation?.title || inv.title,
          status: 'OPEN',
          branch: result.branch,
          commit_sha: result.commit_sha,
          pr_url: result.pr_url,
          prUrl: result.pr_url,
          html_url: result.pr_url,
          human_approved: true
        };
        setPullRequests((prev) => [pr, ...prev.filter((p) => String(p.number) !== String(pr.number))]);
        updateInvestigation(inv.id, {
          status: 'PR_READY',
          human_approved: true,
          prNumber: pr.number,
          prUrl: pr.pr_url || pr.prUrl || pr.html_url
        });
        addNotification(`✓ Pull Request #${pr.number} created on GitHub`);
        return pr;
      } catch (err) {
        addNotification(`Approval failed: ${err.message}`, 'error');
        throw err;
      }
    }

    // Demo Mode PR preparation
    const newPrNumber = 129 + pullRequests.length;
    const newPr = {
      id: `pr-${newPrNumber}`,
      number: newPrNumber,
      title: `Fix ${inv.title?.toLowerCase() || 'issue'}`,
      detailedTitle: `fix(${inv.repo}): ${inv.title}`,
      repo: inv.repo,
      branch: `devrescue/fix-issue-${inv.issueNumber}`,
      baseBranch: inv.branch || 'main',
      issueNumber: inv.issueNumber,
      issueTitle: inv.title,
      status: 'READY_FOR_REVIEW',
      statusLabel: 'Ready for Review',
      testsStatus: 'Passed',
      testsDetail: 'Simulated demo tests',
      securityStatus: 'Passed',
      securityDetail: 'Low Risk · Demo review',
      author: 'DevRescue AI [Bot]',
      createdAt: 'Just now',
      filesChangedCount: inv.filesAnalyzed?.length || 1,
      filesChanged: inv.filesAnalyzed || ['src/handler.py'],
      additions: 3,
      deletions: 1,
      aiSummary: inv.rootCause?.explanation || 'Autonomously generated patch.',
      investigationId: String(inv.id),
      isDemoPr: true
    };

    setPullRequests((prev) => [newPr, ...prev]);
    updateInvestigation(inv.id, {
      status: 'PR_READY',
      progress: 100,
      estimatedTime: 'Done'
    });

    addNotification('✓ Fix approved (Demo Mode)');
    return newPr;
  };

  const rejectPatch = async (investigationId, feedback = '') => {
    if (appMode === 'REAL') {
      try {
        await api.rejectInvestigation(investigationId, feedback);
      } catch {
        // continue local state update
      }
    }
    updateInvestigation(investigationId, {
      status: 'REJECTED',
      rejectionReason: feedback
    });
    addNotification('Fix rejected. Investigation marked for revision.', 'info');
  };

  return (
    <AppContext.Provider
      value={{
        appMode,
        setAppMode,
        backendHealth,
        githubUser,
        githubConnected,
        githubLoading,
        checkGithubStatus,
        disconnectGithub,
        repositories,
        investigations,
        pullRequests,
        notifications,
        addNotification,
        removeNotification,
        resetDemoData,
        connectRepository,
        createInvestigation,
        getInvestigation,
        updateInvestigation,
        approvePatchAndOpenPR,
        rejectPatch
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
}

