"""
Centralized Configuration
Uses pydantic-settings for validated environment variables.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # LLM Settings
    LITELLM_PRIMARY_CHAT_MODEL: str = "nvidia_nim/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
    LITELLM_FALLBACK_CHAT_MODEL: str = "nvidia_nim/deepseek-ai/deepseek-v4-flash-0731"
    LITELLM_CHAT_API_KEY: str
    LITELLM_EMBEDDING_MODEL: str = "nvidia_nim/nvidia/nemotron-3-embed-1b"
    LITELLM_EMBEDDING_API_KEY: str
    LLM_MAX_TOKENS: int = 1024


    # Langcmith
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_API_KEY: str
    LANGCHAIN_PROJECT: str = "production-api-project"

    # Application Settings
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    RATE_LIMIT: str = "20/minute"
    CACHE_TTL_SECONDS: int = 300
    MAX_RETRIES: int = 3

    model_config = {"env_file":".env", "extra":"ignore"}


    @property
    def is_production(self) -> bool:
        return self.APP_ENV=="production"

@lru_cache
def get_settings() -> Settings:
    """Cached settings instance - loaded once, reused everywhere"""
    return Settings()
    