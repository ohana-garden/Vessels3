"""
Vessels Graph operations using FalkorDB.

All Vessels runtime data is stored and managed through this graph interface.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import structlog
from falkordb import Graph

from vessels.db.connection import FalkorDBConnection

logger = structlog.get_logger(__name__)


@dataclass
class Vessel:
    """Represents a Vessel entity in the graph."""

    id: str
    name: str
    vessel_type: str
    created_at: datetime
    metadata: dict[str, Any]

    @classmethod
    def from_node(cls, node: dict) -> "Vessel":
        """Create a Vessel from a graph node."""
        props = node.get("properties", node)
        return cls(
            id=props.get("id"),
            name=props.get("name"),
            vessel_type=props.get("vessel_type", "default"),
            created_at=datetime.fromisoformat(props.get("created_at", datetime.now().isoformat())),
            metadata=props.get("metadata", {}),
        )


@dataclass
class Connection:
    """Represents a connection between vessels."""

    source_id: str
    target_id: str
    connection_type: str
    weight: float
    created_at: datetime

    @classmethod
    def from_edge(cls, edge: dict) -> "Connection":
        """Create a Connection from a graph edge."""
        props = edge.get("properties", edge)
        return cls(
            source_id=props.get("source_id"),
            target_id=props.get("target_id"),
            connection_type=props.get("connection_type", "default"),
            weight=float(props.get("weight", 1.0)),
            created_at=datetime.fromisoformat(props.get("created_at", datetime.now().isoformat())),
        )


class VesselsGraph:
    """
    Graph interface for Vessels application.

    All runtime data is stored in FalkorDB through this interface.
    """

    def __init__(self, connection: FalkorDBConnection, graph_name: str = "vessels"):
        """
        Initialize the Vessels graph.

        Args:
            connection: FalkorDB connection manager.
            graph_name: Name of the graph in FalkorDB.
        """
        self.connection = connection
        self.graph_name = graph_name
        self._graph: Optional[Graph] = None

    @property
    def graph(self) -> Graph:
        """Get the FalkorDB graph instance."""
        if self._graph is None:
            self._graph = self.connection.client.select_graph(self.graph_name)
        return self._graph

    def initialize_schema(self) -> None:
        """
        Initialize the graph schema with indexes and constraints.

        Creates necessary indexes for efficient querying.
        """
        logger.info("initializing_graph_schema", graph=self.graph_name)

        # Create index on Vessel id
        try:
            self.graph.query("CREATE INDEX FOR (v:Vessel) ON (v.id)")
        except Exception as e:
            if "already indexed" not in str(e).lower():
                logger.warning("index_creation_warning", index="Vessel.id", error=str(e))

        # Create index on Vessel name
        try:
            self.graph.query("CREATE INDEX FOR (v:Vessel) ON (v.name)")
        except Exception as e:
            if "already indexed" not in str(e).lower():
                logger.warning("index_creation_warning", index="Vessel.name", error=str(e))

        # Create index on Connection type
        try:
            self.graph.query("CREATE INDEX FOR ()-[c:CONNECTS]-() ON (c.connection_type)")
        except Exception as e:
            if "already indexed" not in str(e).lower():
                logger.warning("index_creation_warning", index="CONNECTS.connection_type", error=str(e))

        logger.info("graph_schema_initialized")

    def create_vessel(
        self,
        vessel_id: str,
        name: str,
        vessel_type: str = "default",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Vessel:
        """
        Create a new vessel in the graph.

        Args:
            vessel_id: Unique identifier for the vessel.
            name: Human-readable name.
            vessel_type: Type categorization.
            metadata: Additional key-value metadata.

        Returns:
            The created Vessel entity.
        """
        now = datetime.now().isoformat()
        metadata_str = str(metadata or {})

        query = """
        CREATE (v:Vessel {
            id: $id,
            name: $name,
            vessel_type: $vessel_type,
            created_at: $created_at,
            metadata: $metadata
        })
        RETURN v
        """

        result = self.graph.query(
            query,
            {"id": vessel_id, "name": name, "vessel_type": vessel_type, "created_at": now, "metadata": metadata_str},
        )

        logger.info("vessel_created", vessel_id=vessel_id, name=name)

        return Vessel(
            id=vessel_id,
            name=name,
            vessel_type=vessel_type,
            created_at=datetime.fromisoformat(now),
            metadata=metadata or {},
        )

    def get_vessel(self, vessel_id: str) -> Optional[Vessel]:
        """
        Get a vessel by ID.

        Args:
            vessel_id: The vessel's unique identifier.

        Returns:
            The Vessel if found, None otherwise.
        """
        query = "MATCH (v:Vessel {id: $id}) RETURN v"
        result = self.graph.query(query, {"id": vessel_id})

        if not result.result_set:
            return None

        node = result.result_set[0][0]
        return Vessel(
            id=node.properties.get("id"),
            name=node.properties.get("name"),
            vessel_type=node.properties.get("vessel_type", "default"),
            created_at=datetime.fromisoformat(node.properties.get("created_at", datetime.now().isoformat())),
            metadata=eval(node.properties.get("metadata", "{}")),
        )

    def get_vessel_by_name(self, name: str) -> Optional[Vessel]:
        """
        Get a vessel by name.

        Args:
            name: The vessel's name.

        Returns:
            The Vessel if found, None otherwise.
        """
        query = "MATCH (v:Vessel {name: $name}) RETURN v"
        result = self.graph.query(query, {"name": name})

        if not result.result_set:
            return None

        node = result.result_set[0][0]
        return Vessel(
            id=node.properties.get("id"),
            name=node.properties.get("name"),
            vessel_type=node.properties.get("vessel_type", "default"),
            created_at=datetime.fromisoformat(node.properties.get("created_at", datetime.now().isoformat())),
            metadata=eval(node.properties.get("metadata", "{}")),
        )

    def list_vessels(self, vessel_type: Optional[str] = None, limit: int = 100) -> list[Vessel]:
        """
        List vessels, optionally filtered by type.

        Args:
            vessel_type: Filter by vessel type.
            limit: Maximum number of results.

        Returns:
            List of Vessel entities.
        """
        if vessel_type:
            query = "MATCH (v:Vessel {vessel_type: $type}) RETURN v LIMIT $limit"
            params = {"type": vessel_type, "limit": limit}
        else:
            query = "MATCH (v:Vessel) RETURN v LIMIT $limit"
            params = {"limit": limit}

        result = self.graph.query(query, params)

        vessels = []
        for row in result.result_set:
            node = row[0]
            vessels.append(
                Vessel(
                    id=node.properties.get("id"),
                    name=node.properties.get("name"),
                    vessel_type=node.properties.get("vessel_type", "default"),
                    created_at=datetime.fromisoformat(node.properties.get("created_at", datetime.now().isoformat())),
                    metadata=eval(node.properties.get("metadata", "{}")),
                )
            )

        return vessels

    def update_vessel(
        self,
        vessel_id: str,
        name: Optional[str] = None,
        vessel_type: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[Vessel]:
        """
        Update an existing vessel.

        Args:
            vessel_id: ID of the vessel to update.
            name: New name (optional).
            vessel_type: New type (optional).
            metadata: New metadata (optional).

        Returns:
            Updated Vessel if found, None otherwise.
        """
        set_clauses = []
        params = {"id": vessel_id}

        if name is not None:
            set_clauses.append("v.name = $name")
            params["name"] = name
        if vessel_type is not None:
            set_clauses.append("v.vessel_type = $type")
            params["type"] = vessel_type
        if metadata is not None:
            set_clauses.append("v.metadata = $metadata")
            params["metadata"] = str(metadata)

        if not set_clauses:
            return self.get_vessel(vessel_id)

        query = f"MATCH (v:Vessel {{id: $id}}) SET {', '.join(set_clauses)} RETURN v"
        result = self.graph.query(query, params)

        if not result.result_set:
            return None

        logger.info("vessel_updated", vessel_id=vessel_id)
        return self.get_vessel(vessel_id)

    def delete_vessel(self, vessel_id: str) -> bool:
        """
        Delete a vessel and all its connections.

        Args:
            vessel_id: ID of the vessel to delete.

        Returns:
            True if vessel was deleted, False if not found.
        """
        # First check if vessel exists
        if not self.get_vessel(vessel_id):
            return False

        # Delete vessel and all relationships
        query = "MATCH (v:Vessel {id: $id}) DETACH DELETE v"
        self.graph.query(query, {"id": vessel_id})

        logger.info("vessel_deleted", vessel_id=vessel_id)
        return True

    def create_connection(
        self,
        source_id: str,
        target_id: str,
        connection_type: str = "default",
        weight: float = 1.0,
    ) -> Optional[Connection]:
        """
        Create a connection between two vessels.

        Args:
            source_id: Source vessel ID.
            target_id: Target vessel ID.
            connection_type: Type of connection.
            weight: Connection weight/strength.

        Returns:
            The created Connection, or None if vessels don't exist.
        """
        now = datetime.now().isoformat()

        query = """
        MATCH (source:Vessel {id: $source_id})
        MATCH (target:Vessel {id: $target_id})
        CREATE (source)-[c:CONNECTS {
            source_id: $source_id,
            target_id: $target_id,
            connection_type: $connection_type,
            weight: $weight,
            created_at: $created_at
        }]->(target)
        RETURN c
        """

        result = self.graph.query(
            query,
            {
                "source_id": source_id,
                "target_id": target_id,
                "connection_type": connection_type,
                "weight": weight,
                "created_at": now,
            },
        )

        if not result.result_set:
            return None

        logger.info(
            "connection_created",
            source=source_id,
            target=target_id,
            type=connection_type,
        )

        return Connection(
            source_id=source_id,
            target_id=target_id,
            connection_type=connection_type,
            weight=weight,
            created_at=datetime.fromisoformat(now),
        )

    def get_connections(self, vessel_id: str, direction: str = "both") -> list[Connection]:
        """
        Get connections for a vessel.

        Args:
            vessel_id: The vessel ID.
            direction: 'outgoing', 'incoming', or 'both'.

        Returns:
            List of connections.
        """
        connections = []

        if direction in ("outgoing", "both"):
            query = """
            MATCH (v:Vessel {id: $id})-[c:CONNECTS]->(target)
            RETURN c
            """
            result = self.graph.query(query, {"id": vessel_id})
            for row in result.result_set:
                edge = row[0]
                connections.append(
                    Connection(
                        source_id=edge.properties.get("source_id"),
                        target_id=edge.properties.get("target_id"),
                        connection_type=edge.properties.get("connection_type", "default"),
                        weight=float(edge.properties.get("weight", 1.0)),
                        created_at=datetime.fromisoformat(edge.properties.get("created_at", datetime.now().isoformat())),
                    )
                )

        if direction in ("incoming", "both"):
            query = """
            MATCH (source)-[c:CONNECTS]->(v:Vessel {id: $id})
            RETURN c
            """
            result = self.graph.query(query, {"id": vessel_id})
            for row in result.result_set:
                edge = row[0]
                conn = Connection(
                    source_id=edge.properties.get("source_id"),
                    target_id=edge.properties.get("target_id"),
                    connection_type=edge.properties.get("connection_type", "default"),
                    weight=float(edge.properties.get("weight", 1.0)),
                    created_at=datetime.fromisoformat(edge.properties.get("created_at", datetime.now().isoformat())),
                )
                # Avoid duplicates for 'both'
                if direction == "incoming" or conn not in connections:
                    connections.append(conn)

        return connections

    def delete_connection(self, source_id: str, target_id: str, connection_type: Optional[str] = None) -> bool:
        """
        Delete a connection between vessels.

        Args:
            source_id: Source vessel ID.
            target_id: Target vessel ID.
            connection_type: Specific type to delete (optional).

        Returns:
            True if connection(s) were deleted.
        """
        if connection_type:
            query = """
            MATCH (s:Vessel {id: $source_id})-[c:CONNECTS {connection_type: $type}]->(t:Vessel {id: $target_id})
            DELETE c
            RETURN count(c) as deleted
            """
            params = {"source_id": source_id, "target_id": target_id, "type": connection_type}
        else:
            query = """
            MATCH (s:Vessel {id: $source_id})-[c:CONNECTS]->(t:Vessel {id: $target_id})
            DELETE c
            RETURN count(c) as deleted
            """
            params = {"source_id": source_id, "target_id": target_id}

        result = self.graph.query(query, params)
        deleted = result.result_set[0][0] if result.result_set else 0

        if deleted > 0:
            logger.info("connection_deleted", source=source_id, target=target_id)

        return deleted > 0

    def find_path(self, start_id: str, end_id: str, max_hops: int = 5) -> list[str]:
        """
        Find the shortest path between two vessels.

        Args:
            start_id: Starting vessel ID.
            end_id: Ending vessel ID.
            max_hops: Maximum path length.

        Returns:
            List of vessel IDs in the path, or empty list if no path.
        """
        query = f"""
        MATCH path = shortestPath(
            (start:Vessel {{id: $start_id}})-[:CONNECTS*1..{max_hops}]-(end:Vessel {{id: $end_id}})
        )
        RETURN [node in nodes(path) | node.id] as path_ids
        """

        result = self.graph.query(query, {"start_id": start_id, "end_id": end_id})

        if not result.result_set:
            return []

        return result.result_set[0][0]

    def get_statistics(self) -> dict[str, Any]:
        """
        Get graph statistics.

        Returns:
            Dictionary with vessel counts, connection counts, etc.
        """
        stats = {}

        # Count vessels
        result = self.graph.query("MATCH (v:Vessel) RETURN count(v) as count")
        stats["total_vessels"] = result.result_set[0][0] if result.result_set else 0

        # Count connections
        result = self.graph.query("MATCH ()-[c:CONNECTS]->() RETURN count(c) as count")
        stats["total_connections"] = result.result_set[0][0] if result.result_set else 0

        # Count by vessel type
        result = self.graph.query(
            "MATCH (v:Vessel) RETURN v.vessel_type as type, count(v) as count"
        )
        stats["vessels_by_type"] = {row[0]: row[1] for row in result.result_set}

        # Count by connection type
        result = self.graph.query(
            "MATCH ()-[c:CONNECTS]->() RETURN c.connection_type as type, count(c) as count"
        )
        stats["connections_by_type"] = {row[0]: row[1] for row in result.result_set}

        return stats

    def clear_graph(self) -> None:
        """Clear all data from the graph."""
        self.graph.query("MATCH (n) DETACH DELETE n")
        logger.warning("graph_cleared", graph=self.graph_name)
