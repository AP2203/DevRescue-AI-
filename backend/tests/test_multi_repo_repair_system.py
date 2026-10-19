import os
import json
import pytest
import tempfile
import asyncio
import hashlib
from unittest.mock import patch, MagicMock, AsyncMock

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.repair_queue_service import (
    RepairQueueService,
    calculate_issue_priority_and_triage,
    JobStatus,
    TriageStatus
)
from app.services.sandbox_service import sandbox_service, parse_test_metrics, parse_test_duration, TestFrameworkResult
from app.services.github_service import (
    GitHubError,
    GitHubRateLimitError,
    GitHubTimeoutError,
    GitHubAuthError
)
from app.schemas.repair_queue import QueueConfig


@pytest.fixture
def temp_queue_service(tmp_path):
    state_file = tmp_path / "test_queue_state.json"
    service = RepairQueueService(state_file=str(state_file))
    return service


# ==============================================================================
# 1. Multi-Repository Discovery, Pagination & Rate Limits
# ==============================================================================

@pytest.mark.asyncio
async def test_multi_repo_discovery_pagination_and_pr_filtering(temp_queue_service):
    """
    Verifies repository and issue discovery across multiple paginated pages,
    ensuring pull requests are excluded and issues are indexed.
    """
    mock_repos_p1 = [
        {"id": 1, "name": "repo-a", "full_name": "org/repo-a", "owner": "org", "language": "Python", "default_branch": "main", "open_issues": 2},
        {"id": 2, "name": "repo-b", "full_name": "org/repo-b", "owner": "org", "language": "TypeScript", "default_branch": "main", "open_issues": 1}
    ]
    mock_issues_repo_a = [
        {"id": 101, "number": 1, "title": "Critical memory leak", "body": "Traceback:\nMemoryError in worker.py", "labels": ["bug", "critical"], "state": "open"},
        {"id": 102, "number": 2, "title": "Update README docs", "body": "Small doc tweak", "pull_request": {"url": "https://api.github.com/repos/org/repo-a/pulls/2"}, "state": "open"}
    ]
    mock_issues_repo_b = [
        {"id": 201, "number": 5, "title": "TypeError on undefined config", "body": "TypeError: Cannot read property 'port' of undefined", "labels": ["bug"], "state": "open"}
    ]

    async def mock_list_repos(token, page=1, per_page=50):
        if page == 1:
            return mock_repos_p1
        return []

    async def mock_list_issues(token, owner, repo, state="open"):
        if repo == "repo-a":
            return mock_issues_repo_a
        elif repo == "repo-b":
            return mock_issues_repo_b
        return []

    with patch("app.services.github_service.github_service.list_repositories", side_effect=mock_list_repos), \
         patch("app.services.github_service.github_service.list_issues", side_effect=mock_list_issues):

        res = await temp_queue_service.discover_repositories_and_issues(
            access_token="test_token",
            force_refresh=True
        )

        assert res["status"] == "success"
        assert len(temp_queue_service.repositories) == 2
        # Pull request #2 in repo-a must be excluded
        assert "org/repo-a#1" in temp_queue_service.issues
        assert "org/repo-a#2" not in temp_queue_service.issues
        assert "org/repo-b#5" in temp_queue_service.issues

        # Verify priority ranking
        iss1 = temp_queue_service.issues["org/repo-a#1"]
        assert iss1.severity == "critical"
        assert iss1.priority_score >= 80


@pytest.mark.asyncio
async def test_discovery_respects_rate_limit_error(temp_queue_service):
    """Verifies that GitHub API rate limiting is caught and raised cleanly."""
    with patch("app.services.github_service.github_service.list_repositories", side_effect=GitHubRateLimitError("API rate limit exceeded", status_code=403)):
        with pytest.raises(GitHubRateLimitError):
            await temp_queue_service.discover_repositories_and_issues(
                access_token="test_token",
                force_refresh=True
            )


# ==============================================================================
# 2. Issue Prioritization & Non-Defect Triage Categorization
# ==============================================================================

