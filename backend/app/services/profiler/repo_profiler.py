import os
import posixpath
from typing import List, Optional, Dict, Any, Tuple, Set

from app.schemas.test_strategy import (
    LanguageDetection,
    SubprojectProfile,
    RepositoryProfile,
    TestStrategyContract
)
from app.services.profiler.base import (
    BaseLanguageAdapter,
    is_ignored_directory,
    safe_relpath,
    to_container_workdir
)
from app.services.profiler.python_adapter import PythonAdapter
from app.services.profiler.node_adapter import NodeAdapter
from app.services.profiler.java_adapter import JavaAdapter
from app.services.profiler.go_adapter import GoAdapter
from app.services.profiler.rust_adapter import RustAdapter
from app.services.profiler.ci_workflow_parser import CIWorkflowParser
from app.services.profiler.env_synthesizer import EnvSynthesizer


LANGUAGE_EXTENSIONS = {
    "python": (".py",),
    "javascript": (".js", ".jsx", ".mjs", ".cjs"),
    "typescript": (".ts", ".tsx"),
    "java": (".java",),
    "go": (".go",),
    "rust": (".rs",),
    "c": (".c", ".h"),
    "cpp": (".cpp", ".hpp", ".cc", ".cxx"),
    "ruby": (".rb",),
    "php": (".php",),
    "csharp": (".cs",),
}


