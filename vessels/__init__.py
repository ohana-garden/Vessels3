"""
Vessels - A Graph Database Application powered by FalkorDB

Vessels manages entities and their relationships in a graph database,
with all runtime data persisted in FalkorDB.
"""

__version__ = "1.0.0"
__author__ = "Vessels Team"

__all__ = [
    "Settings",
    "get_settings",
    "FalkorDBConnection",
    "VesselsGraph",
]


def __getattr__(name: str):
    """Lazy import of modules to avoid loading dependencies until needed."""
    if name in ("Settings", "get_settings"):
        from vessels.core.config import Settings, get_settings
        return Settings if name == "Settings" else get_settings
    elif name == "FalkorDBConnection":
        from vessels.db.connection import FalkorDBConnection
        return FalkorDBConnection
    elif name == "VesselsGraph":
        from vessels.db.graph import VesselsGraph
        return VesselsGraph
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
