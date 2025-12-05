"""
Unit tests for Vessels graph operations.

These tests require FalkorDB dependencies (redis, falkordb).
Set VESSELS_FULL_DEPS=true to run them.
"""

import os

# Check dependencies before importing anything that needs them
if os.environ.get("VESSELS_FULL_DEPS", "").lower() not in ("1", "true", "yes"):
    import pytest
    pytest.skip("FalkorDB dependencies not available", allow_module_level=True)

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from vessels.core.config import Settings
from vessels.db.connection import FalkorDBConnection
from vessels.db.graph import Connection, Vessel, VesselsGraph


class MockNode:
    """Mock FalkorDB node."""

    def __init__(self, properties: dict):
        self.properties = properties


class MockEdge:
    """Mock FalkorDB edge."""

    def __init__(self, properties: dict):
        self.properties = properties


class TestVessel:
    """Tests for Vessel dataclass."""

    def test_from_node(self):
        """Test creating Vessel from node properties."""
        props = {
            "id": "vessel-1",
            "name": "Test Vessel",
            "vessel_type": "container",
            "created_at": "2024-01-01T00:00:00",
            "metadata": "{'key': 'value'}",
        }

        vessel = Vessel.from_node(props)

        assert vessel.id == "vessel-1"
        assert vessel.name == "Test Vessel"
        assert vessel.vessel_type == "container"

    def test_from_node_with_properties_wrapper(self):
        """Test creating Vessel from node with properties wrapper."""
        node = {"properties": {"id": "v1", "name": "Test"}}
        vessel = Vessel.from_node(node)

        assert vessel.id == "v1"
        assert vessel.name == "Test"


class TestConnection:
    """Tests for Connection dataclass."""

    def test_from_edge(self):
        """Test creating Connection from edge properties."""
        props = {
            "source_id": "v1",
            "target_id": "v2",
            "connection_type": "link",
            "weight": 0.5,
            "created_at": "2024-01-01T00:00:00",
        }

        conn = Connection.from_edge(props)

        assert conn.source_id == "v1"
        assert conn.target_id == "v2"
        assert conn.connection_type == "link"
        assert conn.weight == 0.5


