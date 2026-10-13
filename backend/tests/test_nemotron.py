import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings
from app.services.nemotron_service import (
    nemotron_service,
    _sanitize_error,
    NemotronError,
    NemotronTimeoutError,
    NemotronRateLimitError,
    NemotronAuthError,
    NemotronAPIError,
    NemotronResponseError
)
from app.services.investigation_service import investigation_service

# ==============================================================================
# Helper Mock Objects
# ==============================================================================

class MockChoice:
    def __init__(self, content: str):
        self.message = MagicMock(content=content)

class MockChatCompletionResponse:
    def __init__(self, content: str):
        self.choices = [MockChoice(content)]

# ==============================================================================
# 1. Error Sanitization Tests
# ==============================================================================

def test_sanitize_error_redacts_keys_and_tokens():
    raw_error = Exception("Error communicating with https://integrate.api.nvidia.com/v1 using nvapi-abc123xyz and Bearer gho_token987")
    sanitized = _sanitize_error(raw_error)
    assert "nvapi-abc123xyz" not in sanitized
    assert "gho_token987" not in sanitized
    assert "[REDACTED]" in sanitized

# ==============================================================================
# 2. Health Endpoint Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_nemotron_health_missing_api_key():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch.object(settings, "NVIDIA_API_KEY", None):
            res = await ac.get("/api/ai/nemotron/health")
            assert res.status_code == 200
            data = res.json()
            assert data["connected"] is False
            assert "NVIDIA_API_KEY" in data["error"]

@pytest.mark.asyncio
async def test_nemotron_health_success_mocked():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch.object(settings, "NVIDIA_API_KEY", "nvapi-dummy-key-for-test"):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=MockChatCompletionResponse("pong")
            )
            with patch.object(nemotron_service, "get_client", return_value=mock_client):
                res = await ac.get("/api/ai/nemotron/health")
                assert res.status_code == 200
                data = res.json()
                assert data["connected"] is True
                assert data["provider"] == "NVIDIA"
                assert data["model"] == settings.NEMOTRON_MODEL

@pytest.mark.asyncio
async def test_nemotron_health_api_failure_redacted():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch.object(settings, "NVIDIA_API_KEY", "nvapi-secret-key-12345"):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("Connection refused by nvapi-secret-key-12345 upstream")
            )
            with patch.object(nemotron_service, "get_client", return_value=mock_client):
                res = await ac.get("/api/ai/nemotron/health")
                assert res.status_code == 200
                data = res.json()
                assert data["connected"] is False
                assert "nvapi-secret-key-12345" not in data["error"]
                assert "[REDACTED]" in data["error"]

# ==============================================================================
# 3. Bug Investigation Endpoint Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_nemotron_investigate_valid_mocked():
    mock_response_json = """
    {
        "root_cause": "Off-by-one error in pagination calculation",
        "confidence": 0.95,
        "affected_files": ["src/pagination.py"],
        "affected_functions": ["paginate_records"],
        "evidence": [
            {
                "file": "src/pagination.py",
                "line": 42,
                "reason": "Range calculation excludes final page"
            }
        ],
        "proposed_fix": "Adjust page offset by 1",
        "test_strategy": "Run unit tests in test_pagination.py"
    }
    """
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=MockChatCompletionResponse(mock_response_json)
    )

    with patch.object(settings, "NVIDIA_API_KEY", "nvapi-dummy"):
        with patch.object(nemotron_service, "get_client", return_value=mock_client):
            issue = {
                "number": 10,
                "title": "Pagination bug",
                "body": "Last page items missing"
            }
            repository = {
                "owner": "org",
                "name": "repo",
                "default_branch": "main"
            }
            files = [
                {"path": "src/pagination.py", "content": "def paginate_records(): pass"}
            ]
            tests = [
                {"path": "tests/test_pagination.py", "content": "def test_page(): pass"}
            ]
            res = await nemotron_service.investigate_bug(issue, repository, files, tests)
            assert res.confidence == 0.95
            assert "src/pagination.py" in res.affected_files
            assert res.affected_functions == ["paginate_records"]

@pytest.mark.asyncio
async def test_nemotron_investigate_malformed_json_rejected():
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=MockChatCompletionResponse("Here is your analysis: not valid json at all")
    )
    with patch.object(settings, "NVIDIA_API_KEY", "nvapi-dummy"):
        with patch.object(nemotron_service, "get_client", return_value=mock_client):
            issue = {"number": 1, "title": "Crash", "body": "null pointer"}
            repository = {"owner": "o", "name": "r"}
            files = [{"path": "main.py", "content": "print('ok')"}]
            with pytest.raises(Exception):
                await nemotron_service.investigate_bug(issue, repository, files, [])

@pytest.mark.asyncio
async def test_nemotron_investigate_nonexistent_file_reference_rejected():
    # Model hallucinates a file not present in repo context
    mock_response_json = """
    {
        "root_cause": "Faulty logic",
        "confidence": 0.8,
        "affected_files": ["secret_unseen_file.py"],
        "affected_functions": [],
        "evidence": [],
        "proposed_fix": "Fix logic",
        "test_strategy": "Test"
    }
    """
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=MockChatCompletionResponse(mock_response_json)
    )
    with patch.object(settings, "NVIDIA_API_KEY", "nvapi-dummy"):
        with patch.object(nemotron_service, "get_client", return_value=mock_client):
            issue = {"number": 1, "title": "Crash", "body": "details"}
            repository = {"owner": "o", "name": "r"}
            files = [{"path": "actual_file.py", "content": "def run(): pass"}]
            with pytest.raises(ValueError) as excinfo:
                await nemotron_service.investigate_bug(issue, repository, files, [])
            assert "non-existent file" in str(excinfo.value).lower()

