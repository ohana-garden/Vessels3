"""
Configuration management for Vessels.

Handles loading API keys and settings from environment variables
and writing them to .env file when provided at runtime.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # FalkorDB Configuration
    falkordb_host: str = Field(default="localhost", description="FalkorDB host")
    falkordb_port: int = Field(default=6379, description="FalkorDB port")
    falkordb_password: Optional[str] = Field(default=None, description="FalkorDB password")

    # API Keys
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")

    # Application Settings
    vessels_debug: bool = Field(default=False, description="Enable debug mode")
    vessels_log_level: str = Field(default="INFO", description="Logging level")
    vessels_graph_name: str = Field(default="vessels", description="Graph name in FalkorDB")

    # Data persistence
    falkordb_data_dir: str = Field(default="/data/falkordb", description="FalkorDB data directory")

    @field_validator("vessels_log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return upper_v

    @property
    def falkordb_url(self) -> str:
        """Get the FalkorDB connection URL."""
        if self.falkordb_password:
            return f"redis://:{self.falkordb_password}@{self.falkordb_host}:{self.falkordb_port}"
        return f"redis://{self.falkordb_host}:{self.falkordb_port}"

    def has_api_keys(self) -> bool:
        """Check if any API keys are configured."""
        return bool(self.openai_api_key or self.anthropic_api_key)


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


def write_env_file(
    env_path: Path,
    api_keys: dict[str, str],
    falkordb_config: Optional[dict[str, str]] = None,
) -> None:
    """
    Write or update the .env file with API keys and configuration.

    Args:
        env_path: Path to the .env file
        api_keys: Dictionary of API key names to values
        falkordb_config: Optional FalkorDB configuration overrides
    """
    existing_vars: dict[str, str] = {}

    # Read existing .env file if it exists
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    existing_vars[key.strip()] = value.strip()

    # Update with new API keys
    for key, value in api_keys.items():
        if value:  # Only set non-empty values
            existing_vars[key.upper()] = value

    # Update with FalkorDB config
    if falkordb_config:
        for key, value in falkordb_config.items():
            if value:
                existing_vars[key.upper()] = value

    # Write the updated .env file
    with open(env_path, "w") as f:
        f.write("# Vessels Configuration\n")
        f.write("# Auto-generated - API keys and settings\n\n")

        # Group by category
        categories = {
            "FalkorDB": ["FALKORDB_HOST", "FALKORDB_PORT", "FALKORDB_PASSWORD", "FALKORDB_DATA_DIR"],
            "API Keys": ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"],
            "Application": ["VESSELS_DEBUG", "VESSELS_LOG_LEVEL", "VESSELS_GRAPH_NAME"],
        }

        written_keys = set()
        for category, keys in categories.items():
            f.write(f"# {category}\n")
            for key in keys:
                if key in existing_vars:
                    f.write(f"{key}={existing_vars[key]}\n")
                    written_keys.add(key)
            f.write("\n")

        # Write any remaining keys
        remaining = set(existing_vars.keys()) - written_keys
        if remaining:
            f.write("# Additional Settings\n")
            for key in sorted(remaining):
                f.write(f"{key}={existing_vars[key]}\n")

    # Clear the settings cache so new values are loaded
    get_settings.cache_clear()


def load_api_keys_from_env() -> dict[str, Optional[str]]:
    """Load API keys from environment variables."""
    return {
        "openai_api_key": os.environ.get("OPENAI_API_KEY"),
        "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY"),
    }
