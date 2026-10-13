from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class NemotronHealthResponse(BaseModel):
    connected: bool
    provider: str = "NVIDIA"
    model: str
    error: Optional[str] = None

class IssuePayload(BaseModel):
    number: int
    title: str
    body: Optional[str] = ""
    comments: Optional[List[str]] = Field(default_factory=list)

class RepositoryPayload(BaseModel):
    owner: str
    name: str
    default_branch: str = "main"

class FilePayload(BaseModel):
    path: str
    content: str
    language: Optional[str] = "unknown"

class NemotronInvestigateRequest(BaseModel):
    owner: str = Field(..., description="GitHub repository owner/organization", json_schema_extra={"example": "anshpatel2212"})
    repo: str = Field(..., description="GitHub repository name", json_schema_extra={"example": "YOUR_REPO"})
    issue_number: int = Field(..., description="GitHub issue number to investigate", json_schema_extra={"example": 1})
    branch: Optional[str] = Field("main", description="Target git branch", json_schema_extra={"example": "main"})

    model_config = {
        "json_schema_extra": {
            "example": {
                "owner": "anshpatel2212",
                "repo": "YOUR_REPO",
                "issue_number": 1,
                "branch": "main"
            }
        }
    }

class EvidenceItem(BaseModel):
    file: str
    line: Optional[int] = Field(default=0, ge=0)
    reason: str

class NemotronInvestigationResult(BaseModel):
    root_cause: str
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    affected_files: List[str] = Field(default_factory=list)
    affected_functions: List[str] = Field(default_factory=list)
    evidence: List[EvidenceItem] = Field(default_factory=list)
    proposed_fix: str
    test_strategy: str

# Backward compatibility alias
NemotronInvestigateResponse = NemotronInvestigationResult

class AnalyzedFileItem(BaseModel):
    path: str
    language: Optional[str] = "unknown"

class NemotronPipelineResponse(BaseModel):
    success: bool = True
    repository: str
    issue_number: int
    files_analyzed: List[AnalyzedFileItem] = Field(default_factory=list)
    investigation: NemotronInvestigationResult

class NemotronGeneratePatchRequest(BaseModel):
    issue: IssuePayload
    investigation: NemotronInvestigationResult
    files: List[FilePayload] = Field(default_factory=list)
    tests: List[FilePayload] = Field(default_factory=list)

class NemotronPatchResponse(BaseModel):
    patch: str
    changed_files: List[str] = Field(default_factory=list)
    explanation: str
    test_plan: str

class NemotronPatchRequest(BaseModel):
    owner: str = Field(..., description="GitHub repository owner", json_schema_extra={"example": "anshpatel2212"})
    repo: str = Field(..., description="GitHub repository name", json_schema_extra={"example": "2D2Mesh"})
    branch: Optional[str] = Field("main", description="Target branch", json_schema_extra={"example": "main"})
    issue_number: int = Field(..., description="GitHub issue number", json_schema_extra={"example": 1})
    investigation: NemotronInvestigationResult

class PatchValidationDetails(BaseModel):
    is_valid: bool = True
    clean_application: bool = True
    files_checked: List[str] = Field(default_factory=list)
    retries_used: int = 0

class NemotronRealPatchResponse(BaseModel):
    success: bool = True
    patch: str
    files_changed: List[str] = Field(default_factory=list)
    lines_added: int
    lines_removed: int
    explanation: str
    validation: PatchValidationDetails
    file_shas: Dict[str, str] = Field(default_factory=dict)
    source_hashes: Dict[str, str] = Field(default_factory=dict)
    retries_used: int = 0

