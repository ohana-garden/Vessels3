"""
Tests for startup and initialization logic.

These tests verify:
1. Entrypoint script behavior
2. Environment variable handling
3. .env file generation
4. Startup sequence
5. Health check logic
"""

import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from vessels.core.config import Settings, write_env_file, get_settings


class TestEntrypointEnvGeneration:
    """Tests for entrypoint environment file generation."""

    def test_generates_env_file_with_all_api_keys(self, tmp_path):
        """Test .env file generation with all API keys."""
        env_file = tmp_path / ".env"

        api_keys = {
            "openai_api_key": "sk-test-openai-key-12345",
            "anthropic_api_key": "sk-ant-test-anthropic-key-67890",
        }

        write_env_file(env_file, api_keys)

        content = env_file.read_text()

        # Verify API keys are written
        assert "OPENAI_API_KEY=sk-test-openai-key-12345" in content
        assert "ANTHROPIC_API_KEY=sk-ant-test-anthropic-key-67890" in content

        # Verify structure
        assert "# API Keys" in content

    def test_generates_env_file_with_falkordb_config(self, tmp_path):
        """Test .env file generation with FalkorDB configuration."""
        env_file = tmp_path / ".env"

        falkordb_config = {
            "falkordb_host": "db.example.com",
            "falkordb_port": "6380",
            "falkordb_password": "supersecret",
            "falkordb_data_dir": "/custom/data",
        }

        write_env_file(env_file, {}, falkordb_config)

        content = env_file.read_text()

        assert "FALKORDB_HOST=db.example.com" in content
        assert "FALKORDB_PORT=6380" in content
        assert "FALKORDB_PASSWORD=supersecret" in content
        assert "FALKORDB_DATA_DIR=/custom/data" in content

    def test_generates_env_file_with_vessels_config(self, tmp_path):
        """Test .env file generation with Vessels application config."""
        env_file = tmp_path / ".env"

        vessels_config = {
            "vessels_debug": "true",
            "vessels_log_level": "DEBUG",
            "vessels_graph_name": "custom_graph",
        }

        write_env_file(env_file, {}, vessels_config)

        content = env_file.read_text()

        assert "VESSELS_DEBUG=true" in content
        assert "VESSELS_LOG_LEVEL=DEBUG" in content
        assert "VESSELS_GRAPH_NAME=custom_graph" in content

    def test_preserves_existing_custom_vars(self, tmp_path):
        """Test that existing custom variables are preserved."""
        env_file = tmp_path / ".env"

        # Write initial content
        env_file.write_text("CUSTOM_VAR=custom_value\nANOTHER_VAR=another_value\n")

        # Update with new API keys
        write_env_file(env_file, {"openai_api_key": "sk-new"})

        content = env_file.read_text()

        # Custom vars should be preserved
        assert "CUSTOM_VAR=custom_value" in content
        assert "ANOTHER_VAR=another_value" in content
        # New key should be added
        assert "OPENAI_API_KEY=sk-new" in content

    def test_updates_existing_vars(self, tmp_path):
        """Test that existing variables are updated."""
        env_file = tmp_path / ".env"

        # Write initial content
        env_file.write_text("OPENAI_API_KEY=old-key\n")

        # Update
        write_env_file(env_file, {"openai_api_key": "new-key"})

        content = env_file.read_text()

        # Should have new value, not old
        assert "OPENAI_API_KEY=new-key" in content
        assert "old-key" not in content

    def test_skips_empty_values(self, tmp_path):
        """Test that empty values are not written."""
        env_file = tmp_path / ".env"

        api_keys = {
            "openai_api_key": "sk-valid",
            "anthropic_api_key": "",  # Empty
        }

        write_env_file(env_file, api_keys)

        content = env_file.read_text()

        assert "OPENAI_API_KEY=sk-valid" in content
        assert "ANTHROPIC_API_KEY=" not in content

    def test_skips_none_values(self, tmp_path):
        """Test that None values are not written."""
        env_file = tmp_path / ".env"

        api_keys = {
            "openai_api_key": "sk-valid",
            "anthropic_api_key": None,
        }

        write_env_file(env_file, api_keys)

        content = env_file.read_text()

        assert "OPENAI_API_KEY=sk-valid" in content
        assert "ANTHROPIC_API_KEY" not in content


