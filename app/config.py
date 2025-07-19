from typing import List, Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "meAI Backend"
    app_version: str = "1.0.0"
    debug: bool = True
    environment: str = "development"

    database_url: str = ""
    postgres_user: str = ""
    postgres_password: str = ""
    postgres_db: str = ""

    chroma_host: str = "meAI-chromadb"
    chroma_port: int = 8000

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""

    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    google_api_key: str = ""
    google_gemini_model: str = "gemini-pro"

    composio_api_key: str = ""

    allowed_origins: List[str] = ["http://localhost:3000"]

    secret_key: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
