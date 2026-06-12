from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./agentflow.db"
    app_env: str = "development"
    cors_origins: str = "https://agent-orch.vercel.app,http://localhost:3000"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    jwt_secret: str = "change-me-in-production-use-a-long-random-string"
    access_token_expire_days: int = 7

    model_config = {"env_file": ".env"}

    @field_validator("database_url", mode="before")
    @classmethod
    def fix_postgres_scheme(cls, v: str) -> str:
        """Render/Railway/Supabase/Neon은 'postgresql://' 형식으로 주입한다.
        SQLAlchemy async는 'postgresql+asyncpg://' 가 필요하므로 자동 변환."""
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v


settings = Settings()
