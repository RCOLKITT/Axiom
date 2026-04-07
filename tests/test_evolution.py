"""Tests for spec evolution and migration tracking."""

from __future__ import annotations

from pathlib import Path

import pytest

from axiom.evolution import (
    BreakingChangeDetector,
    ChangeType,
    Migration,
    MigrationManager,
    SpecTracker,
    SpecVersion,
)


class TestSpecTracker:
    """Tests for spec version tracking."""

    def test_record_version(self, tmp_path: Path) -> None:
        """Should record a new version."""
        tracker = SpecTracker(cache_dir=tmp_path)

        version = tracker.record_version(
            spec_name="test_spec",
            version="1.0.0",
            spec_content={"metadata": {"name": "test_spec"}},
            changes="Initial version",
        )

        assert version.spec_name == "test_spec"
        assert version.version == "1.0.0"
        assert version.changes == "Initial version"
        assert version.content_hash is not None

    def test_get_history(self, tmp_path: Path) -> None:
        """Should retrieve version history."""
        tracker = SpecTracker(cache_dir=tmp_path)

        tracker.record_version("test_spec", "1.0.0", {"v": 1})
        tracker.record_version("test_spec", "1.1.0", {"v": 2})

        history = tracker.get_history("test_spec")
        assert len(history) == 2
        assert history[0].version == "1.0.0"
        assert history[1].version == "1.1.0"

    def test_get_latest_version(self, tmp_path: Path) -> None:
        """Should get the latest version."""
        tracker = SpecTracker(cache_dir=tmp_path)

        tracker.record_version("test_spec", "1.0.0", {"v": 1})
        tracker.record_version("test_spec", "1.1.0", {"v": 2})

        latest = tracker.get_latest_version("test_spec")
        assert latest is not None
        assert latest.version == "1.1.0"

    def test_get_latest_version_no_history(self, tmp_path: Path) -> None:
        """Should return None if no history."""
        tracker = SpecTracker(cache_dir=tmp_path)
        assert tracker.get_latest_version("nonexistent") is None

    def test_has_changed(self, tmp_path: Path) -> None:
        """Should detect changes from last version."""
        tracker = SpecTracker(cache_dir=tmp_path)

        content1 = {"metadata": {"name": "test", "version": "1.0.0"}}
        content2 = {"metadata": {"name": "test", "version": "1.1.0"}}

        tracker.record_version("test_spec", "1.0.0", content1)

        assert tracker.has_changed("test_spec", content2) is True
        assert tracker.has_changed("test_spec", content1) is False

    def test_has_changed_new_spec(self, tmp_path: Path) -> None:
        """Should return True for new specs."""
        tracker = SpecTracker(cache_dir=tmp_path)
        assert tracker.has_changed("new_spec", {"test": 1}) is True


