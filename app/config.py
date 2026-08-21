from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    search_service_url: str
    search_service_api_key: str
    foundry_project_endpoint: str
    foundry_model_api_key: str
    llm_model_name: str = "gpt-4.1"
    kb_name: str = "health-banking-kb"
    max_output_documents: int = 8


@lru_cache
def get_settings() -> Settings:
    return Settings()
