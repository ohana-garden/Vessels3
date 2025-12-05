"""
Exhaustive tests for FalkorDB loading and readiness.

These tests verify that:
1. FalkorDB module is properly detected
2. Database loading state is correctly identified
3. Graph operations are verified before proceeding
4. Retry logic works correctly
5. Timeout handling is proper
"""

import os
import time
from unittest.mock import MagicMock, patch, call

import pytest

# Skip if dependencies not available
if os.environ.get("VESSELS_FULL_DEPS", "").lower() not in ("1", "true", "yes"):
    pytest.skip("FalkorDB dependencies not available", allow_module_level=True)

from redis.exceptions import ConnectionError, TimeoutError

from vessels.core.config import Settings
from vessels.db.connection import (
    FalkorDBConnection,
    FalkorDBConnectionError,
    FalkorDBNotReadyError,
)


class TestFalkorDBModuleDetection:
    """Tests for detecting FalkorDB graph module."""

    @pytest.fixture
    def settings(self) -> Settings:
        return Settings(falkordb_host="localhost", falkordb_port=6379)

    def test_detects_graph_module(self, settings):
        """Test detection of 'graph' module name."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.module_list.return_value = [
            {"name": "graph", "ver": 20000},
            {"name": "search", "ver": 10000},
        ]
        mock_redis.info.return_value = {"loading": 0}

        mock_client = MagicMock()
        mock_graph = MagicMock()
        mock_result = MagicMock()
        mock_result.result_set = [[1]]
        mock_graph.query.return_value = mock_result
        mock_client.select_graph.return_value = mock_graph

        with patch("vessels.db.connection.Redis", return_value=mock_redis):
            with patch("vessels.db.connection.FalkorDB", return_value=mock_client):
                conn = FalkorDBConnection(settings)
                conn.connect()
                assert conn._check_database_ready() is True

    def test_detects_falkordb_module(self, settings):
        """Test detection of 'falkordb' module name."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.module_list.return_value = [
            {"name": "falkordb", "ver": 40000},
        ]
        mock_redis.info.return_value = {"loading": 0}

        mock_client = MagicMock()
        mock_graph = MagicMock()
        mock_result = MagicMock()
        mock_result.result_set = [[1]]
        mock_graph.query.return_value = mock_result
        mock_client.select_graph.return_value = mock_graph

        with patch("vessels.db.connection.Redis", return_value=mock_redis):
            with patch("vessels.db.connection.FalkorDB", return_value=mock_client):
                conn = FalkorDBConnection(settings)
                conn.connect()
                assert conn._check_database_ready() is True

    def test_fails_without_graph_module(self, settings):
        """Test failure when graph module is not loaded."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.module_list.return_value = [
            {"name": "search", "ver": 10000},
            {"name": "json", "ver": 20000},
        ]

        mock_client = MagicMock()

        with patch("vessels.db.connection.Redis", return_value=mock_redis):
            with patch("vessels.db.connection.FalkorDB", return_value=mock_client):
                conn = FalkorDBConnection(settings)
                conn.connect()

                with pytest.raises(FalkorDBNotReadyError, match="graph module not loaded"):
                    conn._check_database_ready()

    def test_fails_with_empty_module_list(self, settings):
        """Test failure when no modules are loaded."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.module_list.return_value = []

        mock_client = MagicMock()

        with patch("vessels.db.connection.Redis", return_value=mock_redis):
            with patch("vessels.db.connection.FalkorDB", return_value=mock_client):
                conn = FalkorDBConnection(settings)
                conn.connect()

                with pytest.raises(FalkorDBNotReadyError, match="graph module not loaded"):
                    conn._check_database_ready()

    def test_case_insensitive_module_detection(self, settings):
        """Test that module detection is case-insensitive."""
        for module_name in ["GRAPH", "Graph", "FALKORDB", "FalkorDB", "FalkorDb"]:
            mock_redis = MagicMock()
            mock_redis.ping.return_value = True
            mock_redis.module_list.return_value = [{"name": module_name, "ver": 20000}]
            mock_redis.info.return_value = {"loading": 0}

            mock_client = MagicMock()
            mock_graph = MagicMock()
            mock_result = MagicMock()
            mock_result.result_set = [[1]]
            mock_graph.query.return_value = mock_result
            mock_client.select_graph.return_value = mock_graph

            with patch("vessels.db.connection.Redis", return_value=mock_redis):
                with patch("vessels.db.connection.FalkorDB", return_value=mock_client):
                    conn = FalkorDBConnection(settings)
                    conn.connect()
                    assert conn._check_database_ready() is True, f"Failed for module name: {module_name}"