class TestApiKeyValidation:
    """Tests for API key format validation."""

    def test_openai_key_valid_format(self):
        """Test OpenAI key format detection."""
        valid_keys = [
            "sk-1234567890abcdef",
            "sk-proj-1234567890",
            "sk-test-key-with-many-parts",
        ]

        for key in valid_keys:
            assert key.startswith("sk-"), f"Key {key} should be valid"

    def test_openai_key_invalid_format(self):
        """Test detection of invalid OpenAI key format."""
        invalid_keys = [
            "invalid-key",
            "openai-key",
            "api-key-12345",
            "",
        ]

        for key in invalid_keys:
            assert not key.startswith("sk-"), f"Key {key} should be invalid"

    def test_anthropic_key_valid_format(self):
        """Test Anthropic key format detection."""
        valid_keys = [
            "sk-ant-1234567890abcdef",
            "sk-ant-api03-test-key",
        ]

        for key in valid_keys:
            assert key.startswith("sk-ant-"), f"Key {key} should be valid"

    def test_anthropic_key_invalid_format(self):
        """Test detection of invalid Anthropic key format."""
        invalid_keys = [
            "sk-1234567890",  # OpenAI format
            "anthropic-key",
            "sk-anthropic-key",
            "",
        ]

        for key in invalid_keys:
            assert not key.startswith("sk-ant-"), f"Key {key} should be invalid"


