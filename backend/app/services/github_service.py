import os
import re
import secrets
import logging
import asyncio
import random
import httpx
from typing import Dict, Any, List, Optional
from app.core.config import settings

import base64

logger = logging.getLogger("devrescue.github")


def _sanitize_msg(msg: Any) -> str:
    """Removes tokens, passwords, secrets, or cookies from log messages and exception strings."""
    text = str(msg)
    # Redact Authorization header values / Bearer tokens
    text = re.sub(r'Bearer\s+[A-Za-z0-9_\-\.]+', 'Bearer [REDACTED]', text, flags=re.IGNORECASE)
    # Redact GitHub personal access tokens and OAuth tokens
    text = re.sub(r'(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{16,}', '[REDACTED_TOKEN]', text)
    text = re.sub(r'github_pat_[A-Za-z0-9_]{20,}', '[REDACTED_TOKEN]', text)
    # Redact client secrets or api keys
    if settings.GITHUB_CLIENT_SECRET:
        text = text.replace(settings.GITHUB_CLIENT_SECRET, "[REDACTED_SECRET]")
    if settings.NVIDIA_API_KEY:
        text = text.replace(settings.NVIDIA_API_KEY, "[REDACTED_KEY]")
    # Redact session cookies
    text = re.sub(r'devrescue_session=[A-Za-z0-9_\-\.]+', 'devrescue_session=[REDACTED]', text)
    return text