class TestFalkorDBLoadingState:
    """Tests for detecting database loading state."""

    @pytest.fixture
    def settings(self) -> Settings:
        return Settings(falkordb_host="localhost", falkordb_port=6379)

    def test_fails_when_still_loading(self, settings):
        """Test failure when database is still loading from disk."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.module_list.return_value = [{"name": "graph", "ver": 20000}]
        mock_redis.info.return_value = {"loading": 1}  # Still loading

        mock_client = MagicMock()
        mock_graph = MagicMock()
        mock_result = MagicMock()
        mock_result.result_set = [[1]]
        mock_graph.query.return_value = mock_result
        mock_client.select_graph.return_value = mock_graph

        with patch("vessels.db.connection.Redis", return_value=mock_redis):
            with patch("vessels.db.connection.FalkorDB", return_value=mock_client):
                conn = FalkorDBConnection(settings)
                conn.connect()

                with pytest.raises(FalkorDBNotReadyError, match="still loading"):
                    conn._check_database_ready()

    def test_succeeds_when_loading_complete(self, settings):
        """Test success when loading is complete."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.module_list.return_value = [{"name": "graph", "ver": 20000}]
        mock_redis.info.return_value = {"loading": 0}  # Done loading

        mock_client = MagicMock()
        mock_graph = MagicMock()
        mock_result = MagicMock()
        mock_result.result_set = [[1]]
        mock_graph.query.return_value = mock_result
        mock_client.select_graph.return_value = mock_graph

        with patch("vessels.db.connection.Redis", return_value=mock_redis):
            with patch("vessels.db.connection.FalkorDB", return_value=mock_client):
                conn = FalkorDBConnection(settings)
                conn.connect()
                assert conn._check_database_ready() is True

    def test_handles_missing_loading_key(self, settings):
        """Test handling when loading key is not present in info."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.module_list.return_value = [{"name": "graph", "ver": 20000}]
        mock_redis.info.return_value = {}  # No loading key

        mock_client = MagicMock()
        mock_graph = MagicMock()
        mock_result = MagicMock()
        mock_result.result_set = [[1]]
        mock_graph.query.return_value = mock_result
        mock_client.select_graph.return_value = mock_graph

        with patch("vessels.db.connection.Redis", return_value=mock_redis):
            with patch("vessels.db.connection.FalkorDB", return_value=mock_client):
                conn = FalkorDBConnection(settings)
                conn.connect()
                # Should default to not loading (loading: 0)
                assert conn._check_database_ready() is True


class TestGraphOperationsVerification:
    """Tests for verifying graph operations work before proceeding."""

    @pytest.fixture
    def settings(self) -> Settings:
        return Settings(falkordb_host="localhost", falkordb_port=6379)

    def test_verifies_graph_query_works(self, settings):
        """Test that graph query is executed to verify operations."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.module_list.return_value = [{"name": "graph", "ver": 20000}]
        mock_redis.info.return_value = {"loading": 0}

        mock_client = MagicMock()
        mock_graph = MagicMock()
        mock_result = MagicMock()
        mock_result.result_set = [[1]]
        mock_graph.query.return_value = mock_result
        mock_client.select_graph.return_value = mock_graph

        with patch("vessels.db.connection.Redis", return_value=mock_redis):
            with patch("vessels.db.connection.FalkorDB", return_value=mock_client):
                conn = FalkorDBConnection(settings)
                conn.connect()
                conn._check_database_ready()

                # Verify health check graph was created
                mock_client.select_graph.assert_called_with("__health_check__")
                # Verify query was executed
                mock_graph.query.assert_called()

    def test_fails_when_query_returns_empty(self, settings):
        """Test failure when graph query returns empty result."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.module_list.return_value = [{"name": "graph", "ver": 20000}]
        mock_redis.info.return_value = {"loading": 0}

        mock_client = MagicMock()
        mock_graph = MagicMock()
        mock_result = MagicMock()
        mock_result.result_set = []  # Empty result
        mock_graph.query.return_value = mock_result
        mock_client.select_graph.return_value = mock_graph

        with patch("vessels.db.connection.Redis", return_value=mock_redis):
            with patch("vessels.db.connection.FalkorDB", return_value=mock_client):
                conn = FalkorDBConnection(settings)
                conn.connect()

                with pytest.raises(FalkorDBNotReadyError, match="no results"):
                    conn._check_database_ready()

    def test_cleans_up_health_check_graph(self, settings):
        """Test that health check graph is cleaned up after verification."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.module_list.return_value = [{"name": "graph", "ver": 20000}]
        mock_redis.info.return_value = {"loading": 0}
        mock_redis.delete.return_value = 1

        mock_client = MagicMock()
        mock_graph = MagicMock()
        mock_result = MagicMock()
        mock_result.result_set = [[1]]
        mock_graph.query.return_value = mock_result
        mock_client.select_graph.return_value = mock_graph

        with patch("vessels.db.connection.Redis", return_value=mock_redis):
            with patch("vessels.db.connection.FalkorDB", return_value=mock_client):
                conn = FalkorDBConnection(settings)
                conn.connect()
                conn._check_database_ready()

                # Verify cleanup was attempted
                mock_redis.delete.assert_called_with("__health_check__")


