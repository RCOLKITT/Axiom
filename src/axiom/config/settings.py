"""Configuration management for Axiom.

Loads settings from axiom.toml with sensible defaults.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import structlog
import tomli
from pydantic import BaseModel, Field

from axiom.errors import ConfigError

logger = structlog.get_logger()


class GenerationSettings(BaseModel):
    """Settings for code generation."""

    default_model: str = "claude-sonnet-4-20250514"
    fallback_model: str = "claude-haiku-4-5-20251001"
    default_target: str = "python:function"
    temperature: float = 0.0
    max_retries: int = 3
    timeout_seconds: int = 60
    models: dict[str, str] = Field(default_factory=dict)


class VerificationSettings(BaseModel):
    """Settings for verification."""

    run_examples: bool = True
    run_invariants: bool = True
    run_performance: bool = False
    hypothesis_max_examples: int = 100
    timeout_seconds: int = 120


class CacheSettings(BaseModel):
    """Settings for caching."""

    enabled: bool = True
    strategy: str = "content-hash"


class LoggingSettings(BaseModel):
    """Settings for logging."""

    level: str = "INFO"
    format: str = "console"


class ProjectSettings(BaseModel):
    """Project-level settings."""

    name: str = "axiom"
    version: str = "0.1.0"
    spec_dir: str = "specs"
    generated_dir: str = "generated"
    cache_dir: str = ".axiom-cache"


class SecuritySettings(BaseModel):
    """Settings for security features.

    Attributes:
        enable_secret_scan: Whether to scan specs for secrets before generation.
        local_only: Never send data to LLM APIs; only use cache.
        strip_intent: Strip intent/comments from spec before sending to LLM.
        license: License identifier for generated code headers.
        license_header: Custom license header text (overrides license).
        enable_provenance: Whether to log provenance for builds and verifications.
    """

    enable_secret_scan: bool = True
    local_only: bool = False
    strip_intent: bool = False
    license: str = "MIT"
    license_header: str | None = None
    enable_provenance: bool = True


class Settings(BaseModel):
    """Complete Axiom settings.

    Attributes:
        project: Project-level settings.
        generation: Code generation settings.
        verification: Verification settings.
        cache: Caching settings.
        logging: Logging settings.
        security: Security settings.
        config_path: Path to the loaded config file (if any).
    """

    project: ProjectSettings = Field(default_factory=ProjectSettings)
    generation: GenerationSettings = Field(default_factory=GenerationSettings)
    verification: VerificationSettings = Field(default_factory=VerificationSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    config_path: Path | None = None

    def get_model_for_target(self, target: str) -> str:
        """Get the model to use for a given target.

        Args:
            target: The generation target (e.g., 'python:function').

        Returns:
            The model name to use.
        """
        return self.generation.models.get(target, self.generation.default_model)

    def get_spec_dir(self, base_path: Path | None = None) -> Path:
        """Get the absolute path to the spec directory.

        Args:
            base_path: Base path to resolve relative paths from.
                      Defaults to current working directory.

        Returns:
            Absolute path to the spec directory.
        """
        base = base_path or Path.cwd()
        return base / self.project.spec_dir

    def get_generated_dir(self, base_path: Path | None = None) -> Path:
        """Get the absolute path to the generated code directory.

        Args:
            base_path: Base path to resolve relative paths from.
                      Defaults to current working directory.

        Returns:
            Absolute path to the generated directory.
        """
        base = base_path or Path.cwd()
        return base / self.project.generated_dir

    def get_cache_dir(self, base_path: Path | None = None) -> Path:
        """Get the absolute path to the cache directory.

        Args:
            base_path: Base path to resolve relative paths from.
                      Defaults to current working directory.

        Returns:
            Absolute path to the cache directory.
        """
        base = base_path or Path.cwd()
        return base / self.project.cache_dir

    def get_provenance_log_path(self, base_path: Path | None = None) -> Path:
        """Get the absolute path to the provenance log file.

        Args:
            base_path: Base path to resolve relative paths from.
                      Defaults to current working directory.

        Returns:
            Absolute path to the provenance log file.
        """
        return self.get_cache_dir(base_path) / "provenance.jsonl"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries.

    Args:
        base: The base dictionary.
        override: The dictionary to merge on top.

    Returns:
        Merged dictionary.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_settings(
    config_path: Path | None = None,
    search_parents: bool = True,
) -> Settings:
    """Load settings from axiom.toml.

    Args:
        config_path: Explicit path to axiom.toml. If not provided,
                    searches current directory and parents.
        search_parents: Whether to search parent directories for axiom.toml.

    Returns:
        Loaded Settings object.

    Raises:
        ConfigError: If the config file exists but cannot be parsed.
    """
    # Find config file
    found_path: Path | None
    if config_path is not None:
        if not config_path.exists():
            logger.debug("Config file not found, using defaults", path=str(config_path))
            return Settings()
        found_path = config_path
    else:
        found_path = _find_config_file(search_parents)

    if found_path is None:
        logger.debug("No axiom.toml found, using defaults")
        return Settings()

    # Load and parse config
    try:
        with open(found_path, "rb") as f:
            data = tomli.load(f)
    except tomli.TOMLDecodeError as e:
        raise ConfigError(
            f"Invalid TOML syntax: {e}",
            config_file=str(found_path),
        ) from e

    logger.debug("Loaded config", path=str(found_path))

    # Build settings from parsed data
    try:
        settings_data: dict[str, Any] = {}

        if "project" in data:
            settings_data["project"] = data["project"]

        if "generation" in data:
            settings_data["generation"] = data["generation"]

        if "verification" in data:
            settings_data["verification"] = data["verification"]

        if "cache" in data:
            settings_data["cache"] = data["cache"]

        if "logging" in data:
            settings_data["logging"] = data["logging"]

        if "security" in data:
            settings_data["security"] = data["security"]

        settings_data["config_path"] = found_path

        return Settings(**settings_data)
    except Exception as e:
        raise ConfigError(
            f"Invalid configuration: {e}",
            config_file=str(found_path),
        ) from e


def _find_config_file(search_parents: bool) -> Path | None:
    """Find axiom.toml in current directory or parents.

    Args:
        search_parents: Whether to search parent directories.

    Returns:
        Path to axiom.toml if found, None otherwise.
    """
    current = Path.cwd()

    while True:
        config_path = current / "axiom.toml"
        if config_path.exists():
            return config_path

        if not search_parents:
            return None

        parent = current.parent
        if parent == current:
            # Reached root
            return None
        current = parent


def get_api_key(provider: str = "anthropic") -> str | None:
    """Get API key for a provider from environment.

    Args:
        provider: The provider name ('anthropic' or 'openai').

    Returns:
        The API key if found, None otherwise.
    """
    env_vars = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
    }

    env_var = env_vars.get(provider.lower())
    if env_var:
        return os.environ.get(env_var)
    return None
