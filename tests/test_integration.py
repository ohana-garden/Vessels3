"""
Integration tests for Vessels running from FalkorDB.

These tests verify the complete workflow:
1. Connection establishment
2. Graph initialization
3. Full CRUD operations
4. Relationship traversal
5. Data persistence verification
"""

import os
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Skip if dependencies not available
if os.environ.get("VESSELS_FULL_DEPS", "").lower() not in ("1", "true", "yes"):
    pytest.skip("FalkorDB dependencies not available", allow_module_level=True)

from vessels.core.config import Settings
from vessels.db.connection import FalkorDBConnection
from vessels.db.graph import VesselsGraph, Vessel, Connection


class MockQueryResult:
    """Mock for FalkorDB query results."""

    def __init__(self, result_set=None):
        self.result_set = result_set or []


class MockNode:
    """Mock for FalkorDB nodes."""

    def __init__(self, properties):
        self.properties = properties


class MockEdge:
    """Mock for FalkorDB edges."""

    def __init__(self, properties):
        self.properties = properties


class TestVesselsFullWorkflow:
    """Tests for complete Vessels workflow running from FalkorDB."""

    @pytest.fixture
    def mock_graph_connection(self):
        """Create a comprehensive mock graph connection."""
        # Storage for simulated graph data
        vessels_store = {}
        connections_store = []

        mock_graph = MagicMock()

        def query_handler(cypher, params=None):
            params = params or {}

            # Handle CREATE vessel
            if "CREATE (v:Vessel" in cypher:
                vessel_id = params.get("id")
                vessels_store[vessel_id] = {
                    "id": vessel_id,
                    "name": params.get("name"),
                    "vessel_type": params.get("vessel_type", "default"),
                    "created_at": params.get("created_at", datetime.now().isoformat()),
                    "metadata": params.get("metadata", "{}"),
                }
                node = MockNode(vessels_store[vessel_id])
                return MockQueryResult([[node]])

            # Handle MATCH vessel by ID
            if "MATCH (v:Vessel {id: $id})" in cypher and "DELETE" not in cypher and "SET" not in cypher:
                vessel_id = params.get("id")
                if vessel_id in vessels_store:
                    node = MockNode(vessels_store[vessel_id])
                    return MockQueryResult([[node]])
                return MockQueryResult([])

            # Handle MATCH vessel by name
            if "MATCH (v:Vessel {name: $name})" in cypher:
                name = params.get("name")
                for v in vessels_store.values():
                    if v["name"] == name:
                        return MockQueryResult([[MockNode(v)]])
                return MockQueryResult([])

            # Handle list all vessels
            if "MATCH (v:Vessel)" in cypher and "RETURN v LIMIT" in cypher:
                nodes = [MockNode(v) for v in vessels_store.values()]
                return MockQueryResult([[n] for n in nodes])

            # Handle vessel by type
            if "MATCH (v:Vessel {vessel_type: $type})" in cypher:
                vessel_type = params.get("type")
                nodes = [MockNode(v) for v in vessels_store.values() if v["vessel_type"] == vessel_type]
                return MockQueryResult([[n] for n in nodes])

            # Handle UPDATE vessel
            if "MATCH (v:Vessel {id: $id})" in cypher and "SET" in cypher:
                vessel_id = params.get("id")
                if vessel_id in vessels_store:
                    if "name" in params:
                        vessels_store[vessel_id]["name"] = params["name"]
                    if "type" in params:
                        vessels_store[vessel_id]["vessel_type"] = params["type"]
                    if "metadata" in params:
                        vessels_store[vessel_id]["metadata"] = params["metadata"]
                    return MockQueryResult([[MockNode(vessels_store[vessel_id])]])
                return MockQueryResult([])

            # Handle DELETE vessel
            if "DETACH DELETE" in cypher:
                vessel_id = params.get("id")
                if vessel_id in vessels_store:
                    del vessels_store[vessel_id]
                    # Remove associated connections
                    connections_store[:] = [
                        c for c in connections_store
                        if c["source_id"] != vessel_id and c["target_id"] != vessel_id
                    ]
                return MockQueryResult([])

            # Handle CREATE connection
            if "CREATE (source)-[c:CONNECTS" in cypher:
                source_id = params.get("source_id")
                target_id = params.get("target_id")
                if source_id in vessels_store and target_id in vessels_store:
                    conn = {
                        "source_id": source_id,
                        "target_id": target_id,
                        "connection_type": params.get("connection_type", "default"),
                        "weight": params.get("weight", 1.0),
                        "created_at": params.get("created_at", datetime.now().isoformat()),
                    }
                    connections_store.append(conn)
                    return MockQueryResult([[MockEdge(conn)]])
                return MockQueryResult([])

            # Handle outgoing connections
            if "(v:Vessel {id: $id})-[c:CONNECTS]->(target)" in cypher:
                vessel_id = params.get("id")
                edges = [MockEdge(c) for c in connections_store if c["source_id"] == vessel_id]
                return MockQueryResult([[e] for e in edges])

            # Handle incoming connections
            if "(source)-[c:CONNECTS]->(v:Vessel {id: $id})" in cypher:
                vessel_id = params.get("id")
                edges = [MockEdge(c) for c in connections_store if c["target_id"] == vessel_id]
                return MockQueryResult([[e] for e in edges])

            # Handle DELETE connection
            if "DELETE c" in cypher and "CONNECTS" in cypher:
                source_id = params.get("source_id")
                target_id = params.get("target_id")
                initial_count = len(connections_store)
                connections_store[:] = [
                    c for c in connections_store
                    if not (c["source_id"] == source_id and c["target_id"] == target_id)
                ]
                deleted = initial_count - len(connections_store)
                return MockQueryResult([[deleted]])

            # Handle shortestPath
            if "shortestPath" in cypher:
                start_id = params.get("start_id")
                end_id = params.get("end_id")
                # Simple path finding - just check if direct connection exists
                for c in connections_store:
                    if c["source_id"] == start_id and c["target_id"] == end_id:
                        return MockQueryResult([[[start_id, end_id]]])
                    if c["target_id"] == start_id and c["source_id"] == end_id:
                        return MockQueryResult([[[start_id, end_id]]])
                return MockQueryResult([])

            # Handle count queries
            if "count(v)" in cypher:
                return MockQueryResult([[len(vessels_store)]])
            if "count(c)" in cypher:
                return MockQueryResult([[len(connections_store)]])

            # Handle group by type
            if "v.vessel_type as type, count(v)" in cypher:
                type_counts = {}
                for v in vessels_store.values():
                    t = v["vessel_type"]
                    type_counts[t] = type_counts.get(t, 0) + 1
                return MockQueryResult([[t, c] for t, c in type_counts.items()])

            if "c.connection_type as type, count(c)" in cypher:
                type_counts = {}
                for c in connections_store:
                    t = c["connection_type"]
                    type_counts[t] = type_counts.get(t, 0) + 1
                return MockQueryResult([[t, c] for t, c in type_counts.items()])

            # Handle CREATE INDEX (just succeed)
            if "CREATE INDEX" in cypher:
                return MockQueryResult([])

            # Handle clear graph
            if "MATCH (n) DETACH DELETE n" in cypher:
                vessels_store.clear()
                connections_store.clear()
                return MockQueryResult([])

            # Default
            return MockQueryResult([[1]])

        mock_graph.query.side_effect = query_handler

        # Create mock connection
        mock_conn = MagicMock(spec=FalkorDBConnection)
        mock_client = MagicMock()
        mock_client.select_graph.return_value = mock_graph
        type(mock_conn).client = PropertyMock(return_value=mock_client)

        return mock_conn, vessels_store, connections_store

    def test_complete_vessel_lifecycle(self, mock_graph_connection):
        """Test creating, reading, updating, and deleting a vessel."""
        mock_conn, vessels_store, _ = mock_graph_connection

        graph = VesselsGraph(mock_conn, "test_graph")
        graph.initialize_schema()

        # Create
        vessel = graph.create_vessel(
            vessel_id="test-vessel-1",
            name="Test Vessel",
            vessel_type="container",
            metadata={"env": "test"},
        )
        assert vessel.id == "test-vessel-1"
        assert vessel.name == "Test Vessel"
        assert vessel.vessel_type == "container"

        # Read
        retrieved = graph.get_vessel("test-vessel-1")
        assert retrieved is not None
        assert retrieved.id == "test-vessel-1"

        # Update
        updated = graph.update_vessel("test-vessel-1", name="Updated Vessel")
        assert updated is not None
        assert updated.name == "Updated Vessel"

        # Delete
        deleted = graph.delete_vessel("test-vessel-1")
        assert deleted is True

        # Verify deleted
        not_found = graph.get_vessel("test-vessel-1")
        assert not_found is None

    def test_complete_connection_lifecycle(self, mock_graph_connection):
        """Test creating, reading, and deleting connections."""
        mock_conn, _, _ = mock_graph_connection

        graph = VesselsGraph(mock_conn, "test_graph")
        graph.initialize_schema()

        # Create vessels
        v1 = graph.create_vessel("v1", "Vessel 1")
        v2 = graph.create_vessel("v2", "Vessel 2")

        # Create connection
        conn = graph.create_connection("v1", "v2", "link", 0.8)
        assert conn is not None
        assert conn.source_id == "v1"
        assert conn.target_id == "v2"
        assert conn.connection_type == "link"
        assert conn.weight == 0.8

        # Get connections
        outgoing = graph.get_connections("v1", direction="outgoing")
        assert len(outgoing) == 1
        assert outgoing[0].target_id == "v2"

        incoming = graph.get_connections("v2", direction="incoming")
        assert len(incoming) == 1
        assert incoming[0].source_id == "v1"

        # Delete connection
        deleted = graph.delete_connection("v1", "v2")
        assert deleted is True

    def test_vessel_listing_and_filtering(self, mock_graph_connection):
        """Test listing vessels with and without filters."""
        mock_conn, _, _ = mock_graph_connection

        graph = VesselsGraph(mock_conn, "test_graph")
        graph.initialize_schema()

        # Create multiple vessels of different types
        graph.create_vessel("v1", "Vessel 1", vessel_type="container")
        graph.create_vessel("v2", "Vessel 2", vessel_type="container")
        graph.create_vessel("v3", "Vessel 3", vessel_type="service")

        # List all
        all_vessels = graph.list_vessels()
        assert len(all_vessels) == 3

        # List by type
        containers = graph.list_vessels(vessel_type="container")
        assert len(containers) == 2

        services = graph.list_vessels(vessel_type="service")
        assert len(services) == 1

    def test_path_finding(self, mock_graph_connection):
        """Test finding paths between vessels."""
        mock_conn, _, _ = mock_graph_connection

        graph = VesselsGraph(mock_conn, "test_graph")
        graph.initialize_schema()

        # Create vessels and connections
        graph.create_vessel("start", "Start")
        graph.create_vessel("middle", "Middle")
        graph.create_vessel("end", "End")

        graph.create_connection("start", "middle")
        graph.create_connection("middle", "end")

        # Find path (our mock only finds direct connections)
        path = graph.find_path("start", "middle")
        assert len(path) > 0

    def test_statistics(self, mock_graph_connection):
        """Test getting graph statistics."""
        mock_conn, _, _ = mock_graph_connection

        graph = VesselsGraph(mock_conn, "test_graph")
        graph.initialize_schema()

        # Create some data
        graph.create_vessel("v1", "Vessel 1", vessel_type="a")
        graph.create_vessel("v2", "Vessel 2", vessel_type="a")
        graph.create_vessel("v3", "Vessel 3", vessel_type="b")
        graph.create_connection("v1", "v2", "link")

        stats = graph.get_statistics()
        assert stats["total_vessels"] == 3
        assert stats["total_connections"] == 1
        assert "a" in stats["vessels_by_type"]
        assert stats["vessels_by_type"]["a"] == 2

    def test_graph_clear(self, mock_graph_connection):
        """Test clearing all data from the graph."""
        mock_conn, vessels_store, connections_store = mock_graph_connection

        graph = VesselsGraph(mock_conn, "test_graph")
        graph.initialize_schema()

        # Create some data
        graph.create_vessel("v1", "Vessel 1")
        graph.create_vessel("v2", "Vessel 2")
        graph.create_connection("v1", "v2")

        # Verify data exists
        assert len(vessels_store) == 2
        assert len(connections_store) == 1

        # Clear
        graph.clear_graph()

        # Verify cleared
        assert len(vessels_store) == 0
        assert len(connections_store) == 0

    def test_cascading_delete(self, mock_graph_connection):
        """Test that deleting a vessel removes associated connections."""
        mock_conn, vessels_store, connections_store = mock_graph_connection

        graph = VesselsGraph(mock_conn, "test_graph")
        graph.initialize_schema()

        # Create network
        graph.create_vessel("hub", "Hub")
        graph.create_vessel("spoke1", "Spoke 1")
        graph.create_vessel("spoke2", "Spoke 2")
        graph.create_connection("hub", "spoke1")
        graph.create_connection("hub", "spoke2")

        assert len(connections_store) == 2

        # Delete hub
        graph.delete_vessel("hub")

        # Connections should be removed
        assert len(connections_store) == 0