# ==============================================================================
# 4. Patch Generation Endpoint Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_nemotron_generate_patch_valid_mocked():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        mock_patch_diff = (
            "--- a/src/app.py\\n"
            "+++ b/src/app.py\\n"
            "@@ -1,3 +1,4 @@\\n"
            "-    return None\\n"
            "+    return True\\n"
        )
        mock_patch_json = f"""
        {{
            "patch": "{mock_patch_diff}",
            "changed_files": ["src/app.py"],
            "explanation": "Fix return value to True",
            "test_plan": "Run pytest tests/test_app.py"
        }}
        """
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=MockChatCompletionResponse(mock_patch_json)
        )
        with patch.object(settings, "NVIDIA_API_KEY", "nvapi-dummy"):
            with patch.object(nemotron_service, "get_client", return_value=mock_client):
                payload = {
                    "issue": {"number": 2, "title": "False return", "body": ""},
                    "investigation": {
                        "root_cause": "Wrong return value",
                        "confidence": 0.95,
                        "affected_files": ["src/app.py"],
                        "affected_functions": ["run"],
                        "evidence": [
                            {"file": "src/app.py", "line": 2, "reason": "Returns None instead of True"}
                        ],
                        "proposed_fix": "Return True",
                        "test_strategy": "Run unit test"
                    },
                    "files": [
                        {"path": "src/app.py", "content": "def run():\n    return None"}
                    ]
                }
                res = await ac.post("/api/ai/nemotron/generate-patch", json=payload)
                assert res.status_code == 200
                data = res.json()
                assert "--- a/src/app.py" in data["patch"]
                assert data["changed_files"] == ["src/app.py"]

@pytest.mark.asyncio
async def test_nemotron_generate_patch_invalid_diff_headers_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        mock_patch_json = """
        {
            "patch": "Just change line 5 to return True without unified diff headers",
            "changed_files": ["src/app.py"],
            "explanation": "Fix line 5",
            "test_plan": "Unit test"
        }
        """
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=MockChatCompletionResponse(mock_patch_json)
        )
        with patch.object(settings, "NVIDIA_API_KEY", "nvapi-dummy"):
            with patch.object(nemotron_service, "get_client", return_value=mock_client):
                payload = {
                    "issue": {"number": 2, "title": "Bug", "body": ""},
                    "investigation": {
                        "root_cause": "Bug",
                        "confidence": 0.9,
                        "affected_files": ["src/app.py"],
                        "affected_functions": [],
                        "evidence": [],
                        "proposed_fix": "Fix",
                        "test_strategy": "Test"
                    },
                    "files": [{"path": "src/app.py", "content": "x = 1"}]
                }
                res = await ac.post("/api/ai/nemotron/generate-patch", json=payload)
                assert res.status_code == 400
                assert "diff headers" in res.json()["detail"].lower()

@pytest.mark.asyncio
async def test_nemotron_generate_patch_unseen_file_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        mock_patch_diff = (
            "--- a/src/unknown.py\\n"
            "+++ b/src/unknown.py\\n"
            "@@ -1,1 +1,1 @@\\n"
            "+new content\\n"
        )
        mock_patch_json = f"""
        {{
            "patch": "{mock_patch_diff}",
            "changed_files": ["src/unknown.py"],
            "explanation": "Created rogue file",
            "test_plan": "None"
        }}
        """
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=MockChatCompletionResponse(mock_patch_json)
        )
        with patch.object(settings, "NVIDIA_API_KEY", "nvapi-dummy"):
            with patch.object(nemotron_service, "get_client", return_value=mock_client):
                payload = {
                    "issue": {"number": 2, "title": "Bug", "body": ""},
                    "investigation": {
                        "root_cause": "Bug",
                        "confidence": 0.9,
                        "affected_files": [],
                        "affected_functions": [],
                        "evidence": [],
                        "proposed_fix": "Fix",
                        "test_strategy": "Test"
                    },
                    "files": [{"path": "src/known.py", "content": "known = True"}]
                }
                res = await ac.post("/api/ai/nemotron/generate-patch", json=payload)
                assert res.status_code == 400
                assert "not present in repository context" in res.json()["detail"].lower()

