"""
Unit tests for Vessels configuration module.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from vessels.core.config import (
    Settings,
    get_settings,
    load_api_keys_from_env,
    write_env_file,
)


class TestSettings:
    """Tests for Settings class."""

    def test_default_settings(self):
        """Test that default settings are applied correctly."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

            assert settings.falkordb_host == "localhost"
            assert settings.falkordb_port == 6379
            assert settings.falkordb_password is None
            assert settings.vessels_debug is False
            assert settings.vessels_log_level == "INFO"
            assert settings.vessels_graph_name == "vessels"

    def test_settings_from_environment(self):
        """Test that settings are loaded from environment variables."""
        env_vars = {
            "FALKORDB_HOST": "testhost",
            "FALKORDB_PORT": "6380",
            "FALKORDB_PASSWORD": "testpass",
            "OPENAI_API_KEY": "sk-test-key",
            "ANTHROPIC_API_KEY": "sk-ant-test-key",
            "VESSELS_DEBUG": "true",
            "VESSELS_LOG_LEVEL": "DEBUG",
            "VESSELS_GRAPH_NAME": "test_graph",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()

            assert settings.falkordb_host == "testhost"
            assert settings.falkordb_port == 6380
            assert settings.falkordb_password == "testpass"
            assert settings.openai_api_key == "sk-test-key"
            assert settings.anthropic_api_key == "sk-ant-test-key"
            assert settings.vessels_debug is True
            assert settings.vessels_log_level == "DEBUG"
            assert settings.vessels_graph_name == "test_graph"

    def test_falkordb_url_without_password(self):
        """Test FalkorDB URL generation without password."""
        settings = Settings(falkordb_host="myhost", falkordb_port=6380)
        assert settings.falkordb_url == "redis://myhost:6380"

    def test_falkordb_url_with_password(self):
        """Test FalkorDB URL generation with password."""
        settings = Settings(
            falkordb_host="myhost",
            falkordb_port=6380,
            falkordb_password="secret",
        )
        assert settings.falkordb_url == "redis://:secret@myhost:6380"

    def test_has_api_keys_true(self):
        """Test has_api_keys returns True when keys are set."""
        settings = Settings(openai_api_key="sk-test")
        assert settings.has_api_keys() is True

        settings = Settings(anthropic_api_key="sk-ant-test")
        assert settings.has_api_keys() is True

    def test_has_api_keys_false(self):
        """Test has_api_keys returns False when no keys are set."""
        settings = Settings()
        assert settings.has_api_keys() is False

    def test_invalid_log_level(self):
        """Test that invalid log level raises error."""
        with pytest.raises(ValueError, match="Invalid log level"):
            Settings(vessels_log_level="INVALID")

    def test_valid_log_levels(self):
        """Test all valid log levels are accepted."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            settings = Settings(vessels_log_level=level)
            assert settings.vessels_log_level == level

        # Test case insensitivity
        settings = Settings(vessels_log_level="debug")
        assert settings.vessels_log_level == "DEBUG"


class TestGetSettings:
    """Tests for get_settings function."""

    def test_settings_cached(self, clear_settings_cache):
        """Test that settings are cached."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_cache_cleared(self, clear_settings_cache):
        """Test that cache can be cleared."""
        settings1 = get_settings()
        get_settings.cache_clear()
        settings2 = get_settings()
        assert settings1 is not settings2


class TestWriteEnvFile:
    """Tests for write_env_file function."""

    def test_write_new_env_file(self, temp_env_file):
        """Test writing a new .env file."""
        # Remove existing file
        temp_env_file.unlink()

        api_keys = {
            "openai_api_key": "sk-new-key",
            "anthropic_api_key": "sk-ant-new-key",
        }

        write_env_file(temp_env_file, api_keys)

        content = temp_env_file.read_text()
        assert "OPENAI_API_KEY=sk-new-key" in content
        assert "ANTHROPIC_API_KEY=sk-ant-new-key" in content

    def test_update_existing_env_file(self, temp_env_file):
        """Test updating an existing .env file."""
        # Write initial content
        temp_env_file.write_text("EXISTING_VAR=existing_value\n")

        api_keys = {"openai_api_key": "sk-updated-key"}

        write_env_file(temp_env_file, api_keys)

        content = temp_env_file.read_text()
        assert "OPENAI_API_KEY=sk-updated-key" in content
        assert "EXISTING_VAR=existing_value" in content

    def test_write_falkordb_config(self, temp_env_file):
        """Test writing FalkorDB configuration."""
        temp_env_file.unlink()

        api_keys = {}
        falkordb_config = {
            "falkordb_host": "customhost",
            "falkordb_port": "6380",
        }

        write_env_file(temp_env_file, api_keys, falkordb_config)

        content = temp_env_file.read_text()
        assert "FALKORDB_HOST=customhost" in content
        assert "FALKORDB_PORT=6380" in content

    def test_empty_values_not_written(self, temp_env_file):
        """Test that empty values are not written."""
        temp_env_file.unlink()

        api_keys = {
            "openai_api_key": "",
            "anthropic_api_key": None,
        }

        write_env_file(temp_env_file, api_keys)

        content = temp_env_file.read_text()
        assert "OPENAI_API_KEY=" not in content
        assert "ANTHROPIC_API_KEY=" not in content


class TestLoadApiKeysFromEnv:
    """Tests for load_api_keys_from_env function."""

    def test_load_existing_keys(self):
        """Test loading API keys from environment."""
        env_vars = {
            "OPENAI_API_KEY": "sk-env-key",
            "ANTHROPIC_API_KEY": "sk-ant-env-key",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            keys = load_api_keys_from_env()

            assert keys["openai_api_key"] == "sk-env-key"
            assert keys["anthropic_api_key"] == "sk-ant-env-key"

    def test_load_missing_keys(self):
        """Test loading when keys are not set."""
        with patch.dict(os.environ, {}, clear=True):
            keys = load_api_keys_from_env()

            assert keys["openai_api_key"] is None
            assert keys["anthropic_api_key"] is None
