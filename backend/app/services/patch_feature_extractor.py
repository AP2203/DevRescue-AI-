import re
from typing import Dict, Any

class PatchFeatureExtractor:
    """
    Extracts the 13 features required by the DevRescue XGBoost model
    from patch diffs, file changes, and execution metadata.
    """

    @staticmethod
    def extract_from_patch(
        diff_text: str,
        files_count: int = 1,
        code_size: int = 1000,
        dependency_changes: int = 0,
        test_count: int = 0,
        tests_passed: int = 0,
        tests_failed: int = 0
    ) -> Dict[str, Any]:
        """
        Extracts all 13 features from a patch diff string.
        """
        if not diff_text:
            diff_text = ""

        lines = diff_text.splitlines()
        
        # 1. Count additions and removals
        lines_added = 0
        lines_removed = 0
        functions_changed = 0
        classes_changed = 0
        complexity_branches = 0

        # Regex patterns for heuristic feature extraction
        fn_pattern = re.compile(r'^\+[^+].*\b(def|function|async function|fn|func|public\s+\w+\s+\w+\(|private\s+\w+\s+\w+\()\b')
        class_pattern = re.compile(r'^\+[^+].*\b(class|struct|interface|type)\b')
        branch_pattern = re.compile(r'^\+[^+].*\b(if|else if|elif|for|while|switch|case|catch|\?\?|&&|\|\|)\b')

        for line in lines:
            if line.startswith('+++') or line.startswith('---'):
                continue
            if line.startswith('+'):
                lines_added += 1
                if fn_pattern.search(line):
                    functions_changed += 1
                if class_pattern.search(line):
                    classes_changed += 1
                if branch_pattern.search(line):
                    complexity_branches += 1
            elif line.startswith('-'):
                lines_removed += 1
                if fn_pattern.search(line):
                    functions_changed += 1
                if class_pattern.search(line):
                    classes_changed += 1

        total_changed_lines = lines_added + lines_removed
        patch_size = len(diff_text.encode('utf-8'))

        # Cyclomatic complexity baseline: 1.0 base + branches added
        cyclomatic_complexity = round(1.0 + (complexity_branches * 0.75), 2)

        # Build exactly the 13 expected features in devrescue_features.json order
        return {
            "files_changed": max(1, files_count),
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "total_changed_lines": total_changed_lines,
            "patch_size": max(patch_size, total_changed_lines * 25),
            "functions_changed": functions_changed,
            "classes_changed": classes_changed,
            "cyclomatic_complexity": cyclomatic_complexity,
            "code_size": max(code_size, total_changed_lines * 40),
            "dependency_changes": dependency_changes,
            "test_count": test_count,
            "tests_passed": tests_passed,
            "tests_failed": tests_failed
        }

patch_feature_extractor = PatchFeatureExtractor()
