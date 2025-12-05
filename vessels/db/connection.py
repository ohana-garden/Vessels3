"""
FalkorDB connection management for Vessels.

Provides a robust connection handler with retry logic and health checks
to ensure FalkorDB is fully loaded before operations begin.
"""

import time
from typing import Optional

import structlog
from falkordb import FalkorDB
from redis import Redis
from redis.exceptions import ConnectionError, TimeoutError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from vessels.core.config import Settings, get_settings

logger = structlog.get_logger(__name__)


class FalkorDBConnectionError(Exception):
    """Raised when FalkorDB connection fails."""

    pass


class FalkorDBNotReadyError(Exception):
    """Raised when FalkorDB is not fully loaded."""

    pass


class FalkorDBConnection:
    """
    Manages FalkorDB connection with health checking and retry logic.

    Ensures the database is fully loaded and ready before allowing operations.
    """

    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize the connection manager.

        Args:
            settings: Application settings. If None, loads from environment.
        """
        self.settings = settings or get_settings()
        self._client: Optional[FalkorDB] = None
        self._redis: Optional[Redis] = None
        self._connected = False

    @property
    def client(self) -> FalkorDB:
        """Get the FalkorDB client, connecting if necessary."""
        if not self._client or not self._connected:
            self.connect()
        return self._client

    @property
    def redis(self) -> Redis:
        """Get the underlying Redis client."""
        if not self._redis or not self._connected:
            self.connect()
        return self._redis

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def connect(self) -> "FalkorDBConnection":
        """
        Connect to FalkorDB with retry logic.

        Returns:
            Self for method chaining.

        Raises:
            FalkorDBConnectionError: If connection fails after retries.
        """
        try:
            logger.info(
                "connecting_to_falkordb",
                host=self.settings.falkordb_host,
                port=self.settings.falkordb_port,
            )

            self._client = FalkorDB(
                host=self.settings.falkordb_host,
                port=self.settings.falkordb_port,
                password=self.settings.falkordb_password,
            )

            # Also create a raw Redis connection for health checks
            self._redis = Redis(
                host=self.settings.falkordb_host,
                port=self.settings.falkordb_port,
                password=self.settings.falkordb_password,
                decode_responses=True,
            )

            # Verify connection
            self._redis.ping()
            self._connected = True

            logger.info("falkordb_connected")
            return self

        except Exception as e:
            logger.error("falkordb_connection_failed", error=str(e))
            raise FalkorDBConnectionError(f"Failed to connect to FalkorDB: {e}") from e

    def disconnect(self) -> None:
        """Disconnect from FalkorDB."""
        if self._redis:
            self._redis.close()
        self._client = None
        self._redis = None
        self._connected = False
        logger.info("falkordb_disconnected")

    def is_connected(self) -> bool:
        """Check if currently connected."""
        if not self._connected or not self._redis:
            return False
        try:
            self._redis.ping()
            return True
        except Exception:
            self._connected = False
            return False

    def wait_for_ready(self, timeout: int = 60, check_interval: float = 1.0) -> bool:
        """
        Wait for FalkorDB to be fully loaded and ready.

        Args:
            timeout: Maximum seconds to wait.
            check_interval: Seconds between health checks.

        Returns:
            True if database is ready, False if timeout reached.

        Raises:
            FalkorDBNotReadyError: If database fails health checks.
        """
        start_time = time.time()
        last_error = None

        logger.info("waiting_for_falkordb_ready", timeout=timeout)

        while time.time() - start_time < timeout:
            try:
                if self._check_database_ready():
                    logger.info(
                        "falkordb_ready",
                        elapsed=round(time.time() - start_time, 2),
                    )
                    return True
            except Exception as e:
                last_error = e
                logger.debug("falkordb_not_ready_yet", error=str(e))

            time.sleep(check_interval)

        logger.error(
            "falkordb_ready_timeout",
            timeout=timeout,
            last_error=str(last_error) if last_error else None,
        )
        return False

    def _check_database_ready(self) -> bool:
        """
        Perform comprehensive health check on FalkorDB.

        Returns:
            True if all checks pass.
        """
        if not self.is_connected():
            self.connect()

        # Check 1: Basic ping
        self._redis.ping()

        # Check 2: Verify FalkorDB module is loaded
        modules = self._redis.module_list()
        graph_module_loaded = any(
            mod.get("name", "").lower() in ("graph", "falkordb")
            for mod in modules
        )
        if not graph_module_loaded:
            raise FalkorDBNotReadyError("FalkorDB graph module not loaded")

        # Check 3: Verify we can perform a simple graph operation
        test_graph = self._client.select_graph("__health_check__")
        try:
            # Simple query to verify graph operations work
            result = test_graph.query("RETURN 1 as test")
            if not result.result_set:
                raise FalkorDBNotReadyError("Graph query returned no results")
        finally:
            # Clean up health check graph
            try:
                self._redis.delete("__health_check__")
            except Exception:
                pass  # Ignore cleanup errors

        # Check 4: Check memory info to ensure data is loaded
        info = self._redis.info("memory")
        if info.get("loading", 0) == 1:
            raise FalkorDBNotReadyError("Database is still loading data from disk")

        return True

    def get_database_info(self) -> dict:
        """
        Get information about the FalkorDB instance.

        Returns:
            Dictionary with database status and metrics.
        """
        if not self.is_connected():
            return {"connected": False}

        try:
            info = self._redis.info()
            modules = self._redis.module_list()

            return {
                "connected": True,
                "host": self.settings.falkordb_host,
                "port": self.settings.falkordb_port,
                "redis_version": info.get("redis_version"),
                "uptime_seconds": info.get("uptime_in_seconds"),
                "connected_clients": info.get("connected_clients"),
                "used_memory_human": info.get("used_memory_human"),
                "total_keys": info.get("db0", {}).get("keys", 0) if "db0" in info else 0,
                "modules": [m.get("name") for m in modules],
                "loading": info.get("loading", 0) == 1,
            }
        except Exception as e:
            logger.error("get_database_info_failed", error=str(e))
            return {"connected": False, "error": str(e)}

    def __enter__(self) -> "FalkorDBConnection":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.disconnect()