class TestBreakingChangeDetector:
    """Tests for breaking change detection."""

    def test_no_changes(self) -> None:
        """Should detect no changes for identical specs."""
        detector = BreakingChangeDetector()
        spec = {"metadata": {"name": "test"}}

        changes = detector.detect_changes(spec, spec)
        assert len(changes) == 0

    def test_version_change_not_breaking(self) -> None:
        """Version change should not be breaking."""
        detector = BreakingChangeDetector()
        old_spec = {"metadata": {"version": "1.0.0"}}
        new_spec = {"metadata": {"version": "1.1.0"}}

        changes = detector.detect_changes(old_spec, new_spec)
        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.VERSION_CHANGED
        assert changes[0].is_breaking is False

    def test_parameter_removed_breaking(self) -> None:
        """Removing a parameter should be breaking."""
        detector = BreakingChangeDetector()
        old_spec = {
            "interface": {
                "parameters": [
                    {"name": "x", "type": "int"},
                    {"name": "y", "type": "int"},
                ]
            }
        }
        new_spec = {"interface": {"parameters": [{"name": "x", "type": "int"}]}}

        changes = detector.detect_changes(old_spec, new_spec)
        breaking = [c for c in changes if c.is_breaking]
        assert len(breaking) == 1
        assert breaking[0].change_type == ChangeType.PARAMETER_REMOVED

    def test_parameter_type_changed_breaking(self) -> None:
        """Changing parameter type should be breaking."""
        detector = BreakingChangeDetector()
        old_spec = {"interface": {"parameters": [{"name": "x", "type": "int"}]}}
        new_spec = {"interface": {"parameters": [{"name": "x", "type": "str"}]}}

        changes = detector.detect_changes(old_spec, new_spec)
        breaking = [c for c in changes if c.is_breaking]
        assert len(breaking) == 1
        assert breaking[0].change_type == ChangeType.PARAMETER_TYPE_CHANGED

    def test_optional_parameter_added_not_breaking(self) -> None:
        """Adding optional parameter should not be breaking."""
        detector = BreakingChangeDetector()
        old_spec = {"interface": {"parameters": [{"name": "x", "type": "int"}]}}
        new_spec = {
            "interface": {
                "parameters": [
                    {"name": "x", "type": "int"},
                    {"name": "y", "type": "int", "constraints": "optional"},
                ]
            }
        }

        changes = detector.detect_changes(old_spec, new_spec)
        assert not any(c.is_breaking for c in changes)

    def test_required_parameter_added_breaking(self) -> None:
        """Adding required parameter should be breaking."""
        detector = BreakingChangeDetector()
        old_spec = {"interface": {"parameters": [{"name": "x", "type": "int"}]}}
        new_spec = {
            "interface": {
                "parameters": [
                    {"name": "x", "type": "int"},
                    {"name": "y", "type": "int"},  # No default or optional
                ]
            }
        }

        changes = detector.detect_changes(old_spec, new_spec)
        breaking = [c for c in changes if c.is_breaking]
        assert len(breaking) == 1
        assert breaking[0].change_type == ChangeType.REQUIRED_PARAMETER_ADDED

    def test_return_type_changed_breaking(self) -> None:
        """Changing return type should be breaking."""
        detector = BreakingChangeDetector()
        old_spec = {"interface": {"returns": {"type": "int"}}}
        new_spec = {"interface": {"returns": {"type": "str"}}}

        changes = detector.detect_changes(old_spec, new_spec)
        breaking = [c for c in changes if c.is_breaking]
        assert len(breaking) == 1
        assert breaking[0].change_type == ChangeType.RETURN_TYPE_CHANGED

    def test_function_name_changed_breaking(self) -> None:
        """Changing function name should be breaking."""
        detector = BreakingChangeDetector()
        old_spec = {"interface": {"function_name": "old_func"}}
        new_spec = {"interface": {"function_name": "new_func"}}

        changes = detector.detect_changes(old_spec, new_spec)
        breaking = [c for c in changes if c.is_breaking]
        assert len(breaking) == 1
        assert breaking[0].change_type == ChangeType.FUNCTION_NAME_CHANGED

    def test_example_behavior_changed_breaking(self) -> None:
        """Changing example output should be breaking."""
        detector = BreakingChangeDetector()
        old_spec = {"examples": [{"name": "test1", "input": {"x": 1}, "expected_output": 2}]}
        new_spec = {"examples": [{"name": "test1", "input": {"x": 1}, "expected_output": 3}]}

        changes = detector.detect_changes(old_spec, new_spec)
        breaking = [c for c in changes if c.is_breaking]
        assert len(breaking) == 1
        assert breaking[0].change_type == ChangeType.EXAMPLE_BEHAVIOR_CHANGED

    def test_example_added_not_breaking(self) -> None:
        """Adding an example should not be breaking."""
        detector = BreakingChangeDetector()
        old_spec = {"examples": []}
        new_spec = {"examples": [{"name": "new_test", "input": {}}]}

        changes = detector.detect_changes(old_spec, new_spec)
        assert not any(c.is_breaking for c in changes)

    def test_has_breaking_changes(self) -> None:
        """Should correctly identify breaking changes."""
        detector = BreakingChangeDetector()

        # Non-breaking change
        old1 = {"metadata": {"version": "1.0.0"}}
        new1 = {"metadata": {"version": "1.1.0"}}
        assert detector.has_breaking_changes(old1, new1) is False

        # Breaking change
        old2 = {"interface": {"returns": {"type": "int"}}}
        new2 = {"interface": {"returns": {"type": "str"}}}
        assert detector.has_breaking_changes(old2, new2) is True


