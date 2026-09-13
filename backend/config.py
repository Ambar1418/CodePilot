from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "CodePilot API"
    groq_api_key: Optional[str] = None
    llm_model: str = "qwen/qwen3.8-27b"

    # Database
    database_url: str = "sqlite:///./codepilot.db"

    # Auth
    secret_key: str = "CHANGE_ME_IN_PRODUCTION_USE_A_LONG_RANDOM_STRING"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # Repository safety
    repository_base_dir: Optional[str] = None  # If set, only paths under this dir allowed

    # Orchestration limits
    max_debug_attempts: int = 3
    worktree_base_dir: str = "/tmp/codepilot-worktrees"

    # Sandbox defaults
    sandbox_timeout_seconds: int = 60
    sandbox_memory_limit: str = "512m"
    sandbox_cpu_limit: str = "1.0"
    sandbox_docker_image: str = "python:3.13-slim"

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"


settings = Settings()
