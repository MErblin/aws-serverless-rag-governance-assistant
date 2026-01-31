"""
Unit tests for the configuration module.
"""

import os
from unittest.mock import patch

import pytest

from app.config import Settings, get_settings


class TestSettings:
    """Tests for the Settings class."""

    def test_default_values(self):
        """Test that default settings are loaded correctly."""
        settings = Settings()
        
        assert settings.app_name == "DocuChat RAG"
        assert settings.app_version == "0.1.0"
        assert settings.debug is True
        assert settings.api_port == 8000
        assert settings.ollama_model == "llama3.2"
        assert settings.chunk_size == 512

    def test_chroma_path_property(self):
        """Test the chroma_path property returns a Path object."""
        settings = Settings()
        path = settings.chroma_path
        
        assert path.name == "chroma"
        assert path.parent.name == "data"

    def test_max_file_size_bytes_property(self):
        """Test the max_file_size_bytes calculation."""
        settings = Settings(max_file_size_mb=5)
        
        assert settings.max_file_size_bytes == 5 * 1024 * 1024

    @patch.dict(os.environ, {"OLLAMA_MODEL": "mistral"})
    def test_environment_override(self):
        """Test that environment variables override defaults."""
        # Clear cached settings
        get_settings.cache_clear()
        
        settings = Settings()
        assert settings.ollama_model == "mistral"


class TestGetSettings:
    """Tests for the get_settings function."""

    def test_returns_settings_instance(self):
        """Test that get_settings returns a Settings instance."""
        get_settings.cache_clear()
        settings = get_settings()
        
        assert isinstance(settings, Settings)

    def test_caching(self):
        """Test that get_settings returns the same cached instance."""
        get_settings.cache_clear()
        
        settings1 = get_settings()
        settings2 = get_settings()
        
        assert settings1 is settings2
