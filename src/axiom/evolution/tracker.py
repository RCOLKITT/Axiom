"""Spec version tracking.

Tracks spec changes over time by storing versions in the cache directory.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class SpecVersion:
    """A snapshot of a spec at a point in time.

    Attributes:
        spec_name: Name of the spec.
        version: Semantic version string.
        content_hash: SHA-256 hash of spec content.
        timestamp: When this version was recorded.
        spec_content: Full spec content as dict.
        changes: Description of changes from previous version.
    """

    spec_name: str
    version: str
    content_hash: str
    timestamp: datetime
    spec_content: dict[str, Any]
    changes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "spec_name": self.spec_name,
            "version": self.version,
            "content_hash": self.content_hash,
            "timestamp": self.timestamp.isoformat(),
            "spec_content": self.spec_content,
            "changes": self.changes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpecVersion:
        """Create from dictionary."""
        return cls(
            spec_name=data["spec_name"],
            version=data["version"],
            content_hash=data["content_hash"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            spec_content=data["spec_content"],
            changes=data.get("changes", ""),
        )


class SpecTracker:
    """Tracks spec versions and their history.

    Stores version history in `.axiom-cache/history/` as JSON files.
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        """Initialize the tracker.

        Args:
            cache_dir: Directory for storing history. Defaults to .axiom-cache.
        """
        self.cache_dir = cache_dir or Path(".axiom-cache")
        self.history_dir = self.cache_dir / "history"
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def record_version(
        self,
        spec_name: str,
        version: str,
        spec_content: dict[str, Any],
        changes: str = "",
    ) -> SpecVersion:
        """Record a new version of a spec.

        Args:
            spec_name: Name of the spec.
            version: Semantic version string.
            spec_content: Full spec content as dict.
            changes: Description of changes from previous version.

        Returns:
            The recorded SpecVersion.
        """
        content_hash = self._compute_hash(spec_content)
        timestamp = datetime.now()

        spec_version = SpecVersion(
            spec_name=spec_name,
            version=version,
            content_hash=content_hash,
            timestamp=timestamp,
            spec_content=spec_content,
            changes=changes,
        )

        self._save_version(spec_version)
        return spec_version

    def get_history(self, spec_name: str) -> list[SpecVersion]:
        """Get version history for a spec.

        Args:
            spec_name: Name of the spec.

        Returns:
            List of versions, oldest first.
        """
        history_file = self._get_history_file(spec_name)
        if not history_file.exists():
            return []

        with open(history_file) as f:
            data = json.load(f)

        return [SpecVersion.from_dict(v) for v in data.get("versions", [])]

    def get_latest_version(self, spec_name: str) -> SpecVersion | None:
        """Get the latest version of a spec.

        Args:
            spec_name: Name of the spec.

        Returns:
            Latest version, or None if no history.
        """
        history = self.get_history(spec_name)
        return history[-1] if history else None

    def get_version(self, spec_name: str, version: str) -> SpecVersion | None:
        """Get a specific version of a spec.

        Args:
            spec_name: Name of the spec.
            version: Semantic version string.

        Returns:
            The version, or None if not found.
        """
        history = self.get_history(spec_name)
        for v in history:
            if v.version == version:
                return v
        return None

    def has_changed(
        self,
        spec_name: str,
        spec_content: dict[str, Any],
    ) -> bool:
        """Check if a spec has changed from its last recorded version.

        Args:
            spec_name: Name of the spec.
            spec_content: Current spec content.

        Returns:
            True if changed, False if same as latest version.
        """
        latest = self.get_latest_version(spec_name)
        if latest is None:
            return True  # No history = new spec

        current_hash = self._compute_hash(spec_content)
        return current_hash != latest.content_hash

    def clear_history(self, spec_name: str) -> None:
        """Clear all history for a spec.

        Args:
            spec_name: Name of the spec.
        """
        history_file = self._get_history_file(spec_name)
        if history_file.exists():
            history_file.unlink()

    def _get_history_file(self, spec_name: str) -> Path:
        """Get the path to a spec's history file."""
        return self.history_dir / f"{spec_name}.history.json"

    def _save_version(self, version: SpecVersion) -> None:
        """Save a version to the history file."""
        history_file = self._get_history_file(version.spec_name)

        if history_file.exists():
            with open(history_file) as f:
                data = json.load(f)
        else:
            data = {"spec_name": version.spec_name, "versions": []}

        data["versions"].append(version.to_dict())

        with open(history_file, "w") as f:
            json.dump(data, f, indent=2)

    def _compute_hash(self, content: dict[str, Any]) -> str:
        """Compute SHA-256 hash of spec content."""
        # Normalize the content for consistent hashing
        normalized = json.dumps(content, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(normalized.encode()).hexdigest()
