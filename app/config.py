from typing import List, Optional
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    app_name: str = ""
    app_version: str = ""
    debug: bool = False
    environment: str = ""

    database_url: str = ""
    postgres_user: str = ""
    postgres_password: str = ""
    postgres_db: str = ""

    chroma_host: str = ""
    chroma_port: int = 8000

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""

    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    google_api_key: str = ""
    openai_api_key: str = ""

    model : str = ""

    composio_api_key: str = ""
    
    google_calendar_auth_config_id: str = ""
    notion_auth_config_id: str = ""
    gmail_auth_config_id: str = ""
    google_tasks_auth_config_id: str = ""
    slackbot_auth_config_id: str = ""
    twitter_auth_config_id: str = ""

    allowed_origin: Optional[str] = "*"

    secret_key: str = ""

    cookie_name: str = ""
    cookie_max_age: int = 86400 * 7
    cookie_path: str = ""
    cookie_domain: Optional[str] = None
    cookie_secure: bool = True
    cookie_httponly: bool = True
    cookie_samesite: str = ""
    frontend_url: str = "http://localhost:5173"

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
