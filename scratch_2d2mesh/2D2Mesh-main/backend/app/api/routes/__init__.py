"""API route handlers."""
from app.api.routes import admin, auth, files, health, jobs, models, projects, uploads, users

__all__ = ["auth", "users", "projects", "jobs", "uploads", "models", "files", "admin", "health"]