class TestVesselsDataPersistence:
    """Tests verifying data is properly stored in graph."""

    @pytest.fixture
    def mock_graph_with_persistence(self):
        """Create a mock that tracks all operations."""
        operations = []
        mock_graph = MagicMock()

        def query_handler(cypher, params=None):
            operations.append({"query": cypher, "params": params})

            if "CREATE" in cypher:
                node = MockNode({
                    "id": params.get("id") if params else "test",
                    "name": params.get("name") if params else "Test",
                    "vessel_type": "default",
                    "created_at": datetime.now().isoformat(),
                    "metadata": "{}",
                })
                return MockQueryResult([[node]])

            return MockQueryResult([[1]])

        mock_graph.query.side_effect = query_handler

        mock_conn = MagicMock(spec=FalkorDBConnection)
        mock_client = MagicMock()
        mock_client.select_graph.return_value = mock_graph
        type(mock_conn).client = PropertyMock(return_value=mock_client)

        return mock_conn, operations

    def test_all_vessel_fields_persisted(self, mock_graph_with_persistence):
        """Test that all vessel fields are written to database."""
        mock_conn, operations = mock_graph_with_persistence

        graph = VesselsGraph(mock_conn, "test_graph")

        graph.create_vessel(
            vessel_id="persistence-test",
            name="Persistence Test Vessel",
            vessel_type="test-type",
            metadata={"key": "value"},
        )

        # Find the CREATE operation
        create_ops = [op for op in operations if "CREATE" in op["query"]]
        assert len(create_ops) == 1

        params = create_ops[0]["params"]
        assert params["id"] == "persistence-test"
        assert params["name"] == "Persistence Test Vessel"
        assert params["vessel_type"] == "test-type"
        assert "created_at" in params
        assert params["metadata"] == "{'key': 'value'}"

    def test_connection_fields_persisted(self, mock_graph_with_persistence):
        """Test that all connection fields are written to database."""
        mock_conn, operations = mock_graph_with_persistence

        graph = VesselsGraph(mock_conn, "test_graph")

        # Mock vessels exist
        mock_conn.client.select_graph.return_value.query.side_effect = lambda q, p=None: MockQueryResult([
            [MockEdge({
                "source_id": p.get("source_id") if p else "",
                "target_id": p.get("target_id") if p else "",
                "connection_type": p.get("connection_type") if p else "default",
                "weight": p.get("weight") if p else 1.0,
                "created_at": datetime.now().isoformat(),
            })]
        ])

        graph.create_connection(
            source_id="src",
            target_id="tgt",
            connection_type="depends_on",
            weight=0.75,
        )

        # Find the CREATE connection operation
        create_ops = [op for op in operations if "CONNECTS" in op.get("query", "")]
        assert len(create_ops) >= 1


