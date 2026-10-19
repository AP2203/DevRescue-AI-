import os
import json
import re
import ast
import time
import uuid
import asyncio
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("devrescue.nemotron")
from openai import AsyncOpenAI, APIError, APITimeoutError, APIConnectionError
import httpx
from app.core.config import settings
from app.schemas.nemotron import (
    NemotronHealthResponse,
    NemotronInvestigateResponse,
    NemotronPatchResponse,
    EvidenceItem
)

class NemotronError(Exception):
    """Base exception for Nemotron AI errors."""
    def __init__(self, message: str, status_code: int = 502, error_code: str = "NEMOTRON_API_ERROR"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code

class NemotronTimeoutError(NemotronError):
    """Raised when Nemotron API times out."""
    def __init__(self, message: str = "NVIDIA Nemotron API request timed out."):
        super().__init__(message, status_code=504, error_code="NEMOTRON_TIMEOUT")

class NemotronRateLimitError(NemotronError):
    """Raised when Nemotron API rate limits (429)."""
    def __init__(self, message: str = "NVIDIA Nemotron API rate limit exceeded."):
        super().__init__(message, status_code=429, error_code="NEMOTRON_RATE_LIMITED")

class NemotronAuthError(NemotronError):
    """Raised when Nemotron API returns authentication or permission failures (401/403)."""
    def __init__(self, message: str = "NVIDIA Nemotron API authentication failed."):
        super().__init__(message, status_code=401, error_code="NEMOTRON_AUTH_ERROR")

class NemotronAPIError(NemotronError):
    """Raised on upstream Nemotron / NVIDIA API errors or connection failures."""
    def __init__(self, message: str = "NVIDIA Nemotron API error."):
        super().__init__(message, status_code=502, error_code="NEMOTRON_API_ERROR")

class NemotronResponseError(NemotronError, ValueError):
    """Raised when Nemotron returns invalid JSON or schema violation."""
    def __init__(self, message: str = "Nemotron returned invalid response structure."):
        super().__init__(message, status_code=502, error_code="NEMOTRON_INVALID_RESPONSE")

def _sanitize_error(err: Exception) -> str:
    """Removes sensitive keys, tokens, or credentials from error strings."""
    msg = str(err)
    if settings.NVIDIA_API_KEY:
        msg = msg.replace(settings.NVIDIA_API_KEY, "[REDACTED]")
    if settings.GITHUB_CLIENT_SECRET:
        msg = msg.replace(settings.GITHUB_CLIENT_SECRET, "[REDACTED]")
    # Redact common bearer tokens or keys matching patterns
    msg = re.sub(r'(Bearer\s+)[A-Za-z0-9_\-\.]+', r'\1[REDACTED]', msg)
    msg = re.sub(r'(nvapi-[A-Za-z0-9_\-]+)', '[REDACTED]', msg)
    return msg

_TIMEOUT_MESSAGE_PATTERNS = (
    "timeout",
    "timed out",
    "read timed out",
    "connect timeout",
    "connection timed out",
    "deadline exceeded",
)


def new_correlation_id(prefix: str = "nem") -> str:
    """Generates a short, non-secret correlation id to trace a single provider call chain."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def is_timeout_error(exc: BaseException) -> bool:
    """
    Robust timeout detection that does not rely on fragile substring matching alone.

    The OpenAI SDK surfaces timeouts as ``APITimeoutError`` whose ``str()`` is
    ``"Request timed out."``. That string does NOT contain the substring
    ``"timeout"`` (it contains ``"timed out"``), which previously caused genuine
    timeouts to be misclassified as generic 502 upstream errors.
    """
    if isinstance(exc, (asyncio.TimeoutError, APITimeoutError, httpx.TimeoutException)):
        return True
    if isinstance(exc, TimeoutError):  # builtin TimeoutError (asyncio.TimeoutError aliases this on 3.11)
        return True
    msg = str(exc).lower()
    return any(pattern in msg for pattern in _TIMEOUT_MESSAGE_PATTERNS)


def _status_code_of(exc: BaseException) -> Optional[int]:
    """Best-effort extraction of an HTTP status code from an OpenAI/httpx exception."""
    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
    try:
        return int(status_code) if status_code is not None else None
    except (TypeError, ValueError):
        return None


def _retry_after_seconds(exc: BaseException) -> Optional[float]:
    """Reads provider ``Retry-After`` guidance (seconds) if present, respecting rate-limit guidance."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    try:
        raw = headers.get("Retry-After") or headers.get("retry-after")
    except Exception:
        return None
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return None


def is_retryable_error(exc: BaseException) -> bool:
    """
    Classifies whether an error is safe to retry.

    Retryable: timeouts, connection failures, HTTP 408/409/429 and 5xx.
    Non-retryable: authentication (401/403), bad request (400) and malformed model output.
    """
    if isinstance(exc, (NemotronAuthError, NemotronResponseError)):
        return False
    if is_timeout_error(exc):
        return True
    if isinstance(exc, APIConnectionError):
        return True
    status_code = _status_code_of(exc)
    if status_code is not None:
        if status_code in (400, 401, 403, 404, 422):
            return False
        if status_code in (408, 409, 429) or status_code >= 500:
            return True
    msg = str(exc).lower()
    if any(term in msg for term in ("rate limit", "connection", "temporarily unavailable", "overloaded", "bad gateway", "service unavailable")):
        return True
    return False


def _repair_truncated_json(raw: str) -> Optional[Dict[str, Any]]:
    """
    Repairs truncated JSON strings where model output hit token limits.
    Closes open strings, strips trailing incomplete keys/commas, and closes unclosed braces/brackets.
    """
    start_idx = raw.find('{')
    if start_idx == -1:
        return None

    snippet = raw[start_idx:].strip()
    in_string = False
    escape = False
    stack = []

    for ch in snippet:
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if not in_string:
            if ch in ('{', '['):
                stack.append(ch)
            elif ch == '}':
                if stack and stack[-1] == '{':
                    stack.pop()
            elif ch == ']':
                if stack and stack[-1] == '[':
                    stack.pop()

    repaired = snippet
    if in_string:
        repaired += '"'

    # Remove trailing colon with unquoted value, or dangling key
    repaired = re.sub(r':\s*"?[^"}\]]*$', ': ""', repaired)
    # Remove trailing comma before closing
    repaired = re.sub(r',\s*$', '', repaired)

    # Close remaining unclosed brackets and braces in LIFO order
    closing_map = {'{': '}', '[': ']'}
    for opener in reversed(stack):
        repaired += closing_map[opener]

    try:
        parsed = json.loads(repaired, strict=False)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return None


def _extract_json_payload(content: str) -> Dict[str, Any]:
    """
    Robustly extracts and parses JSON/dict objects from model responses.
    Handles:
    - Thinking/reasoning tags: <think>...</think>, <thought>...</thought> (and unclosed tags)
    - Markdown code fences: ```json ... ``` or ``` ... ```
    - Inner braces/code blocks inside string values without premature non-greedy cutoff
    - Slicing strictly from the first '{' to the last '}'
    - Literal unescaped newlines and control characters via json.loads(..., strict=False)
    - Python dictionary syntax with single quotes and boolean literals
    - Truncated JSON repair (unclosed quotes/braces/brackets)
    """
    if not content or not content.strip():
        raise ValueError("Cannot extract JSON from empty content.")

    text = content.strip()

    # Step 1: Strip thinking/reasoning blocks
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<thought>.*?</thought>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # If <think> was opened but never closed (e.g. truncated)
    if "<think>" in text.lower():
        text = re.sub(r'<think>.*', '', text, flags=re.DOTALL | re.IGNORECASE).strip()
    if "<thought>" in text.lower():
        text = re.sub(r'<thought>.*', '', text, flags=re.DOTALL | re.IGNORECASE).strip()

    # Step 2: Strip markdown code block fences ```json ... ``` or ``` ... ```
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)

    # Step 3: Locate outermost JSON boundaries from first '{' to last '}'
    start_idx = text.find('{')
    end_idx = text.rfind('}')

    if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
        candidate = text[start_idx : end_idx + 1].strip()
    elif start_idx != -1:
        candidate = text[start_idx:].strip()
    else:
        candidate = text.strip()

    # Step 4: Attempt standard JSON parsing with strict=False (allows literal newlines in strings)
    try:
        parsed = json.loads(candidate, strict=False)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # Step 5: Attempt safe Python literal evaluation (handles single-quoted dicts without mutating string contents)
    try:
        tree = ast.parse(candidate, mode='eval')
        allowed_nodes = (
            ast.Expression, ast.Dict, ast.List, ast.Tuple, ast.Set,
            ast.Constant, ast.UnaryOp, ast.USub, ast.UAdd, ast.Name, ast.Load
        )
        if all(isinstance(node, allowed_nodes) for node in ast.walk(tree)):
            valid_names = {"true", "false", "null", "True", "False", "None"}
            name_nodes = [node for node in ast.walk(tree) if isinstance(node, ast.Name)]
            if all(n.id in valid_names for n in name_nodes):
                res = eval(compile(tree, "<string>", "eval"), {"__builtins__": {}}, {
                    "true": True, "false": False, "null": None,
                    "True": True, "False": False, "None": None
                })
                if isinstance(res, dict):
                    return res
    except Exception:
        pass

    # Step 6: Single-quote to double-quote conversion repair
    try:
        repaired = re.sub(r',\s*([}\]])', r'\1', candidate)
        repaired = re.sub(r"(?<!\\)'([^'\\]*(?:\\.[^'\\]*)*)'", r'"\1"', repaired)
        parsed = json.loads(repaired, strict=False)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # Step 7: Truncated JSON repair fallback (close unclosed quotes/braces when truncated)
    try:
        repaired_dict = _repair_truncated_json(text)
        if repaired_dict and isinstance(repaired_dict, dict):
            return repaired_dict
    except Exception:
        pass

    # Step 8: Final parse attempt using strict=False to raise descriptive JSONDecodeError if invalid
    return json.loads(candidate, strict=False)


