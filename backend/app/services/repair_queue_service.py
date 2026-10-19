import os
import json
import time
import asyncio
import logging
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Tuple

from app.core.config import settings
from app.services.github_service import (
    github_service,
    GitHubError,
    GitHubAuthError,
    GitHubRateLimitError,
    GitHubTimeoutError,
    GitHubConnectionError,
    GitHubConflictError,
    GitHubValidationError
)
from app.services.investigation_service import investigation_service, StageStatus
from app.schemas.repair_queue import (
    JobStatus,
    TriageStatus,
    IssueSeverity,
    DiscoveredRepository,
    DiscoveredIssue,
    QueueJob,
    QueueStats,
    QueueConfig
)

logger = logging.getLogger("devrescue.repair_queue")

QUEUE_STATE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "repair_queue_state.json"
)

SUPPORTED_LANGUAGES = {"Python", "JavaScript", "TypeScript", "Java"}


def calculate_issue_priority_and_triage(
    issue: Dict[str, Any],
    repo_lang: str = "Other",
    has_test_suite: bool = False
) -> Tuple[int, str, str, str, Optional[str]]:
    """
    Computes priority score (0-100), severity, category, triage_status, and triage_reason.
    Does not assume every issue is a code defect.
    Categorizes feature requests, unclear reports, unsupported languages, and questions.
    """
    labels = [l.lower() for l in issue.get("labels", [])]
    title = (issue.get("title") or "").strip()
    body = (issue.get("body") or "").strip()
    full_text = f"{title}\n{body}".lower()

    # 1. Non-defect classification:
    # Feature request / enhancement
    is_feature = any(lbl in ("enhancement", "feature", "feature request", "proposal", "rfc") for lbl in labels) or \
                 any(k in title.lower() for k in ("feature request", "add support for", "proposal:", "feature:"))
    if is_feature:
        return 35, "low", "feature_request", TriageStatus.REQUIRES_REVIEW.value, "Feature request: requires design specification rather than automated bug repair."

    # Questions / Documentation / Discussion
    is_question = any(lbl in ("question", "documentation", "docs", "discussion", "needs-info", "help wanted") for lbl in labels)
    if is_question:
        return 30, "low", "needs_info", TriageStatus.REQUIRES_REVIEW.value, "Clarification or documentation task: requires maintainer triage."

    # Unsupported language
    if repo_lang and repo_lang != "Other" and repo_lang not in SUPPORTED_LANGUAGES:
        return 20, "low", "unsupported_runtime", TriageStatus.BLOCKED.value, f"Unsupported language '{repo_lang}': DevRescue AI currently supports Python, Node.js, and Java."

    # Unclear / insufficient issue description (< 35 chars and no error trace)
    has_stack_trace = any(pattern in full_text for pattern in ("traceback", "error:", "exception:", "fail", "errno", "nullpointer", "typeerror", "referenceerror", "syntaxerror"))
    has_code_block = "```" in body or "<code>" in body
    if len(body) < 35 and not has_stack_trace and not has_code_block:
        return 25, "low", "unclear", TriageStatus.REQUIRES_REVIEW.value, "Unclear report: description is too brief (< 35 chars) with no stack trace or error log."

    # 2. Severity scoring:
    score = 50
    severity = "medium"

    if any(lbl in ("critical", "blocker", "p0", "security", "high-priority", "urgent") for lbl in labels):
        score += 30
        severity = "critical"
    elif any(lbl in ("bug", "high", "p1") for lbl in labels):
        score += 20
        severity = "high"
    elif any(lbl in ("medium", "p2") for lbl in labels):
        score += 10
        severity = "medium"
    elif any(lbl in ("low", "minor", "p3") for lbl in labels):
        score -= 10
        severity = "low"

    # 3. Reproducibility & Quality:
    if has_stack_trace:
        score += 15
    if has_code_block or "reproduce" in full_text or "steps to" in full_text:
        score += 10
    if len(body) > 120:
        score += 5

    # 4. Test availability:
    if has_test_suite:
        score += 10

    # 5. Language support bonus:
    if repo_lang in SUPPORTED_LANGUAGES:
        score += 10

    clamped_score = max(1, min(100, score))
    return clamped_score, severity, "defect", TriageStatus.READY_FOR_REPAIR.value, None


