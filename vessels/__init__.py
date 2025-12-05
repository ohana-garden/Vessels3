"""
Vessels - A Graph Database Application powered by FalkorDB

Vessels manages entities and their relationships in a graph database,
with all runtime data persisted in FalkorDB.
"""

__version__ = "1.0.0"
__author__ = "Vessels Team"

from vessels.core.config import Settings, get_settings
from vessels.db.connection import FalkorDBConnection
from vessels.db.graph import VesselsGraph

__all__ = [
    "Settings",
    "get_settings",
    "FalkorDBConnection",
    "VesselsGraph",
]
