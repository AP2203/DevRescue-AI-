import pytest
from app.services.diff_validator import (
    diff_validator,
    DiffValidationError,
    DiffSyntaxError,
    DiffPathError,
    DiffScopeError,
    DiffLimitExceededError,
    DiffApplicationError,
    MAX_PATCH_SIZE_BYTES,
    MAX_LINES_ADDED,
    MAX_FILES_CHANGED
)
from app.services.patch_service import extract_unified_diff

SAMPLE_ORIGINAL = """import React, { useState } from 'react';

export function SubmitButton({ onSubmit }) {
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    onSubmit();
  };

  return (
    <button onClick={handleClick}>
      Submit
    </button>
  );
}
"""

VALID_DIFF = """--- a/src/components/SubmitButton.jsx
+++ b/src/components/SubmitButton.jsx
@@ -6,3 +6,5 @@
   const handleClick = async () => {
+    setLoading(true);
     onSubmit();
+    setLoading(false);
   };
"""


# 1. Valid unified diff
def test_valid_unified_diff():
    files, added, removed = diff_validator.validate_syntax_and_limits(VALID_DIFF)
    assert files == ["src/components/SubmitButton.jsx"]
    assert added == 2
    assert removed == 0


# 2. Invalid diff (arbitrary prose or missing headers)
def test_invalid_diff():
    prose = "Here is the fix: you should add setLoading(true) before onSubmit()."
    with pytest.raises(DiffSyntaxError) as exc:
        diff_validator.validate_syntax_and_limits(prose)
    assert "Invalid unified diff" in str(exc.value)


# 3. Path traversal (../)
def test_path_traversal():
    traversal_diff = """--- a/src/components/../../secret.env
+++ b/src/components/../../secret.env
@@ -1,1 +1,1 @@
-SECRET=123
+SECRET=456
"""
    with pytest.raises(DiffPathError) as exc:
        diff_validator.validate_syntax_and_limits(traversal_diff)
    assert "Path traversal" in str(exc.value) or "Unsafe" in str(exc.value)


# 4. Absolute path (/etc/passwd, C:\...)
def test_absolute_path_unix():
    abs_diff = """--- /etc/passwd
+++ /etc/passwd
@@ -1,1 +1,1 @@
-root:x:0:0
+root:x:0:1
"""
    with pytest.raises(DiffPathError) as exc:
        diff_validator.validate_syntax_and_limits(abs_diff)
    assert "Absolute path" in str(exc.value) or "Unsafe" in str(exc.value)


def test_absolute_path_windows():
    win_diff = """--- C:\\Windows\\System32\\drivers\\etc\\hosts
+++ C:\\Windows\\System32\\drivers\\etc\\hosts
@@ -1,1 +1,1 @@
-127.0.0.1 localhost
+127.0.0.1 local
"""
    with pytest.raises(DiffPathError) as exc:
        diff_validator.validate_syntax_and_limits(win_diff)
    assert "Drive letter" in str(exc.value) or "Unsafe" in str(exc.value)


# 5. Unexpected file / scope violation
def test_unexpected_file():
    unrelated_diff = """--- a/package.json
+++ b/package.json
@@ -1,2 +1,2 @@
 {
-  "version": "1.0.0"
+  "version": "1.0.1"
 }
"""
    with pytest.raises(DiffScopeError) as exc:
        diff_validator.validate_and_apply(
            patch=unrelated_diff,
            file_contents={"src/components/SubmitButton.jsx": SAMPLE_ORIGINAL},
            allowed_files=["src/components/SubmitButton.jsx"]
        )
    assert "not within investigated scope" in str(exc.value)


# 6. Empty patch
def test_empty_patch():
    with pytest.raises(DiffValidationError) as exc:
        diff_validator.validate_syntax_and_limits("")
    assert "empty" in str(exc.value).lower()

    with pytest.raises(DiffValidationError) as exc:
        diff_validator.validate_syntax_and_limits("   \n\t  ")
    assert "empty" in str(exc.value).lower()


