"""Cache store for generated code.

Content-addressed storage that persists generated code and metadata.
Cache location: .axiom/cache/ (configurable via settings).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from axiom.cache.keys import compute_cache_key, get_cache_filename
from axiom.spec.models import Spec

logger = structlog.get_logger()


@dataclass
class CacheEntry:
    """A single cache entry."""

    key: str
    spec_name: str
    model: str
    target: str
    code: str
    created_at: datetime
    axiom_version: str
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "key": self.key,
            "spec_name": self.spec_name,
            "model": self.model,
            "target": self.target,
            "code": self.code,
            "created_at": self.created_at.isoformat(),
            "axiom_version": self.axiom_version,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CacheEntry:
        """Deserialize from dictionary."""
        return cls(
            key=data["key"],
            spec_name=data["spec_name"],
            model=data["model"],
            target=data["target"],
            code=data["code"],
            created_at=datetime.fromisoformat(data["created_at"]),
            axiom_version=data["axiom_version"],
            metadata=data.get("metadata"),
        )


@dataclass
class CacheStatus:
    """Status of a cache lookup."""

    hit: bool
    entry: CacheEntry | None = None
    reason: str | None = None  # For misses/stale: why cache wasn't used


class CacheStore:
    """File-based cache store for generated code."""

    def __init__(self, cache_dir: Path) -> None:
        """Initialize the cache store.

        Args:
            cache_dir: Directory to store cache files.
        """
        self.cache_dir = cache_dir
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """Ensure the cache directory exists."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_entry_path(self, key: str) -> Path:
        """Get the file path for a cache entry."""
        return self.cache_dir / get_cache_filename(key)

    def get(self, key: str) -> CacheEntry | None:
        """Get a cache entry by key.

        Args:
            key: The cache key (hash).

        Returns:
            The cache entry if found, None otherwise.
        """
        entry_path = self._get_entry_path(key)
        if not entry_path.exists():
            return None

        try:
            data = json.loads(entry_path.read_text(encoding="utf-8"))
            return CacheEntry.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(
                "Failed to read cache entry",
                key=key[:12] + "...",
                error=str(e),
            )
            return None

    def put(
        self,
        spec: Spec,
        model: str,
        code: str,
        axiom_version: str,
        metadata: dict[str, Any] | None = None,
    ) -> CacheEntry:
        """Store a cache entry.

        Args:
            spec: The spec that was generated.
            model: The model used for generation.
            code: The generated code.
            axiom_version: The axiom version used.
            metadata: Optional additional metadata.

        Returns:
            The created cache entry.
        """
        key = compute_cache_key(spec, model)

        entry = CacheEntry(
            key=key,
            spec_name=spec.spec_name,
            model=model,
            target=spec.metadata.target,
            code=code,
            created_at=datetime.now(),
            axiom_version=axiom_version,
            metadata=metadata,
        )

        entry_path = self._get_entry_path(key)
        entry_path.write_text(
            json.dumps(entry.to_dict(), indent=2),
            encoding="utf-8",
        )

        logger.debug(
            "Stored cache entry",
            spec=spec.spec_name,
            key=key[:12] + "...",
        )

        return entry

    def delete(self, key: str) -> bool:
        """Delete a cache entry.

        Args:
            key: The cache key to delete.

        Returns:
            True if entry was deleted, False if it didn't exist.
        """
        entry_path = self._get_entry_path(key)
        if entry_path.exists():
            entry_path.unlink()
            logger.debug("Deleted cache entry", key=key[:12] + "...")
            return True
        return False

    def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries cleared.
        """
        count = 0
        for entry_path in self.cache_dir.glob("*.json"):
            entry_path.unlink()
            count += 1

        logger.info("Cleared cache", entries=count)
        return count

    def list_entries(self) -> list[CacheEntry]:
        """List all cache entries.

        Returns:
            List of all cache entries.
        """
        entries = []
        for entry_path in self.cache_dir.glob("*.json"):
            try:
                data = json.loads(entry_path.read_text(encoding="utf-8"))
                entries.append(CacheEntry.from_dict(data))
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(
                    "Failed to read cache entry",
                    path=entry_path.name,
                    error=str(e),
                )
        return entries

    def get_entry_for_spec(self, spec_name: str) -> CacheEntry | None:
        """Find a cache entry by spec name.

        Note: There may be multiple entries for the same spec (different models/versions).
        This returns the most recent one.

        Args:
            spec_name: The name of the spec.

        Returns:
            The most recent cache entry for the spec, or None.
        """
        entries = [e for e in self.list_entries() if e.spec_name == spec_name]
        if not entries:
            return None
        # Return most recent
        return max(entries, key=lambda e: e.created_at)

    def lookup(
        self,
        spec: Spec,
        model: str,
        current_axiom_version: str,
    ) -> CacheStatus:
        """Look up cache status for a spec.

        Checks if there's a valid cache entry and determines if it's:
        - HIT: Exact match, can use cached code
        - MISS: No cache entry exists
        - STALE: Entry exists but axiom version changed (needs re-verification)

        Args:
            spec: The spec to look up.
            model: The model being used.
            current_axiom_version: The current axiom version.

        Returns:
            CacheStatus with hit/miss info and reason.
        """
        key = compute_cache_key(spec, model)
        entry = self.get(key)

        if entry is None:
            logger.debug(
                "Cache MISS",
                spec=spec.spec_name,
                reason="no entry",
            )
            return CacheStatus(hit=False, reason="no cache entry")

        # Check axiom version
        if entry.axiom_version != current_axiom_version:
            logger.debug(
                "Cache STALE",
                spec=spec.spec_name,
                cached_version=entry.axiom_version,
                current_version=current_axiom_version,
            )
            return CacheStatus(
                hit=False,
                entry=entry,
                reason=f"axiom version changed ({entry.axiom_version} -> {current_axiom_version})",
            )

        logger.debug(
            "Cache HIT",
            spec=spec.spec_name,
            key=key[:12] + "...",
        )
        return CacheStatus(hit=True, entry=entry)

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats.
        """
        entries = self.list_entries()

        # Group by spec
        specs: dict[str, list[CacheEntry]] = {}
        for entry in entries:
            if entry.spec_name not in specs:
                specs[entry.spec_name] = []
            specs[entry.spec_name].append(entry)

        # Calculate total size
        total_size = sum(
            self._get_entry_path(e.key).stat().st_size
            for e in entries
            if self._get_entry_path(e.key).exists()
        )

        return {
            "total_entries": len(entries),
            "unique_specs": len(specs),
            "total_size_bytes": total_size,
            "total_size_human": _format_bytes(total_size),
            "entries_by_spec": {name: len(es) for name, es in specs.items()},
        }


def _format_bytes(size: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size //= 1024
    return f"{size:.1f} TB"
