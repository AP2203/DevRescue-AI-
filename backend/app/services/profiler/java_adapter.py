import os
import re
from typing import List, Optional, Tuple, Set

from app.schemas.test_strategy import SubprojectProfile, TestStrategyContract
from app.services.profiler.base import (
    BaseLanguageAdapter,
    is_ignored_directory,
    safe_relpath,
    to_container_workdir
)


class JavaAdapter(BaseLanguageAdapter):
    """
    Adapter for Java projects.
    Supports Maven (pom.xml) and Gradle (build.gradle / build.gradle.kts).
    """

    @property
    def name(self) -> str:
        return "java"

    @property
    def default_image(self) -> str:
        return "maven:3.9-eclipse-temurin-17"

    def find_test_files(self, project_dir: str, rel_path: str = "") -> List[str]:
        """Discovers Java test files (e.g. *Test.java, *Tests.java, *TestCase.java)."""
        test_files: List[str] = []
        if not os.path.isdir(project_dir):
            return test_files

        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if not is_ignored_directory(d)]
            for file in files:
                if file.endswith(".java") and (file.endswith("Test.java") or file.endswith("Tests.java") or file.endswith("TestCase.java")):
                    full = os.path.join(root, file)
                    rel = safe_relpath(full, project_dir)
                    if rel_path:
                        rel = f"{rel_path.strip('/')}/{rel}"
                    test_files.append(rel)
        return sorted(test_files)

    def resolve_runtime_and_image(self, project_dir: str, repo_root: str) -> Tuple[Optional[str], str]:
        """Detects Java version and resolves Maven or Gradle container image."""
        java_version = None
        pom_path = os.path.join(project_dir, "pom.xml")
        gradle_path = os.path.join(project_dir, "build.gradle")
        gradle_kts_path = os.path.join(project_dir, "build.gradle.kts")

        is_gradle = os.path.isfile(gradle_path) or os.path.isfile(gradle_kts_path)

        if os.path.isfile(pom_path):
            try:
                with open(pom_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                m = re.search(r"<(?:java\.version|maven\.compiler\.source|maven\.compiler\.target)>(\d+)</", content)
                if m:
                    java_version = m.group(1)
            except Exception:
                pass
        elif is_gradle:
            target_gradle = gradle_path if os.path.isfile(gradle_path) else gradle_kts_path
            try:
                with open(target_gradle, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                m = re.search(r"(?:sourceCompatibility|targetCompatibility)\s*=\s*['\"]?(?:JavaVersion\.VERSION_)?(\d+)", content)
                if m:
                    java_version = m.group(1)
            except Exception:
                pass

        if is_gradle:
            if java_version == "21":
                return java_version, "gradle:8.5-jdk21"
            return java_version or "17", "gradle:8.5-jdk17"

        # Maven image
        if java_version == "21":
            return java_version, "maven:3.9-eclipse-temurin-21"
        elif java_version == "11":
            return java_version, "maven:3.9-eclipse-temurin-11"
        return java_version or "17", "maven:3.9-eclipse-temurin-17"

    def detect(self, project_dir: str, rel_path: str, repo_root: str) -> Optional[SubprojectProfile]:
        """Detects Maven or Gradle Java subprojects."""
        pom_path = os.path.join(project_dir, "pom.xml")
        gradle_path = os.path.join(project_dir, "build.gradle")
        gradle_kts = os.path.join(project_dir, "build.gradle.kts")

        is_maven = os.path.isfile(pom_path)
        is_gradle = os.path.isfile(gradle_path) or os.path.isfile(gradle_kts)

        if not is_maven and not is_gradle:
            return None

        evidence = []
        manifest_path = None
        build_tool = None
        test_framework = None
        test_cmd = None

        if is_maven:
            evidence.append("Found pom.xml (Maven)")
            manifest_path = safe_relpath(pom_path, repo_root)
            build_tool = "maven"
            test_framework = "maven"
            test_cmd = "mvn test"
        elif is_gradle:
            target_g = gradle_path if os.path.isfile(gradle_path) else gradle_kts
            manifest_path = safe_relpath(target_g, repo_root)
            evidence.append(f"Found {os.path.basename(target_g)} (Gradle)")
            build_tool = "gradle"
            test_framework = "gradle"
            gradlew = os.path.join(project_dir, "gradlew")
            test_cmd = "./gradlew test" if os.path.isfile(gradlew) else "gradle test"

        test_files = self.find_test_files(project_dir, rel_path)
        evidence.append(f"Discovered {len(test_files)} Java test file(s)")

        runtime_ver, docker_image = self.resolve_runtime_and_image(project_dir, repo_root)

        return SubprojectProfile(
            path=rel_path,
            language="java",
            runtime_version=runtime_ver,
            build_tool=build_tool,
            manifest_path=manifest_path,
            lockfile_path=None,
            test_framework=test_framework,
            test_config_path=manifest_path,
            test_files=test_files,
            test_files_count=len(test_files),
            test_command=test_cmd,
            docker_image=docker_image,
            is_monorepo=False,
            confidence=1.0 if len(test_files) > 0 else 0.8,
            evidence=evidence
        )

    def resolve_test_strategy(
        self,
        profile: SubprojectProfile,
        changed_files: List[str]
    ) -> TestStrategyContract:
        """Builds a validated TestStrategyContract for Java."""
        workdir = to_container_workdir(profile.path)
        test_files = profile.test_files
        count = len(test_files)
        evidence = list(profile.evidence)

        if not profile.test_command and count == 0:
            status = "TESTS_NOT_CONFIGURED"
            cmd = None
        elif profile.test_command and count == 0:
            status = "NO_TESTS_FOUND"
            evidence.append("Java build tool configured, but 0 test files matching *Test.java discovered")
            cmd = profile.test_command
        else:
            status = "READY"
            cmd = profile.test_command
            evidence.append(f"Configured '{cmd}' for {count} test file(s)")

        tool = profile.build_tool or "maven"
        plan = f"Phase 1: Cache {tool} base image dependencies. Phase 2: isolated execution with --network none."

        return TestStrategyContract(
            subproject_path=profile.path,
            container_workdir=workdir,
            language="java",
            runtime_version=profile.runtime_version,
            manifest_path=profile.manifest_path,
            lockfile_path=profile.lockfile_path,
            package_manager=tool,
            test_framework=profile.test_framework,
            test_config_path=profile.test_config_path,
            discovered_test_files=test_files,
            test_files_count=count,
            test_command=cmd,
            docker_image=profile.docker_image or self.default_image,
            dependency_prep_plan=plan,
            confidence=profile.confidence,
            status=status,
            supporting_evidence=evidence,
            env_var_names=profile.env_var_names
        )