# 7. Oversized patch (exceeding byte limit or line count limit)
def test_oversized_patch_bytes():
    oversized = "--- a/file.txt\n+++ b/file.txt\n@@ -1,1 +1,1 @@\n" + ("+A" * (MAX_PATCH_SIZE_BYTES + 100))
    with pytest.raises(DiffLimitExceededError) as exc:
        diff_validator.validate_syntax_and_limits(oversized)
    assert "exceeds maximum allowable limit" in str(exc.value)


def test_oversized_patch_lines():
    large_lines = "\n".join([f"+console.log({i});" for i in range(MAX_LINES_ADDED + 20)])
    diff = f"""--- a/file.js
+++ b/file.js
@@ -1,1 +1,{MAX_LINES_ADDED + 20} @@
{large_lines}
"""
    with pytest.raises(DiffLimitExceededError) as exc:
        diff_validator.validate_syntax_and_limits(diff)
    assert f"exceeds maximum limit of {MAX_LINES_ADDED}" in str(exc.value)


# 8. Patch for unaffected file
def test_patch_for_unaffected_file():
    diff = """--- a/src/unaffected.ts
+++ b/src/unaffected.ts
@@ -1,1 +1,1 @@
-const x = 1;
+const x = 2;
"""
    with pytest.raises(DiffScopeError) as exc:
        diff_validator.validate_and_apply(
            patch=diff,
            file_contents={"src/affected.ts": "const x = 1;\n"},
            allowed_files=["src/affected.ts"]
        )
    assert "not within investigated scope" in str(exc.value)


# 9. Clean patch application & conflict detection
def test_clean_patch_application_success():
    res = diff_validator.validate_and_apply(
        patch=VALID_DIFF,
        file_contents={"src/components/SubmitButton.jsx": SAMPLE_ORIGINAL},
        allowed_files=["src/components/SubmitButton.jsx"]
    )
    assert res.is_valid is True
    assert "src/components/SubmitButton.jsx" in res.applied_contents
    new_content = res.applied_contents["src/components/SubmitButton.jsx"]
    assert "setLoading(true);" in new_content
    assert "setLoading(false);" in new_content


def test_clean_patch_application_conflict():
    mismatched_diff = """--- a/src/components/SubmitButton.jsx
+++ b/src/components/SubmitButton.jsx
@@ -1,3 +1,3 @@
-const NON_EXISTENT_FUNCTION = 999;
+const REPLACED_FUNCTION = 1000;
"""
    with pytest.raises(DiffApplicationError) as exc:
        diff_validator.validate_and_apply(
            patch=mismatched_diff,
            file_contents={"src/components/SubmitButton.jsx": SAMPLE_ORIGINAL},
            allowed_files=["src/components/SubmitButton.jsx"]
        )
    assert "does not apply cleanly" in str(exc.value)


# 10. Malformed Nemotron patch responses handled by extract_unified_diff
def test_malformed_nemotron_patch_response_markdown():
    wrapped_in_markdown = f"""Here is your patch to fix the issue:
```diff
{VALID_DIFF}
```
This resolves the problem.
"""
    extracted = extract_unified_diff(wrapped_in_markdown)
    assert extracted.startswith("--- a/src/components/SubmitButton.jsx")
    files, added, removed = diff_validator.validate_syntax_and_limits(extracted)
    assert files == ["src/components/SubmitButton.jsx"]


def test_malformed_nemotron_patch_response_thinking_blocks():
    with_thinking = f"""<think>
I need to add setLoading(true) before calling onSubmit.
Let me generate the unified diff.
</think>
{VALID_DIFF}
"""
    extracted = extract_unified_diff(with_thinking)
    assert extracted.startswith("--- a/src/components/SubmitButton.jsx")
    assert "<think>" not in extracted


def test_malformed_nemotron_patch_pure_prose_rejected():
    pure_prose = "I have reviewed your code and you should change lines 6-8."
    with pytest.raises(DiffSyntaxError) as exc:
        extract_unified_diff(pure_prose)
    assert "Response did not contain a unified diff" in str(exc.value)


def test_binary_modification_rejected():
    binary_diff = """--- a/assets/logo.png
+++ b/assets/logo.png
Binary files a/assets/logo.png and b/assets/logo.png differ
"""
    with pytest.raises(DiffValidationError) as exc:
        diff_validator.validate_syntax_and_limits(binary_diff)
    assert "Binary file" in str(exc.value)