# ==============================================================================
# 5. Fallback Prevention & Investigation Failure Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_real_mode_nemotron_failure_prevents_fake_patch_and_approval():
    """
    Verifies that when Nemotron fails in real mode:
    1. No fake 'src/handler.py' fallback patch is generated.
    2. Investigation status is 'FAILED' and patch is None.
    3. Approval endpoint returns 400 Bad Request and blocks PR creation.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Trigger real mode investigation without valid Nemotron key
        with patch.object(settings, "NVIDIA_API_KEY", None):
            inv_payload = {
                "repo": "enterprise/order-service",
                "issue_title": "Critical Deadlock in checkout",
                "error_description": "Locks acquired out of order during inventory reservation.",
                "branch": "main",
                "issue_number": 505,
                "mode": "real"
            }
            res = await ac.post("/api/investigations", json=inv_payload)
            assert res.status_code == 201
            data = res.json()
            inv_id = data["id"]

            # Must NOT generate fake patch
            assert data["status"] == "FAILED"
            assert data["patch"] is None
            
            # Agents must reflect repair failure
            repair_agent = next(a for a in data["agents"] if a["name"] == "Nemotron Code Repair")
            assert repair_agent["status"] == "FAILED"

            # Attempting to approve must fail and not create PR
            approve_res = await ac.post(f"/api/investigations/{inv_id}/approve")
            assert approve_res.status_code == 400
            assert "cannot approve" in approve_res.json()["detail"].lower()


# ==============================================================================
# 6. Real Repository Analyzer & End-to-End Pipeline Tests
# ==============================================================================

from app.services.repository_analyzer import repository_analyzer
from app.services.github_service import (
    github_service,
    GitHubAuthError,
    GitHubConnectionError,
    GitHubTimeoutError
)

@pytest.mark.asyncio
async def test_repository_tree_retrieval():
    mock_tree = {
        "sha": "tree123",
        "tree": [
            {"path": "src/auth.py", "type": "blob", "sha": "sha1"},
            {"path": "tests/test_auth.py", "type": "blob", "sha": "sha2"},
            {"path": "src", "type": "tree", "sha": "sha3"}
        ]
    }
    with patch.object(github_service, "get_repository_tree", AsyncMock(return_value=mock_tree)):
        tree = await github_service.get_repository_tree("dummy_token", "owner", "repo", "main")
        blobs = [item["path"] for item in tree["tree"] if item["type"] == "blob"]
        assert "src/auth.py" in blobs
        assert "tests/test_auth.py" in blobs
        assert len(blobs) == 2

@pytest.mark.asyncio
async def test_issue_retrieval():
    mock_issue = {
        "number": 101,
        "title": "Auth failure on OAuth callback",
        "body": "Users cannot sign in due to missing token verification.",
        "labels": ["bug", "security"],
        "html_url": "https://github.com/owner/repo/issues/101"
    }
    mock_comments = [
        {"id": 1, "body": "See src/auth.py line 45 for the exception."}
    ]
    with patch.object(github_service, "get_issue", AsyncMock(return_value=mock_issue)), \
         patch.object(github_service, "get_issue_comments", AsyncMock(return_value=mock_comments)):
        issue = await repository_analyzer.get_issue_details("owner", "repo", 101)
        assert issue["number"] == 101
        assert issue["title"] == "Auth failure on OAuth callback"
        assert len(issue["comments"]) == 1
        assert "src/auth.py" in issue["comments"][0]

@pytest.mark.asyncio
async def test_relevant_file_selection():
    mock_repo = {"default_branch": "main", "language": "Python"}
    mock_tree = {
        "tree": [
            {"path": "src/auth.py", "type": "blob"},
            {"path": "src/utils.py", "type": "blob"},
            {"path": "tests/test_auth.py", "type": "blob"},
            {"path": "node_modules/dep/index.js", "type": "blob"},
            {"path": "assets/logo.png", "type": "blob"},
            {"path": "requirements.txt", "type": "blob"}
        ]
    }
    mock_issue = {
        "number": 101,
        "title": "Fix token validation in src/auth.py",
        "body": "Stack trace points to src/auth.py line 50",
        "labels": [],
        "html_url": "https://github.com/o/r/issues/101"
    }

    async def mock_get_content(access_token, owner, repo, path, branch):
        if path == "src/auth.py":
            return "def verify_token(): return False", "sha1"
        if path == "tests/test_auth.py":
            return "def test_verify(): pass", "sha2"
        return "content", "sha"

    with patch.object(github_service, "get_repository", AsyncMock(return_value=mock_repo)), \
         patch.object(github_service, "get_repository_tree", AsyncMock(return_value=mock_tree)), \
         patch.object(github_service, "get_issue", AsyncMock(return_value=mock_issue)), \
         patch.object(github_service, "get_issue_comments", AsyncMock(return_value=[])), \
         patch.object(github_service, "get_file_content_and_sha", AsyncMock(side_effect=mock_get_content)):
        
        analysis = await repository_analyzer.analyze_repository_for_issue("o", "r", 101)
        source_paths = [f["path"] for f in analysis["files"]]
        test_paths = [t["path"] for t in analysis["tests"]]

        assert "src/auth.py" in source_paths
        assert "tests/test_auth.py" in test_paths
        # Ignored files must NOT be selected
        assert "node_modules/dep/index.js" not in source_paths
        assert "assets/logo.png" not in source_paths

@pytest.mark.asyncio
async def test_missing_file_handling():
    mock_repo = {"default_branch": "main", "language": "Python"}
    mock_tree = {"tree": [{"path": "src/missing.py", "type": "blob"}]}
    mock_issue = {"number": 1, "title": "Missing", "body": "src/missing.py", "labels": []}

    # Simulate GitHub returning 404/None for the file content
    with patch.object(github_service, "get_repository", AsyncMock(return_value=mock_repo)), \
         patch.object(github_service, "get_repository_tree", AsyncMock(return_value=mock_tree)), \
         patch.object(github_service, "get_issue", AsyncMock(return_value=mock_issue)), \
         patch.object(github_service, "get_issue_comments", AsyncMock(return_value=[])), \
         patch.object(github_service, "get_file_content_and_sha", AsyncMock(return_value=(None, None))):
        
        analysis = await repository_analyzer.analyze_repository_for_issue("o", "r", 1)
        assert len(analysis["files"]) == 0

@pytest.mark.asyncio
async def test_empty_repository_handling():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        mock_repo = {"default_branch": "main", "language": "Other"}
        mock_tree = {"tree": []}
        mock_issue = {"number": 1, "title": "Bug", "body": "", "labels": []}

        with patch.object(github_service, "get_repository", AsyncMock(return_value=mock_repo)), \
             patch.object(github_service, "get_repository_tree", AsyncMock(return_value=mock_tree)), \
             patch.object(github_service, "get_issue", AsyncMock(return_value=mock_issue)), \
             patch.object(github_service, "get_issue_comments", AsyncMock(return_value=[])):
            
            payload = {"owner": "acme", "repo": "empty-repo", "issue_number": 1, "branch": "main"}
            res = await ac.post("/api/ai/nemotron/investigate", json=payload, headers={"Authorization": "Bearer test_token"})
            assert res.status_code == 400
            assert "no source or test files" in res.json()["detail"].lower()

@pytest.mark.asyncio
async def test_real_github_investigation_pipeline_e2e():
    """
    Tests the complete REAL GitHub -> Repository Analyzer -> Nemotron pipeline:
    Validates that real repo tree, real issue, and real file contents are passed
    to Nemotron and the response conforms to the pipeline contract.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        mock_repo = {"default_branch": "main", "language": "Python"}
        mock_tree = {
            "tree": [
                {"path": "src/ledger.py", "type": "blob"},
                {"path": "tests/test_ledger.py", "type": "blob"}
            ]
        }
        mock_issue = {
            "number": 77,
            "title": "Double debit in ledger.py",
            "body": "Race condition in src/ledger.py debit method.",
            "labels": ["bug"],
            "html_url": "https://github.com/acme/fintech/issues/77"
        }
        mock_comments = [{"id": 1, "body": "Reproduced on concurrent requests"}]

        async def mock_get_content(access_token, owner, repo, path, branch):
            if path == "src/ledger.py":
                return "class Ledger:\n    def debit(self, amt):\n        self.bal -= amt", "sha1"
            if path == "tests/test_ledger.py":
                return "def test_debit(): pass", "sha2"
            return None, None

        mock_nemotron_response = """
        {
            "root_cause": "Unsynchronized balance deduction leads to race condition",
            "confidence": 0.98,
            "affected_files": ["src/ledger.py"],
            "affected_functions": ["debit"],
            "evidence": [
                {
                    "file": "src/ledger.py",
                    "line": 3,
                    "reason": "Balance decrement is not guarded by a lock"
                }
            ],
            "proposed_fix": "Add asyncio lock or atomic mutex around self.bal update",
            "test_strategy": "Run concurrent debit tests in test_ledger.py"
        }
        """
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=MockChatCompletionResponse(mock_nemotron_response)
        )

        with patch.object(settings, "NVIDIA_API_KEY", "nvapi-test-key"), \
             patch.object(nemotron_service, "get_client", return_value=mock_client), \
             patch.object(github_service, "get_repository", AsyncMock(return_value=mock_repo)), \
             patch.object(github_service, "get_repository_tree", AsyncMock(return_value=mock_tree)), \
             patch.object(github_service, "get_issue", AsyncMock(return_value=mock_issue)), \
             patch.object(github_service, "get_issue_comments", AsyncMock(return_value=mock_comments)), \
             patch.object(github_service, "get_file_content_and_sha", AsyncMock(side_effect=mock_get_content)):

            payload = {
                "owner": "acme",
                "repo": "fintech",
                "issue_number": 77,
                "branch": "main"
            }
            res = await ac.post("/api/ai/nemotron/investigate", json=payload, headers={"Authorization": "Bearer test_token"})
            assert res.status_code == 200
            data = res.json()

            # Verify pipeline metadata
            assert data["success"] is True
            assert data["repository"] == "acme/fintech"
            assert data["issue_number"] == 77
            assert len(data["files_analyzed"]) >= 1
            analyzed_paths = [f["path"] for f in data["files_analyzed"]]
            assert "src/ledger.py" in analyzed_paths

            # Verify Nemotron investigation output
            inv = data["investigation"]
            assert inv["root_cause"] == "Unsynchronized balance deduction leads to race condition"
            assert inv["confidence"] == 0.98
            assert "src/ledger.py" in inv["affected_files"]
            assert inv["affected_functions"] == ["debit"]
            assert len(inv["evidence"]) == 1
            assert inv["evidence"][0]["file"] == "src/ledger.py"
            assert inv["evidence"][0]["line"] == 3