class RepairQueueService:
    """
    Multi-Repository GitHub Issue Auto-Repair Orchestrator.
    Manages discovery, prioritization, background worker scheduling,
    resumability, mutual exclusion, rate limiting, and human approval gates.
    """

    def __init__(self, state_file: str = QUEUE_STATE_FILE):
        self.state_file = state_file
        self.repositories: Dict[str, DiscoveredRepository] = {}
        self.issues: Dict[str, DiscoveredIssue] = {}  # key: "owner/repo#number"
        self.jobs: Dict[str, QueueJob] = {}           # key: job_id
        self.config = QueueConfig(max_concurrency=2, per_repo_concurrency=1, auto_process=True)

        self._lock = asyncio.Lock()
        self._active_issue_locks: Set[str] = set()    # Active issue keys currently executing
        self._active_workers: int = 0
        self._worker_task: Optional[asyncio.Task] = None
        self._is_processing: bool = False

        # Load persisted jobs and recover interrupted states
        self._load_state()

    # -------------------------------------------------------------
    # State Persistence & Recovery
    # -------------------------------------------------------------

    def _load_state(self) -> None:
        """Loads jobs, repositories, and issues from disk, recovering interrupted jobs."""
        if not os.path.isfile(self.state_file):
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 1. Repositories
            for r_data in data.get("repositories", []):
                repo_obj = DiscoveredRepository(**r_data)
                self.repositories[repo_obj.full_name.lower()] = repo_obj

            # 2. Issues
            for i_data in data.get("issues", []):
                issue_obj = DiscoveredIssue(**i_data)
                key = f"{issue_obj.repo_full_name.lower()}#{issue_obj.number}"
                self.issues[key] = issue_obj

            # 3. Jobs with Restart Recovery
            for j_data in data.get("jobs", []):
                job_obj = QueueJob(**j_data)
                # Restart Recovery: if job was interrupted during active execution, recover to PENDING
                if job_obj.status in (JobStatus.INVESTIGATING.value, JobStatus.TESTING.value, JobStatus.SECURITY_REVIEW.value):
                    logger.info(f"[RECOVERY] Recovered interrupted job {job_obj.job_id} ({job_obj.status}) to PENDING after restart.")
                    job_obj.status = JobStatus.PENDING.value
                    job_obj.updated_at = datetime.utcnow().isoformat()
                    job_obj.logs.append({
                        "timestamp": datetime.utcnow().isoformat(),
                        "agent": "SYS",
                        "level": "INFO",
                        "message": "Recovered job to PENDING after backend restart. Eligible for resumption."
                    })
                self.jobs[job_obj.job_id] = job_obj

            # 4. Config
            if "config" in data:
                self.config = QueueConfig(**data["config"])

            logger.info(f"[QUEUE] Loaded {len(self.repositories)} repos, {len(self.issues)} issues, {len(self.jobs)} jobs from disk.")
        except Exception as e:
            logger.error(f"[QUEUE] Failed to load queue state from {self.state_file}: {e}", exc_info=True)

    def _save_state(self) -> None:
        """Atomically persists queue state to disk."""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            data = {
                "repositories": [r.model_dump() for r in self.repositories.values()],
                "issues": [i.model_dump() for i in self.issues.values()],
                "jobs": [j.model_dump() for j in self.jobs.values()],
                "config": self.config.model_dump(),
                "saved_at": datetime.utcnow().isoformat()
            }
            tmp_file = f"{self.state_file}.tmp.{os.getpid()}"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            if os.path.exists(self.state_file):
                os.replace(tmp_file, self.state_file)
            else:
                os.rename(tmp_file, self.state_file)
        except Exception as e:
            logger.warning(f"[QUEUE] Failed to persist queue state: {e}")

    # -------------------------------------------------------------
    # Multi-Repository & Issue Discovery
    # -------------------------------------------------------------

    async def discover_repositories_and_issues(
        self,
        access_token: str,
        repositories: Optional[List[str]] = None,
        org_filter: Optional[str] = None,
        force_refresh: bool = False,
        max_issues_per_repo: int = 30
    ) -> Dict[str, Any]:
        """
        Discovers accessible repositories and open issues using the authenticated token.
        Supports pagination, organization filtering, incremental updates, and exclusion rules.
        """
        now_iso = datetime.utcnow().isoformat()

        # 1. Fetch user accessible repositories
        all_repos = []
        page = 1
        per_page = 50
        while True:
            repos_page = await github_service.list_repositories(access_token, page=page, per_page=per_page)
            if not repos_page:
                break
            all_repos.extend(repos_page)
            if len(repos_page) < per_page or len(all_repos) >= 100:
                break
            page += 1

        # Apply org_filter or repo selection
        filtered_repos = []
        target_keys = {r.strip().lower() for r in repositories} if repositories else None

        for r in all_repos:
            full_name = r.get("full_name", "").lower()
            owner = r.get("owner", "").lower()
            if target_keys and full_name not in target_keys and r.get("name", "").lower() not in target_keys:
                continue
            if org_filter and org_filter.lower() != owner:
                continue
            filtered_repos.append(r)

        discovered_repos_count = 0
        discovered_issues_count = 0

        for r in filtered_repos:
            repo_full_name = r.get("full_name")
            owner = r.get("owner")
            name = r.get("name")
            default_branch = r.get("default_branch") or "main"
            language = r.get("language") or "Other"

            # Check incremental refresh (skip if scanned in last 5 minutes unless force_refresh)
            existing_repo = self.repositories.get(repo_full_name.lower())
            if not force_refresh and existing_repo and existing_repo.last_scanned_at:
                try:
                    last_dt = datetime.fromisoformat(existing_repo.last_scanned_at)
                    if (datetime.utcnow() - last_dt).total_seconds() < 300:
                        continue
                except Exception:
                    pass

            # Update repository record
            repo_entry = DiscoveredRepository(
                id=r.get("id"),
                name=name,
                full_name=repo_full_name,
                owner=owner,
                description=r.get("description") or "",
                private=bool(r.get("private")),
                default_branch=default_branch,
                language=language,
                open_issues_count=r.get("open_issues", 0),
                stars=r.get("stars", 0),
                forks=r.get("forks", 0),
                last_scanned_at=now_iso,
                scan_status="scanning"
            )
            self.repositories[repo_full_name.lower()] = repo_entry
            discovered_repos_count += 1

            # Discover issues for repository
            try:
                raw_issues = await github_service.list_issues(access_token, owner, name, state="open")
                for item in raw_issues[:max_issues_per_repo]:
                    # Section 1 rules: Exclude PRs, locked issues, closed issues
                    if item.get("pull_request") is not None:
                        continue
                    if item.get("locked"):
                        continue
                    if item.get("state") != "open":
                        continue

                    labels = [l.lower() for l in item.get("labels", [])]
                    # Exclude duplicate / invalid / wontfix
                    if any(l in ("duplicate", "invalid", "wontfix") for l in labels):
                        continue

                    # Prioritization & Triage evaluation
                    priority, severity, category, triage_status, triage_reason = calculate_issue_priority_and_triage(
                        item,
                        repo_lang=language,
                        has_test_suite=language in ("Python", "JavaScript", "TypeScript", "Java")
                    )

                    issue_number = item["number"]
                    issue_key = f"{repo_full_name.lower()}#{issue_number}"

                    issue_obj = DiscoveredIssue(
                        id=item["id"],
                        repo_full_name=repo_full_name,
                        owner=owner,
                        repo=name,
                        number=issue_number,
                        title=item["title"],
                        body=item.get("body", ""),
                        author=item.get("author", "unknown"),
                        html_url=item.get("html_url") or f"https://github.com/{repo_full_name}/issues/{issue_number}",
                        labels=item.get("labels", []),
                        state=item.get("state", "open"),
                        created_at=item.get("created_at") or now_iso,
                        updated_at=item.get("updated_at") or now_iso,
                        priority_score=priority,
                        severity=severity,
                        category=category,
                        triage_status=triage_status,
                        triage_reason=triage_reason,
                        has_test_suite=language in ("Python", "JavaScript", "TypeScript", "Java"),
                        language=language,
                        estimated_risk="low" if priority < 60 else "medium"
                    )
                    self.issues[issue_key] = issue_obj
                    discovered_issues_count += 1

                repo_entry.scan_status = "scanned"
            except Exception as scan_err:
                logger.warning(f"[DISCOVERY] Error listing issues for {repo_full_name}: {scan_err}")
                repo_entry.scan_status = "error"
                repo_entry.error_message = str(scan_err)

        self._save_state()
        return {
            "status": "success",
            "repositories_discovered": len(self.repositories),
            "new_repositories_scanned": discovered_repos_count,
            "issues_discovered": len(self.issues),
            "new_issues_indexed": discovered_issues_count
        }

    # -------------------------------------------------------------
    # Queue Management
    # -------------------------------------------------------------

    def enqueue_issue(
        self,
        issue_key: str,
        priority_override: Optional[int] = None
    ) -> QueueJob:
        """
        Enqueues an issue into the repair job queue idempotently.
        Prevents duplicate jobs for the same issue.
        """
        issue_key_norm = issue_key.strip().lower()
        issue = self.issues.get(issue_key_norm)
        if not issue:
            # Try splitting owner/repo#number
            if "#" in issue_key_norm:
                repo_part, num_part = issue_key_norm.split("#", 1)
                owner, repo = repo_part.split("/", 1) if "/" in repo_part else ("owner", repo_part)
                num = int(num_part)
                # Create synthetic issue object
                issue = DiscoveredIssue(
                    id=num,
                    repo_full_name=f"{owner}/{repo}",
                    owner=owner,
                    repo=repo,
                    number=num,
                    title=f"Repair issue #{num}",
                    html_url=f"https://github.com/{owner}/{repo}/issues/{num}",
                    created_at=datetime.utcnow().isoformat(),
                    updated_at=datetime.utcnow().isoformat()
                )
                self.issues[issue_key_norm] = issue
            else:
                raise KeyError(f"Issue '{issue_key}' not found in discovered index.")

        job_id = f"job_{issue.owner}_{issue.repo}_{issue.number}".lower()

        # Idempotent deduplication: reuse existing job if pending or running
        if job_id in self.jobs:
            existing = self.jobs[job_id]
            if existing.status in (JobStatus.PENDING.value, JobStatus.INVESTIGATING.value, JobStatus.TESTING.value):
                if priority_override:
                    existing.priority_score = priority_override
                    self._save_state()
                return existing

        priority = priority_override or issue.priority_score
        repo_obj = self.repositories.get(issue.repo_full_name.lower())
        default_branch = repo_obj.default_branch if repo_obj else "main"

        job = QueueJob(
            job_id=job_id,
            repo_full_name=issue.repo_full_name,
            owner=issue.owner,
            repo=issue.repo,
            issue_number=issue.number,
            issue_title=issue.title,
            issue_url=issue.html_url,
            branch=default_branch,
            status=JobStatus.PENDING.value,
            priority_score=priority,
            retry_count=0,
            max_retries=3,
            logs=[
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "agent": "SYS",
                    "level": "INFO",
                    "message": f"Issue #{issue.number} enqueued with priority score {priority}."
                }
            ]
        )

        self.jobs[job_id] = job
        self._save_state()
        return job

    def cancel_job(self, job_id: str) -> QueueJob:
        """Cancels a pending or active job."""
        job = self.jobs.get(job_id)
        if not job:
            raise KeyError(f"Job '{job_id}' not found.")

        job.status = JobStatus.CANCELLED.value
        job.updated_at = datetime.utcnow().isoformat()
        job.logs.append({
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "SYS",
            "level": "INFO",
            "message": "Job cancelled by operator."
        })
        # Release mutex lock if active
        issue_key = f"{job.owner}/{job.repo}#{job.issue_number}".lower()
        self._active_issue_locks.discard(issue_key)

        self._save_state()
        return job

    def retry_job(self, job_id: str, force: bool = False) -> QueueJob:
        """
        Manually retries a failed, blocked, or cancelled job.
        Resets error states and moves job to PENDING.
        """
        job = self.jobs.get(job_id)
        if not job:
            raise KeyError(f"Job '{job_id}' not found.")

        job.status = JobStatus.PENDING.value
        job.retry_count = 0 if force else job.retry_count + 1
        job.blocked_reason = None
        job.error_summary = None
        job.updated_at = datetime.utcnow().isoformat()
        job.logs.append({
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "SYS",
            "level": "INFO",
            "message": f"Job reset to PENDING for retry attempt #{job.retry_count}."
        })

        issue_key = f"{job.owner}/{job.repo}#{job.issue_number}".lower()
        self._active_issue_locks.discard(issue_key)

        self._save_state()
        return job

    # -------------------------------------------------------------
    # Concurrency, Execution & Recovery
    # -------------------------------------------------------------

    async def start_queue_processing(self, access_token: Optional[str] = None) -> None:
        """Starts the autonomous queue processing background worker."""
        self._is_processing = True
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._queue_worker_loop(access_token))
        logger.info("[QUEUE] Autonomous queue processing started.")

    def pause_queue_processing(self) -> None:
        """Pauses the queue processor."""
        self._is_processing = False
        logger.info("[QUEUE] Autonomous queue processing paused.")

    async def _queue_worker_loop(self, access_token: Optional[str] = None) -> None:
        """
        Continuous worker loop respecting global & per-repo concurrency limits,
        issue mutual exclusion, and rate limits.
        """
        while self._is_processing:
            try:
                # Find eligible pending jobs
                available_slots = self.config.max_concurrency - self._active_workers
                if available_slots > 0:
                    pending_candidates = [
                        j for j in self.jobs.values()
                        if j.status == JobStatus.PENDING.value
                    ]
                    # Sort by priority_score DESC, created_at ASC
                    pending_candidates.sort(key=lambda j: (-j.priority_score, j.created_at))

                    for job in pending_candidates:
                        if self._active_workers >= self.config.max_concurrency:
                            break

                        issue_key = f"{job.owner}/{job.repo}#{job.issue_number}".lower()
                        # Mutual exclusion: prevent concurrent worker on same issue
                        if issue_key in self._active_issue_locks:
                            continue

                        # Per-repository concurrency limit
                        active_repo_count = sum(
                            1 for active_key in self._active_issue_locks
                            if active_key.startswith(f"{job.owner}/{job.repo}".lower())
                        )
                        if active_repo_count >= self.config.per_repo_concurrency:
                            continue

                        # Claim lock and dispatch job
                        self._active_issue_locks.add(issue_key)
                        self._active_workers += 1
                        asyncio.create_task(self._process_single_job(job, access_token))

                await asyncio.sleep(1.0)
            except Exception as loop_err:
                logger.error(f"[QUEUE] Error in worker loop: {loop_err}", exc_info=True)
                await asyncio.sleep(2.0)

    async def _process_single_job(self, job: QueueJob, access_token: Optional[str] = None) -> None:
        """
        Executes end-to-end investigation, patch synthesis, testing, security,
        and approval staging for a single queued issue.
        """
        issue_key = f"{job.owner}/{job.repo}#{job.issue_number}".lower()
        now_iso = datetime.utcnow().isoformat()
        job.started_at = now_iso
        job.status = JobStatus.INVESTIGATING.value
        job.updated_at = now_iso
        self._save_state()

        try:
            # 1. Non-defect triage check: Block if issue is categorized as feature or unclear
            issue_item = self.issues.get(issue_key)
            if issue_item and issue_item.triage_status in (TriageStatus.BLOCKED.value, TriageStatus.REQUIRES_REVIEW.value):
                job.status = JobStatus.BLOCKED.value
                job.blocked_reason = issue_item.triage_reason or "Issue requires human review."
                job.logs.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "agent": "TRIAGE",
                    "level": "WARNING",
                    "message": f"Auto-repair halted: {job.blocked_reason}"
                })
                self._save_state()
                return

            # 2. Initialize or attach to Investigation
            inv = await investigation_service.create_github_investigation(
                repository=job.repo_full_name,
                owner=job.owner,
                repo=job.repo,
                branch=job.branch,
                issue_number=job.issue_number,
                issue_title=job.issue_title,
                issue_url=job.issue_url
            )
            job.investigation_id = inv["id"]
            job.run_id = inv["latest_run_id"]

            # 3. Execute staged run
            run_result = await investigation_service.execute_staged_run(
                inv_id=inv["id"],
                run_id=job.run_id,
                access_token=access_token,
                mode="real" if access_token else "demo"
            )

            # 4. Inspect outcomes and record dossiers
            run_stages = {s["key"]: s for s in run_result.get("stages", [])}
            patch_data = run_result.get("patch") or {}
            test_data = run_result.get("sandbox_result") or {}
            sec_data = run_result.get("security_result") or {}
            risk_data = run_result.get("risk_assessment") or {}

            job.patch_summary = patch_data
            job.test_summary = test_data
            job.security_summary = sec_data
            job.risk_summary = risk_data
            job.patch_hash = patch_data.get("patch_hash")

            # Check if testing succeeded
            test_status = test_data.get("status")

            if test_status == "PASSED":
                job.status = JobStatus.AWAITING_APPROVAL.value
                job.logs.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "agent": "SYS",
                    "level": "INFO",
                    "message": f"Tests PASSED. Synthesized patch {job.patch_hash[:10]}... awaiting mandatory human approval."
                })
            elif test_status == "DEPENDENCIES_UNAVAILABLE":
                job.status = JobStatus.BLOCKED.value
                job.blocked_reason = f"Dependencies unavailable: {test_data.get('message', 'Could not prepare container dependencies.')}"
                job.logs.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "agent": "TESTER",
                    "level": "ERROR",
                    "message": job.blocked_reason
                })
            elif test_status == "TESTS_NOT_CONFIGURED":
                job.status = JobStatus.AWAITING_APPROVAL.value
                job.logs.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "agent": "TESTER",
                    "level": "WARNING",
                    "message": "No tests configured in repository. Patch generated and awaiting human review."
                })
            elif test_status in ("FAILED", "ENVIRONMENT_ERROR"):
                job.status = JobStatus.BLOCKED.value
                job.blocked_reason = f"Container tests failed ({test_status}): {test_data.get('message', 'Test assertions failed after repair retry.')}"
                job.logs.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "agent": "TESTER",
                    "level": "ERROR",
                    "message": job.blocked_reason
                })
            elif not patch_data.get("patch"):
                job.status = JobStatus.BLOCKED.value
                job.blocked_reason = "Nemotron could not synthesize a minimal unified patch."
                job.logs.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "agent": "REPAIR",
                    "level": "ERROR",
                    "message": job.blocked_reason
                })
            else:
                job.status = JobStatus.AWAITING_APPROVAL.value

        except (GitHubTimeoutError, GitHubConnectionError, GitHubRateLimitError) as trans_err:
            logger.warning(f"[JOB {job.job_id}] Transient error: {trans_err}")
            job.error_summary = f"Transient network/API error: {str(trans_err)}"
            if job.retry_count < job.max_retries:
                job.status = JobStatus.PENDING.value
                job.retry_count += 1
                job.logs.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "agent": "SYS",
                    "level": "WARNING",
                    "message": f"Transient error encountered: {job.error_summary}. Scheduled for retry ({job.retry_count}/{job.max_retries})."
                })
            else:
                job.status = JobStatus.FAILED.value
                job.blocked_reason = f"Exceeded max retries after transient failures: {job.error_summary}"
        except Exception as det_err:
            logger.error(f"[JOB {job.job_id}] Fatal deterministic error: {det_err}", exc_info=True)
            job.status = JobStatus.FAILED.value
            job.error_summary = str(det_err)
            job.blocked_reason = f"Execution failed: {str(det_err)}"
            job.logs.append({
                "timestamp": datetime.utcnow().isoformat(),
                "agent": "SYS",
                "level": "ERROR",
                "message": f"Execution halted: {str(det_err)}"
            })
        finally:
            job.completed_at = datetime.utcnow().isoformat()
            job.updated_at = datetime.utcnow().isoformat()
            self._active_issue_locks.discard(issue_key)
            self._active_workers = max(0, self._active_workers - 1)
            self._save_state()

    # -------------------------------------------------------------
    # Human Approval & PR Dispatch
    # -------------------------------------------------------------

    async def approve_job_and_dispatch_pr(
        self,
        job_id: str,
        patch_hash: Optional[str] = None,
        access_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enforces human approval bound to exact run_id and verified patch_hash.
        Dispatches GitHub PR and updates job state to PR_CREATED only on success.
        """
        job = self.jobs.get(job_id)
        if not job:
            raise KeyError(f"Job '{job_id}' not found.")

        if not job.investigation_id or not job.run_id:
            raise ValueError(f"Job '{job_id}' has not executed an investigation run yet.")

        # Recheck patch hash validity
        expected_hash = job.patch_hash
        if patch_hash and expected_hash and patch_hash != expected_hash:
            raise ValueError(
                f"Approval rejected: patch hash mismatch (received {patch_hash}, expected {expected_hash}). "
                f"Patch may have been revised or modified."
            )

        # Call investigation_service.approve_run
        res = await investigation_service.approve_run(
            inv_id=job.investigation_id,
            run_id=job.run_id,
            patch_hash=expected_hash,
            access_token=access_token
        )

        job.status = JobStatus.PR_CREATED.value
        job.pull_request = res.get("pull_request")
        job.updated_at = datetime.utcnow().isoformat()
        job.logs.append({
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "PR Dispatcher",
            "level": "INFO",
            "message": f"PR #{res.get('pr_number')} verified and created: {res.get('pr_url')}"
        })

        self._save_state()
        return res

    # -------------------------------------------------------------
    # Statistics & Reporting
    # -------------------------------------------------------------

    def get_stats(self) -> QueueStats:
        """Returns consolidated queue and multi-repository metrics."""
        jobs_list = list(self.jobs.values())

        waiting = sum(1 for j in jobs_list if j.status == JobStatus.PENDING.value)
        running = sum(1 for j in jobs_list if j.status in (JobStatus.INVESTIGATING.value, JobStatus.TESTING.value, JobStatus.SECURITY_REVIEW.value))
        blocked = sum(1 for j in jobs_list if j.status in (JobStatus.BLOCKED.value, JobStatus.FAILED.value))
        awaiting = sum(1 for j in jobs_list if j.status == JobStatus.AWAITING_APPROVAL.value)
        approved = sum(1 for j in jobs_list if j.status == JobStatus.APPROVED.value)
        prs_created = sum(1 for j in jobs_list if j.status == JobStatus.PR_CREATED.value)

        tests_passed = sum(1 for j in jobs_list if j.test_summary and j.test_summary.get("status") == "PASSED")
        tests_failed = sum(1 for j in jobs_list if j.test_summary and j.test_summary.get("status") in ("FAILED", "ENVIRONMENT_ERROR"))

        return QueueStats(
            repositories_scanned=len(self.repositories),
            open_issues_discovered=len(self.issues),
            waiting_count=waiting,
            running_count=running,
            blocked_count=blocked,
            awaiting_approval_count=awaiting,
            approved_count=approved,
            prs_created_count=prs_created,
            tests_passed_count=tests_passed,
            tests_failed_count=tests_failed,
            is_processing=self._is_processing,
            max_concurrency=self.config.max_concurrency,
            active_workers=self._active_workers
        )


repair_queue_service = RepairQueueService()