# 11. Multi-hunk patch application (Hunk #1 alters line offsets for Hunk #2)
def test_multiple_hunks_application_with_offset():
    source = """// Component header
import React from 'react';

export function Button({ label, onClick, disabled }) {
  // Handler start
  const handleAction = () => {
    if (disabled) return;
    onClick();
  };

  // Render return
  return (
    <button onClick={handleAction} disabled={disabled}>
      {label}
    </button>
  );
}

export default Button;
"""
    # Hunk 1 modifies line 4 (adds props and 3 lines)
    # Hunk 2 modifies line 14 (changes button styling / props)
    multi_hunk_diff = """--- a/frontend/src/components/ui/Button.tsx
+++ b/frontend/src/components/ui/Button.tsx
@@ -2,4 +2,7 @@
 import React from 'react';

+import { Loader2 } from 'lucide-react';
+
+export function Button({ label, onClick, disabled, loading }: any) {
-export function Button({ label, onClick, disabled }) {
@@ -11,4 +14,5 @@
   return (
-    <button onClick={handleAction} disabled={disabled}>
+    <button onClick={handleAction} disabled={disabled || loading} className="btn-primary">
+      {loading && <Loader2 className="animate-spin" />}
       {label}
     </button>
"""
    res = diff_validator.validate_and_apply(
        patch=multi_hunk_diff,
        file_contents={"frontend/src/components/ui/Button.tsx": source},
        allowed_files=["frontend/src/components/ui/Button.tsx"]
    )
    assert res.is_valid is True
    applied = res.applied_contents["frontend/src/components/ui/Button.tsx"]
    assert "import { Loader2 } from 'lucide-react';" in applied
    assert 'loading && <Loader2 className="animate-spin" />' in applied
    assert 'disabled={disabled || loading}' in applied


# 12. Whitespace and CRLF line ending tolerance
def test_crlf_and_trailing_whitespace_tolerance():
    source_crlf = "export function test() {\r\n    const a = 1;    \r\n    return a;\r\n}\r\n"
    diff = """--- a/test.ts
+++ b/test.ts
@@ -1,4 +1,4 @@
 export function test() {
-    const a = 1;
+    const a = 2;
     return a;
 }
"""
    res = diff_validator.validate_and_apply(
        patch=diff,
        file_contents={"test.ts": source_crlf},
        allowed_files=["test.ts"]
    )
    assert res.is_valid is True
    applied = res.applied_contents["test.ts"]
    assert "const a = 2;" in applied
    assert "\r\n" in applied  # Preserves CRLF convention


# 13. Truncated diff rejection
def test_truncated_diff_rejected():
    truncated_diff = """--- a/Button.tsx
+++ b/Button.tsx
@@ -10,15 +10,20 @@
"""
    with pytest.raises(DiffSyntaxError) as exc:
        diff_validator.validate_and_apply(
            patch=truncated_diff,
            file_contents={"Button.tsx": "const x = 1;\n"},
            allowed_files=["Button.tsx"]
        )
    assert "truncated" in str(exc.value).lower() or "no hunk lines" in str(exc.value).lower()


# 14. Partial application prevention: entire patch rejected if any hunk on any file fails
def test_multi_file_partial_application_prevented():
    file1_content = "const file1 = 'original';\n"
    file2_content = "const file2 = 'original';\n"

    # File 1 has a valid diff, File 2 has an impossible hunk
    patch = """--- a/file1.ts
+++ b/file1.ts
@@ -1,1 +1,1 @@
-const file1 = 'original';
+const file1 = 'modified';
--- a/file2.ts
+++ b/file2.ts
@@ -1,1 +1,1 @@
-const MISSING_TARGET_LINE = true;
+const REPLACED = false;
"""
    with pytest.raises(DiffApplicationError) as exc:
        diff_validator.validate_and_apply(
            patch=patch,
            file_contents={"file1.ts": file1_content, "file2.ts": file2_content},
            allowed_files=["file1.ts", "file2.ts"]
        )
    assert exc.value.file == "file2.ts"
    assert exc.value.hunk == 1
    assert "Hunk #1 failed" in str(exc.value)


