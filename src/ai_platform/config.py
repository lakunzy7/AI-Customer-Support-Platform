from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "ai-platform"
    app_env: str = "development"
    app_debug: bool = False
    app_log_level: str = "info"

    # LLM Provider (OpenAI-compatible — Groq, OpenRouter, etc.)
    llm_api_key: str = ""
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "llama-3.3-70b-versatile"

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://aiplatform:aiplatform@localhost:5432/aiplatform"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 3600

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "faq_documents"

    # File uploads
    upload_dir: str = "/tmp/ai-platform-uploads"
    max_upload_size_mb: int = 10

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


settings = Settings()
