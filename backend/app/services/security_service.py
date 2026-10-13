"""
DevRescue AI — Automated Security Analysis Service.
Performs SAST checks on synthesized unified diff patches to catch hardcoded secrets,
unsafe shell commands, dangerous eval/exec calls, and injection vulnerabilities before review.
"""

import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class SecurityFinding:
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    rule_id: str
    file: str
    line_number: Optional[int]
    description: str
    snippet: str


class SecurityReviewService:
    def __init__(self):
        # 1. Regex patterns for detecting hardcoded secrets (CRITICAL)
        self.secret_patterns = [
            (r'(?i)(?:api[_-]?key|apikey|secret[_-]?key|auth[_-]?token|access[_-]?token)\s*[:=]\s*["\'][A-Za-z0-9_\-\.]{16,}["\']', "HARDCODED_API_KEY", "High entropy API key or access token hardcoded in diff", "CRITICAL"),
            (r'(?i)ghp_[A-Za-z0-9_]{36}', "GITHUB_PERSONAL_ACCESS_TOKEN", "GitHub Personal Access Token detected", "CRITICAL"),
            (r'(?i)nvapi-[A-Za-z0-9_\-]{32,}', "NVIDIA_API_KEY", "NVIDIA API key detected in patch", "CRITICAL"),
            (r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----', "PRIVATE_KEY_MATERIAL", "Cryptographic private key detected in patch", "CRITICAL"),
            (r'(?i)(?:password|passwd|pwd)\s*[:=]\s*["\'][^"\']{4,}["\']', "HARDCODED_PASSWORD", "Hardcoded password or credential assignment", "CRITICAL"),
            (r'(?i)AKIA[0-9A-Z]{16}', "AWS_ACCESS_KEY_ID", "AWS Access Key ID detected in patch", "CRITICAL"),
            (r'(?i)Bearer\s+[A-Za-z0-9_\-\.]{24,}', "HARDCODED_BEARER_TOKEN", "Hardcoded Bearer authentication token in diff", "CRITICAL"),
        ]

        # 2. Regex patterns for unsafe command execution / code execution (HIGH)
        self.code_patterns = [
            (r'(?i)\b(?:os\.system|posix\.system)\s*\(', "UNSAFE_OS_SYSTEM", "Direct invocation of os.system()", "HIGH"),
            (r'(?i)\bsubprocess\.(?:call|check_call|check_output|run|Popen)\s*\(.*?\bshell\s*=\s*(?:True|1)', "SUBPROCESS_SHELL_TRUE", "Subprocess execution with shell=True enabled", "HIGH"),
            (r'(?i)\bpty\.spawn\s*\(', "UNSAFE_PTY_SPAWN", "Interactive shell spawn via pty.spawn()", "HIGH"),
            (r'(?i)\b(?:eval|exec)\s*\(', "UNSAFE_EVAL_EXEC", "Dynamic code evaluation via eval() or exec()", "HIGH"),
        ]

        # 3. Regex patterns for SQL/Command injection risks (HIGH)
        self.injection_patterns = [
            (r'(?i)(?:execute|raw|cursor\.execute)\s*\(\s*f["\'].*?(?:SELECT|INSERT|UPDATE|DELETE).*?\{', "SQLI_FSTRING", "SQL query assembled via unescaped f-string formatting", "HIGH"),
            (r'(?i)(?:SELECT|INSERT|UPDATE|DELETE)\s+.*?%\s*\(', "SQLI_PERCENT_FORMAT", "SQL query assembled via percent string formatting", "HIGH"),
            (r'(?i)(?:execute|cursor\.execute)\s*\(\s*["\'].*?(?:SELECT|INSERT|UPDATE|DELETE).*?["\']\s*\+', "SQLI_CONCATENATION", "SQL query assembled via string concatenation", "HIGH"),
        ]

        # 4. Warnings / Medium severity patterns (MEDIUM)
        self.warning_patterns = [
            (r'(?i)\bos\.popen\s*\(', "UNSAFE_OS_POPEN", "Use of os.popen() is discouraged; use subprocess with argument lists", "MEDIUM"),
            (r'(?i)\b__import__\s*\(', "UNSAFE_DYNAMIC_IMPORT", "Arbitrary dynamic module import via __import__()", "MEDIUM"),
            (r'(?i)\bverify\s*=\s*False\b', "INSECURE_TLS_VERIFY_FALSE", "TLS verification disabled via verify=False", "MEDIUM"),
            (r'(?i)\btempfile\.mktemp\s*\(', "INSECURE_MKTEMP", "tempfile.mktemp() is prone to race conditions; use NamedTemporaryFile", "MEDIUM"),
        ]

        # 5. Low severity / Hygiene checks (LOW)
        self.low_patterns = [
            (r'(?i)\bDEBUG\s*=\s*True\b', "DEBUG_MODE_ENABLED", "Debug flag explicitly enabled in patch code", "LOW"),
            (r'(?i)#\s*(?:TODO|FIXME)\s*.*?(?:secur|auth|vuln|password|token)', "SECURITY_TODO_COMMENT", "Pending security or authorization TODO marker in patch", "LOW"),
        ]

    def scan_patch(self, patch: str) -> Dict[str, Any]:
        """
        Scans added lines in a unified diff patch.
        Returns a structured dictionary with status ('PASSED', 'WARNINGS', 'FAILED', 'NOT_IMPLEMENTED'),
        findings list, breakdown counts, and clear scanner limitations.
        Never fabricates 'no secrets detected' when scanner did not execute.
        """
        if not patch or not patch.strip():
            return {
                "status": "NOT_IMPLEMENTED",
                "clean": False,
                "executed": False,
                "findings": [],
                "findings_count": 0,
                "critical_count": 0,
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0,
                "scanner": "DevRescue SAST Heuristic Engine",
                "scanner_type": "heuristic_ast_pattern",
                "limitations": "Scanner did not execute: No patch content provided. Host does not have native Semgrep binary.",
                "summary": "Security review not executed: No patch content provided.",
                "message": "No patch content provided to security reviewer."
            }

        findings: List[SecurityFinding] = []
        current_file = "unknown"
        line_num = 0
        total_added_lines = 0

        for line in patch.splitlines():
            if line.startswith("+++ b/"):
                current_file = line[6:].strip()
                line_num = 0
                continue
            elif line.startswith("@@"):
                # Approximate line numbering from hunk header
                m = re.search(r'\+(\d+)', line)
                line_num = int(m.group(1)) if m else 0
                continue

            # Only analyze added lines (+)
            if line.startswith("+") and not line.startswith("+++"):
                line_num += 1
                total_added_lines += 1
                added_content = line[1:].strip()

                # Ignore pure comment lines for code patterns (except security TODO check)
                is_comment = added_content.startswith("#") or added_content.startswith("//")

                # 1. Secrets check (CRITICAL)
                for pattern, rule_id, desc, sev in self.secret_patterns:
                    if re.search(pattern, added_content):
                        findings.append(SecurityFinding(
                            severity=sev,
                            rule_id=rule_id,
                            file=current_file,
                            line_number=line_num,
                            description=desc,
                            snippet=added_content[:120]
                        ))

                # 2. Dangerous execution check (HIGH)
                if not is_comment:
                    for pattern, rule_id, desc, sev in self.code_patterns:
                        if re.search(pattern, added_content):
                            findings.append(SecurityFinding(
                                severity=sev,
                                rule_id=rule_id,
                                file=current_file,
                                line_number=line_num,
                                description=desc,
                                snippet=added_content[:120]
                            ))

                # 3. Injection risks (HIGH)
                if not is_comment:
                    for pattern, rule_id, desc, sev in self.injection_patterns:
                        if re.search(pattern, added_content):
                            findings.append(SecurityFinding(
                                severity=sev,
                                rule_id=rule_id,
                                file=current_file,
                                line_number=line_num,
                                description=desc,
                                snippet=added_content[:120]
                            ))

                # 4. Warnings (MEDIUM)
                if not is_comment:
                    for pattern, rule_id, desc, sev in self.warning_patterns:
                        if re.search(pattern, added_content):
                            findings.append(SecurityFinding(
                                severity=sev,
                                rule_id=rule_id,
                                file=current_file,
                                line_number=line_num,
                                description=desc,
                                snippet=added_content[:120]
                            ))

                # 5. Low severity / Hygiene checks (LOW)
                for pattern, rule_id, desc, sev in self.low_patterns:
                    if re.search(pattern, added_content):
                        findings.append(SecurityFinding(
                            severity=sev,
                            rule_id=rule_id,
                            file=current_file,
                            line_number=line_num,
                            description=desc,
                            snippet=added_content[:120]
                        ))

        critical_count = sum(1 for f in findings if f.severity == "CRITICAL")
        high_count = sum(1 for f in findings if f.severity == "HIGH")
        medium_count = sum(1 for f in findings if f.severity == "MEDIUM")
        low_count = sum(1 for f in findings if f.severity == "LOW")

        if critical_count > 0 or high_count > 0:
            status = "FAILED"
            summary = f"Security Review Failed: {len(findings)} potential security finding(s) detected ({critical_count} critical, {high_count} high)."
        elif medium_count > 0 or low_count > 0:
            status = "WARNINGS"
            summary = f"Security Review Passed with Warnings: {len(findings)} security notice(s) detected ({medium_count} medium, {low_count} low)."
        else:
            status = "PASSED"
            summary = f"Security Review Passed: No vulnerabilities or leaked secrets detected across {total_added_lines} added line(s)."

        return {
            "status": status,
            "clean": (status == "PASSED"),
            "executed": True,
            "findings": [asdict(f) for f in findings],
            "findings_count": len(findings),
            "critical_count": critical_count,
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
            "scanner": "DevRescue SAST Heuristic Engine",
            "scanner_type": "heuristic_ast_pattern",
            "limitations": "Pattern-based heuristic static analysis; host does not have native Semgrep binary. Does not replace dynamic taint analysis or container isolation.",
            "summary": summary,
            "message": summary
        }


security_service = SecurityReviewService()