# 15. Sandbox atomic workspace preservation on failure
def test_sandbox_workspace_preserves_disk_on_failure():
    import tempfile
    import os
    from app.services.sandbox_service import sandbox_service

    with tempfile.TemporaryDirectory() as tmp_dir:
        f1_path = os.path.join(tmp_dir, "f1.txt")
        f2_path = os.path.join(tmp_dir, "f2.txt")
        with open(f1_path, "w") as f:
            f.write("line 1\n")
        with open(f2_path, "w") as f:
            f.write("line 2\n")

        # Patch valid for f1, failing for f2
        bad_patch = """--- a/f1.txt
+++ b/f1.txt
@@ -1,1 +1,1 @@
-line 1
+line 1 modified
--- a/f2.txt
+++ b/f2.txt
@@ -1,1 +1,1 @@
-UNMATCHED LINE
+new line
"""
        with pytest.raises(DiffApplicationError) as exc:
            sandbox_service.apply_patch_to_workspace(tmp_dir, bad_patch)

        assert exc.value.file == "f2.txt"

        # Verify f1.txt on disk was NOT modified (atomic workspace protection)
        with open(f1_path, "r") as f:
            assert f.read() == "line 1\n"


# 16. Stale source hash rejection
def test_stale_source_hash_rejection():
    file_content = "const version = 1;\n"
    patch = """--- a/src/app.ts
+++ b/src/app.ts
@@ -1,1 +1,1 @@
-const version = 1;
+const version = 2;
"""
    wrong_hash = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    with pytest.raises(DiffApplicationError) as exc:
        diff_validator.validate_and_apply(
            patch=patch,
            file_contents={"src/app.ts": file_content},
            expected_source_hashes={"src/app.ts": wrong_hash}
        )
    assert "Stale source detected" in str(exc.value)
    assert exc.value.file == "src/app.ts"
    assert exc.value.details.get("stale_source") is True


# 17. Ambiguous matches rejected when duplicate blocks exist in file
def test_ambiguous_matches_rejected():
    duplicate_source = """function handleA() {
  doSomething();
}

function handleB() {
  doSomething();
}
"""
    # Diff with ambiguous single-line context '  doSomething();' that appears in both functions far from line 50
    ambiguous_diff = """--- a/src/handlers.js
+++ b/src/handlers.js
@@ -50,1 +50,1 @@
-  doSomething();
+  doSomethingElse();
"""
    with pytest.raises(DiffApplicationError) as exc:
        diff_validator.validate_and_apply(
            patch=ambiguous_diff,
            file_contents={"src/handlers.js": duplicate_source}
        )
    assert "Ambiguous match" in str(exc.value)
    assert exc.value.details.get("ambiguous") is True


# 18. Malformed diff prefix syntax error
def test_malformed_diff_prefix_syntax_error():
    malformed_diff = """--- a/src/index.js
+++ b/src/index.js
@@ -1,3 +1,3 @@
 const a = 1;
INVALID_LINE_WITHOUT_DIFF_PREFIX
 const c = 3;
"""
    with pytest.raises(DiffSyntaxError) as exc:
        diff_validator.validate_and_apply(
            patch=malformed_diff,
            file_contents={"src/index.js": "const a = 1;\nconst b = 2;\nconst c = 3;\n"}
        )
    assert "missing diff prefix" in str(exc.value).lower() or "syntax" in str(exc.value).lower()


# 19. CRLF and LF explicit preservation
def test_lf_and_crlf_line_endings_preserved():
    # LF content
    lf_content = "function test() {\n  return 1;\n}\n"
    lf_diff = """--- a/test_lf.ts
+++ b/test_lf.ts
@@ -1,3 +1,3 @@
 function test() {
-  return 1;
+  return 2;
 }
"""
    res_lf = diff_validator.validate_and_apply(
        patch=lf_diff,
        file_contents={"test_lf.ts": lf_content}
    )
    assert res_lf.is_valid is True
    assert "\r\n" not in res_lf.applied_contents["test_lf.ts"]
    assert res_lf.applied_contents["test_lf.ts"] == "function test() {\n  return 2;\n}\n"

    # CRLF content
    crlf_content = "function test() {\r\n  return 1;\r\n}\r\n"
    crlf_diff = """--- a/test_crlf.ts
+++ b/test_crlf.ts
@@ -1,3 +1,3 @@
 function test() {
-  return 1;
+  return 2;
 }
"""
    res_crlf = diff_validator.validate_and_apply(
        patch=crlf_diff,
        file_contents={"test_crlf.ts": crlf_content}
    )
    assert res_crlf.is_valid is True
    assert "\r\n" in res_crlf.applied_contents["test_crlf.ts"]
    assert res_crlf.applied_contents["test_crlf.ts"] == "function test() {\r\n  return 2;\r\n}\r\n"


