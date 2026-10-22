from fastapi import APIRouter
from typing import List, Dict, Any

router = APIRouter(prefix="/repositories", tags=["Repositories"])

DEFAULT_REPOSITORIES = [
    {
        "id": "repo-1",
        "name": "payment-gateway",
        "fullName": "acme-corp/payment-gateway",
        "owner": "acme-corp",
        "language": "TypeScript",
        "filterCategory": "Fintech / Payments",
        "filesCount": 142,
        "openIssuesCount": 3,
        "defaultBranch": "main",
        "branches": ["main", "develop", "staging"],
        "lastActivity": "12m ago",
        "lastUpdated": "Today",
        "description": "PCI-DSS compliant payment processing engine and settlement microservice.",
        "issues": [
            {
                "id": "iss-109",
                "number": 109,
                "title": "Race condition in idempotency ledger during concurrent capture calls",
                "description": "When two concurrent webhook events attempt to capture the same settlement ledger row, isolation level permits duplicate transaction credit records.",
                "status": "Open",
                "author": "alex-dev",
                "createdAt": "2 hours ago",
                "labels": ["bug", "high-priority", "concurrency"]
            }
        ]
    },
    {
        "id": "repo-2",
        "name": "kernel-indexer",
        "fullName": "hyperion/kernel-indexer",
        "owner": "hyperion",
        "language": "Rust",
        "filterCategory": "Systems / Infrastructure",
        "filesCount": 380,
        "openIssuesCount": 1,
        "defaultBranch": "master",
        "branches": ["master", "v2-next"],
        "lastActivity": "1h ago",
        "lastUpdated": "Yesterday",
        "description": "High-throughput AST code graph indexer and symbol search pipeline.",
        "issues": [
            {
                "id": "iss-88",
                "number": 88,
                "title": "Panic on AST parsing of unterminated macro invocations in Rust 2024",
                "description": "Parser fails to recover token stream boundaries when encountering unclosed delimiters inside procedural attribute macros.",
                "status": "Open",
                "author": "r-maintainer",
                "createdAt": "5 hours ago",
                "labels": ["bug", "parser", "macro"]
            }
        ]
    }
]

@router.get("", response_model=List[Dict[str, Any]])
def list_repositories():
    """Returns connected repositories."""
    return DEFAULT_REPOSITORIES

@router.post("/connect", response_model=Dict[str, Any], status_code=201)
@router.post("", response_model=Dict[str, Any], status_code=201)
def connect_repository(payload: Dict[str, Any]):
    """Registers or connects a repository."""
    repo_name = payload.get("repository_name") or payload.get("name") or payload.get("fullName") or "custom-repo"
    owner = repo_name.split("/")[0] if "/" in repo_name else "user"
    name = repo_name.split("/")[-1]
    
    new_repo = {
        "id": f"repo-{len(DEFAULT_REPOSITORIES) + 1}",
        "name": name,
        "fullName": repo_name if "/" in repo_name else f"{owner}/{name}",
        "owner": owner,
        "language": payload.get("language", "TypeScript"),
        "filterCategory": payload.get("filterCategory", "General"),
        "filesCount": payload.get("filesCount", 120),
        "openIssuesCount": 1,
        "defaultBranch": payload.get("defaultBranch", "main"),
        "branches": ["main", "develop"],
        "lastActivity": "Just now",
        "lastUpdated": "Today",
        "description": payload.get("description", "Connected repository via DevRescue AI."),
        "issues": [
            {
                "id": f"iss-{len(DEFAULT_REPOSITORIES) + 100}",
                "number": 1,
                "title": f"Initial issue for {name}",
                "description": f"Automated monitoring and invariant check registered for {repo_name}.",
                "status": "Open",
                "author": owner,
                "createdAt": "Just now",
                "labels": ["bug", "triage"]
            }
        ]
    }
    DEFAULT_REPOSITORIES.insert(0, new_repo)
    return new_repo

