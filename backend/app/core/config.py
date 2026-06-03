from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./agentflow.db"
    app_env: str = "development"
    cors_origins: str = "http://localhost:3000"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    jwt_secret: str = "change-me-in-production-use-a-long-random-string"
    access_token_expire_days: int = 7

    model_config = {"env_file": ".env"}


settings = Settings()