# 20. Regression test: Valid diff followed by '*** End of diff ***'
def test_valid_diff_followed_by_end_of_diff_marker():
    source = """export function Button({ onClick, disabled }) {
  const handleClick = () => {
    onClick();
  };
  return <button onClick={handleClick}>Click</button>;
}
"""
    raw_response = """--- a/frontend/src/components/ui/Button.tsx
+++ b/frontend/src/components/ui/Button.tsx
@@ -2,3 +2,3 @@
   const handleClick = () => {
-    onClick();
+    if (!disabled) onClick();
   };
*** End of diff ***
"""
    cleaned = extract_unified_diff(raw_response)
    assert "*** End of diff ***" not in cleaned
    assert cleaned.startswith("--- a/frontend/src/components/ui/Button.tsx")

    res = diff_validator.validate_and_apply(
        patch=cleaned,
        file_contents={"frontend/src/components/ui/Button.tsx": source},
        allowed_files=["frontend/src/components/ui/Button.tsx"]
    )
    assert res.is_valid is True
    assert "if (!disabled) onClick();" in res.applied_contents["frontend/src/components/ui/Button.tsx"]


# 21. Regression test: Diff wrapped in Markdown code fences
def test_diff_wrapped_in_markdown_fences():
    source = "const greeting = 'hello';\n"
    raw_response = """Here is the fix for the issue:
```diff
--- a/src/greet.ts
+++ b/src/greet.ts
@@ -1,1 +1,1 @@
-const greeting = 'hello';
+const greeting = 'hello world';
*** End of diff ***
```
Please let me know if this works!
"""
    cleaned = extract_unified_diff(raw_response)
    assert "```" not in cleaned
    assert "*** End of diff ***" not in cleaned

    res = diff_validator.validate_and_apply(
        patch=cleaned,
        file_contents={"src/greet.ts": source},
        allowed_files=["src/greet.ts"]
    )
    assert res.is_valid is True
    assert "hello world" in res.applied_contents["src/greet.ts"]


# 22. Regression test: Diff with explanatory prose before and after
def test_diff_with_explanatory_prose_before_and_after():
    source = "let count = 0;\nfunction increment() {\n  count += 1;\n}\n"
    raw_response = """I have investigated the issue and identified the root cause.
The counter increment should be guarded to avoid negative or overflow states.

--- a/src/counter.ts
+++ b/src/counter.ts
@@ -2,3 +2,3 @@
 function increment() {
-  count += 1;
+  if (count < 100) count += 1;
 }

*** End of diff ***

Explanation of change:
We added a condition to guard against exceeding maximum capacity.
All unit tests should now pass.
"""
    cleaned = extract_unified_diff(raw_response)
    assert "I have investigated" not in cleaned
    assert "Explanation of change" not in cleaned
    assert "*** End of diff ***" not in cleaned

    res = diff_validator.validate_and_apply(
        patch=cleaned,
        file_contents={"src/counter.ts": source},
        allowed_files=["src/counter.ts"]
    )
    assert res.is_valid is True
    assert "if (count < 100) count += 1;" in res.applied_contents["src/counter.ts"]