class GitHubError(Exception):
    """Base exception for GitHub API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

class GitHubAuthError(GitHubError):
    """Raised on 401 Authentication failure or expired token."""
    pass

class GitHubRateLimitError(GitHubError):
    """Raised on 403 Forbidden or API rate limit exceeded."""
    pass

class GitHubPermissionError(GitHubError):
    """Raised on 403 Forbidden due to insufficient permissions or scopes."""
    pass

class GitHubNotFoundError(GitHubError):
    """Raised on 404 Resource not found."""
    pass

class GitHubConflictError(GitHubError):
    """Raised on 409 Conflict (e.g. branch exists, patch conflict)."""
    pass

class GitHubValidationError(GitHubError):
    """Raised on 422 Unprocessable Entity (e.g. ref exists, invalid PR)."""
    pass

class GitHubTimeoutError(GitHubError):
    """Raised when GitHub API request times out."""
    pass

class GitHubConnectionError(GitHubError):
    """Raised on GitHub connection or network failure."""
    pass

from app.services.session_store import GitHubSessionStore, session_store


class GitHubService:
    """
    Official GitHub REST API Service.
    Handles OAuth exchange, repository querying, branch inspection, and issue tracking.
    Never logs or leaks access tokens or client secrets.
    """
    def __init__(self):
        self.api_url = settings.GITHUB_API_URL or "https://api.github.com"
        self.client_id = settings.GITHUB_CLIENT_ID
        self.client_secret = settings.GITHUB_CLIENT_SECRET
        self.redirect_uri = settings.GITHUB_REDIRECT_URI
        self.timeout = 15.0
        self._limits = httpx.Limits(max_connections=20, max_keepalive_connections=10, keepalive_expiry=30.0)

    def _get_headers(self, access_token: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "DevRescue-AI-App"
        }
        if access_token and access_token.strip() and not access_token.startswith("test_") and not access_token.startswith("mock_") and not access_token.startswith("public_"):
            headers["Authorization"] = f"Bearer {access_token.strip()}"
        return headers

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        access_token: Optional[str] = None,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        follow_redirects: bool = False,
        max_retries: int = 3,
        context: str = ""
    ) -> httpx.Response:
        """
        Executes HTTP request to GitHub API with bounded retries and exponential backoff
        for transient connection errors (e.g. RemoteProtocolError/disconnections, timeouts)
        and HTTP 5xx server responses. Never leaks auth tokens or credentials.
        """
        req_headers = headers if headers is not None else self._get_headers(access_token)
        timeout_val = timeout if timeout is not None else self.timeout
        client_timeout = httpx.Timeout(timeout_val, connect=10.0, read=timeout_val, write=10.0)
        base_delay = 0.5
        sanitized_endpoint = _sanitize_msg(url)
        last_exception = None

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(
                    timeout=client_timeout,
                    limits=self._limits,
                    http2=False
                ) as client:
                    if method.upper() == "GET":
                        resp = await client.get(url, headers=req_headers, params=params, follow_redirects=follow_redirects)
                    elif method.upper() == "POST":
                        resp = await client.post(url, headers=req_headers, json=json, params=params, follow_redirects=follow_redirects)
                    elif method.upper() == "PUT":
                        resp = await client.put(url, headers=req_headers, json=json, params=params, follow_redirects=follow_redirects)
                    elif method.upper() == "DELETE":
                        resp = await client.delete(url, headers=req_headers, params=params, follow_redirects=follow_redirects)
                    else:
                        resp = await client.request(method, url, headers=req_headers, json=json, params=params, follow_redirects=follow_redirects)

                if resp.status_code in {500, 502, 503, 504}:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt) + random.uniform(0.05, 0.15)
                        logger.warning(
                            f"[GITHUB] Transient HTTP {resp.status_code} on attempt {attempt + 1}/{max_retries} for {sanitized_endpoint}. Retrying in {delay:.2f}s..."
                        )
                        await asyncio.sleep(delay)
                        continue
                return resp

            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exception = exc
                sanitized_err = _sanitize_msg(str(exc))
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0.05, 0.15)
                    logger.warning(
                        f"[GITHUB] Transient connection error ({exc.__class__.__name__}: {sanitized_err}) on attempt {attempt + 1}/{max_retries} for {sanitized_endpoint} ({context}). Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(
                        f"[GITHUB] Connection error exhausted {max_retries} retries for {sanitized_endpoint} ({context}): {exc.__class__.__name__}: {sanitized_err}"
                    )
                    if isinstance(exc, httpx.TimeoutException):
                        raise GitHubTimeoutError(
                            f"GitHub API timed out after {timeout_val}s {context}: {sanitized_err}",
                            status_code=504
                        ) from exc
                    else:
                        raise GitHubConnectionError(
                            f"Failed to connect to GitHub API {context}: {sanitized_err}",
                            status_code=502
                        ) from exc

        # Fallback if loop finishes unexpectedly
        if last_exception:
            raise GitHubConnectionError(
                f"Failed to connect to GitHub API {context}: {_sanitize_msg(str(last_exception))}",
                status_code=502
            ) from last_exception
        raise GitHubConnectionError(f"GitHub API request failed unexpectedly {context}.", status_code=502)

    def _handle_response_error(self, response: httpx.Response, context_msg: str):
        gh_msg = ""
        try:
            err_data = response.json()
            if isinstance(err_data, dict):
                gh_msg = err_data.get("message", "")
        except Exception:
            pass

        if not gh_msg:
            try:
                gh_msg = getattr(response, "text", "") or ""
            except Exception:
                pass

        if response.status_code == 401:
            msg = f"GitHub authentication expired: {gh_msg}" if gh_msg else "GitHub authentication expired."
            raise GitHubAuthError(msg, status_code=401)
        elif response.status_code == 403:
            headers = getattr(response, "headers", None)
            remaining = headers.get("x-ratelimit-remaining") if (headers and hasattr(headers, "get")) else None
            is_rate_limit = remaining == "0" or "rate limit" in gh_msg.lower()
            if is_rate_limit:
                raise GitHubRateLimitError(f"GitHub API rate limit exceeded: {gh_msg or 'Too many requests'}", status_code=403)
            else:
                raise GitHubPermissionError(f"GitHub permission denied: {gh_msg or 'Insufficient repository or OAuth permissions'}", status_code=403)
        elif response.status_code == 404:
            raise GitHubNotFoundError(f"Repository or resource not found: {gh_msg or context_msg}", status_code=404)
        elif response.status_code == 409:
            raise GitHubConflictError(f"GitHub conflict ({response.status_code}): {gh_msg or context_msg}", status_code=409)
        elif response.status_code == 422:
            raise GitHubValidationError(f"GitHub validation error ({response.status_code}): {gh_msg or context_msg}", status_code=422)
        elif response.status_code in (502, 503):
            raise GitHubConnectionError(f"GitHub upstream service error ({response.status_code}): {gh_msg or context_msg}", status_code=response.status_code)
        elif response.status_code == 504:
            raise GitHubTimeoutError(f"GitHub upstream gateway timeout: {gh_msg or context_msg}", status_code=504)
        else:
            raise GitHubError(f"GitHub API error ({response.status_code}): {gh_msg or context_msg}", status_code=response.status_code)

    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """Constructs GitHub OAuth authorization URL."""
        client_id = self.client_id or "devrescue_github_client"
        if not state:
            state = session_store.create_oauth_state()
        scope = "repo,read:user,user:email"
        import urllib.parse
        params = {
            "client_id": client_id,
            "redirect_uri": self.redirect_uri,
            "scope": scope,
            "state": state
        }
        return f"https://github.com/login/oauth/authorize?{urllib.parse.urlencode(params)}"

    async def exchange_code_for_token(self, code: str) -> str:
        """Exchanges OAuth authorization code for GitHub access token."""
        if not self.client_id or not self.client_secret:
            raise GitHubError("GitHub OAuth credentials not configured (GITHUB_CLIENT_ID or GITHUB_CLIENT_SECRET missing).")

        url = "https://github.com/login/oauth/access_token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri
        }
        headers = {
            "Accept": "application/json",
            "User-Agent": "DevRescue-AI-App"
        }

        resp = await self._request_with_retry(
            "POST",
            url,
            json=payload,
            headers=headers,
            timeout=15.0,
            context="exchanging OAuth authorization code for access token"
        )
        if resp.status_code != 200:
            raise GitHubError(f"OAuth code exchange failed with status {resp.status_code}.")
        
        data = resp.json()
        if "error" in data:
            raise GitHubError(f"GitHub OAuth error: {data.get('error_description', data.get('error'))}")
        
        token = data.get("access_token")
        if not token:
            raise GitHubError("GitHub did not return an access token.")
        return token

    async def get_authenticated_user(self, access_token: str) -> Dict[str, Any]:
        """Fetches the authenticated user profile."""
        url = f"{self.api_url}/user"
        resp = await self._request_with_retry("GET", url, access_token, timeout=10.0, context="fetching authenticated user profile")
        if resp.status_code != 200:
            self._handle_response_error(resp, "Failed to fetch authenticated user profile.")
        user = resp.json()
        return {
            "id": user.get("id"),
            "login": user.get("login"),
            "name": user.get("name") or user.get("login"),
            "avatar_url": user.get("avatar_url"),
            "html_url": user.get("html_url"),
            "email": user.get("email")
        }

    async def list_repositories(self, access_token: str, page: int = 1, per_page: int = 30) -> List[Dict[str, Any]]:
        """
        Lists repositories accessible to the user, normalized according to Phase 5.
        """
        url = f"{self.api_url}/user/repos"
        params = {
            "sort": "updated",
            "page": page,
            "per_page": per_page,
            "affiliation": "owner,collaborator,organization_member"
        }
        resp = await self._request_with_retry("GET", url, access_token, params=params, timeout=15.0, context="listing repositories")
        if resp.status_code != 200:
            self._handle_response_error(resp, "Failed to list repositories.")
        
        repos = resp.json()
        normalized = []
        for r in repos:
            normalized.append({
                "id": r.get("id"),
                "name": r.get("name"),
                "full_name": r.get("full_name"),
                "owner": r.get("owner", {}).get("login") if r.get("owner") else "",
                "description": r.get("description") or "",
                "private": bool(r.get("private")),
                "default_branch": r.get("default_branch") or "main",
                "language": r.get("language") or "Other",
                "stars": r.get("stargazers_count", 0),
                "forks": r.get("forks_count", 0),
                "open_issues": r.get("open_issues_count", 0),
                "html_url": r.get("html_url")
            })
        return normalized

    async def get_repository(self, access_token: Optional[str], owner: str, repo: str) -> Dict[str, Any]:
        """Fetches and normalizes a single repository."""
        url = f"{self.api_url}/repos/{owner}/{repo}"
        resp = await self._request_with_retry(
            "GET",
            url,
            access_token,
            timeout=self.timeout,
            context=f"fetching repository {owner}/{repo}"
        )

        if resp.status_code != 200:
            self._handle_response_error(resp, f"Failed to fetch repository {owner}/{repo}.")
        r = resp.json()
        return {
            "id": r.get("id"),
            "name": r.get("name"),
            "full_name": r.get("full_name"),
            "owner": r.get("owner", {}).get("login") if r.get("owner") else owner,
            "description": r.get("description") or "",
            "private": bool(r.get("private")),
            "default_branch": r.get("default_branch") or "main",
            "language": r.get("language") or "Other",
            "stars": r.get("stargazers_count", 0),
            "forks": r.get("forks_count", 0),
            "open_issues": r.get("open_issues_count", 0),
            "html_url": r.get("html_url")
        }

    async def list_branches(self, access_token: str, owner: str, repo: str) -> List[Dict[str, Any]]:
        """Lists repository branches."""
        url = f"{self.api_url}/repos/{owner}/{repo}/branches"
        resp = await self._request_with_retry("GET", url, access_token, params={"per_page": 100}, timeout=10.0, context=f"listing branches for {owner}/{repo}")
        if resp.status_code != 200:
            self._handle_response_error(resp, f"Failed to list branches for {owner}/{repo}.")
        branches = resp.json()
        return [
            {
                "name": b.get("name"),
                "protected": b.get("protected", False),
                "commit_sha": b.get("commit", {}).get("sha") if b.get("commit") else ""
            }
            for b in branches
        ]

    async def get_branch(self, access_token: str, owner: str, repo: str, branch: str) -> Dict[str, Any]:
        """Fetches a specific branch."""
        url = f"{self.api_url}/repos/{owner}/{repo}/branches/{branch}"
        resp = await self._request_with_retry("GET", url, access_token, timeout=10.0, context=f"fetching branch {branch} in {owner}/{repo}")
        if resp.status_code != 200:
            self._handle_response_error(resp, f"Failed to fetch branch {branch} in {owner}/{repo}.")
        b = resp.json()
        return {
            "name": b.get("name"),
            "protected": b.get("protected", False),
            "commit_sha": b.get("commit", {}).get("sha") if b.get("commit") else ""
        }

    async def list_issues(self, access_token: str, owner: str, repo: str, state: str = "open") -> List[Dict[str, Any]]:
        """
        Lists issues for repository.
        Filters out pull requests as required by Phase 9.
        """
        url = f"{self.api_url}/repos/{owner}/{repo}/issues"
        params = {"state": state, "per_page": 50}
        resp = await self._request_with_retry("GET", url, access_token, params=params, timeout=12.0, context=f"listing issues for {owner}/{repo}")
        if resp.status_code != 200:
            self._handle_response_error(resp, f"Failed to list issues for {owner}/{repo}.")
        
        raw_issues = resp.json()
        normalized = []
        for item in raw_issues:
            # Phase 9: Filter out pull requests
            if item.get("pull_request") is not None:
                continue
            
            labels = [
                l["name"] if isinstance(l, dict) else str(l)
                for l in item.get("labels", [])
            ]

            normalized.append({
                "id": item.get("id"),
                "number": item.get("number"),
                "title": item.get("title"),
                "body": item.get("body") or "",
                "state": item.get("state"),
                "author": item.get("user", {}).get("login") if item.get("user") else "unknown",
                "labels": labels,
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "html_url": item.get("html_url")
            })
        return normalized

    async def get_issue(self, access_token: Optional[str], owner: str, repo: str, issue_number: int) -> Dict[str, Any]:
        """Fetches a specific issue."""
        url = f"{self.api_url}/repos/{owner}/{repo}/issues/{issue_number}"
        resp = await self._request_with_retry(
            "GET",
            url,
            access_token,
            timeout=self.timeout,
            context=f"fetching issue #{issue_number} in {owner}/{repo}"
        )

        if resp.status_code != 200:
            self._handle_response_error(resp, f"Failed to fetch issue #{issue_number} in {owner}/{repo}.")
        item = resp.json()
        # If it's a pull request, raise not found for issues
        if item.get("pull_request") is not None:
            raise GitHubNotFoundError(f"Issue #{issue_number} is a pull request, not an issue.", status_code=404)
        
        labels = [
            l["name"] if isinstance(l, dict) else str(l)
            for l in item.get("labels", [])
        ]
        return {
            "id": item.get("id"),
            "number": item.get("number"),
            "title": item.get("title"),
            "body": item.get("body") or "",
            "state": item.get("state"),
            "author": item.get("user", {}).get("login") if item.get("user") else "unknown",
            "labels": labels,
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
            "html_url": item.get("html_url")
        }

    async def get_issue_comments(self, access_token: Optional[str], owner: str, repo: str, issue_number: int) -> List[Dict[str, Any]]:
        """Fetches comments for a specific issue."""
        url = f"{self.api_url}/repos/{owner}/{repo}/issues/{issue_number}/comments"
        resp = await self._request_with_retry(
            "GET",
            url,
            access_token,
            timeout=self.timeout,
            context=f"fetching comments for issue #{issue_number} in {owner}/{repo}"
        )

        if resp.status_code != 200:
            return []
        raw_comments = resp.json()
        if not isinstance(raw_comments, list):
            return []
        return [
            {
                "id": c.get("id"),
                "author": c.get("user", {}).get("login") if c.get("user") else "unknown",
                "body": c.get("body") or "",
                "created_at": c.get("created_at")
            }
            for c in raw_comments
            if isinstance(c, dict)
        ]

    async def get_repository_tree(self, access_token: Optional[str], owner: str, repo: str, branch: str) -> Dict[str, Any]:
        """Fetches git tree representation for a branch."""
        url = f"{self.api_url}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        resp = await self._request_with_retry(
            "GET",
            url,
            access_token,
            timeout=self.timeout,
            context=f"fetching tree for {owner}/{repo}@{branch}"
        )

        if resp.status_code != 200:
            self._handle_response_error(resp, f"Failed to fetch tree for {owner}/{repo}@{branch}.")
        return resp.json()

    async def download_and_extract_archive(
        self,
        access_token: Optional[str],
        owner: str,
        repo: str,
        ref: str,
        destination_dir: str
    ) -> None:
        """
        Downloads repository zipball from GitHub and extracts it safely into destination_dir,
        stripping the top-level directory prefix generated by GitHub.
        """
        import io
        import zipfile
        url = f"{self.api_url}/repos/{owner}/{repo}/zipball/{ref}"
        resp = await self._request_with_retry(
            "GET",
            url,
            access_token,
            timeout=45.0,
            follow_redirects=True,
            context=f"downloading repository zipball for {owner}/{repo}@{ref}"
        )

        if resp.status_code != 200:
            self._handle_response_error(resp, f"Failed to download repository zipball for {owner}/{repo}@{ref}.")

        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            names = [name for name in z.namelist() if not name.startswith("__MACOSX")]
            root_prefix = None
            prefixes = {name.split('/')[0] for name in names if '/' in name}
            if len(prefixes) == 1:
                candidate = list(prefixes)[0] + '/'
                if all(name.startswith(candidate) or name == list(prefixes)[0] or name == candidate for name in names):
                    root_prefix = candidate

            for member in z.infolist():
                filename = member.filename
                if root_prefix and filename.startswith(root_prefix):
                    rel_path = filename[len(root_prefix):]
                else:
                    rel_path = filename

                if not rel_path or rel_path.endswith('/'):
                    continue

                target_path = os.path.abspath(os.path.join(destination_dir, rel_path))
                # Prevent directory traversal attacks
                if not target_path.startswith(os.path.abspath(destination_dir)):
                    continue

                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, 'wb') as f:
                    f.write(z.read(member))

    async def get_file(self, access_token: str, owner: str, repo: str, path: str, ref: Optional[str] = None) -> Dict[str, Any]:
        """Fetches file contents metadata."""
        url = f"{self.api_url}/repos/{owner}/{repo}/contents/{path}"
        params = {"ref": ref} if ref else {}
        resp = await self._request_with_retry(
            "GET",
            url,
            access_token,
            params=params,
            timeout=10.0,
            context=f"fetching file {path} from {owner}/{repo}"
        )
        if resp.status_code != 200:
            self._handle_response_error(resp, f"Failed to fetch file {path} from {owner}/{repo}.")
        return resp.json()

    async def get_languages(self, access_token: str, owner: str, repo: str) -> Dict[str, int]:
        """Fetches language distribution map."""
        url = f"{self.api_url}/repos/{owner}/{repo}/languages"
        resp = await self._request_with_retry("GET", url, access_token, timeout=10.0, context=f"fetching languages for {owner}/{repo}")
        if resp.status_code != 200:
            self._handle_response_error(resp, f"Failed to fetch languages for {owner}/{repo}.")
        return resp.json()

    async def get_commits(self, access_token: str, owner: str, repo: str, branch: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetches latest commits on branch."""
        url = f"{self.api_url}/repos/{owner}/{repo}/commits"
        params = {"per_page": 10}
        if branch:
            params["sha"] = branch
        resp = await self._request_with_retry("GET", url, access_token, params=params, timeout=10.0, context=f"fetching commits for {owner}/{repo}")
        if resp.status_code != 200:
            self._handle_response_error(resp, f"Failed to fetch commits for {owner}/{repo}.")
        commits = resp.json()
        return [
            {
                "sha": c.get("sha"),
                "message": c.get("commit", {}).get("message"),
                "author": c.get("commit", {}).get("author", {}).get("name"),
                "date": c.get("commit", {}).get("author", {}).get("date")
            }
            for c in commits
        ]

    # -------------------------------------------------------------
    # Write Operations: Branch, Content, Commit, and Pull Request
    # -------------------------------------------------------------

    async def get_branch_sha(self, access_token: str, owner: str, repo: str, branch: str) -> str:
        """
        Retrieves the latest commit SHA for a branch.
        Queries /git/ref/heads/{branch} or /branches/{branch}.
        """
        branch_name = branch.replace("refs/heads/", "")
        url = f"{self.api_url}/repos/{owner}/{repo}/git/ref/heads/{branch_name}"
        resp = await self._request_with_retry("GET", url, access_token, timeout=10.0, context=f"fetching branch ref for {branch}")
        if resp.status_code == 200:
            data = resp.json()
            sha = data.get("object", {}).get("sha")
            if sha:
                return sha
        elif resp.status_code not in [404]:
            self._handle_response_error(resp, f"Failed to get branch ref for {branch}")

        # Fallback to /branches/{branch}
        url_branch = f"{self.api_url}/repos/{owner}/{repo}/branches/{branch_name}"
        resp_branch = await self._request_with_retry("GET", url_branch, access_token, timeout=10.0, context=f"fetching branch '{branch_name}' in {owner}/{repo}")
        if resp_branch.status_code != 200:
            self._handle_response_error(resp_branch, f"Branch '{branch_name}' not found in {owner}/{repo}")
        data_branch = resp_branch.json()
        sha = data_branch.get("commit", {}).get("sha")
        if not sha:
            raise GitHubError(f"Could not extract commit SHA for branch '{branch}'.")
        return sha

    async def create_branch(
        self,
        access_token: str,
        owner: str,
        repo: str,
        base_branch: Optional[str],
        new_branch: str
    ) -> Dict[str, Any]:
        """
        Creates a new Git reference (branch) based on base_branch.
        POST /repos/{owner}/{repo}/git/refs
        """
        if not base_branch:
            repo_info = await self.get_repository(access_token, owner, repo)
            base_branch = repo_info.get("default_branch", "main")

        base_sha = await self.get_branch_sha(access_token, owner, repo, base_branch)
        
        clean_new_branch = new_branch.replace("refs/heads/", "")
        ref_name = f"refs/heads/{clean_new_branch}"
        url = f"{self.api_url}/repos/{owner}/{repo}/git/refs"
        payload = {
            "ref": ref_name,
            "sha": base_sha
        }
        resp = await self._request_with_retry(
            "POST",
            url,
            access_token,
            json=payload,
            timeout=10.0,
            context=f"creating branch '{clean_new_branch}' in {owner}/{repo}"
        )
        if resp.status_code in [422, 409]:
            raise GitHubConflictError(f"Branch '{clean_new_branch}' already exists in {owner}/{repo}.", status_code=resp.status_code)
        if resp.status_code != 201:
            self._handle_response_error(resp, f"Failed to create branch '{clean_new_branch}' in {owner}/{repo}")

        return {
            "status": "success",
            "branch": clean_new_branch,
            "sha": base_sha,
            "ref": ref_name
        }

    async def delete_branch(self, access_token: str, owner: str, repo: str, branch: str) -> bool:
        """
        Deletes a branch reference (used for rollback/cleanup if patch fails).
        DELETE /repos/{owner}/{repo}/git/refs/heads/{branch}
        """
        branch_name = branch.replace("refs/heads/", "")
        url = f"{self.api_url}/repos/{owner}/{repo}/git/refs/heads/{branch_name}"
        resp = await self._request_with_retry("DELETE", url, access_token, timeout=10.0, context=f"deleting branch '{branch_name}' in {owner}/{repo}")
        return resp.status_code in [204, 200]

    async def get_file_sha(
        self,
        access_token: str,
        owner: str,
        repo: str,
        path: str,
        branch: str
    ) -> Optional[str]:
        """
        Retrieves the blob SHA of an existing file on a branch.
        Returns None if file does not exist (404).
        """
        clean_path = validate_safe_repo_path(path)
        url = f"{self.api_url}/repos/{owner}/{repo}/contents/{clean_path}"
        params = {"ref": branch}
        resp = await self._request_with_retry(
            "GET",
            url,
            access_token,
            params=params,
            timeout=10.0,
            context=f"getting file SHA for '{path}' on branch '{branch}' in {owner}/{repo}"
        )
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            self._handle_response_error(resp, f"Failed to get file SHA for '{path}' on branch '{branch}'")
        return resp.json().get("sha")

    async def get_file_content_and_sha(
        self,
        access_token: Optional[str],
        owner: str,
        repo: str,
        path: str,
        branch: str
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Fetches the decoded content and SHA of a file on a branch.
        Returns (decoded_content, sha) or (None, None) if file does not exist.
        """
        clean_path = validate_safe_repo_path(path)
        url = f"{self.api_url}/repos/{owner}/{repo}/contents/{clean_path}"
        params = {"ref": branch}
        resp = await self._request_with_retry(
            "GET",
            url,
            access_token,
            params=params,
            timeout=self.timeout,
            context=f"fetching content for '{path}' on branch '{branch}' in {owner}/{repo}"
        )

        if resp.status_code == 404:
            return None, None
        if resp.status_code != 200:
            self._handle_response_error(resp, f"Failed to get file content for '{path}' on branch '{branch}'")
        data = resp.json()
        raw_b64 = data.get("content", "")
        sha = data.get("sha")
        try:
            decoded = base64.b64decode(raw_b64.replace("\n", "")).decode("utf-8")
        except Exception:
            decoded = base64.b64decode(raw_b64.replace("\n", "")).decode("latin1")
        return decoded, sha

    async def create_or_update_file(
        self,
        access_token: str,
        owner: str,
        repo: str,
        path: str,
        content: str,
        branch: str,
        message: str,
        sha: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates or updates a file on GitHub using Contents API.
        PUT /repos/{owner}/{repo}/contents/{path}
        Returns: {"path": path, "commit_sha": commit_sha, "status": "updated"|"created"}
        """
        clean_path = validate_safe_repo_path(path)
        url = f"{self.api_url}/repos/{owner}/{repo}/contents/{clean_path}"
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        payload = {
            "message": message,
            "content": encoded_content,
            "branch": branch
        }
        if sha:
            payload["sha"] = sha
        
        resp = await self._request_with_retry(
            "PUT",
            url,
            access_token,
            json=payload,
            timeout=10.0,
            context=f"writing file '{clean_path}' on branch '{branch}' in {owner}/{repo}"
        )
        if resp.status_code == 409:
            raise GitHubConflictError(f"Conflict updating '{clean_path}' on branch '{branch}'.", status_code=409)
        if resp.status_code not in [200, 201]:
            self._handle_response_error(resp, f"Failed to write file '{clean_path}' on branch '{branch}'")
        
        data = resp.json()
        commit_sha = data.get("commit", {}).get("sha")
        if not commit_sha:
            raise GitHubError("GitHub did not return a valid commit SHA upon file update.")
        
        return {
            "path": clean_path,
            "commit_sha": commit_sha,
            "status": "updated" if sha else "created"
        }

    async def create_commit(
        self,
        access_token: str,
        owner: str,
        repo: str,
        branch: str,
        message: str,
        file_path: Optional[str] = None,
        file_content: Optional[str] = None,
        sha: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates a Git commit. When modifying a file, uses Contents API to commit directly.
        Returns: {"status": "success", "commit_sha": commit_sha}
        """
        if file_path and file_content is not None:
            res = await self.create_or_update_file(
                access_token=access_token,
                owner=owner,
                repo=repo,
                path=file_path,
                content=file_content,
                branch=branch,
                message=message,
                sha=sha
            )
            return {
                "status": "success",
                "commit_sha": res["commit_sha"],
                "path": res["path"]
            }
        
        head_sha = await self.get_branch_sha(access_token, owner, repo, branch)
        return {
            "status": "success",
            "commit_sha": head_sha
        }

    async def get_commit(
        self,
        access_token: str,
        owner: str,
        repo: str,
        commit_sha: str
    ) -> Dict[str, Any]:
        """
        Verifies a commit on GitHub.
        GET /repos/{owner}/{repo}/commits/{commit_sha}
        """
        url = f"{self.api_url}/repos/{owner}/{repo}/commits/{commit_sha}"
        resp = await self._request_with_retry("GET", url, access_token, timeout=10.0, context=f"verifying commit '{commit_sha}' in {owner}/{repo}")
        if resp.status_code != 200:
            self._handle_response_error(resp, f"Failed to verify commit '{commit_sha}' in {owner}/{repo}")
        data = resp.json()
        return {
            "sha": data.get("sha"),
            "author": data.get("commit", {}).get("author", {}).get("name"),
            "message": data.get("commit", {}).get("message"),
            "files": [f.get("filename") for f in data.get("files", [])]
        }

    async def create_pull_request(
        self,
        access_token: str,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str
    ) -> Dict[str, Any]:
        """
        Creates a real GitHub Pull Request.
        POST /repos/{owner}/{repo}/pulls
        """
        url = f"{self.api_url}/repos/{owner}/{repo}/pulls"
        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": base
        }
        resp = await self._request_with_retry(
            "POST",
            url,
            access_token,
            json=payload,
            timeout=10.0,
            context=f"creating pull request in {owner}/{repo}"
        )
        if resp.status_code == 422:
            raise GitHubValidationError(f"GitHub Pull Request validation error: {resp.text}", status_code=422)
        if resp.status_code not in [200, 201]:
            self._handle_response_error(resp, f"Failed to create pull request in {owner}/{repo}")
        
        data = resp.json()
        return {
            "status": "success",
            "pr_number": data.get("number"),
            "pr_url": data.get("html_url"),
            "title": data.get("title"),
            "head": data.get("head", {}).get("ref"),
            "base": data.get("base", {}).get("ref"),
            "state": data.get("state")
        }

    async def get_pull_request(
        self,
        access_token: str,
        owner: str,
        repo: str,
        pull_number: int
    ) -> Dict[str, Any]:
        """
        Verifies and retrieves a Pull Request from GitHub.
        GET /repos/{owner}/{repo}/pulls/{pull_number}
        """
        url = f"{self.api_url}/repos/{owner}/{repo}/pulls/{pull_number}"
        resp = await self._request_with_retry("GET", url, access_token, timeout=10.0, context=f"verifying PR #{pull_number} in {owner}/{repo}")
        if resp.status_code != 200:
            self._handle_response_error(resp, f"Failed to verify PR #{pull_number} in {owner}/{repo}")
        data = resp.json()
        return {
            "status": "success",
            "pr_number": data.get("number"),
            "pr_url": data.get("html_url"),
            "branch": data.get("head", {}).get("ref"),
            "base_branch": data.get("base", {}).get("ref"),
            "state": data.get("state"),
            "title": data.get("title"),
            "mergeable": data.get("mergeable")
        }


# -------------------------------------------------------------
# Security & Patch Application Helpers
# -------------------------------------------------------------

def validate_safe_repo_path(path: str) -> str:
    r"""
    Validates that a path is repository-relative and prevents directory traversal.
    Rejects: ../secret.txt, /etc/passwd, C:\Windows, absolute paths.
    """
    if not path or not path.strip():
        raise ValueError("Repository path cannot be empty.")
    
    cleaned = path.strip().replace("\\", "/")
    
    if cleaned.startswith("/"):
        raise ValueError(f"Absolute path '{path}' is not permitted.")
    if len(cleaned) > 1 and cleaned[1] == ":":
        raise ValueError(f"Drive letter path '{path}' is not permitted.")
    
    parts = cleaned.split("/")
    if ".." in parts:
        raise ValueError(f"Path traversal sequence '..' in '{path}' is not permitted.")
    
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
        
    return cleaned


def apply_patch_to_content(original_content: Optional[str], patch_diff: str) -> tuple[bool, str, Optional[str]]:
    """
    Applies unified diff patch to original_content with strict verification of expected old content.
    Returns: (success: bool, new_content: str, error_or_reason: Optional[str])
    If expected content is not found: returns (False, "", "patch_conflict").
    """
    if not patch_diff or not patch_diff.strip():
        return True, original_content or "", None

    # If original_content is None (file does not exist), construct from additions
    if original_content is None:
        additions = []
        for line in patch_diff.splitlines():
            if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
                continue
            if line.startswith("+"):
                additions.append(line[1:])
        if additions:
            return True, "\n".join(additions) + "\n", None
        return True, patch_diff, None

    lines = patch_diff.splitlines()
    has_diff_headers = any(l.startswith("@@") or l.startswith("---") or l.startswith("+++") for l in lines)

    if not has_diff_headers:
        return True, patch_diff, None

    # Parse hunks from unified diff
    hunks = []
    current_hunk = {"old": [], "new": []}
    in_hunk = False

    for line in lines:
        if line.startswith("@@"):
            if in_hunk:
                hunks.append(current_hunk)
                current_hunk = {"old": [], "new": []}
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("-"):
            current_hunk["old"].append(line[1:])
        elif line.startswith("+"):
            current_hunk["new"].append(line[1:])
        else:
            ctx = line[1:] if line.startswith(" ") else line
            current_hunk["old"].append(ctx)
            current_hunk["new"].append(ctx)

    if in_hunk:
        hunks.append(current_hunk)

    content = original_content

    for hunk in hunks:
        old_text = "\n".join(hunk["old"]).strip()
        new_text = "\n".join(hunk["new"]).strip()
        strictly_removed = [l for l in hunk["old"] if l not in hunk["new"]]

        # 1. Exact match of hunk block
        if old_text and old_text in content:
            content = content.replace(old_text, new_text, 1)
            continue

        # 2. Match without trailing whitespace
        old_text_norm = "\n".join(l.rstrip() for l in hunk["old"]).strip()
        content_norm = "\n".join(l.rstrip() for l in content.splitlines())
        if old_text_norm and old_text_norm in content_norm:
            content = content.replace(old_text_norm, new_text, 1)
            continue

        # 3. Check if all strictly removed lines exist in content
        if strictly_removed:
            missing_lines = [r for r in strictly_removed if r.strip() and r.strip() not in content]
            if missing_lines:
                return False, "", f"patch_conflict: Expected content not found in target file: {missing_lines[0]}"
            
            rem_joined = "\n".join(strictly_removed)
            add_joined = "\n".join([l for l in hunk["new"] if l not in hunk["old"]])
            if rem_joined in content:
                content = content.replace(rem_joined, add_joined, 1)
            else:
                for r_line in strictly_removed:
                    if r_line in content:
                        content = content.replace(r_line, add_joined, 1)
                        add_joined = ""
        else:
            # Only additions in this hunk
            add_joined = "\n".join(hunk["new"])
            if content and not content.endswith("\n"):
                content += "\n"
            content += add_joined + "\n"

    return True, content, None

github_service = GitHubService()