class RepoProfiler:
    """
    Modular repository profiler that inspects polyglot repositories,
    identifies languages, monorepo/workspace layouts, build tools,
    dependency manifests, test suites, and CI workflows, producing
    validated TestStrategyContracts.
    """

    def __init__(self, adapters: Optional[List[BaseLanguageAdapter]] = None):
        self.adapters: List[BaseLanguageAdapter] = adapters or [
            PythonAdapter(),
            NodeAdapter(),
            JavaAdapter(),
            GoAdapter(),
            RustAdapter()
        ]
        self.ci_parser = CIWorkflowParser()

    def register_adapter(self, adapter: BaseLanguageAdapter) -> None:
        """Adds or overrides a language adapter."""
        self.adapters.append(adapter)

    def _scan_language_files(self, repo_root: str) -> Dict[str, List[str]]:
        """Counts files and gathers samples for each known language."""
        files_by_lang: Dict[str, List[str]] = {lang: [] for lang in LANGUAGE_EXTENSIONS}
        files_by_lang["unknown"] = []

        for root, dirs, files in os.walk(repo_root):
            dirs[:] = [d for d in dirs if not is_ignored_directory(d)]
            for file in files:
                file_lower = file.lower()
                matched = False
                for lang, exts in LANGUAGE_EXTENSIONS.items():
                    if any(file_lower.endswith(ext) for ext in exts):
                        rel = safe_relpath(os.path.join(root, file), repo_root)
                        files_by_lang[lang].append(rel)
                        matched = True
                        break
                if not matched and not file_lower.startswith("."):
                    rel = safe_relpath(os.path.join(root, file), repo_root)
                    files_by_lang["unknown"].append(rel)

        return files_by_lang

    def profile_repository(self, repo_root: str) -> RepositoryProfile:
        """
        Inspects the full repository tree, scanning manifests, test files,
        CI configurations, and language distributions.
        """
        repo_root = os.path.abspath(repo_root)
        if not os.path.isdir(repo_root):
            return RepositoryProfile(
                root_path=repo_root,
                languages=[],
                primary_language=None,
                is_monorepo=False,
                subprojects=[]
            )

        # 1. Scan language distribution
        lang_files = self._scan_language_files(repo_root)
        language_detections: List[LanguageDetection] = []
        total_source_files = sum(len(f) for f in lang_files.values())

        for lang, files in lang_files.items():
            if lang == "unknown" or len(files) == 0:
                continue
            conf = min(1.0, round(len(files) / max(1, total_source_files), 2))
            language_detections.append(LanguageDetection(
                name=lang,
                files_count=len(files),
                sample_files=files[:5],
                confidence=conf
            ))

        # Sort language detections by file count
        language_detections.sort(key=lambda x: x.files_count, reverse=True)
        primary_lang = language_detections[0].name if language_detections else None

        # 2. Parse CI workflows
        wf_files, ci_cmds, ci_envs = self.ci_parser.parse_workflows(repo_root)

        # 3. Discover subprojects across root and nested directories (up to depth 4)
        subprojects: List[SubprojectProfile] = []
        directories_to_check: List[Tuple[str, str]] = [(repo_root, "")]

        for root, dirs, _ in os.walk(repo_root):
            dirs[:] = [d for d in dirs if not is_ignored_directory(d)]
            rel = safe_relpath(root, repo_root)
            if not rel:
                continue
            depth = len(rel.split("/"))
            if depth > 4:
                dirs[:] = []
                continue
            directories_to_check.append((root, rel))

        for dir_abs, rel_path in directories_to_check:
            for adapter in self.adapters:
                sub = adapter.detect(dir_abs, rel_path, repo_root)
                if sub:
                    # Enrich with CI environment variables if applicable
                    if ci_envs:
                        sub.env_var_names = list(set(sub.env_var_names + ci_envs))
                    subprojects.append(sub)

        # 4. Check for monorepo patterns
        is_monorepo = False
        monorepo_type = None

        if os.path.isfile(os.path.join(repo_root, "pnpm-workspace.yaml")):
            is_monorepo = True
            monorepo_type = "pnpm_workspaces"
        elif os.path.isfile(os.path.join(repo_root, "lerna.json")):
            is_monorepo = True
            monorepo_type = "lerna"
        elif os.path.isfile(os.path.join(repo_root, "go.work")):
            is_monorepo = True
            monorepo_type = "go_workspaces"
        else:
            # Check package.json workspaces
            root_pkg = os.path.join(repo_root, "package.json")
            if os.path.isfile(root_pkg):
                try:
                    import json
                    with open(root_pkg, "r", encoding="utf-8") as f:
                        if "workspaces" in json.load(f):
                            is_monorepo = True
                            monorepo_type = "npm_workspaces"
                except Exception:
                    pass

        # If not explicit workspace but multiple distinct subprojects exist
        if not is_monorepo and len(subprojects) > 1:
            distinct_paths = {s.path for s in subprojects if s.path}
            if len(distinct_paths) >= 2:
                is_monorepo = True
                monorepo_type = "nested_directories"

        return RepositoryProfile(
            root_path=repo_root,
            languages=language_detections,
            primary_language=primary_lang,
            is_monorepo=is_monorepo,
            monorepo_type=monorepo_type,
            subprojects=subprojects,
            ci_workflows=wf_files,
            ci_test_commands=ci_cmds,
            ci_env_vars=ci_envs
        )

    def evaluate_test_strategy(
        self,
        repo_root: str,
        changed_files: Optional[List[str]] = None,
        profile: Optional[RepositoryProfile] = None,
        repo_identity: Optional[Dict[str, Any]] = None
    ) -> TestStrategyContract:
        """
        Determines the optimal TestStrategyContract for execution based on the
        repository profile and any changed/target files.

        repo_identity optionally carries the verified (owner, repo, branch,
        commit, workspace) of the checkout so the resulting contract can record
        exactly which repository/commit was inspected (guards against inspecting
        a different repo's workspace).
        """
        if not profile:
            profile = self.profile_repository(repo_root)

        changed_files = changed_files or []
        normalized_changed = [cf.replace("\\", "/").lstrip("/") for cf in changed_files]

        if not profile.subprojects:
            # Check if this is an unsupported language project
            if profile.languages:
                top_lang = profile.languages[0].name
                if top_lang in ("c", "cpp", "ruby", "php", "csharp"):
                    return TestStrategyContract(
                        subproject_path="",
                        container_workdir="/workspace",
                        language=top_lang,
                        test_framework=None,
                        discovered_test_files=[],
                        test_files_count=0,
                        test_command=None,
                        docker_image="scratch",
                        status="UNSUPPORTED_PROJECT",
                        confidence=0.9,
                        supporting_evidence=[
                            f"Detected primary language '{top_lang}' with {profile.languages[0].files_count} files, "
                            f"which is not currently supported for isolated test execution."
                        ]
                    )

            return TestStrategyContract(
                subproject_path="",
                container_workdir="/workspace",
                language=profile.primary_language or "unknown",
                test_framework=None,
                discovered_test_files=[],
                test_files_count=0,
                test_command=None,
                docker_image="python:3.11-slim",
                status="TESTS_NOT_CONFIGURED",
                confidence=0.5,
                supporting_evidence=[
                    "No supported subproject manifests (package.json, pytest/pyproject, pom.xml, build.gradle, go.mod, Cargo.toml) found."
                ]
            )

        # Select the subproject that best matches the changed files.
        #
        # The root pseudo-subproject (path == "") acts as a recursive catch-all:
        # it qualifies whenever any Python/Node file exists *anywhere* in the
        # repository, which makes it outrank nothing and win ties. Nested
        # directories that are merely packages inside a real project (e.g.
        # "backend/app/models") are also detected as subprojects. A naive
        # "deepest match wins" rule therefore selects an untested inner package
        # and can fall back to the root catch-all, running dependency
        # preparation at the workspace root of a polyglot repo where a stray
        # package.json hijacks the run into the wrong ecosystem.
        def _depth(sub: SubprojectProfile) -> int:
            path = sub.path.replace("\\", "/").strip("/")
            return len(path.split("/")) if path else 0

        def _matches(sub_path: str) -> bool:
            return any(
                cf == sub_path or cf.startswith(sub_path + "/")
                for cf in normalized_changed
            )

        # Only real (non-root) subprojects can "match" changed files. The root
        # catch-all is used solely as a last resort.
        matched = [
            s for s in profile.subprojects
            if s.path.replace("\\", "/").strip("/")
            and _matches(s.path.replace("\\", "/").strip("/"))
        ]
        tested = [s for s in profile.subprojects if s.test_files_count > 0 or s.test_command]
        matched_tested = [s for s in matched if s.test_files_count > 0 or s.test_command]

        def _fallback_rank(sub: SubprojectProfile):
            # Run a real project rather than the recursive root catch-all.
            # Prefer a nested project with a manifest, then the shallowest,
            # then the one with the most tests.
            path = sub.path.replace("\\", "/").strip("/")
            return (
                0 if path else 1,            # avoid the root catch-all
                0 if sub.manifest_path else 1,
                _depth(sub),
                -sub.test_files_count,
            )

        best_sub: Optional[SubprojectProfile] = None
        if matched_tested:
            # The changed files hit a project that owns a real test suite.
            # Prefer the most specific (deepest) match.
            best_sub = max(matched_tested, key=lambda s: (_depth(s), s.test_files_count))
        elif tested:
            # Either there was no changed-file match, or the match pointed at an
            # untested package directory. Run a real sibling project instead of
            # falsely reporting TESTS_NOT_CONFIGURED or selecting the catch-all.
            best_sub = min(tested, key=_fallback_rank)
        elif matched:
            best_sub = max(matched, key=_depth)

        if best_sub is None:
            best_sub = profile.subprojects[0]

        # Find the adapter that owns this subproject's language
        target_adapter = None
        for adapter in self.adapters:
            if adapter.name == best_sub.language or (
                adapter.name == "javascript" and best_sub.language in ("javascript", "typescript")
            ):
                target_adapter = adapter
                break

        if not target_adapter:
            return TestStrategyContract(
                subproject_path=best_sub.path,
                container_workdir=to_container_workdir(best_sub.path),
                language=best_sub.language,
                test_framework=best_sub.test_framework,
                discovered_test_files=best_sub.test_files,
                test_files_count=best_sub.test_files_count,
                test_command=best_sub.test_command,
                docker_image=best_sub.docker_image or "scratch",
                status="UNSUPPORTED_PROJECT",
                confidence=0.8,
                supporting_evidence=[
                    f"Subproject at '{best_sub.path}' identified as '{best_sub.language}', "
                    "but no matching runtime adapter is available."
                ]
            )

        # Delegate resolution to adapter
        contract = target_adapter.resolve_test_strategy(best_sub, changed_files)

        # Cross-reference with CI workflow commands if available and contract command is default
        if profile.ci_test_commands:
            contract.supporting_evidence.append(
                f"CI workflow(s) define test command(s): {', '.join(profile.ci_test_commands)}"
            )
            # If contract has status TESTS_NOT_CONFIGURED or no test_command,
            # adopt matching test command from CI workflow
            if contract.status == "TESTS_NOT_CONFIGURED" or not contract.test_command:
                for ci_cmd in profile.ci_test_commands:
                    ci_cmd_lower = ci_cmd.lower()
                    matched = False
                    if contract.language == "python" and any(k in ci_cmd_lower for k in ("pytest", "unittest", "python -m", "tox")):
                        contract.test_command = ci_cmd
                        contract.test_framework = "pytest" if "pytest" in ci_cmd_lower else "unittest"
                        matched = True
                    elif contract.language in ("javascript", "typescript") and any(k in ci_cmd_lower for k in ("npm test", "yarn test", "pnpm test", "jest", "vitest")):
                        contract.test_command = ci_cmd
                        contract.test_framework = "jest" if "jest" in ci_cmd_lower else ("vitest" if "vitest" in ci_cmd_lower else "npm")
                        matched = True

                    if matched:
                        if contract.test_files_count == 0:
                            contract.status = "NO_TESTS_FOUND"
                        else:
                            contract.status = "READY"
                        contract.supporting_evidence.append(f"Adopted test command from CI workflow: {ci_cmd}")
                        break
            elif contract.language == "python" and contract.test_command == "pytest":
                for ci_cmd in profile.ci_test_commands:
                    if ci_cmd.startswith("pytest ") and ci_cmd != "pytest":
                        contract.test_command = ci_cmd
                        contract.supporting_evidence.append(f"Refined test command from CI workflow: {ci_cmd}")
                        break

        # Discover .env templates (.env.example, .env.sample, etc.) and synthesize safe dummy env vars
        sub_dir = os.path.join(repo_root, best_sub.path) if best_sub.path else repo_root
        templates = EnvSynthesizer.discover_env_templates(repo_root, sub_dir)
        env_keys: Set[str] = set(profile.ci_env_vars)
        template_defaults: Dict[str, str] = {}

        for tpath in templates:
            parsed = EnvSynthesizer.parse_env_template(tpath)
            env_keys.update(parsed.keys())
            template_defaults.update(parsed)

        if templates:
            contract.supporting_evidence.append(
                f"Discovered runtime environment template(s): {', '.join([os.path.basename(t) for t in templates])}"
            )

        contract.env_var_names = sorted(list(env_keys))
        contract.dummy_env_vars = EnvSynthesizer.synthesize_dummy_env_vars(env_keys, template_defaults)

        # Record exactly which repository/commit/workdir was inspected so failures
        # can never be silently attributed to a different repository's workspace.
        if repo_identity:
            ident = f"{repo_identity.get('owner', '?')}/{repo_identity.get('repo', '?')}"
            commit = str(repo_identity.get("commit") or "unknown")
            branch = repo_identity.get("branch")
            ref = f"{ident}@{branch}" if branch else ident
            contract.supporting_evidence.append(
                f"Verified workspace for {ref} (commit {commit[:12]}) at "
                f"'{repo_identity.get('workspace', 'workspace')}' -> workdir {contract.container_workdir}."
            )

        # When no tests could be configured, surface exactly what was searched.
        if contract.status in ("NO_TESTS_FOUND", "TESTS_NOT_CONFIGURED", "UNSUPPORTED_PROJECT"):
            try:
                top_dirs = sorted(
                    d for d in os.listdir(repo_root)
                    if os.path.isdir(os.path.join(repo_root, d)) and not is_ignored_directory(d)
                )
            except Exception:
                top_dirs = []
            contract.supporting_evidence.append(
                "Searched project roots: "
                + (", ".join(top_dirs) if top_dirs else "(repository root only)")
                + f"; inspected subproject '{best_sub.path or '(root)'}'."
            )
            if contract.language == "python":
                contract.supporting_evidence.append(
                    "Checked for Python test suites/configs: tests/ and test/ directories, "
                    "test_*.py, *_test.py, tests.py, conftest.py, pytest.ini, .pytest.ini, "
                    "setup.cfg, tox.ini, noxfile.py, pyproject.toml, requirements*.txt, Pipfile, lockfiles."
                )

        return contract


# Global singleton instance
repo_profiler = RepoProfiler()