class TestWaitForReady:
    """Tests for wait_for_ready functionality."""

    @pytest.fixture
    def settings(self) -> Settings:
        return Settings(falkordb_host="localhost", falkordb_port=6379)

    def test_returns_true_when_immediately_ready(self, settings):
        """Test immediate return when database is ready."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.module_list.return_value = [{"name": "graph", "ver": 20000}]
        mock_redis.info.return_value = {"loading": 0}

        mock_client = MagicMock()
        mock_graph = MagicMock()
        mock_result = MagicMock()
        mock_result.result_set = [[1]]
        mock_graph.query.return_value = mock_result
        mock_client.select_graph.return_value = mock_graph

        with patch("vessels.db.connection.Redis", return_value=mock_redis):
            with patch("vessels.db.connection.FalkorDB", return_value=mock_client):
                conn = FalkorDBConnection(settings)
                conn.connect()

                start = time.time()
                result = conn.wait_for_ready(timeout=10)
                elapsed = time.time() - start

                assert result is True
                assert elapsed < 2  # Should be nearly instant

    def test_waits_until_ready(self, settings):
        """Test waiting for database to become ready."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.module_list.return_value = [{"name": "graph", "ver": 20000}]

        # First few calls show loading, then ready
        call_count = [0]

        def info_side_effect(*args):
            call_count[0] += 1
            if call_count[0] < 3:
                return {"loading": 1}
            return {"loading": 0}

        mock_redis.info.side_effect = info_side_effect

        mock_client = MagicMock()
        mock_graph = MagicMock()
        mock_result = MagicMock()
        mock_result.result_set = [[1]]
        mock_graph.query.return_value = mock_result
        mock_client.select_graph.return_value = mock_graph

        with patch("vessels.db.connection.Redis", return_value=mock_redis):
            with patch("vessels.db.connection.FalkorDB", return_value=mock_client):
                conn = FalkorDBConnection(settings)
                conn.connect()

                result = conn.wait_for_ready(timeout=10, check_interval=0.1)
                assert result is True
                assert call_count[0] >= 3

    def test_returns_false_on_timeout(self, settings):
        """Test timeout when database never becomes ready."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.module_list.return_value = [{"name": "graph", "ver": 20000}]
        mock_redis.info.return_value = {"loading": 1}  # Always loading

        mock_client = MagicMock()
        mock_graph = MagicMock()
        mock_result = MagicMock()
        mock_result.result_set = [[1]]
        mock_graph.query.return_value = mock_result
        mock_client.select_graph.return_value = mock_graph

        with patch("vessels.db.connection.Redis", return_value=mock_redis):
            with patch("vessels.db.connection.FalkorDB", return_value=mock_client):
                conn = FalkorDBConnection(settings)
                conn.connect()

                start = time.time()
                result = conn.wait_for_ready(timeout=1, check_interval=0.1)
                elapsed = time.time() - start

                assert result is False
                assert elapsed >= 1
                assert elapsed < 2


class TestConnectionRetry:
    """Tests for connection retry logic."""

    @pytest.fixture
    def settings(self) -> Settings:
        return Settings(falkordb_host="localhost", falkordb_port=6379)

    def test_retries_on_connection_error(self, settings):
        """Test that connection is retried on ConnectionError."""
        call_count = [0]

        def falkordb_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("Connection refused")
            return MagicMock()

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch("vessels.db.connection.FalkorDB", side_effect=falkordb_side_effect):
            with patch("vessels.db.connection.Redis", return_value=mock_redis):
                conn = FalkorDBConnection(settings)

                # Should succeed after retries
                conn.connect()
                assert call_count[0] == 3

    def test_retries_on_timeout_error(self, settings):
        """Test that connection is retried on TimeoutError."""
        call_count = [0]

        def falkordb_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 2:
                raise TimeoutError("Connection timed out")
            return MagicMock()

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch("vessels.db.connection.FalkorDB", side_effect=falkordb_side_effect):
            with patch("vessels.db.connection.Redis", return_value=mock_redis):
                conn = FalkorDBConnection(settings)
                conn.connect()
                assert call_count[0] == 2

    def test_fails_after_max_retries(self, settings):
        """Test that connection fails after max retries."""
        with patch("vessels.db.connection.FalkorDB", side_effect=ConnectionError("Connection refused")):
            with patch("vessels.db.connection.Redis", side_effect=ConnectionError("Connection refused")):
                conn = FalkorDBConnection(settings)

                with pytest.raises(FalkorDBConnectionError):
                    conn.connect()


class TestDatabaseInfo:
    """Tests for database info retrieval."""

    @pytest.fixture
    def settings(self) -> Settings:
        return Settings(falkordb_host="localhost", falkordb_port=6379)

    def test_returns_complete_info(self, settings):
        """Test that complete database info is returned."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.info.return_value = {
            "redis_version": "7.2.0",
            "uptime_in_seconds": 3600,
            "connected_clients": 5,
            "used_memory_human": "10M",
            "loading": 0,
            "db0": {"keys": 100},
        }
        mock_redis.module_list.return_value = [
            {"name": "graph", "ver": 20000},
            {"name": "search", "ver": 10000},
        ]

        mock_client = MagicMock()

        with patch("vessels.db.connection.Redis", return_value=mock_redis):
            with patch("vessels.db.connection.FalkorDB", return_value=mock_client):
                conn = FalkorDBConnection(settings)
                conn.connect()

                info = conn.get_database_info()

                assert info["connected"] is True
                assert info["host"] == "localhost"
                assert info["port"] == 6379
                assert info["redis_version"] == "7.2.0"
                assert info["uptime_seconds"] == 3600
                assert info["connected_clients"] == 5
                assert info["used_memory_human"] == "10M"
                assert info["loading"] is False
                assert "graph" in info["modules"]

    def test_returns_disconnected_info(self, settings):
        """Test info when not connected."""
        conn = FalkorDBConnection(settings)
        info = conn.get_database_info()

        assert info["connected"] is False