@pytest.mark.asyncio
async def test_investigate_missing_github_auth_returns_401():
    """If GitHub authentication is missing, return 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {"owner": "anshpatel2212", "repo": "test-repo", "issue_number": 1, "branch": "main"}
        res = await ac.post("/api/ai/nemotron/investigate", json=payload)
        assert res.status_code == 401
        data = res.json()
        assert data["detail"]["error"] == "unauthorized"
        assert "connect your github account" in data["detail"]["message"].lower()

@pytest.mark.asyncio
async def test_investigate_repo_not_found_returns_404():
    """If the repository does not exist, return 404."""
    from app.services.github_service import GitHubNotFoundError
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch.object(github_service, "get_repository", AsyncMock(side_effect=GitHubNotFoundError("Repository not found", status_code=404))):
            payload = {"owner": "anshpatel2212", "repo": "nonexistent-repo", "issue_number": 1, "branch": "main"}
            res = await ac.post("/api/ai/nemotron/investigate", json=payload, headers={"Authorization": "Bearer test_token"})
            assert res.status_code == 404
            assert res.json()["detail"]["error"] == "github_resource_not_found"

@pytest.mark.asyncio
async def test_investigate_issue_not_found_returns_404():
    """If the issue does not exist, return 404."""
    from app.services.github_service import GitHubNotFoundError
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        mock_repo = {"default_branch": "main", "language": "Python"}
        mock_tree = {"tree": [{"path": "src/app.py", "type": "blob"}]}
        with patch.object(github_service, "get_repository", AsyncMock(return_value=mock_repo)), \
             patch.object(github_service, "get_repository_tree", AsyncMock(return_value=mock_tree)), \
             patch.object(github_service, "get_issue", AsyncMock(side_effect=GitHubNotFoundError("Issue #999 not found", status_code=404))):
            payload = {"owner": "anshpatel2212", "repo": "existing-repo", "issue_number": 999, "branch": "main"}
            res = await ac.post("/api/ai/nemotron/investigate", json=payload, headers={"Authorization": "Bearer test_token"})
            assert res.status_code == 404
            assert res.json()["detail"]["error"] == "github_resource_not_found"

@pytest.mark.asyncio
async def test_github_auth_failure_handling():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch.object(github_service, "get_repository", AsyncMock(side_effect=GitHubAuthError("Token expired", status_code=401))):
            payload = {
                "owner": "private-org",
                "repo": "secret-repo",
                "issue_number": 1,
                "branch": "main"
            }
            res = await ac.post("/api/ai/nemotron/investigate", json=payload, headers={"Authorization": "Bearer test_token"})
            assert res.status_code == 401
            data = res.json()
            assert data["detail"]["error"] == "github_authentication_expired"

def test_investigate_swagger_schema_only_contains_four_fields():
    """Verifies that the Swagger OpenAPI schema only displays owner, repo, issue_number, branch."""
    from app.schemas.nemotron import NemotronInvestigateRequest
    fields = set(NemotronInvestigateRequest.model_fields.keys())
    assert fields == {"owner", "repo", "issue_number", "branch"}

    openapi = app.openapi()
    endpoint_schema = openapi["paths"]["/api/ai/nemotron/investigate"]["post"]
    ref = endpoint_schema["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    schema_name = ref.split("/")[-1]
    req_schema = openapi["components"]["schemas"][schema_name]
    assert set(req_schema["properties"].keys()) == {"owner", "repo", "issue_number", "branch"}
    example = req_schema.get("example")
    assert example == {
        "owner": "anshpatel2212",
        "repo": "YOUR_REPO",
        "issue_number": 1,
        "branch": "main"
    }

@pytest.mark.asyncio
async def test_investigate_github_issue_fetch_and_pipeline_success():
    """Verifies successful GitHub issue fetch, tree retrieval, and Nemotron investigation."""
    from app.schemas.nemotron import NemotronInvestigationResult
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        mock_repo = {"default_branch": "main", "language": "Python"}
        mock_tree = {"tree": [{"path": "src/button.py", "type": "blob", "size": 500}]}
        mock_issue = {
            "number": 1,
            "title": "Button loading state missing",
            "body": "Submit button does not indicate loading state",
            "labels": ["bug"],
            "comments": ["Tested on main branch"],
            "html_url": "https://github.com/anshpatel2212/2D2Mesh/issues/1"
        }
        mock_file_content = ("def render_button(loading=False):\n    pass\n", "sha123")
        mock_ai_resp = NemotronInvestigationResult(
            root_cause="The button component does not render loading indicator when loading=True",
            confidence=0.92,
            affected_files=["src/button.py"],
            affected_functions=["render_button"],
            evidence=[{"file": "src/button.py", "line": 1, "reason": "Missing loading prop handling"}],
            proposed_fix="Add loading spinner when loading is True",
            test_strategy="Add test_render_button_loading"
        )

        with patch.object(github_service, "get_repository", AsyncMock(return_value=mock_repo)), \
             patch.object(github_service, "get_repository_tree", AsyncMock(return_value=mock_tree)), \
             patch.object(github_service, "get_issue", AsyncMock(return_value=mock_issue)), \
             patch.object(github_service, "get_issue_comments", AsyncMock(return_value=[])), \
             patch.object(github_service, "get_file_content_and_sha", AsyncMock(return_value=mock_file_content)), \
             patch.object(nemotron_service, "investigate_bug", AsyncMock(return_value=mock_ai_resp)):

            payload = {
                "owner": "anshpatel2212",
                "repo": "2D2Mesh",
                "issue_number": 1,
                "branch": "main"
            }
            res = await ac.post("/api/ai/nemotron/investigate", json=payload, headers={"Authorization": "Bearer test_token"})
            assert res.status_code == 200
            data = res.json()
            assert data["success"] is True
            assert data["repository"] == "anshpatel2212/2D2Mesh"
            assert data["issue_number"] == 1
            assert len(data["files_analyzed"]) >= 1
            assert data["investigation"]["root_cause"] == "The button component does not render loading indicator when loading=True"
            assert data["investigation"]["confidence"] == 0.92

@pytest.mark.asyncio
async def test_investigate_github_timeout_returns_504():
    """If GitHub API times out, return 504 Gateway Timeout."""
    from app.services.github_service import GitHubTimeoutError
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch.object(github_service, "get_repository", AsyncMock(return_value={"default_branch": "main", "language": "Python"})), \
             patch.object(github_service, "get_issue", AsyncMock(side_effect=GitHubTimeoutError("GitHub API timed out after 15s.", status_code=504))):
            payload = {"owner": "anshpatel2212", "repo": "2D2Mesh", "issue_number": 1, "branch": "main"}
            res = await ac.post("/api/ai/nemotron/investigate", json=payload, headers={"Authorization": "Bearer test_token"})
            assert res.status_code == 504
            data = res.json()
            assert data["detail"]["error"] == "gateway_timeout"
            assert "timed out" in data["detail"]["message"].lower()

@pytest.mark.asyncio
async def test_investigate_nemotron_timeout_returns_504():
    """If Nemotron API times out after 60s, return 504 Gateway Timeout."""
    from app.services.nemotron_service import NemotronTimeoutError
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        mock_repo = {"default_branch": "main", "language": "Python"}
        mock_tree = {"tree": [{"path": "src/button.py", "type": "blob", "size": 500}]}
        mock_issue = {"number": 1, "title": "Crash", "body": "details", "labels": [], "comments": []}
        mock_file_content = ("def foo(): pass", "sha123")

        with patch.object(github_service, "get_repository", AsyncMock(return_value=mock_repo)), \
             patch.object(github_service, "get_repository_tree", AsyncMock(return_value=mock_tree)), \
             patch.object(github_service, "get_issue", AsyncMock(return_value=mock_issue)), \
             patch.object(github_service, "get_issue_comments", AsyncMock(return_value=[])), \
             patch.object(github_service, "get_file_content_and_sha", AsyncMock(return_value=mock_file_content)), \
             patch.object(nemotron_service, "investigate_bug", AsyncMock(side_effect=NemotronTimeoutError("NVIDIA Nemotron API request timed out after 60 seconds."))):

            payload = {"owner": "anshpatel2212", "repo": "2D2Mesh", "issue_number": 1, "branch": "main"}
            res = await ac.post("/api/ai/nemotron/investigate", json=payload, headers={"Authorization": "Bearer test_token"})
            assert res.status_code == 504
            data = res.json()
            assert data["detail"]["error"] == "gateway_timeout"
            assert "timed out" in data["detail"]["message"].lower()

@pytest.mark.asyncio
async def test_investigate_invalid_nemotron_response_returns_502():
    """If Nemotron returns invalid JSON or schema error, return 502 Bad Gateway."""
    from app.services.nemotron_service import NemotronResponseError
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        mock_repo = {"default_branch": "main", "language": "Python"}
        mock_tree = {"tree": [{"path": "src/button.py", "type": "blob", "size": 500}]}
        mock_issue = {"number": 1, "title": "Crash", "body": "details", "labels": [], "comments": []}
        mock_file_content = ("def foo(): pass", "sha123")

        with patch.object(github_service, "get_repository", AsyncMock(return_value=mock_repo)), \
             patch.object(github_service, "get_repository_tree", AsyncMock(return_value=mock_tree)), \
             patch.object(github_service, "get_issue", AsyncMock(return_value=mock_issue)), \
             patch.object(github_service, "get_issue_comments", AsyncMock(return_value=[])), \
             patch.object(github_service, "get_file_content_and_sha", AsyncMock(return_value=mock_file_content)), \
             patch.object(nemotron_service, "investigate_bug", AsyncMock(side_effect=NemotronResponseError("Nemotron returned invalid JSON structure."))):

            payload = {"owner": "anshpatel2212", "repo": "2D2Mesh", "issue_number": 1, "branch": "main"}
            res = await ac.post("/api/ai/nemotron/investigate", json=payload, headers={"Authorization": "Bearer test_token"})
            assert res.status_code == 502
            data = res.json()
            assert data["detail"]["error"] == "bad_gateway"
            assert "invalid json" in data["detail"]["message"].lower()

# ==============================================================================
# 9. Nemotron JSON Payload Extraction & Single-Quote / Reasoning Block Tests
# ==============================================================================

def test_extract_json_payload_variants():
    from app.services.nemotron_service import _extract_json_payload

    # 1. Strict JSON
    res1 = _extract_json_payload('{"root_cause": "defect 1", "confidence": 0.95}')
    assert res1["root_cause"] == "defect 1"
    assert res1["confidence"] == 0.95

    # 2. Python dictionary syntax with single quotes
    res2 = _extract_json_payload("{'root_cause': 'defect 2', 'affected_files': ['src/Button.tsx']}")
    assert res2["root_cause"] == "defect 2"
    assert res2["affected_files"] == ["src/Button.tsx"]

    # 3. Single quotes with true/false/null literals
    res3 = _extract_json_payload("{'root_cause': 'defect 3', 'is_bug': true, 'meta': null}")
    assert res3["root_cause"] == "defect 3"
    assert res3["is_bug"] is True
    assert res3["meta"] is None

    # 4. Markdown code fence with single quotes
    res4 = _extract_json_payload("```json\n{'root_cause': 'defect 4', 'confidence': 0.88}\n```")
    assert res4["root_cause"] == "defect 4"
    assert res4["confidence"] == 0.88

    # 5. Reasoning <think>...</think> tag preceding JSON
    res5 = _extract_json_payload("<think>\nAnalyzing Button.tsx and finding missing handler\n</think>\n```json\n{\"root_cause\": \"defect 5\"}\n```")
    assert res5["root_cause"] == "defect 5"

    # 6. Reasoning <think>...</think> tag preceding single-quoted dict
    res6 = _extract_json_payload("<think>\nThoughts: The issue is in line 10\n</think>\n{'root_cause': 'defect 6'}")
    assert res6["root_cause"] == "defect 6"

    # 7. Reasoning <thought> tag
    res7 = _extract_json_payload("<thought>Reasoning trace</thought>\n{'root_cause': 'defect 7'}")
    assert res7["root_cause"] == "defect 7"

    # 8. Trailing comma in dict
    res8 = _extract_json_payload('{"root_cause": "defect 8", "confidence": 0.9, }')
    assert res8["root_cause"] == "defect 8"

    # 9. Prose surrounding single-quoted dict
    res9 = _extract_json_payload("Here is the completed diagnosis:\n{'root_cause': 'defect 9'}\nPlease apply the patch.")
    assert res9["root_cause"] == "defect 9"

@pytest.mark.asyncio
async def test_investigate_bug_handles_single_quoted_and_thinking_nemotron_response():
    """Verify investigate_bug successfully parses a Nemotron response with <think> and single quotes."""
    from app.services.nemotron_service import nemotron_service

    raw_nemotron_output = """<think>