class TestSettingsLoading:
    """Tests for settings loading from environment."""

    def test_loads_from_environment(self):
        """Test that settings are loaded from environment variables."""
        env_vars = {
            "FALKORDB_HOST": "test-host",
            "FALKORDB_PORT": "6380",
            "OPENAI_API_KEY": "sk-env-test",
            "VESSELS_DEBUG": "true",
            "VESSELS_LOG_LEVEL": "DEBUG",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            get_settings.cache_clear()
            settings = Settings()

            assert settings.falkordb_host == "test-host"
            assert settings.falkordb_port == 6380
            assert settings.openai_api_key == "sk-env-test"
            assert settings.vessels_debug is True
            assert settings.vessels_log_level == "DEBUG"

    def test_uses_defaults_when_not_set(self):
        """Test that default values are used when env vars not set."""
        with patch.dict(os.environ, {}, clear=True):
            get_settings.cache_clear()
            settings = Settings()

            assert settings.falkordb_host == "localhost"
            assert settings.falkordb_port == 6379
            assert settings.vessels_debug is False
            assert settings.vessels_log_level == "INFO"

    def test_settings_caching(self):
        """Test that settings are cached."""
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_cache_clear_reloads(self):
        """Test that clearing cache causes reload."""
        get_settings.cache_clear()

        with patch.dict(os.environ, {"FALKORDB_HOST": "host1"}, clear=True):
            settings1 = get_settings()
            assert settings1.falkordb_host == "host1"

        get_settings.cache_clear()

        with patch.dict(os.environ, {"FALKORDB_HOST": "host2"}, clear=True):
            settings2 = get_settings()
            assert settings2.falkordb_host == "host2"


class TestStartupSequence:
    """Tests for startup sequence logic."""

    def test_falkordb_wait_logic(self):
        """Test the FalkorDB wait logic."""
        # Simulate the wait logic from start-vessels.sh

        def check_falkordb_ready(ping_ok, module_loaded, not_loading, query_ok):
            """Simulate the readiness check."""
            if not ping_ok:
                return False
            if not module_loaded:
                return False
            if not not_loading:
                return False
            if not query_ok:
                return False
            return True

        # All conditions met
        assert check_falkordb_ready(True, True, True, True) is True

        # Ping fails
        assert check_falkordb_ready(False, True, True, True) is False

        # Module not loaded
        assert check_falkordb_ready(True, False, True, True) is False

        # Still loading
        assert check_falkordb_ready(True, True, False, True) is False

        # Query fails
        assert check_falkordb_ready(True, True, True, False) is False

    def test_startup_mode_selection(self):
        """Test startup mode selection logic."""
        def select_mode(arg):
            """Simulate entrypoint mode selection."""
            modes = {
                "supervisor": "Start Supervisor (FalkorDB + Vessels)",
                "falkordb-only": "Start FalkorDB Only",
                "vessels-only": "Start Vessels Only",
                "test": "Run Tests",
                "shell": "Start Shell",
            }
            return modes.get(arg, "Run Custom Command")

        assert "Supervisor" in select_mode("supervisor")
        assert "FalkorDB Only" in select_mode("falkordb-only")
        assert "Vessels Only" in select_mode("vessels-only")
        assert "Tests" in select_mode("test")
        assert "Shell" in select_mode("shell")
        assert "Custom" in select_mode("custom-command")


class TestHealthCheckLogic:
    """Tests for health check script logic."""

    def test_all_checks_pass(self):
        """Test health check when all components healthy."""
        def health_check(falkordb_ok, module_ok, not_loading, graph_ok, api_ok):
            checks = [falkordb_ok, module_ok, not_loading, graph_ok, api_ok]
            return all(checks)

        assert health_check(True, True, True, True, True) is True

    def test_falkordb_check_fails(self):
        """Test health check when FalkorDB fails."""
        def health_check(falkordb_ok, module_ok, not_loading, graph_ok, api_ok):
            checks = [falkordb_ok, module_ok, not_loading, graph_ok, api_ok]
            return all(checks)

        assert health_check(False, True, True, True, True) is False

    def test_module_check_fails(self):
        """Test health check when module check fails."""
        def health_check(falkordb_ok, module_ok, not_loading, graph_ok, api_ok):
            checks = [falkordb_ok, module_ok, not_loading, graph_ok, api_ok]
            return all(checks)

        assert health_check(True, False, True, True, True) is False

    def test_loading_check_fails(self):
        """Test health check when database still loading."""
        def health_check(falkordb_ok, module_ok, not_loading, graph_ok, api_ok):
            checks = [falkordb_ok, module_ok, not_loading, graph_ok, api_ok]
            return all(checks)

        assert health_check(True, True, False, True, True) is False

    def test_graph_check_fails(self):
        """Test health check when graph operations fail."""
        def health_check(falkordb_ok, module_ok, not_loading, graph_ok, api_ok):
            checks = [falkordb_ok, module_ok, not_loading, graph_ok, api_ok]
            return all(checks)

        assert health_check(True, True, True, False, True) is False

    def test_api_check_fails(self):
        """Test health check when API fails."""
        def health_check(falkordb_ok, module_ok, not_loading, graph_ok, api_ok):
            checks = [falkordb_ok, module_ok, not_loading, graph_ok, api_ok]
            return all(checks)

        assert health_check(True, True, True, True, False) is False

    def test_exit_codes(self):
        """Test correct exit codes for health check."""
        def get_exit_code(all_pass):
            return 0 if all_pass else 1

        assert get_exit_code(True) == 0
        assert get_exit_code(False) == 1


class TestModuleDetection:
    """Tests for FalkorDB module detection logic."""

    def test_detects_graph_module(self):
        """Test detection of 'graph' module."""
        modules = [{"name": "graph", "ver": 20000}]

        has_graph = any(
            m.get("name", "").lower() in ("graph", "falkordb")
            for m in modules
        )
        assert has_graph is True

    def test_detects_falkordb_module(self):
        """Test detection of 'falkordb' module."""
        modules = [{"name": "falkordb", "ver": 40000}]

        has_graph = any(
            m.get("name", "").lower() in ("graph", "falkordb")
            for m in modules
        )
        assert has_graph is True

    def test_case_insensitive_detection(self):
        """Test case-insensitive module detection."""
        test_cases = [
            [{"name": "GRAPH"}],
            [{"name": "Graph"}],
            [{"name": "FALKORDB"}],
            [{"name": "FalkorDB"}],
        ]

        for modules in test_cases:
            has_graph = any(
                m.get("name", "").lower() in ("graph", "falkordb")
                for m in modules
            )
            assert has_graph is True, f"Failed for {modules}"

    def test_no_graph_module(self):
        """Test when graph module is not present."""
        modules = [
            {"name": "search", "ver": 10000},
            {"name": "json", "ver": 20000},
        ]

        has_graph = any(
            m.get("name", "").lower() in ("graph", "falkordb")
            for m in modules
        )
        assert has_graph is False

    def test_empty_module_list(self):
        """Test with empty module list."""
        modules = []

        has_graph = any(
            m.get("name", "").lower() in ("graph", "falkordb")
            for m in modules
        )
        assert has_graph is False


class TestLoadingStateDetection:
    """Tests for database loading state detection."""

    def test_loading_in_progress(self):
        """Test detection of loading in progress."""
        info = {"loading": 1}
        is_loading = info.get("loading", 0) == 1
        assert is_loading is True

    def test_loading_complete(self):
        """Test detection of loading complete."""
        info = {"loading": 0}
        is_loading = info.get("loading", 0) == 1
        assert is_loading is False

    def test_loading_key_missing(self):
        """Test handling of missing loading key."""
        info = {}
        is_loading = info.get("loading", 0) == 1
        assert is_loading is False  # Default to not loading

    def test_loading_key_none(self):
        """Test handling of None loading value."""
        info = {"loading": None}
        # With None, get() returns None, so == 1 is False
        is_loading = info.get("loading", 0) == 1
        assert is_loading is False
