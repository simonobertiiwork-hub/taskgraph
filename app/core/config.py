from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    postgres_user: str
    postgres_password: str
    postgres_db: str

    database_url: str

    pool_size: int = 5
    max_overflow: int = 0

    llm_provider: str = "ollama"
    llm_base_url: str = "http://ollama:11434/v1"
    llm_api_key: SecretStr | None = SecretStr("ollama")
    llm_model: str = "qwen2.5:1.5b"
    llm_timeout_seconds: float = Field(default=180.0, gt=0, le=300)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    llm_retry_backoff_seconds: float = Field(default=0.25, ge=0, le=5)
    llm_trust_env: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
