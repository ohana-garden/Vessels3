"""
Pytest configuration and fixtures for Vessels tests.
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vessels.core.config import Settings, get_settings


@pytest.fixture
def temp_env_file() -> Generator[Path, None, None]:
    """Create a temporary .env file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("# Test env file\n")
        f.write("FALKORDB_HOST=testhost\n")
        f.write("FALKORDB_PORT=6380\n")
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings for testing without real database."""
    return Settings(
        falkordb_host="localhost",
        falkordb_port=6379,
        falkordb_password=None,
        openai_api_key="sk-test-openai-key",
        anthropic_api_key="sk-ant-test-anthropic-key",
        vessels_debug=True,
        vessels_log_level="DEBUG",
        vessels_graph_name="vessels_test",
        falkordb_data_dir="/tmp/falkordb_test",
    )


@pytest.fixture
def mock_redis() -> Generator[MagicMock, None, None]:
    """Mock Redis client for testing without real database."""
    mock = MagicMock()
    mock.ping.return_value = True
    mock.module_list.return_value = [{"name": "graph", "ver": 20000}]
    mock.info.return_value = {
        "redis_version": "7.0.0",
        "uptime_in_seconds": 1000,
        "connected_clients": 1,
        "used_memory_human": "1M",
        "loading": 0,
    }
    mock.delete.return_value = 1

    with patch("vessels.db.connection.Redis", return_value=mock):
        yield mock


@pytest.fixture
def mock_falkordb() -> Generator[MagicMock, None, None]:
    """Mock FalkorDB client for testing without real database."""
    mock_client = MagicMock()
    mock_graph = MagicMock()

    # Mock query results
    mock_result = MagicMock()
    mock_result.result_set = [[1]]
    mock_graph.query.return_value = mock_result

    mock_client.select_graph.return_value = mock_graph

    with patch("vessels.db.connection.FalkorDB", return_value=mock_client):
        yield mock_client


@pytest.fixture
def clear_settings_cache():
    """Clear the settings cache before and after test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
