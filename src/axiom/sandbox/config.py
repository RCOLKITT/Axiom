"""Sandbox configuration for execution limits and security settings."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SandboxConfig:
    """Configuration for sandboxed execution.

    Attributes:
        memory_limit_mb: Maximum memory in megabytes.
        cpu_limit: CPU quota (1.0 = 1 CPU core).
        timeout_seconds: Maximum execution time.
        network_enabled: Whether to allow network access.
        read_only_root: Mount root filesystem as read-only.
        allowed_paths: Paths that can be read/written.
        env_vars: Environment variables to pass.
        image: Docker image to use.
        python_version: Python version (for default image).
    """

    memory_limit_mb: int = 256
    cpu_limit: float = 1.0
    timeout_seconds: int = 30
    network_enabled: bool = False
    read_only_root: bool = True
    allowed_paths: list[Path] = field(default_factory=list)
    env_vars: dict[str, str] = field(default_factory=dict)
    image: str = ""
    python_version: str = "3.12"

    def get_image(self) -> str:
        """Get the Docker image to use."""
        if self.image:
            return self.image
        return f"python:{self.python_version}-slim"

    @classmethod
    def default(cls) -> SandboxConfig:
        """Create a default sandbox configuration."""
        return cls()

    @classmethod
    def strict(cls) -> SandboxConfig:
        """Create a strict sandbox configuration with minimal resources."""
        return cls(
            memory_limit_mb=128,
            cpu_limit=0.5,
            timeout_seconds=10,
            network_enabled=False,
            read_only_root=True,
        )

    @classmethod
    def permissive(cls) -> SandboxConfig:
        """Create a permissive sandbox for trusted code."""
        return cls(
            memory_limit_mb=1024,
            cpu_limit=2.0,
            timeout_seconds=120,
            network_enabled=True,
            read_only_root=False,
        )
