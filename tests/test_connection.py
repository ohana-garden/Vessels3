"""
Unit tests for FalkorDB connection module.
"""

from unittest.mock import MagicMock, patch

import pytest
from redis.exceptions import ConnectionError

from vessels.core.config import Settings
from vessels.db.connection import (
    FalkorDBConnection,
    FalkorDBConnectionError,
    FalkorDBNotReadyError,
)


class TestFalkorDBConnection:
    """Tests for FalkorDBConnection class."""

    @pytest.fixture
    def settings(self) -> Settings:
        """Create test settings."""
        return Settings(
            falkordb_host="localhost",
            falkordb_port=6379,
            falkordb_password=None,
        )

    def test_init_with_settings(self, settings):
        """Test initialization with explicit settings."""
        conn = FalkorDBConnection(settings)
        assert conn.settings == settings
        assert conn._client is None
        assert conn._connected is False

    def test_init_without_settings(self):
        """Test initialization loads settings automatically."""
        with patch("vessels.db.connection.get_settings") as mock_get:
            mock_settings = MagicMock()
            mock_get.return_value = mock_settings

            conn = FalkorDBConnection()
            assert conn.settings == mock_settings

    def test_connect_success(self, settings, mock_redis, mock_falkordb):
        """Test successful connection."""
        conn = FalkorDBConnection(settings)
        result = conn.connect()

        assert result is conn
        assert conn._connected is True
        mock_redis.ping.assert_called()

    def test_connect_failure(self, settings):
        """Test connection failure raises error."""
        with patch("vessels.db.connection.FalkorDB") as mock_fdb:
            mock_fdb.side_effect = ConnectionError("Connection refused")

            conn = FalkorDBConnection(settings)

            with pytest.raises(FalkorDBConnectionError):
                conn.connect()

    def test_disconnect(self, settings, mock_redis, mock_falkordb):
        """Test disconnection."""
        conn = FalkorDBConnection(settings)
        conn.connect()
        conn.disconnect()

        assert conn._client is None
        assert conn._redis is None
        assert conn._connected is False

    def test_is_connected_true(self, settings, mock_redis, mock_falkordb):
        """Test is_connected returns True when connected."""
        conn = FalkorDBConnection(settings)
        conn.connect()

        assert conn.is_connected() is True

    def test_is_connected_false(self, settings):
        """Test is_connected returns False when not connected."""
        conn = FalkorDBConnection(settings)
        assert conn.is_connected() is False

    def test_is_connected_after_disconnect(self, settings, mock_redis, mock_falkordb):
        """Test is_connected returns False after disconnect."""
        conn = FalkorDBConnection(settings)
        conn.connect()
        conn.disconnect()

        assert conn.is_connected() is False

    def test_context_manager(self, settings, mock_redis, mock_falkordb):
        """Test connection as context manager."""
        with FalkorDBConnection(settings) as conn:
            assert conn._connected is True

        # After context exit, should be disconnected
        assert conn._connected is False

    def test_get_database_info_connected(self, settings, mock_redis, mock_falkordb):
        """Test getting database info when connected."""
        conn = FalkorDBConnection(settings)
        conn.connect()

        info = conn.get_database_info()

        assert info["connected"] is True
        assert "host" in info
        assert "port" in info

    def test_get_database_info_disconnected(self, settings):
        """Test getting database info when not connected."""
        conn = FalkorDBConnection(settings)
        info = conn.get_database_info()

        assert info["connected"] is False


class TestFalkorDBConnectionHealthCheck:
    """Tests for health check functionality."""

    @pytest.fixture
    def settings(self) -> Settings:
        """Create test settings."""
        return Settings(
            falkordb_host="localhost",
            falkordb_port=6379,
        )

    def test_check_database_ready_success(self, settings, mock_redis, mock_falkordb):
        """Test successful database readiness check."""
        conn = FalkorDBConnection(settings)
        conn.connect()

        # Should not raise
        assert conn._check_database_ready() is True

    def test_check_database_ready_no_module(self, settings):
        """Test readiness check fails when graph module not loaded."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.module_list.return_value = []  # No modules
        mock_redis.info.return_value = {"loading": 0}

        mock_client = MagicMock()

        with patch("vessels.db.connection.Redis", return_value=mock_redis):
            with patch("vessels.db.connection.FalkorDB", return_value=mock_client):
                conn = FalkorDBConnection(settings)
                conn.connect()

                with pytest.raises(FalkorDBNotReadyError, match="graph module not loaded"):
                    conn._check_database_ready()

    def test_check_database_ready_still_loading(self, settings):
        """Test readiness check fails when database is loading."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.module_list.return_value = [{"name": "graph"}]
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

    def test_wait_for_ready_success(self, settings, mock_redis, mock_falkordb):
        """Test wait_for_ready succeeds when database is ready."""
        conn = FalkorDBConnection(settings)
        conn.connect()

        result = conn.wait_for_ready(timeout=5)
        assert result is True

    def test_wait_for_ready_timeout(self, settings):
        """Test wait_for_ready times out when database never ready."""
        mock_redis = MagicMock()
        mock_redis.ping.side_effect = ConnectionError("Not ready")

        with patch("vessels.db.connection.Redis", return_value=mock_redis):
            with patch("vessels.db.connection.FalkorDB"):
                conn = FalkorDBConnection(settings)
                conn._redis = mock_redis
                conn._connected = True

                result = conn.wait_for_ready(timeout=1, check_interval=0.1)
                assert result is False