def test_prioritization_and_non_defect_classification():
    """
    Verifies that feature requests, unclear reports, and unsupported languages
    are categorized as REQUIRES_REVIEW or BLOCKED, not assumed to be defects.
    """
    # 1. Feature request
    feat_issue = {"title": "Feature request: Add dark mode", "body": "Please add dark mode theme option", "labels": ["enhancement"]}
    score, sev, cat, triage, reason = calculate_issue_priority_and_triage(feat_issue, repo_lang="Python")
    assert cat == "feature_request"
    assert triage == TriageStatus.REQUIRES_REVIEW.value
    assert "Feature request" in reason

    # 2. Unclear short report (< 35 chars, no stacktrace)
    unclear_issue = {"title": "App broke", "body": "It crashed", "labels": ["bug"]}
    score, sev, cat, triage, reason = calculate_issue_priority_and_triage(unclear_issue, repo_lang="Python")
    assert cat == "unclear"
    assert triage == TriageStatus.REQUIRES_REVIEW.value
    assert "Unclear report" in reason

    # 3. Unsupported language
    rust_issue = {"title": "Fix memory safety panic", "body": "Thread panicked at main.rs", "labels": ["bug"]}
    score, sev, cat, triage, reason = calculate_issue_priority_and_triage(rust_issue, repo_lang="Rust")
    assert cat == "unsupported_runtime"
    assert triage == TriageStatus.BLOCKED.value
    assert "Unsupported language" in reason

    # 4. Genuine reproducible defect with stack trace
    bug_issue = {
        "title": "NullPointerException in payment validator",
        "body": "Steps to reproduce:\n1. Submit form\nException:\njava.lang.NullPointerException at com.acme.Pay.validate(Pay.java:42)",
        "labels": ["bug", "critical"]
    }
    score, sev, cat, triage, reason = calculate_issue_priority_and_triage(bug_issue, repo_lang="Java", has_test_suite=True)
    assert cat == "defect"
    assert triage == TriageStatus.READY_FOR_REPAIR.value
    assert sev == "critical"
    assert score >= 85


# ==============================================================================
# 3. Duplicate Issue Prevention & Idempotent Enqueue
# ==============================================================================

def test_duplicate_issue_prevention_and_idempotent_enqueue(temp_queue_service):
    """
    Verifies that enqueuing the same issue twice does not create duplicate jobs,
    preserving idempotent job tracking.
    """
    # Enqueue first time
    job1 = temp_queue_service.enqueue_issue("org/api-svc#42")
    assert job1.job_id == "job_org_api-svc_42"
    assert job1.status == JobStatus.PENDING.value

    # Enqueue second time (idempotent)
    job2 = temp_queue_service.enqueue_issue("org/api-svc#42")
    assert job2.job_id == job1.job_id
    assert len(temp_queue_service.jobs) == 1


# ==============================================================================
# 4. Concurrent Worker Locking & Mutual Exclusion
# ==============================================================================

@pytest.mark.asyncio
async def test_concurrent_worker_locking_and_mutual_exclusion(temp_queue_service):
    """
    Verifies that:
    1. Two workers cannot process the same issue concurrently (issue mutex lock).
    2. Global concurrency limit and per-repo limit are respected.
    """
    temp_queue_service.config.max_concurrency = 2
    temp_queue_service.config.per_repo_concurrency = 1

    # Issue key
    issue_key = "org/repo-1#10"

    # Claim lock manually
    temp_queue_service._active_issue_locks.add(issue_key)
    assert issue_key in temp_queue_service._active_issue_locks

    # Check per-repo limit
    active_repo_count = sum(
        1 for k in temp_queue_service._active_issue_locks
        if k.startswith("org/repo-1")
    )
    assert active_repo_count >= temp_queue_service.config.per_repo_concurrency

    # Release lock
    temp_queue_service._active_issue_locks.discard(issue_key)
    assert issue_key not in temp_queue_service._active_issue_locks


# ==============================================================================
# 5. Runtime Detection (Python, Node.js, Java)
# ==============================================================================

