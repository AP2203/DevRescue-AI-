from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class GitHubUser(BaseModel):
    id: Optional[int] = None
    login: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    html_url: Optional[str] = None
    email: Optional[str] = None

class GitHubUserResponse(BaseModel):
    authenticated: bool
    user: Optional[GitHubUser] = None

class GitHubConnectPATRequest(BaseModel):
    token: str = Field(..., min_length=3, description="GitHub Personal Access Token (classic or fine-grained) or 'demo'")

class GitHubRepositoryResponse(BaseModel):
    id: int
    name: str
    full_name: str
    owner: str
    description: Optional[str] = ""
    private: bool = False
    default_branch: str = "main"
    language: Optional[str] = "Other"
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    html_url: Optional[str] = None

class GitHubBranchResponse(BaseModel):
    name: str
    protected: bool = False
    commit_sha: Optional[str] = ""

class GitHubIssueResponse(BaseModel):
    id: int
    number: int
    title: str
    body: Optional[str] = ""
    state: str
    author: str
    labels: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    html_url: Optional[str] = None

class GitHubCommitResponse(BaseModel):
    sha: Optional[str] = None
    message: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None

class GitHubErrorResponse(BaseModel):
    error: str
    message: str

