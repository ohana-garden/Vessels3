"""
FastAPI application for Vessels.

Provides HTTP API for vessel and connection management.
"""

from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from vessels.core.config import get_settings
from vessels.db.connection import FalkorDBConnection
from vessels.db.graph import VesselsGraph
from vessels.utils.logging import setup_logging


class VesselCreate(BaseModel):
    """Request model for creating a vessel."""

    id: str = Field(..., description="Unique vessel identifier")
    name: str = Field(..., description="Vessel name")
    vessel_type: str = Field(default="default", description="Vessel type")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class VesselUpdate(BaseModel):
    """Request model for updating a vessel."""

    name: Optional[str] = None
    vessel_type: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class VesselResponse(BaseModel):
    """Response model for vessel data."""

    id: str
    name: str
    vessel_type: str
    created_at: str
    metadata: dict[str, Any]


class ConnectionCreate(BaseModel):
    """Request model for creating a connection."""

    source_id: str
    target_id: str
    connection_type: str = "default"
    weight: float = 1.0


class ConnectionResponse(BaseModel):
    """Response model for connection data."""

    source_id: str
    target_id: str
    connection_type: str
    weight: float
    created_at: str


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str
    database: dict[str, Any]
    api_keys_configured: bool


# Global connection and graph instances
_connection: Optional[FalkorDBConnection] = None
_graph: Optional[VesselsGraph] = None


def get_connection() -> FalkorDBConnection:
    """Get the global database connection."""
    global _connection
    if _connection is None:
        raise RuntimeError("Database not initialized")
    return _connection


def get_graph() -> VesselsGraph:
    """Get the global graph instance."""
    global _graph
    if _graph is None:
        raise RuntimeError("Graph not initialized")
    return _graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown."""
    global _connection, _graph

    settings = get_settings()
    setup_logging(settings.vessels_log_level)

    # Initialize database connection
    _connection = FalkorDBConnection(settings)
    _connection.connect()

    # Wait for database to be ready
    if not _connection.wait_for_ready(timeout=60):
        raise RuntimeError("FalkorDB failed to become ready")

    # Initialize graph
    _graph = VesselsGraph(_connection, settings.vessels_graph_name)
    _graph.initialize_schema()

    yield

    # Cleanup
    if _connection:
        _connection.disconnect()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Vessels API",
        description="Graph-based vessel management powered by FalkorDB",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """Check application and database health."""
        settings = get_settings()
        conn = get_connection()

        return HealthResponse(
            status="healthy" if conn.is_connected() else "unhealthy",
            database=conn.get_database_info(),
            api_keys_configured=settings.has_api_keys(),
        )

    @app.get("/stats")
    async def get_statistics():
        """Get graph statistics."""
        graph = get_graph()
        return graph.get_statistics()

    # Vessel endpoints
    @app.post("/vessels", response_model=VesselResponse)
    async def create_vessel(vessel: VesselCreate):
        """Create a new vessel."""
        graph = get_graph()

        # Check if vessel already exists
        existing = graph.get_vessel(vessel.id)
        if existing:
            raise HTTPException(status_code=409, detail=f"Vessel {vessel.id} already exists")

        created = graph.create_vessel(
            vessel_id=vessel.id,
            name=vessel.name,
            vessel_type=vessel.vessel_type,
            metadata=vessel.metadata,
        )

        return VesselResponse(
            id=created.id,
            name=created.name,
            vessel_type=created.vessel_type,
            created_at=created.created_at.isoformat(),
            metadata=created.metadata,
        )

    @app.get("/vessels", response_model=list[VesselResponse])
    async def list_vessels(vessel_type: Optional[str] = None, limit: int = 100):
        """List all vessels."""
        graph = get_graph()
        vessels = graph.list_vessels(vessel_type=vessel_type, limit=limit)

        return [
            VesselResponse(
                id=v.id,
                name=v.name,
                vessel_type=v.vessel_type,
                created_at=v.created_at.isoformat(),
                metadata=v.metadata,
            )
            for v in vessels
        ]

    @app.get("/vessels/{vessel_id}", response_model=VesselResponse)
    async def get_vessel(vessel_id: str):
        """Get a vessel by ID."""
        graph = get_graph()
        vessel = graph.get_vessel(vessel_id)

        if not vessel:
            raise HTTPException(status_code=404, detail=f"Vessel {vessel_id} not found")

        return VesselResponse(
            id=vessel.id,
            name=vessel.name,
            vessel_type=vessel.vessel_type,
            created_at=vessel.created_at.isoformat(),
            metadata=vessel.metadata,
        )

    @app.patch("/vessels/{vessel_id}", response_model=VesselResponse)
    async def update_vessel(vessel_id: str, updates: VesselUpdate):
        """Update a vessel."""
        graph = get_graph()

        updated = graph.update_vessel(
            vessel_id=vessel_id,
            name=updates.name,
            vessel_type=updates.vessel_type,
            metadata=updates.metadata,
        )

        if not updated:
            raise HTTPException(status_code=404, detail=f"Vessel {vessel_id} not found")

        return VesselResponse(
            id=updated.id,
            name=updated.name,
            vessel_type=updated.vessel_type,
            created_at=updated.created_at.isoformat(),
            metadata=updated.metadata,
        )

    @app.delete("/vessels/{vessel_id}")
    async def delete_vessel(vessel_id: str):
        """Delete a vessel."""
        graph = get_graph()

        if not graph.delete_vessel(vessel_id):
            raise HTTPException(status_code=404, detail=f"Vessel {vessel_id} not found")

        return {"deleted": vessel_id}

    # Connection endpoints
    @app.post("/connections", response_model=ConnectionResponse)
    async def create_connection(connection: ConnectionCreate):
        """Create a connection between vessels."""
        graph = get_graph()

        created = graph.create_connection(
            source_id=connection.source_id,
            target_id=connection.target_id,
            connection_type=connection.connection_type,
            weight=connection.weight,
        )

        if not created:
            raise HTTPException(
                status_code=404,
                detail="One or both vessels not found",
            )

        return ConnectionResponse(
            source_id=created.source_id,
            target_id=created.target_id,
            connection_type=created.connection_type,
            weight=created.weight,
            created_at=created.created_at.isoformat(),
        )

    @app.get("/vessels/{vessel_id}/connections", response_model=list[ConnectionResponse])
    async def get_vessel_connections(vessel_id: str, direction: str = "both"):
        """Get connections for a vessel."""
        graph = get_graph()

        if direction not in ("outgoing", "incoming", "both"):
            raise HTTPException(
                status_code=400,
                detail="Direction must be 'outgoing', 'incoming', or 'both'",
            )

        connections = graph.get_connections(vessel_id, direction)

        return [
            ConnectionResponse(
                source_id=c.source_id,
                target_id=c.target_id,
                connection_type=c.connection_type,
                weight=c.weight,
                created_at=c.created_at.isoformat(),
            )
            for c in connections
        ]

    @app.delete("/connections")
    async def delete_connection(
        source_id: str,
        target_id: str,
        connection_type: Optional[str] = None,
    ):
        """Delete a connection between vessels."""
        graph = get_graph()

        if not graph.delete_connection(source_id, target_id, connection_type):
            raise HTTPException(status_code=404, detail="Connection not found")

        return {"deleted": True}

    @app.get("/path")
    async def find_path(start_id: str, end_id: str, max_hops: int = 5):
        """Find shortest path between vessels."""
        graph = get_graph()
        path = graph.find_path(start_id, end_id, max_hops)

        if not path:
            raise HTTPException(status_code=404, detail="No path found")

        return {"path": path}

    return app


# Create app instance for uvicorn
app = create_app()