class TestVesselsGraph:
    """Tests for VesselsGraph class."""

    @pytest.fixture
    def mock_connection(self) -> MagicMock:
        """Create a mock FalkorDB connection."""
        mock_conn = MagicMock(spec=FalkorDBConnection)
        mock_client = MagicMock()
        mock_graph = MagicMock()

        mock_conn.client = mock_client
        mock_client.select_graph.return_value = mock_graph

        return mock_conn

    @pytest.fixture
    def graph(self, mock_connection) -> VesselsGraph:
        """Create a VesselsGraph instance with mocked connection."""
        return VesselsGraph(mock_connection, "test_graph")

    def test_init(self, mock_connection):
        """Test graph initialization."""
        graph = VesselsGraph(mock_connection, "my_graph")

        assert graph.connection == mock_connection
        assert graph.graph_name == "my_graph"

    def test_graph_property(self, graph, mock_connection):
        """Test graph property selects correct graph."""
        _ = graph.graph
        mock_connection.client.select_graph.assert_called_with("test_graph")

    def test_initialize_schema(self, graph):
        """Test schema initialization creates indexes."""
        mock_result = MagicMock()
        graph.graph.query.return_value = mock_result

        graph.initialize_schema()

        # Should create indexes
        assert graph.graph.query.call_count >= 2

    def test_create_vessel(self, graph):
        """Test creating a vessel."""
        mock_result = MagicMock()
        mock_result.result_set = [[MockNode({"id": "v1", "name": "Test"})]]
        graph.graph.query.return_value = mock_result

        vessel = graph.create_vessel(
            vessel_id="v1",
            name="Test Vessel",
            vessel_type="container",
            metadata={"key": "value"},
        )

        assert vessel.id == "v1"
        assert vessel.name == "Test Vessel"
        assert vessel.vessel_type == "container"

        # Verify query was called
        graph.graph.query.assert_called_once()
        call_args = graph.graph.query.call_args
        assert "CREATE" in call_args[0][0]

    def test_get_vessel_found(self, graph):
        """Test getting an existing vessel."""
        mock_node = MockNode({
            "id": "v1",
            "name": "Test",
            "vessel_type": "default",
            "created_at": datetime.now().isoformat(),
            "metadata": "{}",
        })
        mock_result = MagicMock()
        mock_result.result_set = [[mock_node]]
        graph.graph.query.return_value = mock_result

        vessel = graph.get_vessel("v1")

        assert vessel is not None
        assert vessel.id == "v1"

    def test_get_vessel_not_found(self, graph):
        """Test getting a non-existent vessel."""
        mock_result = MagicMock()
        mock_result.result_set = []
        graph.graph.query.return_value = mock_result

        vessel = graph.get_vessel("nonexistent")

        assert vessel is None

    def test_list_vessels(self, graph):
        """Test listing vessels."""
        mock_nodes = [
            MockNode({"id": "v1", "name": "Vessel 1", "vessel_type": "a", "created_at": datetime.now().isoformat(), "metadata": "{}"}),
            MockNode({"id": "v2", "name": "Vessel 2", "vessel_type": "b", "created_at": datetime.now().isoformat(), "metadata": "{}"}),
        ]
        mock_result = MagicMock()
        mock_result.result_set = [[n] for n in mock_nodes]
        graph.graph.query.return_value = mock_result

        vessels = graph.list_vessels()

        assert len(vessels) == 2
        assert vessels[0].id == "v1"
        assert vessels[1].id == "v2"

    def test_list_vessels_by_type(self, graph):
        """Test listing vessels filtered by type."""
        mock_result = MagicMock()
        mock_result.result_set = []
        graph.graph.query.return_value = mock_result

        graph.list_vessels(vessel_type="container")

        call_args = graph.graph.query.call_args
        assert "vessel_type" in call_args[0][0]

    def test_update_vessel(self, graph):
        """Test updating a vessel."""
        # First call for update, second for get
        mock_node = MockNode({
            "id": "v1",
            "name": "Updated",
            "vessel_type": "default",
            "created_at": datetime.now().isoformat(),
            "metadata": "{}",
        })
        mock_result = MagicMock()
        mock_result.result_set = [[mock_node]]
        graph.graph.query.return_value = mock_result

        vessel = graph.update_vessel("v1", name="Updated")

        assert vessel is not None
        # Verify SET was in query
        call_args = graph.graph.query.call_args_list[0]
        assert "SET" in call_args[0][0]

    def test_delete_vessel(self, graph):
        """Test deleting a vessel."""
        # Mock get_vessel to return a vessel
        mock_node = MockNode({
            "id": "v1",
            "name": "Test",
            "vessel_type": "default",
            "created_at": datetime.now().isoformat(),
            "metadata": "{}",
        })
        mock_result = MagicMock()
        mock_result.result_set = [[mock_node]]
        graph.graph.query.return_value = mock_result

        result = graph.delete_vessel("v1")

        assert result is True
        # Verify DELETE was called
        calls = [str(c) for c in graph.graph.query.call_args_list]
        assert any("DELETE" in c for c in calls)

    def test_delete_vessel_not_found(self, graph):
        """Test deleting a non-existent vessel."""
        mock_result = MagicMock()
        mock_result.result_set = []
        graph.graph.query.return_value = mock_result

        result = graph.delete_vessel("nonexistent")

        assert result is False

    def test_create_connection(self, graph):
        """Test creating a connection between vessels."""
        mock_edge = MockEdge({
            "source_id": "v1",
            "target_id": "v2",
            "connection_type": "link",
            "weight": 1.0,
            "created_at": datetime.now().isoformat(),
        })
        mock_result = MagicMock()
        mock_result.result_set = [[mock_edge]]
        graph.graph.query.return_value = mock_result

        conn = graph.create_connection("v1", "v2", "link", 1.0)

        assert conn is not None
        assert conn.source_id == "v1"
        assert conn.target_id == "v2"

    def test_create_connection_vessels_not_found(self, graph):
        """Test creating connection when vessels don't exist."""
        mock_result = MagicMock()
        mock_result.result_set = []
        graph.graph.query.return_value = mock_result

        conn = graph.create_connection("nonexistent1", "nonexistent2")

        assert conn is None

    def test_get_connections_outgoing(self, graph):
        """Test getting outgoing connections."""
        mock_edge = MockEdge({
            "source_id": "v1",
            "target_id": "v2",
            "connection_type": "link",
            "weight": 1.0,
            "created_at": datetime.now().isoformat(),
        })
        mock_result = MagicMock()
        mock_result.result_set = [[mock_edge]]
        graph.graph.query.return_value = mock_result

        connections = graph.get_connections("v1", direction="outgoing")

        assert len(connections) == 1
        assert connections[0].source_id == "v1"

    def test_delete_connection(self, graph):
        """Test deleting a connection."""
        mock_result = MagicMock()
        mock_result.result_set = [[1]]  # 1 deleted
        graph.graph.query.return_value = mock_result

        result = graph.delete_connection("v1", "v2")

        assert result is True

    def test_find_path(self, graph):
        """Test finding path between vessels."""
        mock_result = MagicMock()
        mock_result.result_set = [[["v1", "v2", "v3"]]]
        graph.graph.query.return_value = mock_result

        path = graph.find_path("v1", "v3")

        assert path == ["v1", "v2", "v3"]

    def test_find_path_not_found(self, graph):
        """Test finding path when no path exists."""
        mock_result = MagicMock()
        mock_result.result_set = []
        graph.graph.query.return_value = mock_result

        path = graph.find_path("v1", "v100")

        assert path == []

    def test_get_statistics(self, graph):
        """Test getting graph statistics."""
        # Mock different query results
        mock_results = [
            MagicMock(result_set=[[10]]),  # total vessels
            MagicMock(result_set=[[5]]),   # total connections
            MagicMock(result_set=[["type1", 5], ["type2", 5]]),  # by type
            MagicMock(result_set=[["link", 5]]),  # connections by type
        ]
        graph.graph.query.side_effect = mock_results

        stats = graph.get_statistics()

        assert stats["total_vessels"] == 10
        assert stats["total_connections"] == 5

    def test_clear_graph(self, graph):
        """Test clearing all data from graph."""
        mock_result = MagicMock()
        graph.graph.query.return_value = mock_result

        graph.clear_graph()

        call_args = graph.graph.query.call_args
        assert "DETACH DELETE" in call_args[0][0]