class TestVesselsErrorHandling:
    """Tests for error handling when running from FalkorDB."""

    def test_handles_connection_failure_gracefully(self):
        """Test graceful handling of connection failures."""
        settings = Settings(falkordb_host="nonexistent", falkordb_port=9999)

        with patch("vessels.db.connection.FalkorDB") as mock_fdb:
            mock_fdb.side_effect = Exception("Connection failed")

            with patch("vessels.db.connection.Redis") as mock_redis:
                mock_redis.side_effect = Exception("Connection failed")

                conn = FalkorDBConnection(settings)

                from vessels.db.connection import FalkorDBConnectionError
                with pytest.raises(FalkorDBConnectionError):
                    conn.connect()

    def test_handles_query_failure(self):
        """Test handling of query failures."""
        mock_graph = MagicMock()
        mock_graph.query.side_effect = Exception("Query failed")

        mock_conn = MagicMock(spec=FalkorDBConnection)
        mock_client = MagicMock()
        mock_client.select_graph.return_value = mock_graph
        type(mock_conn).client = PropertyMock(return_value=mock_client)

        graph = VesselsGraph(mock_conn, "test_graph")

        with pytest.raises(Exception, match="Query failed"):
            graph.create_vessel("test", "Test")

    def test_handles_missing_vessel_gracefully(self):
        """Test graceful handling when vessel not found."""
        mock_graph = MagicMock()
        mock_graph.query.return_value = MockQueryResult([])

        mock_conn = MagicMock(spec=FalkorDBConnection)
        mock_client = MagicMock()
        mock_client.select_graph.return_value = mock_graph
        type(mock_conn).client = PropertyMock(return_value=mock_client)

        graph = VesselsGraph(mock_conn, "test_graph")

        result = graph.get_vessel("nonexistent")
        assert result is None

        deleted = graph.delete_vessel("nonexistent")
        assert deleted is False
