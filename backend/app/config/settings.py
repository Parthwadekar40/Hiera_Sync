from pydantic import field_validator
from pydantic_settings import BaseSettings
import os
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "CampusFlow"
    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "my-firebase-project")
    FIREBASE_PRIVATE_KEY_PATH: str = os.getenv("FIREBASE_PRIVATE_KEY_PATH", "firebase-credentials.json")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "supersecretkey")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    # Comma-separated list, e.g. "http://localhost:5173,https://hiera-sync.web.app"
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


    class Config:
        env_file = ".env"

settings = Settings()
