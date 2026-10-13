import re
import difflib
import hashlib
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Any
from app.services.github_service import validate_safe_repo_path

# Safety limits (configurable via environment variables)
import os
MAX_FILES_CHANGED = int(os.environ.get("DEVRESCUE_MAX_FILES_CHANGED", 25))
MAX_LINES_ADDED = int(os.environ.get("DEVRESCUE_MAX_LINES_ADDED", 2500))
MAX_LINES_REMOVED = int(os.environ.get("DEVRESCUE_MAX_LINES_REMOVED", 1000))
MAX_PATCH_SIZE_BYTES = int(os.environ.get("DEVRESCUE_MAX_PATCH_SIZE_BYTES", 100 * 1024))  # 100 KB
MAX_SINGLE_FILE_MODIFICATION_BYTES = int(os.environ.get("DEVRESCUE_MAX_SINGLE_FILE_BYTES", 50 * 1024))  # 50 KB


# Standalone explicit end marker pattern (e.g., '*** End of diff ***', '=== End of patch ===')
# Only matched when occurring outside actual diff content.
EXPLICIT_END_MARKER_REGEX = re.compile(
    r'^\s*(?:[*=-]{3,}|<!--)\s*(?:end\s+of\s+(?:unified\s+)?(?:diff|patch|file)|end\s+(?:diff|patch))\s*(?:[*=-]{3,}|-->)?\s*$',
    re.IGNORECASE
)


def is_explicit_end_marker(line: str) -> bool:
    """Returns True if the line is a standalone explicit diff end marker."""
    if not line:
        return False
    return bool(EXPLICIT_END_MARKER_REGEX.match(line.strip()))


class DiffValidationError(ValueError):
    """Base exception for diff validation errors."""
    def __init__(self, message: str, status_code: int = 400, file: Optional[str] = None, hunk: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.file = file
        self.hunk = hunk


class DiffSyntaxError(DiffValidationError):
    """Raised when unified diff syntax is malformed or invalid."""
    def __init__(self, message: str, status_code: int = 400, file: Optional[str] = None, hunk: Optional[int] = None):
        super().__init__(message, status_code=status_code, file=file, hunk=hunk)


class DiffPathError(DiffValidationError):
    """Raised when diff contains unsafe or invalid file paths."""
    pass


class DiffScopeError(DiffValidationError):
    """Raised when diff modifies files outside the investigated scope."""
    pass


class DiffLimitExceededError(DiffValidationError):
    """Raised when diff exceeds configured size, lines, or file limits."""
    pass


class DiffApplicationError(DiffValidationError):
    """Raised when diff cannot be cleanly applied to target file contents."""
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        file: Optional[str] = None,
        hunk: Optional[int] = None,
        retry_available: bool = True,
        attempts: int = 1,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, status_code=status_code)
        self.file = file
        self.hunk = hunk
        self.retry_available = retry_available
        self.attempts = attempts
        self.details = details or {}


class DiffValidationResult:
    def __init__(
        self,
        is_valid: bool,
        files_changed: List[str],
        lines_added: int,
        lines_removed: int,
        clean_diff: str,
        applied_contents: Dict[str, str],
        source_hashes: Optional[Dict[str, str]] = None,
        error: Optional[str] = None
    ):
        self.is_valid = is_valid
        self.files_changed = files_changed
        self.lines_added = lines_added
        self.lines_removed = lines_removed
        self.clean_diff = clean_diff
        self.applied_contents = applied_contents
        self.source_hashes = source_hashes or {}
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "files_changed": self.files_changed,
            "lines_added": self.lines_added,
            "lines_removed": self.lines_removed,
            "clean_diff": self.clean_diff,
            "source_hashes": self.source_hashes,
            "error": self.error
        }


