"""Migration management for spec evolution.

Provides tools for creating and applying migrations between spec versions.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Migration:
    """A migration between spec versions.

    Attributes:
        id: Unique migration identifier (timestamp-based).
        spec_name: Name of the spec being migrated.
        from_version: Source version.
        to_version: Target version.
        description: Human-readable description.
        created_at: When the migration was created.
        applied_at: When the migration was applied (None if pending).
        changes: List of changes in this migration.
        auto_generated: Whether this was auto-generated.
    """

    id: str
    spec_name: str
    from_version: str
    to_version: str
    description: str
    created_at: datetime
    applied_at: datetime | None = None
    changes: list[dict[str, Any]] = field(default_factory=list)
    auto_generated: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "spec_name": self.spec_name,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "changes": self.changes,
            "auto_generated": self.auto_generated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Migration:
        """Create from dictionary."""
        return cls(
            id=data["id"],
            spec_name=data["spec_name"],
            from_version=data["from_version"],
            to_version=data["to_version"],
            description=data["description"],
            created_at=datetime.fromisoformat(data["created_at"]),
            applied_at=(
                datetime.fromisoformat(data["applied_at"]) if data.get("applied_at") else None
            ),
            changes=data.get("changes", []),
            auto_generated=data.get("auto_generated", False),
        )

    @property
    def is_applied(self) -> bool:
        """Check if migration has been applied."""
        return self.applied_at is not None


class MigrationManager:
    """Manages migrations for spec evolution.

    Stores migrations in `.axiom-cache/migrations/` as JSON files.
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        """Initialize the manager.

        Args:
            cache_dir: Directory for storing migrations. Defaults to .axiom-cache.
        """
        self.cache_dir = cache_dir or Path(".axiom-cache")
        self.migrations_dir = self.cache_dir / "migrations"
        self.migrations_dir.mkdir(parents=True, exist_ok=True)

    def create_migration(
        self,
        spec_name: str,
        from_version: str,
        to_version: str,
        description: str,
        changes: list[dict[str, Any]] | None = None,
        auto_generated: bool = False,
    ) -> Migration:
        """Create a new migration.

        Args:
            spec_name: Name of the spec.
            from_version: Source version.
            to_version: Target version.
            description: Human-readable description.
            changes: List of changes (from detector).
            auto_generated: Whether this was auto-generated.

        Returns:
            The created migration.
        """
        # Generate unique ID using timestamp and uuid
        timestamp = datetime.now()
        unique_suffix = uuid.uuid4().hex[:8]
        migration_id = timestamp.strftime("%Y%m%d_%H%M%S") + f"_{spec_name}_{unique_suffix}"

        migration = Migration(
            id=migration_id,
            spec_name=spec_name,
            from_version=from_version,
            to_version=to_version,
            description=description,
            created_at=timestamp,
            changes=changes or [],
            auto_generated=auto_generated,
        )

        self._save_migration(migration)
        return migration

    def get_migrations(self, spec_name: str | None = None) -> list[Migration]:
        """Get all migrations, optionally filtered by spec name.

        Args:
            spec_name: Optional spec name filter.

        Returns:
            List of migrations, oldest first.
        """
        migrations: list[Migration] = []

        for migration_file in sorted(self.migrations_dir.glob("*.json")):
            with open(migration_file) as f:
                data = json.load(f)
            migration = Migration.from_dict(data)

            if spec_name is None or migration.spec_name == spec_name:
                migrations.append(migration)

        return migrations

    def get_pending_migrations(
        self,
        spec_name: str | None = None,
    ) -> list[Migration]:
        """Get migrations that haven't been applied.

        Args:
            spec_name: Optional spec name filter.

        Returns:
            List of pending migrations.
        """
        return [m for m in self.get_migrations(spec_name) if not m.is_applied]

    def get_migration(self, migration_id: str) -> Migration | None:
        """Get a specific migration by ID.

        Args:
            migration_id: Migration identifier.

        Returns:
            The migration, or None if not found.
        """
        migration_file = self.migrations_dir / f"{migration_id}.json"
        if not migration_file.exists():
            return None

        with open(migration_file) as f:
            data = json.load(f)
        return Migration.from_dict(data)

    def apply_migration(self, migration_id: str) -> Migration:
        """Mark a migration as applied.

        Args:
            migration_id: Migration identifier.

        Returns:
            The updated migration.

        Raises:
            ValueError: If migration not found or already applied.
        """
        migration = self.get_migration(migration_id)
        if migration is None:
            raise ValueError(f"Migration '{migration_id}' not found")

        if migration.is_applied:
            raise ValueError(f"Migration '{migration_id}' is already applied")

        migration.applied_at = datetime.now()
        self._save_migration(migration)
        return migration

    def get_status(self, spec_name: str) -> dict[str, Any]:
        """Get migration status for a spec.

        Args:
            spec_name: Name of the spec.

        Returns:
            Status dictionary with counts and details.
        """
        migrations = self.get_migrations(spec_name)
        pending = [m for m in migrations if not m.is_applied]
        applied = [m for m in migrations if m.is_applied]

        return {
            "spec_name": spec_name,
            "total_migrations": len(migrations),
            "applied_count": len(applied),
            "pending_count": len(pending),
            "pending_migrations": [
                {
                    "id": m.id,
                    "from_version": m.from_version,
                    "to_version": m.to_version,
                    "description": m.description,
                }
                for m in pending
            ],
            "latest_applied": applied[-1].to_dict() if applied else None,
        }

    def _save_migration(self, migration: Migration) -> None:
        """Save a migration to disk."""
        migration_file = self.migrations_dir / f"{migration.id}.json"
        with open(migration_file, "w") as f:
            json.dump(migration.to_dict(), f, indent=2)

    def _get_migration_file(self, migration_id: str) -> Path:
        """Get the path to a migration file."""
        return self.migrations_dir / f"{migration_id}.json"