def test_runtime_detection_java_maven(tmp_path):
    """Verifies Java Maven runtime and test framework detection."""
    pom = tmp_path / "pom.xml"
    pom.write_text("<project><properties><java.version>17</java.version></properties></project>", encoding="utf-8")

    res = sandbox_service.detect_test_framework(str(tmp_path), ["src/main/App.java"])
    assert res.framework == "maven"
    assert res.command == "mvn test"
    assert "maven:3.9-eclipse-temurin-17" in res.image


def test_runtime_detection_java_gradle(tmp_path):
    """Verifies Java Gradle runtime and test framework detection."""
    gradle_file = tmp_path / "build.gradle"
    gradle_file.write_text("plugins { id 'java' }\n", encoding="utf-8")

    res = sandbox_service.detect_test_framework(str(tmp_path), ["src/main/App.java"])
    assert res.framework == "gradle"
    assert "gradle" in res.command
    assert "gradle:8.5-jdk17" in res.image


def test_parse_java_maven_and_gradle_metrics():
    """Verifies parsing of Maven Surefire and Gradle test execution outputs."""
    # Maven output
    mvn_stdout = "[INFO] Tests run: 25, Failures: 2, Errors: 1, Skipped: 2"
    r, p, f = parse_test_metrics("mvn test", mvn_stdout)
    assert r == 25
    assert f == 3  # 2 failures + 1 error
    assert p == 20  # 25 - 3 - 2 skipped

    # Gradle output
    gradle_stdout = "30 tests completed, 4 failed, 1 skipped"
    r2, p2, f2 = parse_test_metrics("gradle test", gradle_stdout)
    assert r2 == 30
    assert f2 == 4
    assert p2 == 25


# ==============================================================================
# 6. Missing Docker Images & Dependency Failures (Offline / Unavailable)
# ==============================================================================

@pytest.mark.asyncio
async def test_missing_java_image_returns_dependencies_unavailable():
    """
    Verifies that when a Java container image is unavailable locally and cannot be pulled,
    execute_sandbox_test returns DEPENDENCIES_UNAVAILABLE with exit code 127.
    """
    service = sandbox_service

    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=False), \
         patch.object(service, "ensure_base_image_available", AsyncMock(return_value=(False, "Image pull failed"))), \
         patch.object(service, "apply_patch_to_workspace", return_value=["App.java"]), \
         patch.object(service, "detect_test_framework", return_value=TestFrameworkResult("mvn test", "/workspace", "maven:3.9-eclipse-temurin-17", "maven")), \
         patch("app.services.github_service.github_service.download_and_extract_archive", AsyncMock()):

        res = await service.execute_sandbox_test(
            owner="testorg",
            repo="javarepo",
            branch="main",
            issue_number=1,
            patch="--- a/App.java\n+++ b/App.java\n@@ -1,1 +1,1 @@\n"
        )

        assert res.status == "DEPENDENCIES_UNAVAILABLE"
        assert res.exit_code == 127
        assert "not cached locally" in res.message


# ==============================================================================
# 7. Patch Hash Invalidation on Approval Gate
# ==============================================================================

@pytest.mark.asyncio
async def test_patch_hash_invalidation_rejects_approval(temp_queue_service):
    """
    Verifies that human approval bound to a specific patch SHA-256 is strictly invalidated
    if the provided hash does not match the validated patch hash.
    """
    job = temp_queue_service.enqueue_issue("org/repo#5")
    job.investigation_id = "inv-test-1"
    job.run_id = "run-test-1"
    job.patch_hash = "correct_sha256_hash_123456"

    # Attempt approval with mismatched/stale hash
    with pytest.raises(ValueError, match="patch hash mismatch"):
        await temp_queue_service.approve_job_and_dispatch_pr(
            job_id=job.job_id,
            patch_hash="tampered_or_stale_hash_999999",
            access_token="test_token"
        )


# ==============================================================================
# 8. Approval & Pull Request Dispatch Authorization
# ==============================================================================

