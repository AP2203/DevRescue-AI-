from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class LanguageDetection(BaseModel):
    name: str = Field(..., description="Detected language name, e.g. python, javascript, typescript, java, go, rust")
    version: Optional[str] = Field(None, description="Detected runtime or language version, e.g. 3.11, 20.x, 17, 1.22")
    files_count: int = Field(0, description="Number of source files detected for this language")
    sample_files: List[str] = Field(default_factory=list, description="Sample file paths detected")
    confidence: float = Field(1.0, description="Detection confidence score from 0.0 to 1.0")


class SubprojectProfile(BaseModel):
    path: str = Field("", description="Subproject root directory relative to repository root, e.g. 'backend' or ''")
    language: str = Field(..., description="Primary language of the subproject, e.g. python, javascript, java, go, rust, unknown")
    runtime_version: Optional[str] = Field(None, description="Detected language runtime version")
    build_tool: Optional[str] = Field(None, description="Build tool or package manager, e.g. pip, poetry, npm, pnpm, yarn, maven, gradle, cargo, go")
    manifest_path: Optional[str] = Field(None, description="Primary manifest file path relative to repository root")
    lockfile_path: Optional[str] = Field(None, description="Lockfile path relative to repository root if present")
    test_framework: Optional[str] = Field(None, description="Detected test framework, e.g. pytest, unittest, jest, vitest, mocha, maven, gradle, cargo, go")
    test_config_path: Optional[str] = Field(None, description="Path to test config file, e.g. pytest.ini, jest.config.js")
    test_files: List[str] = Field(default_factory=list, description="Discovered test file paths relative to repository root")
    test_files_count: int = Field(0, description="Total count of discovered test files")
    test_command: Optional[str] = Field(None, description="Inferred test execution command")
    docker_image: Optional[str] = Field(None, description="Recommended Docker image for sandbox execution")
    env_var_names: List[str] = Field(default_factory=list, description="Names of required environment variables detected (no secrets)")
    is_monorepo: bool = Field(False, description="Whether subproject belongs to a monorepo workspace")
    confidence: float = Field(1.0, description="Detection confidence score from 0.0 to 1.0")
    evidence: List[str] = Field(default_factory=list, description="Supporting evidence details for this subproject profile")


class RepositoryProfile(BaseModel):
    root_path: str = Field(..., description="Root path of the repository on disk")
    languages: List[LanguageDetection] = Field(default_factory=list, description="Detected languages in repository")
    primary_language: Optional[str] = Field(None, description="Primary language of the overall repository")
    is_monorepo: bool = Field(False, description="Whether repository is organized as a monorepo or workspace")
    monorepo_type: Optional[str] = Field(None, description="Monorepo type, e.g. npm_workspaces, pnpm_workspaces, lerna, cargo_workspace, nested_directories")
    subprojects: List[SubprojectProfile] = Field(default_factory=list, description="List of detected subprojects or services")
    ci_workflows: List[str] = Field(default_factory=list, description="Paths to detected CI workflow definitions")
    ci_test_commands: List[str] = Field(default_factory=list, description="Test commands extracted from CI configurations")
    ci_env_vars: List[str] = Field(default_factory=list, description="Environment variable names extracted from CI workflows")


class TestStrategyContract(BaseModel):
    __test__ = False
    subproject_path: str = Field("", description="Target subproject path relative to repository root, e.g. 'backend'")
    container_workdir: str = Field("/workspace", description="Working directory inside Docker container, e.g. '/workspace/backend'")
    language: str = Field(..., description="Target language, e.g. python, javascript, typescript, java, go, rust, unknown")
    runtime_version: Optional[str] = Field(None, description="Language runtime version")
    manifest_path: Optional[str] = Field(None, description="Primary manifest file path relative to repo root")
    lockfile_path: Optional[str] = Field(None, description="Lockfile path relative to repo root")
    package_manager: Optional[str] = Field(None, description="Package manager, e.g. pip, npm, pnpm, yarn, maven, gradle, cargo, go")
    test_framework: Optional[str] = Field(None, description="Test framework, e.g. pytest, jest, vitest, mocha, maven, gradle, cargo, go")
    test_config_path: Optional[str] = Field(None, description="Test configuration file path if found")
    discovered_test_files: List[str] = Field(default_factory=list, description="Discovered test file paths")
    test_files_count: int = Field(0, description="Total number of discovered test files")
    test_command: Optional[str] = Field(None, description="Explicit test execution command")
    docker_image: str = Field(..., description="Docker base image used for isolated execution")
    dependency_prep_plan: Optional[str] = Field(None, description="Summary of Phase 1 dependency preparation plan")
    confidence: float = Field(1.0, description="Confidence score from 0.0 to 1.0")
    status: str = Field("READY", description="READY, NO_TESTS_FOUND, TESTS_NOT_CONFIGURED, or UNSUPPORTED_PROJECT")
    supporting_evidence: List[str] = Field(default_factory=list, description="Detailed reasons explaining why this strategy was selected")
    env_var_names: List[str] = Field(default_factory=list, description="Environment variable names to provide (no secret values)")
    dummy_env_vars: Dict[str, str] = Field(default_factory=dict, description="Synthesized safe, non-sensitive dummy environment variables")
