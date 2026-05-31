from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./agentflow.db"
    app_env: str = "development"
    cors_origins: str = "http://localhost:3000"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    jwt_secret: str = "change-me-in-production-use-a-long-random-string"
    access_token_expire_days: int = 7

    model_config = {"env_file": ".env"}


settings = Settings()