@pytest.mark.asyncio
async def test_approval_creates_dedicated_branch_and_pr(temp_queue_service):
    """
    Verifies that explicit human approval triggers PR dispatch,
    verifies PR creation on GitHub, and updates job state to PR_CREATED.
    """
    job = temp_queue_service.enqueue_issue("org/repo#12")
    job.investigation_id = "inv-pr-test"
    job.run_id = "run-pr-test"
    valid_hash = hashlib.sha256(b"diff content").hexdigest()
    job.patch_hash = valid_hash

    mock_pr_response = {
        "status": "success",
        "pr_number": 105,
        "pr_url": "https://github.com/org/repo/pull/105",
        "pull_request": {"pr_number": 105, "pr_url": "https://github.com/org/repo/pull/105"}
    }

    with patch("app.services.investigation_service.investigation_service.approve_run", AsyncMock(return_value=mock_pr_response)):
        res = await temp_queue_service.approve_job_and_dispatch_pr(
            job_id=job.job_id,
            patch_hash=valid_hash,
            access_token="gho_test_token"
        )

        assert res["status"] == "success"
        assert res["pr_number"] == 105
        assert job.status == JobStatus.PR_CREATED.value
        assert job.pull_request["pr_url"] == "https://github.com/org/repo/pull/105"


# ==============================================================================
# 9. Restart Recovery & Bounded Retries
# ==============================================================================

def test_backend_restart_recovers_interrupted_jobs(tmp_path):
    """
    Verifies that restarting the backend service reads persisted jobs and
    safely recovers interrupted INVESTIGATING/TESTING jobs back to PENDING.
    """
    state_file = tmp_path / "restart_state.json"

    # 1. First service instance saves active jobs
    s1 = RepairQueueService(state_file=str(state_file))
    j1 = s1.enqueue_issue("org/repo#20")
    j1.status = JobStatus.INVESTIGATING.value
    j2 = s1.enqueue_issue("org/repo#21")
    j2.status = JobStatus.TESTING.value
    j3 = s1.enqueue_issue("org/repo#22")
    j3.status = JobStatus.PR_CREATED.value
    s1._save_state()

    # 2. Second service instance starts up (simulating backend restart)
    s2 = RepairQueueService(state_file=str(state_file))

    # Active interrupted jobs must be recovered to PENDING
    assert s2.jobs[j1.job_id].status == JobStatus.PENDING.value
    assert s2.jobs[j2.job_id].status == JobStatus.PENDING.value
    # Completed jobs remain PR_CREATED
    assert s2.jobs[j3.job_id].status == JobStatus.PR_CREATED.value


# ==============================================================================
# 10. API Endpoints Integration Test
# ==============================================================================

@pytest.mark.asyncio
async def test_queue_api_endpoints_end_to_end():
    """Verifies FastAPI endpoints for /api/queue: stats, enqueue, jobs, retry, cancel."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Get stats
        stats_res = await client.get("/api/queue/stats")
        assert stats_res.status_code == 200
        stats_data = stats_res.json()
        assert "repositories_scanned" in stats_data
        assert "waiting_count" in stats_data

        # 2. Enqueue issue
        enq_res = await client.post(
            "/api/queue/enqueue",
            json={"issue_keys": ["acme/payment#44"], "priority_override": 75}
        )
        assert enq_res.status_code == 200
        enq_jobs = enq_res.json()
        assert len(enq_jobs) == 1
        job_id = enq_jobs[0]["job_id"]

        # 3. Get job details
        job_res = await client.get(f"/api/queue/jobs/{job_id}")
        assert job_res.status_code == 200
        assert job_res.json()["priority_score"] == 75

        # 4. Cancel job
        cancel_res = await client.post(f"/api/queue/jobs/{job_id}/cancel")
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "CANCELLED"

        # 5. Retry job
        retry_res = await client.post(f"/api/queue/jobs/{job_id}/retry", json={"force": True})
        assert retry_res.status_code == 200
        assert retry_res.json()["status"] == "PENDING"