class NemotronService:
    """
    Service for NVIDIA Nemotron 3.5 Lightning 30B (or Nebius Token Factory)
    via OpenAI-compatible Async API.
    """

    def __init__(self):
        self.provider = "NVIDIA"

    def get_client(self) -> AsyncOpenAI:
        """
        Instantiates AsyncOpenAI client using explicit, configurable timeout settings.

        Note: ``max_retries=0`` disables the SDK's hidden retry loop so that DevRescue's
        own bounded retry policy is authoritative. This prevents silently duplicated
        inference requests (which waste tokens and can double effective latency) when
        the outcome of a prior attempt is uncertain.
        """
        if not settings.NVIDIA_API_KEY or not settings.NVIDIA_API_KEY.strip():
            raise ValueError("NVIDIA_API_KEY environment variable is not configured.")
        timeout_config = httpx.Timeout(
            timeout=settings.NEMOTRON_TIMEOUT,
            connect=settings.NEMOTRON_CONNECT_TIMEOUT,
            read=settings.NEMOTRON_TIMEOUT,
            write=30.0,
            pool=settings.NEMOTRON_CONNECT_TIMEOUT
        )
        return AsyncOpenAI(
            api_key=settings.NVIDIA_API_KEY,
            base_url=settings.NVIDIA_BASE_URL,
            timeout=timeout_config,
            max_retries=0
        )

    def _classify_error(
        self,
        exc: BaseException,
        *,
        attempts: int,
        correlation_id: str,
        context: str
    ) -> NemotronError:
        """
        Maps a provider/transport exception to a typed NemotronError.

        Distinguishes timeouts, rate limits (429), authentication failures (401/403),
        bad requests (400), and generic upstream (5xx/connection) failures.
        """
        status_code = _status_code_of(exc)
        msg = str(exc).lower()

        if is_timeout_error(exc):
            error: NemotronError = NemotronTimeoutError(
                f"Nemotron {context} timed out after {attempts} attempt(s) "
                f"(correlation_id={correlation_id})."
            )
        elif status_code in (401, 403) or any(term in msg for term in ("unauthorized", "authentication", "forbidden", "api key")):
            error = NemotronAuthError(
                f"Nemotron authentication error during {context} "
                f"(correlation_id={correlation_id}): {_sanitize_error(exc)}"
            )
        elif status_code == 429 or "rate limit" in msg or "too many requests" in msg:
            error = NemotronRateLimitError(
                f"Nemotron rate limit exceeded during {context} after {attempts} attempt(s) "
                f"(correlation_id={correlation_id})."
            )
        elif status_code == 400 or "bad request" in msg:
            error = NemotronAPIError(
                f"Nemotron rejected the {context} request (correlation_id={correlation_id}): "
                f"{_sanitize_error(exc)}"
            )
        else:
            error = NemotronAPIError(
                f"Nemotron {context} failed after {attempts} attempt(s) "
                f"(correlation_id={correlation_id}): {_sanitize_error(exc)}"
            )
        error.correlation_id = correlation_id
        return error

    async def call_model_with_retries(
        self,
        client: AsyncOpenAI,
        messages: List[Dict[str, Any]],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.1,
        extra_body: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        correlation_id: Optional[str] = None,
        context: str = "model call"
    ) -> str:
        """
        Executes a bounded, non-streaming chat completion with:
        - explicit per-request timeout (model-inference appropriate, configurable),
        - bounded exponential backoff retries only for retryable errors,
        - provider ``Retry-After`` guidance honored for 429/slow responses,
        - typed error classification and a correlation id,
        - cancellation-safe behaviour (``asyncio.CancelledError`` always propagates).
        """
        timeout_val = timeout or settings.NEMOTRON_TIMEOUT
        retries = settings.NEMOTRON_MAX_RETRIES if max_retries is None else max(0, int(max_retries))
        cid = correlation_id or new_correlation_id()
        nl = logging.getLogger("devrescue.nemotron")

        last_exc: Optional[BaseException] = None
        for attempt in range(retries + 1):
            started = time.monotonic()
            try:
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=settings.NEMOTRON_MODEL,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        extra_body=extra_body,
                        stream=False,
                        timeout=timeout_val
                    ),
                    timeout=timeout_val + 5.0
                )
                if not response or not getattr(response, "choices", None):
                    raise NemotronResponseError("Nemotron returned an empty response.")

                choice = response.choices[0]
                content = None
                message = getattr(choice, "message", None)
                if message is not None:
                    content = getattr(message, "content", None)
                if not content:
                    delta = getattr(choice, "delta", None)
                    content = getattr(delta, "content", None) if delta is not None else None
                if not content or not str(content).strip():
                    raise NemotronResponseError("Nemotron returned an empty response.")

                elapsed = time.monotonic() - started
                nl.info(
                    f"[NEMOTRON] {context} succeeded (correlation_id={cid}, "
                    f"attempt={attempt + 1}/{retries + 1}, elapsed={elapsed:.2f}s)"
                )
                return str(content)
            except NemotronResponseError:
                # Malformed/empty model output is not retried here; callers may recover.
                raise
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - classified below
                last_exc = exc
                elapsed = time.monotonic() - started
                if is_retryable_error(exc) and attempt < retries:
                    backoff = min(8.0, 1.0 * (2 ** attempt))
                    retry_after = _retry_after_seconds(exc)
                    if retry_after is not None:
                        backoff = max(backoff, retry_after)
                    nl.warning(
                        f"[NEMOTRON] {context} attempt {attempt + 1}/{retries + 1} failed after "
                        f"{elapsed:.2f}s (correlation_id={cid}): {_sanitize_error(exc)}. "
                        f"Retrying in {backoff:.1f}s..."
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise self._classify_error(
                    exc,
                    attempts=attempt + 1,
                    correlation_id=cid,
                    context=context
                ) from exc

        raise self._classify_error(
            last_exc or RuntimeError("unknown provider failure"),
            attempts=retries + 1,
            correlation_id=cid,
            context=context
        )

    async def _call_model_stream_or_complete(
        self,
        client: AsyncOpenAI,
        messages: List[Dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 0.1,
        extra_body: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None
    ) -> str:
        """
        Calls model with streaming enabled to keep network connection active.
        Falls back to standard non-streaming call if streaming is not supported.
        Handles both streaming responses and mocked chat completion objects.
        """
        timeout_val = timeout or settings.NEMOTRON_TIMEOUT

        # 1. Attempt Streaming
        try:
            stream_resp = await client.chat.completions.create(
                model=settings.NEMOTRON_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body=extra_body,
                stream=True,
                timeout=timeout_val
            )

            # Check if this is an async iterable stream (e.g. real AsyncStream)
            if hasattr(stream_resp, "__aiter__"):
                chunks = []
                async for chunk in stream_resp:
                    if hasattr(chunk, "choices") and chunk.choices:
                        delta = chunk.choices[0].delta
                        content_piece = getattr(delta, "content", None)
                        if content_piece:
                            chunks.append(content_piece)
                accumulated = "".join(chunks).strip()
                if accumulated:
                    return accumulated
            # Check if this is a standard completion response (e.g. from unit test mocks)
            elif hasattr(stream_resp, "choices") and stream_resp.choices:
                choice = stream_resp.choices[0]
                if hasattr(choice, "message") and getattr(choice.message, "content", None):
                    return choice.message.content
                elif hasattr(choice, "delta") and getattr(choice.delta, "content", None):
                    return choice.delta.content
        except (APITimeoutError, asyncio.TimeoutError):
            raise
        except Exception as stream_err:
            status_code = getattr(stream_err, "status_code", None)
            err_str = str(stream_err).lower()
            if status_code in (401, 403) or any(term in err_str for term in ["401", "403", "unauthorized", "authentication", "forbidden", "api key"]):
                raise
            if status_code == 429 or "429" in err_str or "rate limit" in err_str:
                raise
            if "timeout" in err_str:
                raise
            logger.warning(
                f"[NEMOTRON] Streaming attempt failed or unsupported, falling back to non-streaming: {_sanitize_error(stream_err)}"
            )

        # 2. Fallback to Non-Streaming
        response = await client.chat.completions.create(
            model=settings.NEMOTRON_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=extra_body,
            stream=False,
            timeout=timeout_val
        )
        if response and hasattr(response, "choices") and response.choices:
            if hasattr(response.choices[0], "message") and response.choices[0].message.content:
                return response.choices[0].message.content
            if hasattr(response.choices[0], "delta") and getattr(response.choices[0].delta, "content", None):
                return response.choices[0].delta.content

        raise NemotronResponseError("Nemotron returned an empty response.")

    async def health_check(self) -> Dict[str, Any]:
        """
        Executes a real API ping to the configured NVIDIA/Nebius model endpoint.
        Returns connection status without ever leaking API secrets.
        """
        if not settings.NVIDIA_API_KEY or not settings.NVIDIA_API_KEY.strip():
            return {
                "connected": False,
                "provider": self.provider,
                "model": settings.NEMOTRON_MODEL,
                "error": "NVIDIA_API_KEY environment variable is not configured."
            }

        try:
            client = self.get_client()
            response = await client.chat.completions.create(
                model=settings.NEMOTRON_MODEL,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1
            )
            if response and response.choices:
                return {
                    "connected": True,
                    "provider": self.provider,
                    "model": settings.NEMOTRON_MODEL
                }
            return {
                "connected": False,
                "provider": self.provider,
                "model": settings.NEMOTRON_MODEL,
                "error": "Model endpoint returned an empty response."
            }
        except Exception as e:
            return {
                "connected": False,
                "provider": self.provider,
                "model": settings.NEMOTRON_MODEL,
                "error": _sanitize_error(e)
            }

    async def investigate_bug(
        self,
        issue: Dict[str, Any],
        repository: Dict[str, Any],
        files: List[Dict[str, str]],
        tests: Optional[List[Dict[str, str]]] = None
    ) -> NemotronInvestigateResponse:
        """
        Submits real GitHub issue and repository file context to Nemotron 3.5.
        Analyzes root cause, affected components, and minimal repair strategy.
        Validates output strictly with Pydantic.
        """
        client = self.get_client()
        tests = tests or []

        # Build repository context from real files (cap individual file size to keep latency low: 6,000 chars)
        files_context = "\n\n".join([
            f"--- FILE: {f.get('path')} ---\n{f.get('content', '')[:6000]}"
            for f in files
        ])
        tests_context = "\n\n".join([
            f"--- TEST: {t.get('path')} ---\n{t.get('content', '')[:6000]}"
            for t in tests
        ])

        # Compact comments: latest 5 comments, capped to 2,000 total characters
        raw_comments = issue.get('comments', [])
        recent_comments = raw_comments[-5:] if len(raw_comments) > 5 else raw_comments
        compact_comments = []
        total_comment_len = 0
        for c in recent_comments:
            body = c if isinstance(c, str) else (c.get("body", "") if isinstance(c, dict) else str(c))
            if total_comment_len + len(body) > 2000:
                rem = max(0, 2000 - total_comment_len)
                compact_comments.append(body[:rem] + "... [truncated]")
                break
            compact_comments.append(body)
            total_comment_len += len(body)

        system_prompt = (
            "You are DevRescue AI, an autonomous software debugging engineer.\n\n"
            "Analyze ONLY the supplied repository and issue context.\n"
            "Do not invent files, functions, classes, stack traces, or evidence.\n"
            "Identify the most likely root cause.\n"
            "Every important conclusion must reference supplied code.\n"
            "Be concise. Keep explanations, proposed fix, and test strategy direct and compact.\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "- Start your response IMMEDIATELY with the opening curly brace '{'.\n"
            "- DO NOT output any reasoning, thinking process, preamble, or markdown code fences.\n"
            "- Output valid JSON ONLY matching this exact schema:\n"
            "{\n"
            '  "root_cause": "string",\n'
            '  "confidence": 0.95,\n'
            '  "affected_files": ["path/to/file"],\n'
            '  "affected_functions": ["function_name"],\n'
            '  "evidence": [\n'
            '    {\n'
            '      "file": "path/to/file",\n'
            '      "line": 10,\n'
            '      "reason": "explanation of code defect"\n'
            '    }\n'
            '  ],\n'
            '  "proposed_fix": "minimal repair strategy",\n'
            '  "test_strategy": "verification and regression test strategy"\n'
            "}"
        )

        repo_name = repository.get('name') or repository.get('repo') or ''
        user_content = (
            f"REPOSITORY: {repository.get('owner', '')}/{repo_name} (default_branch: {repository.get('default_branch', 'main')})\n"
            f"ISSUE #{issue.get('number', 0)}: {issue.get('title', '')}\n"
            f"ISSUE DESCRIPTION:\n{issue.get('body', '')}\n"
            f"COMMENTS:\n{json.dumps(compact_comments)}\n\n"
            f"AVAILABLE SOURCE FILES:\n{files_context or 'No source files provided'}\n\n"
            f"AVAILABLE TEST FILES:\n{tests_context or 'No test files provided'}\n\n"
            "CRITICAL: Output ONLY valid JSON starting directly with { :"
        )

        nem_logger = logging.getLogger("devrescue.nemotron")
        nem_logger.info(f"[NEMOTRON] Investigation started for issue #{issue.get('number')} on {repository.get('owner')}/{repo_name}")

        max_retries = max(0, settings.NEMOTRON_MAX_RETRIES)
        raw_content = ""

        for attempt in range(max_retries + 1):
            try:
                raw_content = await asyncio.wait_for(
                    self._call_model_stream_or_complete(
                        client=client,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content}
                        ],
                        temperature=0.1,
                        max_tokens=4096,
                        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
                        timeout=settings.NEMOTRON_TIMEOUT
                    ),
                    timeout=settings.NEMOTRON_TIMEOUT + 5.0
                )
                break
            except (asyncio.TimeoutError, APITimeoutError) as te:
                if attempt < max_retries:
                    backoff = min(8.0, 1.0 * (2 ** attempt))
                    nem_logger.warning(
                        f"[NEMOTRON] Request timed out on attempt {attempt + 1}/{max_retries + 1}. Retrying in {backoff:.1f}s..."
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise NemotronTimeoutError(
                    f"NVIDIA Nemotron API request timed out after {int(settings.NEMOTRON_TIMEOUT)}s ({max_retries + 1} attempts exhausted)."
                ) from te
            except APIError as ae:
                err_msg = str(ae).lower()
                status_code = getattr(ae, "status_code", None)

                # 401 / 403 Auth error -> DO NOT retry
                if status_code in (401, 403) or any(term in err_msg for term in ["unauthorized", "authentication", "forbidden"]):
                    raise NemotronAuthError(f"NVIDIA Nemotron authentication error: {_sanitize_error(ae)}") from ae

                # 400 Bad Request -> DO NOT retry
                if status_code == 400 or "bad request" in err_msg:
                    raise NemotronAPIError(f"NVIDIA Nemotron bad request: {_sanitize_error(ae)}") from ae

                # 429 Rate Limit
                if status_code == 429 or "rate limit" in err_msg:
                    if attempt < max_retries:
                        retry_after = 2.0
                        if hasattr(ae, "response") and ae.response and hasattr(ae.response, "headers"):
                            hdr = ae.response.headers.get("Retry-After")
                            if hdr:
                                try:
                                    retry_after = float(hdr)
                                except ValueError:
                                    pass
                        backoff = max(retry_after, 1.5 * (2 ** attempt))
                        nem_logger.warning(
                            f"[NEMOTRON] Rate limited (429) on attempt {attempt + 1}. Waiting {backoff:.1f}s before retry..."
                        )
                        await asyncio.sleep(backoff)
                        continue
                    raise NemotronRateLimitError(
                        f"NVIDIA Nemotron rate limit exceeded ({max_retries + 1} attempts exhausted): {_sanitize_error(ae)}"
                    ) from ae

                # 5xx or transient errors -> retry
                if attempt < max_retries:
                    backoff = min(8.0, 1.0 * (2 ** attempt))
                    nem_logger.warning(
                        f"[NEMOTRON] API error on attempt {attempt + 1}. Retrying in {backoff:.1f}s: {_sanitize_error(ae)}"
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise NemotronAPIError(
                    f"NVIDIA Nemotron API error ({max_retries + 1} attempts exhausted): {_sanitize_error(ae)}"
                ) from ae

            except APIConnectionError as ce:
                if attempt < max_retries:
                    backoff = min(8.0, 1.0 * (2 ** attempt))
                    nem_logger.warning(
                        f"[NEMOTRON] Connection error on attempt {attempt + 1}. Retrying in {backoff:.1f}s: {_sanitize_error(ce)}"
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise NemotronAPIError(
                    f"Failed to connect to NVIDIA Nemotron API endpoint: {_sanitize_error(ce)}"
                ) from ce

            except Exception as e:
                err_msg = str(e).lower()
                if is_timeout_error(e):
                    if attempt < max_retries:
                        backoff = min(8.0, 1.0 * (2 ** attempt))
                        nem_logger.warning(
                            f"[NEMOTRON] Timeout error on attempt {attempt + 1}. Retrying in {backoff:.1f}s: {_sanitize_error(e)}"
                        )
                        await asyncio.sleep(backoff)
                        continue
                    raise NemotronTimeoutError(
                        f"NVIDIA Nemotron API request timed out after {int(settings.NEMOTRON_TIMEOUT)}s ({max_retries + 1} attempts exhausted)."
                    ) from e
                if any(term in err_msg for term in ["401", "403", "unauthorized", "authentication", "forbidden"]):
                    raise NemotronAuthError(f"NVIDIA Nemotron authentication error: {_sanitize_error(e)}") from e
                if "429" in err_msg or "rate limit" in err_msg:
                    if attempt < max_retries:
                        await asyncio.sleep(2.0)
                        continue
                    raise NemotronRateLimitError(f"NVIDIA Nemotron rate limit exceeded: {_sanitize_error(e)}") from e
                raise NemotronAPIError(f"NVIDIA Nemotron call failed: {_sanitize_error(e)}") from e

        if not raw_content or not raw_content.strip():
            raise NemotronResponseError("Nemotron returned an empty response.")

        logger.info(f"[INVESTIGATE] Raw Nemotron response:\n{raw_content}")
        print(f"[INVESTIGATE] Raw Nemotron response:\n{raw_content}", flush=True)

        # Parse Nemotron response with bounded retry (up to 2 attempts) for malformed JSON
        JSON_MAX_RETRIES = 2
        result = None
        current_content = raw_content

        for json_attempt in range(JSON_MAX_RETRIES + 1):
            try:
                parsed = _extract_json_payload(current_content)
                result = NemotronInvestigateResponse(**parsed)
                break
            except Exception as pe:
                if json_attempt < JSON_MAX_RETRIES:
                    nem_logger.warning(
                        f"[NEMOTRON] Malformed JSON on attempt {json_attempt + 1}/{JSON_MAX_RETRIES + 1}: {_sanitize_error(pe)}. Retrying with JSON correction prompt..."
                    )
                    correction_messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                        {"role": "assistant", "content": current_content[:2500]},
                        {
                            "role": "user",
                            "content": (
                                "CRITICAL JSON ERROR: Your previous response could not be parsed as valid JSON: "
                                f"{_sanitize_error(pe)}. "
                                "Return ONLY a valid, properly escaped JSON object starting directly with '{' and ending with '}'. "
                                "Ensure all newlines inside string values are escaped as \\n, all quotes are properly closed, and do NOT include any markdown code blocks or thinking tags."
                            )
                        }
                    ]
                    try:
                        current_content = await asyncio.wait_for(
                            self._call_model_stream_or_complete(
                                client=client,
                                messages=correction_messages,
                                temperature=0.1,
                                max_tokens=4096,
                                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
                                timeout=settings.NEMOTRON_TIMEOUT
                            ),
                            timeout=settings.NEMOTRON_TIMEOUT + 5.0
                        )
                        continue
                    except Exception as retry_err:
                        nem_logger.warning(f"[NEMOTRON] JSON correction call error: {retry_err}")

                raise NemotronResponseError(f"Nemotron returned invalid JSON structure: {_sanitize_error(pe)}") from pe

        # 1. Validate root_cause is not empty
        if not result.root_cause or not result.root_cause.strip():
            raise NemotronResponseError("Nemotron investigation validation failed: 'root_cause' cannot be empty.")

        # 2. Validate proposed_fix is not empty
        if not result.proposed_fix or not result.proposed_fix.strip():
            raise NemotronResponseError("Nemotron investigation validation failed: 'proposed_fix' cannot be empty.")

        # 3. Enforce that affected_files and evidence only reference supplied files
        available_paths = {f.get('path') for f in files} | {t.get('path') for t in tests}
        available_basenames = {os.path.basename(p) for p in available_paths}
        if available_paths:
            for af in result.affected_files:
                clean_af = af.lstrip("./")
                if clean_af not in available_paths and os.path.basename(clean_af) not in available_basenames:
                    raise NemotronResponseError(
                        f"Nemotron referenced non-existent file in affected_files: '{af}'. "
                        f"Available files: {sorted(list(available_paths))}"
                    )

            for ev in result.evidence:
                clean_ev = ev.file.lstrip("./")
                if clean_ev not in available_paths and os.path.basename(clean_ev) not in available_basenames:
                    raise NemotronResponseError(
                        f"Nemotron referenced non-existent file in evidence: '{ev.file}'. "
                        f"Available files: {sorted(list(available_paths))}"
                    )

        nem_logger.info(f"[NEMOTRON] Investigation completed for issue #{issue.get('number')}")
        return result

    async def generate_patch(
        self,
        issue: Dict[str, Any],
        investigation: Dict[str, Any],
        files: List[Dict[str, str]],
        tests: Optional[List[Dict[str, str]]] = None
    ) -> NemotronPatchResponse:
        """
        Synthesizes a minimal unified diff patch for the identified bug.
        The patch must strictly reference and modify only files present in the repository context.
        """
        client = self.get_client()
        tests = tests or []
        available_paths = {f.get('path') for f in files} | {t.get('path') for t in tests}

        files_context = "\n\n".join([
            f"--- FILE: {f.get('path')} ---\n{f.get('content', '')}"
            for f in files
        ])
        tests_context = "\n\n".join([
            f"--- TEST: {t.get('path')} ---\n{t.get('content', '')}"
            for t in tests
        ])

        system_prompt = (
            "You are DevRescue AI, an autonomous software debugging and code repair engineer.\n\n"
            "Your task is to generate a MINIMAL unified diff patch that fixes the bug.\n"
            "Rules:\n"
            "1. Modify ONLY existing files supplied in the context.\n"
            "2. Do NOT invent new files or modify unrelated files.\n"
            "3. The diff must be standard unified diff format (starting with '--- a/path' and '+++ b/path').\n"
            "4. Paths MUST be repository-relative and MUST exactly match a supplied path. NEVER prefix paths with the repository owner or name, and never add extra leading directories.\n"
            "5. Return strict JSON matching:\n"
            "{\n"
            '  "patch": "--- a/path/to/file.py\\n+++ b/path/to/file.py\\n@@ ... @@\\n...",\n'
            '  "changed_files": ["path/to/file.py"],\n'
            '  "explanation": "concise explanation of the minimal fix",\n'
            '  "test_plan": "how this patch will be validated in container tests"\n'
            "}"
        )

        user_content = (
            f"ISSUE #{issue.get('number', 0)}: {issue.get('title', '')}\n"
            f"ROOT CAUSE:\n{investigation.get('root_cause', '')}\n"
            f"PROPOSED FIX STRATEGY:\n{investigation.get('proposed_fix', '')}\n"
            f"AFFECTED FILES:\n{json.dumps(investigation.get('affected_files', []))}\n\n"
            f"SUPPLIED SOURCE FILES:\n{files_context}\n\n"
            f"SUPPLIED TEST FILES:\n{tests_context}"
        )

        raw_content = await self._call_model_stream_or_complete(
            client=client,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.1,
            max_tokens=4096,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            timeout=settings.NEMOTRON_TIMEOUT
        )

        if not raw_content or not raw_content.strip():
            raise NemotronResponseError("Nemotron returned an empty patch response.")

        JSON_MAX_RETRIES = 2
        result = None
        current_content = raw_content

        for json_attempt in range(JSON_MAX_RETRIES + 1):
            try:
                parsed = _extract_json_payload(current_content)
                result = NemotronPatchResponse(**parsed)
                break
            except Exception as pe:
                if json_attempt < JSON_MAX_RETRIES:
                    nem_logger = logging.getLogger("devrescue.nemotron")
                    nem_logger.warning(
                        f"[NEMOTRON] Malformed patch JSON on attempt {json_attempt + 1}/{JSON_MAX_RETRIES + 1}: {_sanitize_error(pe)}. Retrying with patch correction prompt..."
                    )
                    correction_messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                        {"role": "assistant", "content": current_content[:2500]},
                        {
                            "role": "user",
                            "content": (
                                "CRITICAL JSON ERROR: Your previous response could not be parsed as valid patch JSON: "
                                f"{_sanitize_error(pe)}. "
                                "Return ONLY a valid, properly escaped JSON object starting directly with '{' and ending with '}'. "
                                "Ensure the unified diff inside 'patch' has newlines escaped as \\n, all quotes are properly closed, and do NOT include any markdown code blocks or thinking tags."
                            )
                        }
                    ]
                    try:
                        current_content = await self._call_model_stream_or_complete(
                            client=client,
                            messages=correction_messages,
                            temperature=0.1,
                            max_tokens=4096,
                            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
                            timeout=settings.NEMOTRON_TIMEOUT
                        )
                        continue
                    except Exception as retry_err:
                        nem_logger.warning(f"[NEMOTRON] Patch correction call error: {retry_err}")

                raise NemotronResponseError(f"Nemotron returned invalid patch JSON structure: {_sanitize_error(pe)}") from pe

        if not result.patch or not result.patch.strip():
            raise NemotronResponseError("Generated patch is empty.")

        if "--- " not in result.patch or "+++ " not in result.patch:
            raise NemotronResponseError("Generated patch does not contain valid unified diff headers (--- / +++).")

        if not result.changed_files:
            raise NemotronResponseError("Generated patch must list at least one changed file.")

        # Security check: the patch and changed_files must reference only available files
        for changed_file in result.changed_files:
            if changed_file not in available_paths:
                raise NemotronResponseError(
                    f"Generated patch references file not present in repository context: '{changed_file}'. "
                    f"Available files: {sorted(list(available_paths))}"
                )

        return result

    async def investigate_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        branch: str = "main",
        access_token: Optional[str] = None
    ) -> NemotronInvestigateResponse:
        """
        Orchestrates full issue investigation:
        1. Queries GitHub issue details.
        2. Retrieves repository tree and analyzes candidate files.
        3. Calls investigate_bug with repository context.
        """
        from app.services.repository_analyzer import repository_analyzer
        from app.services.github_service import github_service

        repo_info = await github_service.get_repository(access_token, owner, repo)
        target_branch = branch or repo_info.get("default_branch") or "main"

        issue = await repository_analyzer.get_issue_details(
            owner=owner,
            repo=repo,
            issue_number=issue_number,
            access_token=access_token
        )

        tree_res = await github_service.get_repository_tree(access_token, owner, repo, target_branch)

        analysis = await repository_analyzer.analyze_repository_for_issue(
            owner=owner,
            repo=repo,
            issue_number=issue_number,
            branch=target_branch,
            access_token=access_token,
            repo_info=repo_info,
            issue=issue,
            tree_res=tree_res
        )

        if not analysis.get("files") and not analysis.get("tests"):
            raise ValueError(f"Repository '{owner}/{repo}' contains no source or test files to analyze.")

        return await self.investigate_bug(
            issue=analysis["issue"],
            repository=analysis["repository"],
            files=analysis["files"],
            tests=analysis.get("tests", [])
        )


nemotron_service = NemotronService()
