import os
from typing import List, Optional
from pydantic import BaseModel
from dotenv import load_dotenv

# Ensure .env is loaded from backend directory regardless of working directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

class Settings(BaseModel):
    PROJECT_NAME: str = "DevRescue AI Backend API"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api"
    
    # Frontend URL & CORS
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    ALLOWED_ORIGINS: List[str] = [
        os.getenv("FRONTEND_URL", "http://localhost:5173"),
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8001",
        "http://127.0.0.1:8001"
    ]
    
    # GitHub OAuth & API Configuration
    GITHUB_CLIENT_ID: Optional[str] = os.getenv("GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET: Optional[str] = os.getenv("GITHUB_CLIENT_SECRET")
    GITHUB_REDIRECT_URI: str = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8000/api/github/callback")
    GITHUB_API_URL: str = os.getenv("GITHUB_API_URL", "https://api.github.com")
    
    # Session Management
    BASE_DIR: str = BASE_DIR
    SESSION_COOKIE_NAME: str = "devrescue_github_session"
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", os.path.join(BASE_DIR, "devrescue_sessions.db"))
    
    # NVIDIA Nemotron LLM Configuration
    NVIDIA_API_KEY: Optional[str] = os.getenv("NVIDIA_API_KEY") or os.getenv("NEBIUS_API_KEY")
    NVIDIA_BASE_URL: str = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    NEMOTRON_MODEL: str = os.getenv("NEMOTRON_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
    NEMOTRON_TIMEOUT: float = float(os.getenv("NEMOTRON_TIMEOUT", "120.0"))
    NEMOTRON_CONNECT_TIMEOUT: float = float(os.getenv("NEMOTRON_CONNECT_TIMEOUT", "15.0"))
    NEMOTRON_MAX_RETRIES: int = int(os.getenv("NEMOTRON_MAX_RETRIES", "2"))

    # ML Model directory
    ML_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ml")
    MODEL_PATH: str = os.path.join(ML_DIR, "devrescue_risk_model.pkl")
    FEATURES_PATH: str = os.path.join(ML_DIR, "devrescue_features.json")
    LABEL_MAPPING_PATH: str = os.path.join(ML_DIR, "risk_label_mapping.json")

settings = Settings()

