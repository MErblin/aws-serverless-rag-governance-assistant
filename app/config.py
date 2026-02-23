"""
DocuChat RAG - Configuration Module

Centralized configuration management using Pydantic Settings.
Loads values from environment variables or .env file.
"""

from functools import lru_cache
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "DocuChat RAG"
    app_version: str = "0.1.0"
    debug: bool = True

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8501"]

    # Streamlit Settings
    streamlit_port: int = 8501

    # Ollama Settings
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # Embedding Model
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Storage settings
    chroma_persist_dir: str = "./data/chroma"
    chroma_collection_name: str = "documents"
    projects_root_dir: str = "./data/projects"
    default_project_id: str = "default"

    # Prompt defaults
    default_system_prompt: str = (
        "You are a helpful assistant. Answer using only provided context. "
        "If context is insufficient, clearly say you don't know."
    )

    # Document Processing
    chunk_size: int = 512
    chunk_overlap: int = 50
    max_file_size_mb: int = 10

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

    @property
    def chroma_path(self) -> Path:
        """Get ChromaDB persistence path as Path object."""
        return Path(self.chroma_persist_dir)

    @property
    def projects_root_path(self) -> Path:
        """Root path for per-project storage."""
        return Path(self.projects_root_dir)

    @property
    def max_file_size_bytes(self) -> int:
        """Get max file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.
    
    Uses LRU cache to avoid reloading settings on every call.
    
    Returns:
        Settings: Application settings instance.
    """
    return Settings()
