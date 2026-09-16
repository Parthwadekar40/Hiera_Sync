from pydantic_settings import BaseSettings
import os
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "HiéraSync AI"
    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "my-firebase-project")
    FIREBASE_PRIVATE_KEY_PATH: str = os.getenv("FIREBASE_PRIVATE_KEY_PATH", "firebase-credentials.json")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "supersecretkey")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    # Comma-separated list of browser origins allowed to call this API, e.g.
    # "http://localhost:5173,https://hiera-sync.web.app". Kept as a raw string so
    # .env parsing stays plain, and exposed as a list through `cors_origins`.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