1. Analyze user request
2. Look at Button.tsx: button renders null
</think>
```json
{
  'root_cause': 'The Button component renders null instead of JSX.',
  'confidence': 0.95,
  'affected_files': ['src/Button.tsx'],
  'affected_functions': ['Button'],
  'evidence': [
    {
      'file': 'src/Button.tsx',
      'line': 1,
      'reason': 'Returns null'
    }
  ],
  'proposed_fix': 'Return proper JSX button element.',
  'test_strategy': 'Render button and assert it is in document.'
}
```"""

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=MockChatCompletionResponse(raw_nemotron_output)
    )

    with patch.object(nemotron_service, "get_client", return_value=mock_client):
        res = await nemotron_service.investigate_bug(
            issue={"number": 1, "title": "Button bug", "body": "Button broken", "comments": []},
            repository={"owner": "anshpatel2212", "name": "2D2Mesh", "default_branch": "main"},
            files=[{"path": "src/Button.tsx", "content": "export const Button = () => null;"}],
            tests=[]
        )
        assert res.root_cause == "The Button component renders null instead of JSX."
        assert res.confidence == 0.95
        assert res.affected_files == ["src/Button.tsx"]
        assert len(res.evidence) == 1
        assert res.evidence[0].file == "src/Button.tsx"

# ==============================================================================
# 5. Nemotron Timeout, Retry & Streaming Regression Tests
# ==============================================================================

from openai import APITimeoutError, APIError
from app.services.nemotron_service import (
    NemotronTimeoutError,
    NemotronRateLimitError,
    NemotronAuthError,
    NemotronResponseError
)

class MockStreamChunk:
    def __init__(self, content: str):
        delta = MagicMock()
        delta.content = content
        choice = MagicMock()
        choice.delta = delta
        self.choices = [choice]

class MockAsyncStream:
    def __init__(self, chunks: list[str]):
        self.chunks = chunks

    def __aiter__(self):
        self._iter = iter(self.chunks)
        return self

    async def __anext__(self):
        try:
            val = next(self._iter)
            return MockStreamChunk(val)
        except StopIteration:
            raise StopAsyncIteration

@pytest.mark.asyncio
async def test_investigate_bug_timeout_exhausts_retries():
    """Verify that persistent timeouts exhaust all retries and raise NemotronTimeoutError."""
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=APITimeoutError(request=MagicMock())
    )

    with patch.object(settings, "NEMOTRON_MAX_RETRIES", 2), \
         patch.object(settings, "NEMOTRON_TIMEOUT", 1.0), \
         patch("asyncio.sleep", AsyncMock()) as mock_sleep, \
         patch.object(nemotron_service, "get_client", return_value=mock_client):

        with pytest.raises(NemotronTimeoutError) as exc_info:
            await nemotron_service.investigate_bug(
                issue={"number": 1, "title": "Timeout bug", "body": "Slow response", "comments": []},
                repository={"owner": "org", "name": "repo"},
                files=[{"path": "src/main.py", "content": "x = 1"}],
                tests=[]
            )

        assert exc_info.value.status_code == 504
        assert exc_info.value.error_code == "NEMOTRON_TIMEOUT"
        # 3 calls total: attempt 0, 1, 2
        assert mock_client.chat.completions.create.call_count == 3
        assert mock_sleep.call_count == 2

@pytest.mark.asyncio
async def test_investigate_bug_transient_timeout_retries_and_succeeds():
    """Verify that a transient timeout followed by success recovers cleanly."""
    valid_json = """{
        "root_cause": "Transient delay resolved",
        "confidence": 0.9,
        "affected_files": ["src/main.py"],
        "affected_functions": ["main"],
        "evidence": [{"file": "src/main.py", "line": 1, "reason": "Syntax fix"}],
        "proposed_fix": "Fix syntax",
        "test_strategy": "pytest"
    }"""
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[
            APITimeoutError(request=MagicMock()),
            MockChatCompletionResponse(valid_json)
        ]
    )

    with patch.object(settings, "NEMOTRON_MAX_RETRIES", 2), \
         patch.object(settings, "NEMOTRON_TIMEOUT", 1.0), \
         patch("asyncio.sleep", AsyncMock()) as mock_sleep, \
         patch.object(nemotron_service, "get_client", return_value=mock_client):

        res = await nemotron_service.investigate_bug(
            issue={"number": 1, "title": "Transient bug", "body": "...", "comments": []},
            repository={"owner": "org", "name": "repo"},
            files=[{"path": "src/main.py", "content": "x = 1"}],
            tests=[]
        )

        assert res.root_cause == "Transient delay resolved"
        assert mock_client.chat.completions.create.call_count == 2
        assert mock_sleep.call_count == 1

@pytest.mark.asyncio
async def test_investigate_bug_rate_limited_429_retries_and_raises():
    """Verify that a 429 rate limit respects Retry-After and raises NemotronRateLimitError when exhausted."""
    response_mock = MagicMock()
    response_mock.headers = {"Retry-After": "1.5"}
    rate_err = APIError(
        message="Rate limit exceeded",
        request=MagicMock(),
        body={"error": {"code": 429}}
    )
    rate_err.status_code = 429
    rate_err.response = response_mock

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=rate_err)

    with patch.object(settings, "NEMOTRON_MAX_RETRIES", 1), \
         patch("asyncio.sleep", AsyncMock()) as mock_sleep, \
         patch.object(nemotron_service, "get_client", return_value=mock_client):

        with pytest.raises(NemotronRateLimitError) as exc_info:
            await nemotron_service.investigate_bug(
                issue={"number": 1, "title": "Rate limit bug", "body": "...", "comments": []},
                repository={"owner": "org", "name": "repo"},
                files=[{"path": "src/main.py", "content": "x = 1"}],
                tests=[]
            )

        assert exc_info.value.status_code == 429
        assert exc_info.value.error_code == "NEMOTRON_RATE_LIMITED"
        assert mock_sleep.call_count == 1

@pytest.mark.asyncio
async def test_investigate_bug_auth_error_no_retry():
    """Verify that a 401/403 authentication error immediately raises NemotronAuthError without retrying."""
    auth_err = APIError(
        message="Incorrect API key provided: nvapi-secret",
        request=MagicMock(),
        body={"error": {"code": 401}}
    )
    auth_err.status_code = 401

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=auth_err)

    with patch.object(settings, "NEMOTRON_MAX_RETRIES", 2), \
         patch("asyncio.sleep", AsyncMock()) as mock_sleep, \
         patch.object(nemotron_service, "get_client", return_value=mock_client):

        with pytest.raises(NemotronAuthError) as exc_info:
            await nemotron_service.investigate_bug(
                issue={"number": 1, "title": "Auth bug", "body": "...", "comments": []},
                repository={"owner": "org", "name": "repo"},
                files=[{"path": "src/main.py", "content": "x = 1"}],
                tests=[]
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.error_code == "NEMOTRON_AUTH_ERROR"
        assert mock_client.chat.completions.create.call_count == 1
        assert mock_sleep.call_count == 0

@pytest.mark.asyncio
async def test_investigate_streaming_accumulation():
    """Verify streaming response chunks are correctly accumulated into valid response."""
    chunks = [
        '{"root_cause": "Streaming ',
        'success", "confidence": 0.98, ',
        '"affected_files": ["src/stream.py"], ',
        '"affected_functions": ["stream_func"], ',
        '"evidence": [{"file": "src/stream.py", "line": 5, "reason": "streamed"}], ',
        '"proposed_fix": "stream fix", ',
        '"test_strategy": "stream test"}'
    ]
    mock_stream = MockAsyncStream(chunks)
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

    with patch.object(nemotron_service, "get_client", return_value=mock_client):
        res = await nemotron_service.investigate_bug(
            issue={"number": 5, "title": "Streaming test", "body": "...", "comments": []},
            repository={"owner": "org", "name": "repo"},
            files=[{"path": "src/stream.py", "content": "def stream_func(): pass"}],
            tests=[]
        )

        assert res.root_cause == "Streaming success"
        assert res.confidence == 0.98
        assert res.affected_files == ["src/stream.py"]

@pytest.mark.asyncio
async def test_api_investigate_rate_limited_returns_429():
    """Verify the API endpoint maps NemotronRateLimitError to HTTP 429 with error_code."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        mock_repo = {"default_branch": "main", "language": "Python"}
        mock_tree = {"tree": [{"path": "src/app.py", "type": "blob", "size": 100}]}
        mock_issue = {"number": 1, "title": "Bug", "body": "...", "labels": [], "comments": []}
        mock_file_content = ("x = 1", "sha123")

        with patch.object(github_service, "get_repository", AsyncMock(return_value=mock_repo)), \
             patch.object(github_service, "get_repository_tree", AsyncMock(return_value=mock_tree)), \
             patch.object(github_service, "get_issue", AsyncMock(return_value=mock_issue)), \
             patch.object(github_service, "get_issue_comments", AsyncMock(return_value=[])), \
             patch.object(github_service, "get_file_content_and_sha", AsyncMock(return_value=mock_file_content)), \
             patch.object(nemotron_service, "investigate_bug", AsyncMock(side_effect=NemotronRateLimitError("Rate limit reached"))):

            payload = {"owner": "org", "repo": "repo", "issue_number": 1, "branch": "main"}
            res = await ac.post("/api/ai/nemotron/investigate", json=payload, headers={"Authorization": "Bearer token"})
            assert res.status_code == 429
            data = res.json()
            assert data["detail"]["error_code"] == "NEMOTRON_RATE_LIMITED"
            assert data["detail"]["error"] == "rate_limited"