# 23. Regression test: Genuinely malformed hunk must still be rejected
def test_genuinely_malformed_hunk_rejected():
    source = "const a = 1;\nconst b = 2;\nconst c = 3;\n"

    # Case A: Missing prefix on arbitrary code line
    malformed_hunk = """--- a/src/index.js
+++ b/src/index.js
@@ -1,3 +1,3 @@
 const a = 1;
invalid_code_line_without_prefix
 const c = 3;
"""
    with pytest.raises(DiffSyntaxError) as exc_a:
        diff_validator.validate_and_apply(
            patch=malformed_hunk,
            file_contents={"src/index.js": source}
        )
    assert "missing diff prefix" in str(exc_a.value).lower()
    assert exc_a.value.file == "src/index.js"
    assert exc_a.value.hunk == 1

    # Case B: Arbitrary line beginning with *** that is NOT an end marker
    malformed_stars = """--- a/src/index.js
+++ b/src/index.js
@@ -1,3 +1,3 @@
 const a = 1;
*** arbitrary unformatted note without diff prefix ***
 const c = 3;
"""
    with pytest.raises(DiffSyntaxError) as exc_b:
        diff_validator.validate_and_apply(
            patch=malformed_stars,
            file_contents={"src/index.js": source}
        )
    assert "missing diff prefix" in str(exc_b.value).lower()
    assert exc_b.value.file == "src/index.js"


# 24. Regression test: Valid multi-file diff
def test_valid_multi_file_diff():
    f1_source = "export const VERSION = '1.0.0';\n"
    f2_source = "export const NAME = 'devrescue';\n"

    raw_response = """diff --git a/src/version.ts b/src/version.ts
--- a/src/version.ts
+++ b/src/version.ts
@@ -1,1 +1,1 @@
-export const VERSION = '1.0.0';
+export const VERSION = '1.1.0';
*** End of diff ***
diff --git a/src/name.ts b/src/name.ts
--- a/src/name.ts
+++ b/src/name.ts
@@ -1,1 +1,1 @@
-export const NAME = 'devrescue';
+export const NAME = 'devrescue-ai';
*** End of diff ***
"""
    cleaned = extract_unified_diff(raw_response)
    assert "*** End of diff ***" not in cleaned

    res = diff_validator.validate_and_apply(
        patch=cleaned,
        file_contents={"src/version.ts": f1_source, "src/name.ts": f2_source},
        allowed_files=["src/version.ts", "src/name.ts"]
    )
    assert res.is_valid is True
    assert len(res.files_changed) == 2
    assert "1.1.0" in res.applied_contents["src/version.ts"]
    assert "devrescue-ai" in res.applied_contents["src/name.ts"]


# 25. Realistic Button.tsx clean application and validation
REAL_BUTTON_TSX = """import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { Loader2 } from "lucide-react"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline:
          "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
  loading?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, loading = false, children, disabled, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        disabled={disabled || loading}
        {...props}
      >
        {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        {children}
      </Comp>
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
"""


def test_real_button_tsx_clean_application():
    diff = """--- a/frontend/src/components/ui/Button.tsx
+++ b/frontend/src/components/ui/Button.tsx
@@ -46,7 +46,7 @@
     return (
       <Comp
         className={cn(buttonVariants({ variant, size, className }))}
         ref={ref}
-        disabled={disabled || loading}
+        disabled={disabled ?? loading}
         {...props}
       >
         {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
"""
    cleaned = extract_unified_diff(diff)
    res = diff_validator.validate_and_apply(
        patch=cleaned,
        file_contents={"frontend/src/components/ui/Button.tsx": REAL_BUTTON_TSX},
        allowed_files=["frontend/src/components/ui/Button.tsx"]
    )
    assert res.is_valid is True
    applied = res.applied_contents["frontend/src/components/ui/Button.tsx"]
    assert "disabled={disabled ?? loading}" in applied
    assert "disabled={disabled || loading}" not in applied


# 26. Incorrect context returns rich diagnostic details
def test_real_button_tsx_incorrect_context_returns_rich_diagnostics():
    bad_context_diff = """--- a/frontend/src/components/ui/Button.tsx
+++ b/frontend/src/components/ui/Button.tsx
@@ -1,7 +1,7 @@
 // Completely made up imaginary context
 const imaginaryVariable = true;
-disabled={disabled || loading}
+disabled={disabled ?? loading}
 const anotherMadeUpLine = false;
"""
    with pytest.raises(DiffApplicationError) as exc:
        diff_validator.validate_and_apply(
            patch=bad_context_diff,
            file_contents={"frontend/src/components/ui/Button.tsx": REAL_BUTTON_TSX},
            allowed_files=["frontend/src/components/ui/Button.tsx"]
        )
    err = exc.value
    assert err.file == "frontend/src/components/ui/Button.tsx"
    assert err.hunk == 1
    assert "Could not locate target lines in file" in err.message
    # Check rich diagnostics
    details = err.details
    assert "expected_lines" in details
    assert "nearby_actual_lines" in details
    assert "nearby_actual_start_line" in details
    # The best matching line should be located near line 48 (where disabled={disabled || loading} lives)
    assert abs(details["best_match_line"] - 48) <= 5