def normalize_diff_path(raw_path: str) -> str:
    """
    Strips git unified diff path prefixes ('a/', 'b/') and normalizes path.
    Enforces repository-relative path safety.
    """
    if not raw_path or not raw_path.strip():
        raise DiffPathError("Encountered empty file path in diff header.")

    cleaned = raw_path.strip().strip('"').strip("'")
    
    # Remove git prefix a/ or b/ if present
    if cleaned.startswith("a/") or cleaned.startswith("b/"):
        cleaned = cleaned[2:]

    # Remove /dev/null if creating or deleting
    if cleaned == "/dev/null":
        return "/dev/null"

    # Enforce safe repository path (rejects absolute paths, drive letters, .. traversal)
    try:
        validated = validate_safe_repo_path(cleaned)
    except ValueError as ve:
        raise DiffPathError(f"Unsafe repository path '{raw_path}': {str(ve)}")

    return validated


@dataclass
class ParsedHunk:
    hunk_idx: int
    header: str
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    old_lines: List[str]
    new_lines: List[str]
    removed_lines: List[str]
    added_lines: List[str]


class ApplyHunksResult(tuple):
    """
    Result of _apply_hunks.
    Unpacks as 4-tuple (success, new_content, error, failed_hunk) for backwards compatibility.
    Provides explicit attributes: success, new_content, error, failed_hunk, details.
    """
    success: bool
    new_content: str
    error: Optional[str]
    failed_hunk: Optional[int]
    details: Dict[str, Any]

    def __new__(
        cls,
        success: bool,
        new_content: str,
        error: Optional[str] = None,
        failed_hunk: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        instance = super().__new__(cls, (success, new_content, error, failed_hunk))
        instance.success = success
        instance.new_content = new_content
        instance.error = error
        instance.failed_hunk = failed_hunk
        instance.details = details or {}
        return instance


class DiffValidator:
    """
    Strict Unified Diff Validator & Safety Inspector.
    Guarantees that model-generated patches are safe, minimal, within limits,
    and cleanly applicable to real repository code.
    """

    def validate_syntax_and_limits(self, patch: str) -> Tuple[List[str], int, int]:
        """
        Validates unified diff syntax and safety limits without applying to files.
        Returns: (files_changed: List[str], lines_added: int, lines_removed: int)
        """
        if not patch or not patch.strip():
            raise DiffValidationError("Unified diff patch cannot be empty.")

        patch_bytes = len(patch.encode("utf-8"))
        if patch_bytes > MAX_PATCH_SIZE_BYTES:
            raise DiffLimitExceededError(
                f"Patch size ({patch_bytes} bytes) exceeds maximum allowable limit of {MAX_PATCH_SIZE_BYTES} bytes."
            )

        # Check binary file modification
        if "\x00" in patch or "Binary files" in patch or "GIT binary patch" in patch:
            raise DiffValidationError("Binary file modifications are strictly prohibited.")

        lines = patch.splitlines()

        # Check for unified diff headers
        has_minus_header = any(l.startswith("--- ") for l in lines)
        has_plus_header = any(l.startswith("+++ ") for l in lines)
        has_hunk_header = any(l.startswith("@@") for l in lines)

        if not (has_minus_header and has_plus_header and has_hunk_header):
            raise DiffSyntaxError(
                "Invalid unified diff: Must contain valid headers ('--- a/path', '+++ b/path') and hunk headers ('@@ ... @@')."
            )

        files_changed: List[str] = []
        lines_added = 0
        lines_removed = 0
        current_file_bytes = 0

        current_file = None
        for line in lines:
            if line.startswith("+++ "):
                raw_path = line[4:].strip()
                # Split off timestamp or tab if present
                raw_path = re.split(r'[\t\r]', raw_path)[0].strip()
                normalized = normalize_diff_path(raw_path)
                if normalized != "/dev/null":
                    if normalized not in files_changed:
                        files_changed.append(normalized)
                    current_file = normalized
                    current_file_bytes = 0
                continue

            if current_file:
                current_file_bytes += len(line.encode("utf-8")) + 1
                if current_file_bytes > MAX_SINGLE_FILE_MODIFICATION_BYTES:
                    raise DiffLimitExceededError(
                        f"Modification size for file '{current_file}' exceeds limit of {MAX_SINGLE_FILE_MODIFICATION_BYTES} bytes."
                    )

            if line.startswith("+") and not line.startswith("+++"):
                lines_added += 1
            elif line.startswith("-") and not line.startswith("---"):
                lines_removed += 1

        if not files_changed:
            raise DiffSyntaxError("Diff does not specify any valid target files.")

        if len(files_changed) > MAX_FILES_CHANGED:
            raise DiffLimitExceededError(
                f"Patch modifies {len(files_changed)} files, which exceeds maximum limit of {MAX_FILES_CHANGED}."
            )

        if lines_added > MAX_LINES_ADDED:
            raise DiffLimitExceededError(
                f"Patch adds {lines_added} lines, which exceeds maximum limit of {MAX_LINES_ADDED}."
            )

        if lines_removed > MAX_LINES_REMOVED:
            raise DiffLimitExceededError(
                f"Patch removes {lines_removed} lines, which exceeds maximum limit of {MAX_LINES_REMOVED}."
            )

        return files_changed, lines_added, lines_removed

    def split_per_file_diffs(self, patch: str) -> Dict[str, str]:
        """
        Splits a multi-file unified diff into individual per-file diff blocks.
        Preserves git headers ('diff --git') and cleanly ignores explicit end markers between files.
        """
        per_file = {}
        lines = patch.splitlines(keepends=True)
        current_file = None
        current_lines = []

        def commit_current_file():
            nonlocal current_file, current_lines
            if current_file and current_lines:
                while current_lines and not current_lines[-1].strip():
                    current_lines.pop()
                if current_lines:
                    per_file[current_file] = "".join(current_lines)
            current_lines = []
            current_file = None

        i = 0
        while i < len(lines):
            line = lines[i]

            # Detect git diff header (e.g., 'diff --git a/path b/path')
            if line.startswith("diff --git "):
                commit_current_file()
                current_lines.append(line)
                i += 1
                continue

            # Detect unified diff header ('--- ' followed by '+++ ')
            if line.startswith("--- "):
                if i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
                    commit_current_file()

                    plus_line = lines[i + 1]
                    raw_target = plus_line[4:].strip()
                    raw_target = re.split(r'[\t\r\n]', raw_target)[0].strip()
                    current_file = normalize_diff_path(raw_target)
                    current_lines.extend([line, plus_line])
                    i += 2
                    continue

            # If explicit end marker outside actual diff content / between files, omit it
            if is_explicit_end_marker(line.strip()):
                rem = [l.strip() for l in lines[i + 1:] if l.strip()]
                if not rem or any(rem[0].startswith(p) for p in ("diff --git ", "--- ")):
                    commit_current_file()
                    i += 1
                    continue

            if current_file:
                current_lines.append(line)
            i += 1

        commit_current_file()

        return per_file

    def parse_hunks(self, file_diff: str, file_path: str = "file") -> List[ParsedHunk]:
        """
        Parses @@ hunk blocks from a single file diff into structured ParsedHunk objects.
        Validates hunk headers and checks for truncation.
        Tolerates standalone explicit end markers outside actual diff content.
        Strictly rejects arbitrary lines without a diff prefix.
        """
        lines = file_diff.splitlines()
        hunks: List[ParsedHunk] = []

        current_idx = 0
        current_header = ""
        current_old_start = 1
        current_old_count = 1
        current_new_start = 1
        current_new_count = 1
        current_old_lines: List[str] = []
        current_new_lines: List[str] = []
        current_removed_lines: List[str] = []
        current_added_lines: List[str] = []
        in_hunk = False

        def commit_hunk():
            nonlocal in_hunk, current_old_lines, current_new_lines, current_removed_lines, current_added_lines
            if in_hunk:
                if current_old_count > 0 and not current_old_lines and not current_added_lines:
                    raise DiffSyntaxError(
                        f"Hunk #{current_idx} in '{file_path}' has header '{current_header}' but contains no hunk lines (truncated diff).",
                        file=file_path,
                        hunk=current_idx
                    )
                hunks.append(ParsedHunk(
                    hunk_idx=current_idx,
                    header=current_header,
                    old_start=current_old_start,
                    old_count=len(current_old_lines),
                    new_start=current_new_start,
                    new_count=len(current_new_lines),
                    old_lines=list(current_old_lines),
                    new_lines=list(current_new_lines),
                    removed_lines=list(current_removed_lines),
                    added_lines=list(current_added_lines)
                ))
                current_old_lines = []
                current_new_lines = []
                current_removed_lines = []
                current_added_lines = []
                in_hunk = False

        for line_idx, line in enumerate(lines):
            if line.startswith("@@"):
                commit_hunk()
                current_idx += 1
                current_header = line
                header_match = re.match(r'^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@', line)
                if not header_match:
                    raise DiffSyntaxError(f"Malformed hunk header in '{file_path}': '{line}'", file=file_path, hunk=current_idx)
                current_old_start = int(header_match.group(1))
                current_old_count = int(header_match.group(2)) if header_match.group(2) is not None else 1
                current_new_start = int(header_match.group(3))
                current_new_count = int(header_match.group(4)) if header_match.group(4) is not None else 1
                in_hunk = True
                continue

            if not in_hunk:
                if is_explicit_end_marker(line):
                    continue
                continue

            if line.startswith("---") or line.startswith("+++"):
                continue

            if line.startswith("\\"):
                continue

            # Standalone explicit end marker encountered while in hunk
            if is_explicit_end_marker(line):
                # Verify whether this end marker occurs outside remaining diff content
                remaining = [l.strip() for l in lines[line_idx + 1:] if l.strip()]
                has_subsequent_diff_lines = any(
                    l.startswith("@@") or l.startswith("-") or l.startswith("+") or l.startswith(" ") or l.startswith("\\")
                    for l in remaining
                )
                if not has_subsequent_diff_lines:
                    # Marker occurs outside/after actual diff content; commit hunk cleanly
                    commit_hunk()
                    in_hunk = False
                    continue

                # If there are subsequent diff lines, marker was placed inside diff content: reject
                raise DiffSyntaxError(
                    f"Malformed hunk line in '{file_path}' (hunk #{current_idx}): '{line[:80]}' is missing diff prefix (' ', '-', '+').",
                    file=file_path,
                    hunk=current_idx
                )

            if line.startswith("-"):
                rem = line[1:]
                current_old_lines.append(rem)
                current_removed_lines.append(rem)
            elif line.startswith("+"):
                add = line[1:]
                current_new_lines.append(add)
                current_added_lines.append(add)
            elif line.startswith(" "):
                ctx = line[1:]
                current_old_lines.append(ctx)
                current_new_lines.append(ctx)
            elif line == "":
                if in_hunk:
                    if len(current_old_lines) < current_old_count or len(current_new_lines) < current_new_count:
                        current_old_lines.append("")
                        current_new_lines.append("")
                    else:
                        commit_hunk()
                        in_hunk = False
            else:
                # Malformed diff line without unified diff prefix (' ', '-', '+')
                raise DiffSyntaxError(
                    f"Malformed hunk line in '{file_path}' (hunk #{current_idx}): '{line[:80]}' is missing diff prefix (' ', '-', '+').",
                    file=file_path,
                    hunk=current_idx
                )

        commit_hunk()
        return hunks

    def _apply_hunks(
        self,
        original_content: str,
        file_diff: str,
        file_path: str = "file"
    ) -> ApplyHunksResult:
        """
        Strict hunk-by-hunk verification and application with line-offset tracking,
        trailing-whitespace tolerance, window search, and full-file match.
        Returns: ApplyHunksResult(success, new_content, error_reason, failing_hunk_idx, details)
        """
        is_crlf = "\r\n" in original_content
        newline = "\r\n" if is_crlf else "\n"
        ends_with_newline = original_content.endswith("\n") or original_content.endswith("\r\n")

        # Let DiffSyntaxError propagate for malformed/truncated diffs
        hunks = self.parse_hunks(file_diff, file_path=file_path)

        if not hunks:
            return ApplyHunksResult(False, "", "Diff contained no valid @@ hunks.", None)

        # Special case: creating a new file from scratch
        if "--- /dev/null" in file_diff or original_content == "":
            all_new = []
            for h in hunks:
                all_new.extend(h.new_lines)
            res = newline.join(all_new)
            if ends_with_newline or all_new:
                res += newline
            return ApplyHunksResult(True, res, None, None)

        lines = original_content.splitlines()
        cumulative_offset = 0

        for hunk in hunks:
            old_len = len(hunk.old_lines)
            expected_idx = (hunk.old_start - 1) + cumulative_offset
            expected_idx = max(0, min(expected_idx, len(lines)))

            if old_len == 0:
                lines[expected_idx:expected_idx] = hunk.new_lines
                cumulative_offset += len(hunk.new_lines)
                continue

            match_idx = None

            def exact_match(pos: int) -> bool:
                if pos < 0 or pos + old_len > len(lines):
                    return False
                return lines[pos : pos + old_len] == hunk.old_lines

            def rstrip_match(pos: int) -> bool:
                if pos < 0 or pos + old_len > len(lines):
                    return False
                return [l.rstrip() for l in lines[pos : pos + old_len]] == [l.rstrip() for l in hunk.old_lines]

            def norm_match(pos: int) -> bool:
                if pos < 0 or pos + old_len > len(lines):
                    return False
                def norm_line(s: str) -> str:
                    return re.sub(r'\s+', ' ', s).strip()
                return [norm_line(l) for l in lines[pos : pos + old_len]] == [norm_line(l) for l in hunk.old_lines]

            # 1. Exact match at expected_idx
            if exact_match(expected_idx):
                match_idx = expected_idx

            # 2. Exact match across file (unambiguous only)
            if match_idx is None:
                all_exact = [p for p in range(len(lines) - old_len + 1) if exact_match(p)]
                if len(all_exact) == 1:
                    match_idx = all_exact[0]
                elif len(all_exact) > 1:
                    closest = min(all_exact, key=lambda p: abs(p - expected_idx))
                    second_closest = sorted(all_exact, key=lambda p: abs(p - expected_idx))[1]
                    if abs(second_closest - expected_idx) - abs(closest - expected_idx) >= 10:
                        match_idx = closest
                    else:
                        details = {
                            "hunk_idx": hunk.hunk_idx,
                            "header": hunk.header,
                            "old_start": hunk.old_start,
                            "expected_lines": hunk.old_lines,
                            "ambiguous": True
                        }
                        return ApplyHunksResult(
                            False, "",
                            f"Hunk #{hunk.hunk_idx} failed: Ambiguous match in '{file_path}' ({len(all_exact)} identical occurrences found in file).",
                            hunk.hunk_idx,
                            details=details
                        )

            # 3. Trailing-whitespace match at expected_idx
            if match_idx is None and rstrip_match(expected_idx):
                match_idx = expected_idx

            # 4. Trailing-whitespace match across file (unambiguous only)
            if match_idx is None:
                all_rstrip = [p for p in range(len(lines) - old_len + 1) if rstrip_match(p)]
                if len(all_rstrip) == 1:
                    match_idx = all_rstrip[0]
                elif len(all_rstrip) > 1:
                    closest = min(all_rstrip, key=lambda p: abs(p - expected_idx))
                    second_closest = sorted(all_rstrip, key=lambda p: abs(p - expected_idx))[1]
                    if abs(second_closest - expected_idx) - abs(closest - expected_idx) >= 10:
                        match_idx = closest
                    else:
                        details = {
                            "hunk_idx": hunk.hunk_idx,
                            "header": hunk.header,
                            "old_start": hunk.old_start,
                            "expected_lines": hunk.old_lines,
                            "ambiguous": True
                        }
                        return ApplyHunksResult(
                            False, "",
                            f"Hunk #{hunk.hunk_idx} failed: Ambiguous match in '{file_path}' ({len(all_rstrip)} matching occurrences found).",
                            hunk.hunk_idx,
                            details=details
                        )

            # 5. Whitespace-tolerant match (strictly multi-line, old_len > 1, no single-line fuzzy matching)
            if match_idx is None and old_len > 1:
                all_norm = [p for p in range(len(lines) - old_len + 1) if norm_match(p)]
                if len(all_norm) == 1:
                    match_idx = all_norm[0]
                elif len(all_norm) > 1:
                    details = {
                        "hunk_idx": hunk.hunk_idx,
                        "header": hunk.header,
                        "old_start": hunk.old_start,
                        "expected_lines": hunk.old_lines,
                        "ambiguous": True
                    }
                    return ApplyHunksResult(
                        False, "",
                        f"Hunk #{hunk.hunk_idx} failed: Ambiguous whitespace-tolerant match in '{file_path}' ({len(all_norm)} matching locations found).",
                        hunk.hunk_idx,
                        details=details
                    )

            if match_idx is None:
                # Find best candidate position for rich diagnostic reporting
                best_pos = expected_idx
                best_score = -1.0
                search_range = range(len(lines) - old_len + 1 if len(lines) >= old_len else 1)
                for p in search_range:
                    cand = lines[p : p + old_len]
                    if not cand:
                        continue
                    matching_count = sum(1 for c, o in zip(cand, hunk.old_lines) if c.strip() == o.strip())
                    score = matching_count / max(1, old_len)
                    dist_penalty = abs(p - expected_idx) * 0.001
                    final_score = score - dist_penalty
                    if final_score > best_score:
                        best_score = final_score
                        best_pos = p

                target_center = best_pos if best_score > 0.2 else expected_idx
                start_snippet = max(0, target_center - 4)
                end_snippet = min(len(lines), target_center + old_len + 4)
                actual_snippet = lines[start_snippet:end_snippet]
                details = {
                    "hunk_idx": hunk.hunk_idx,
                    "header": hunk.header,
                    "old_start": hunk.old_start,
                    "old_count": hunk.old_count,
                    "expected_lines": hunk.old_lines,
                    "actual_snippet": actual_snippet,
                    "actual_snippet_start_line": start_snippet + 1,
                    "nearby_actual_lines": actual_snippet,
                    "nearby_actual_start_line": start_snippet + 1,
                    "best_match_line": target_center + 1
                }
                return ApplyHunksResult(
                    False, "",
                    f"Hunk #{hunk.hunk_idx} failed: Could not locate target lines in file.",
                    hunk.hunk_idx,
                    details=details
                )

            # Apply replacement in memory
            lines[match_idx : match_idx + old_len] = hunk.new_lines
            # Update cumulative offset reflecting actual placement and delta
            cumulative_offset = (match_idx + len(hunk.new_lines)) - (hunk.old_start - 1 + old_len)

        new_content = newline.join(lines)
        if ends_with_newline and not new_content.endswith(newline):
            new_content += newline
        return ApplyHunksResult(True, new_content, None, None)

    def validate_and_apply(
        self,
        patch: str,
        file_contents: Dict[str, str],
        allowed_files: Optional[List[str]] = None,
        expected_source_hashes: Optional[Dict[str, str]] = None
    ) -> DiffValidationResult:
        """
        Performs end-to-end validation:
        1. Checks syntax, limits, paths, and binary constraints.
        2. Enforces allowed scope.
        3. Validates source hashes to prevent stale patch application.
        4. Validates clean application against real file content.
        5. Produces verified canonical unified diff against original.
        """
        files_changed, lines_added, lines_removed = self.validate_syntax_and_limits(patch)

        # Application testing
        per_file_diffs = self.split_per_file_diffs(patch)

        # Scope enforcement
        if allowed_files:
            allowed_normalized = {f.lstrip("./").replace("\\", "/") for f in allowed_files}
            allowed_basenames = {re.split(r'[/]', f)[-1] for f in allowed_normalized}
            for changed in files_changed:
                norm_changed = changed.lstrip("./").replace("\\", "/")
                basename_changed = re.split(r'[/]', norm_changed)[-1]
                file_diff = per_file_diffs.get(changed, "")
                is_new_file = "--- /dev/null" in file_diff or "new file mode" in file_diff
                is_ignore_file = basename_changed in (".gitignore", ".dockerignore")
                if not is_new_file and not is_ignore_file and norm_changed not in allowed_normalized and basename_changed not in allowed_basenames:
                    raise DiffScopeError(
                        f"Patch modifies file '{changed}', which is not within investigated scope: {sorted(list(allowed_normalized))}"
                    )
        applied_contents: Dict[str, str] = {}
        source_hashes: Dict[str, str] = {}

        for file_path, file_diff in per_file_diffs.items():
            if file_path == "/dev/null":
                continue

            # Target file content lookup
            content = None
            if file_path in file_contents:
                content = file_contents[file_path]
            else:
                for k, v in file_contents.items():
                    if k.endswith(file_path) or file_path.endswith(k) or re.split(r'[/]', k)[-1] == re.split(r'[/]', file_path)[-1]:
                        content = v
                        break

            if content is None:
                if "--- /dev/null" in file_diff:
                    content = ""
                else:
                    raise DiffApplicationError(
                        f"Target file '{file_path}' content is not available in repository context.",
                        file=file_path
                    )

            actual_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if expected_source_hashes and file_path in expected_source_hashes:
                expected_hash = expected_source_hashes[file_path]
                if actual_hash != expected_hash:
                    norm_content = content.replace("\r\n", "\n").replace("\r", "\n")
                    norm_actual_hash = hashlib.sha256(norm_content.encode("utf-8")).hexdigest()
                    expected_norm_hash = expected_source_hashes.get(f"{file_path}__norm")
                    if not (expected_norm_hash and norm_actual_hash == expected_norm_hash):
                        raise DiffApplicationError(
                            f"Stale source detected for '{file_path}': content hash diverged (expected {expected_hash[:12]}..., got {actual_hash[:12]}...).",
                            file=file_path,
                            details={"stale_source": True, "expected_hash": expected_hash, "actual_hash": actual_hash}
                        )
            source_hashes[file_path] = actual_hash
            source_hashes[f"{file_path}__norm"] = hashlib.sha256(
                content.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
            ).hexdigest()

            # Test clean application
            res = self._apply_hunks(content, file_diff, file_path=file_path)
            if not res.success:
                raise DiffApplicationError(
                    f"Patch does not apply cleanly to '{file_path}': {res.error or 'Hunk mismatch'}",
                    file=file_path,
                    hunk=res.failed_hunk,
                    retry_available=True,
                    details=res.details
                )

            applied_contents[file_path] = res.new_content

        # Generate verified clean canonical unified diff from original -> applied
        verified_diff_lines = []
        for file_path, new_content in applied_contents.items():
            orig = file_contents.get(file_path, "")
            orig_lines = orig.splitlines(keepends=True)
            new_lines = new_content.splitlines(keepends=True)
            from_header = "/dev/null" if (not orig and "--- /dev/null" in per_file_diffs.get(file_path, "")) else f"a/{file_path}"
            diff = list(difflib.unified_diff(orig_lines, new_lines, fromfile=from_header, tofile=f"b/{file_path}"))
            if diff:
                verified_diff_lines.extend(diff)

        clean_diff = "".join(verified_diff_lines).strip() or patch.strip()

        # Validate canonical diff against safety limits, file count, and path constraints
        self.validate_syntax_and_limits(clean_diff)

        return DiffValidationResult(
            is_valid=True,
            files_changed=files_changed,
            lines_added=lines_added,
            lines_removed=lines_removed,
            clean_diff=clean_diff,
            applied_contents=applied_contents,
            source_hashes=source_hashes
        )


diff_validator = DiffValidator()