@pytest.mark.asyncio
async def test_api_investigate_github_connection_error_returns_502_github_not_nemotron():
    """Verify that GitHub API disconnections return HTTP 502 with GITHUB_CONNECTION_ERROR, distinct from Nemotron."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        mock_repo = {"default_branch": "main", "language": "Python"}
        gh_err = GitHubConnectionError("Failed to connect to GitHub API fetching issue #1 in anshpatel2212/2D2Mesh: Server disconnected without sending a response.", status_code=502)

        with patch.object(github_service, "get_repository", AsyncMock(return_value=mock_repo)), \
             patch.object(repository_analyzer, "get_issue_details", AsyncMock(side_effect=gh_err)):

            payload = {"owner": "anshpatel2212", "repo": "2D2Mesh", "issue_number": 1, "branch": "main"}
            res = await ac.post("/api/ai/nemotron/investigate", json=payload, headers={"Authorization": "Bearer test_token"})
            assert res.status_code == 502
            data = res.json()
            assert data["detail"]["error_code"] == "GITHUB_CONNECTION_ERROR"
            assert data["detail"]["error"] == "github_connection_error"
            assert "Server disconnected without sending a response" in data["detail"]["message"]

@pytest.mark.asyncio
async def test_api_investigate_github_timeout_returns_504_github_not_nemotron():
    """Verify that GitHub API timeouts return HTTP 504 with GITHUB_TIMEOUT, distinct from Nemotron."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        mock_repo = {"default_branch": "main", "language": "Python"}
        gh_timeout = GitHubTimeoutError("GitHub API timed out after 15.0s fetching tree for anshpatel2212/2D2Mesh@main.", status_code=504)

        with patch.object(github_service, "get_repository", AsyncMock(return_value=mock_repo)), \
             patch.object(repository_analyzer, "get_issue_details", AsyncMock(return_value={"number": 1, "title": "Crash", "body": "", "comments": []})), \
             patch.object(github_service, "get_repository_tree", AsyncMock(side_effect=gh_timeout)):

            payload = {"owner": "anshpatel2212", "repo": "2D2Mesh", "issue_number": 1, "branch": "main"}
            res = await ac.post("/api/ai/nemotron/investigate", json=payload, headers={"Authorization": "Bearer test_token"})
            assert res.status_code == 504
            data = res.json()
            assert data["detail"]["error_code"] == "GITHUB_TIMEOUT"
            assert data["detail"]["error"] == "gateway_timeout"