class TestMigrationManager:
    """Tests for migration management."""

    def test_create_migration(self, tmp_path: Path) -> None:
        """Should create a new migration."""
        manager = MigrationManager(cache_dir=tmp_path)

        migration = manager.create_migration(
            spec_name="test_spec",
            from_version="1.0.0",
            to_version="1.1.0",
            description="Add new feature",
        )

        assert migration.spec_name == "test_spec"
        assert migration.from_version == "1.0.0"
        assert migration.to_version == "1.1.0"
        assert migration.is_applied is False

    def test_get_migrations(self, tmp_path: Path) -> None:
        """Should retrieve all migrations."""
        manager = MigrationManager(cache_dir=tmp_path)

        manager.create_migration("spec_a", "1.0.0", "1.1.0", "Change A")
        manager.create_migration("spec_b", "1.0.0", "1.1.0", "Change B")

        all_migrations = manager.get_migrations()
        assert len(all_migrations) == 2

        spec_a_migrations = manager.get_migrations("spec_a")
        assert len(spec_a_migrations) == 1

    def test_apply_migration(self, tmp_path: Path) -> None:
        """Should mark migration as applied."""
        manager = MigrationManager(cache_dir=tmp_path)

        migration = manager.create_migration("test_spec", "1.0.0", "1.1.0", "Test change")

        assert migration.is_applied is False

        applied = manager.apply_migration(migration.id)
        assert applied.is_applied is True
        assert applied.applied_at is not None

    def test_apply_migration_already_applied(self, tmp_path: Path) -> None:
        """Should raise error if migration already applied."""
        manager = MigrationManager(cache_dir=tmp_path)

        migration = manager.create_migration("test_spec", "1.0.0", "1.1.0", "Test change")
        manager.apply_migration(migration.id)

        with pytest.raises(ValueError, match="already applied"):
            manager.apply_migration(migration.id)

    def test_get_pending_migrations(self, tmp_path: Path) -> None:
        """Should get only pending migrations."""
        manager = MigrationManager(cache_dir=tmp_path)

        m1 = manager.create_migration("spec", "1.0.0", "1.1.0", "Change 1")
        m2 = manager.create_migration("spec", "1.1.0", "1.2.0", "Change 2")

        manager.apply_migration(m1.id)

        pending = manager.get_pending_migrations("spec")
        assert len(pending) == 1
        assert pending[0].id == m2.id

    def test_get_status(self, tmp_path: Path) -> None:
        """Should return migration status."""
        manager = MigrationManager(cache_dir=tmp_path)

        m1 = manager.create_migration("spec", "1.0.0", "1.1.0", "Change 1")
        _m2 = manager.create_migration("spec", "1.1.0", "1.2.0", "Change 2")
        manager.apply_migration(m1.id)

        status = manager.get_status("spec")
        assert status["total_migrations"] == 2
        assert status["applied_count"] == 1
        assert status["pending_count"] == 1


class TestSpecVersionSerialization:
    """Tests for SpecVersion serialization."""

    def test_to_dict_and_from_dict(self) -> None:
        """Should serialize and deserialize correctly."""
        from datetime import datetime

        version = SpecVersion(
            spec_name="test",
            version="1.0.0",
            content_hash="abc123",
            timestamp=datetime.now(),
            spec_content={"test": 1},
            changes="Test change",
        )

        data = version.to_dict()
        restored = SpecVersion.from_dict(data)

        assert restored.spec_name == version.spec_name
        assert restored.version == version.version
        assert restored.content_hash == version.content_hash
        assert restored.changes == version.changes


class TestMigrationSerialization:
    """Tests for Migration serialization."""

    def test_to_dict_and_from_dict(self) -> None:
        """Should serialize and deserialize correctly."""
        from datetime import datetime

        migration = Migration(
            id="test_123",
            spec_name="test",
            from_version="1.0.0",
            to_version="1.1.0",
            description="Test",
            created_at=datetime.now(),
            changes=[{"type": "test"}],
        )

        data = migration.to_dict()
        restored = Migration.from_dict(data)

        assert restored.id == migration.id
        assert restored.spec_name == migration.spec_name
        assert restored.from_version == migration.from_version
        assert restored.to_version == migration.to_version