# 27. Stale source hash rejection with diverged content
def test_stale_source_hash_rejection_diverged():
    import hashlib
    file_path = "frontend/src/components/ui/Button.tsx"
    original_hash = hashlib.sha256(REAL_BUTTON_TSX.encode("utf-8")).hexdigest()
    stale_hash = "0000000000000000000000000000000000000000000000000000000000000000"

    diff = """--- a/frontend/src/components/ui/Button.tsx
+++ b/frontend/src/components/ui/Button.tsx
@@ -46,7 +46,7 @@
     return (
       <Comp
         className={cn(buttonVariants({ variant, size, className }))}
         ref={ref}
-        disabled={disabled || loading}
+        disabled={disabled ?? loading}
         {...props}
       >
         {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
"""
    with pytest.raises(DiffApplicationError) as exc:
        diff_validator.validate_and_apply(
            patch=diff,
            file_contents={file_path: REAL_BUTTON_TSX},
            allowed_files=[file_path],
            expected_source_hashes={file_path: stale_hash}
        )
    assert "Stale source detected" in str(exc.value)
    assert exc.value.details.get("stale_source") is True


# 28. Normalized line endings tolerance between CRLF and LF
def test_crlf_lf_normalized_hash_tolerance():
    import hashlib
    file_path = "frontend/src/components/ui/Button.tsx"
    # Target content has CRLF
    content_crlf = REAL_BUTTON_TSX.replace("\n", "\r\n")
    norm_content = REAL_BUTTON_TSX.replace("\r\n", "\n")
    norm_hash = hashlib.sha256(norm_content.encode("utf-8")).hexdigest()

    # Pass expected_source_hashes with filename and filename__norm
    expected_hashes = {
        file_path: "byte_hash_from_lf_system",
        f"{file_path}__norm": norm_hash
    }

    diff = """--- a/frontend/src/components/ui/Button.tsx
+++ b/frontend/src/components/ui/Button.tsx
@@ -46,7 +46,7 @@
     return (
       <Comp
         className={cn(buttonVariants({ variant, size, className }))}
         ref={ref}
-        disabled={disabled || loading}
+        disabled={disabled ?? loading}
         {...props}
       >
         {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
"""
    res = diff_validator.validate_and_apply(
        patch=diff,
        file_contents={file_path: content_crlf},
        allowed_files=[file_path],
        expected_source_hashes=expected_hashes
    )
    assert res.is_valid is True
    applied = res.applied_contents[file_path]
    # Check CRLF is preserved
    assert "\r\n" in applied
    assert "disabled={disabled ?? loading}" in applied


# 29. Multi-hunk cumulative offset tracking
def test_multi_hunk_cumulative_offsets():
    lines = [f"line {i}" for i in range(1, 31)]
    source = "\n".join(lines) + "\n"

    # Hunk 1: insert 3 lines after line 5
    # Hunk 2: delete 2 lines at line 15 (which now is shifted down by 3 lines)
    # Hunk 3: modify line 25 (which now is shifted by 3 - 2 = 1 line)
    diff = """--- a/test.txt
+++ b/test.txt
@@ -4,3 +4,6 @@
 line 4
 line 5
+inserted 1
+inserted 2
+inserted 3
 line 6
@@ -14,4 +17,2 @@
 line 14
-line 15
-line 16
 line 17
@@ -24,3 +25,3 @@
 line 24
-line 25
+modified 25
 line 26
"""
    res = diff_validator.validate_and_apply(
        patch=diff,
        file_contents={"test.txt": source},
        allowed_files=["test.txt"]
    )
    assert res.is_valid is True
    applied = res.applied_contents["test.txt"]
    assert "inserted 1" in applied
    assert "line 15" not in applied
    assert "modified 25" in applied