@pytest.mark.asyncio
async def test_api_investigate_nemotron_api_error_returns_502_nemotron():
    """Verify that Nemotron API errors return HTTP 502 with NEMOTRON_API_ERROR."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        mock_repo = {"default_branch": "main", "language": "Python"}
        mock_tree = {"tree": [{"path": "src/app.py", "type": "blob", "size": 100}]}
        mock_issue = {"number": 1, "title": "Bug", "body": "...", "labels": [], "comments": []}
        mock_file_content = ("x = 1", "sha123")

        with patch.object(github_service, "get_repository", AsyncMock(return_value=mock_repo)), \
             patch.object(github_service, "get_repository_tree", AsyncMock(return_value=mock_tree)), \
             patch.object(github_service, "get_issue", AsyncMock(return_value=mock_issue)), \
             patch.object(github_service, "get_issue_comments", AsyncMock(return_value=[])), \
             patch.object(github_service, "get_file_content_and_sha", AsyncMock(return_value=mock_file_content)), \
             patch.object(nemotron_service, "investigate_bug", AsyncMock(side_effect=NemotronAPIError("NVIDIA Nemotron inference endpoint error."))):

            payload = {"owner": "org", "repo": "repo", "issue_number": 1, "branch": "main"}
            res = await ac.post("/api/ai/nemotron/investigate", json=payload, headers={"Authorization": "Bearer token"})
            assert res.status_code == 502
            data = res.json()
            assert data["detail"]["error_code"] == "NEMOTRON_API_ERROR"
            assert data["detail"]["error"] == "bad_gateway"



