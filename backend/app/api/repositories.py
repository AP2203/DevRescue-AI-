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
