"""Tests for the provenance logging module."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from axiom.security.provenance import (
    ProvenanceEntry,
    ProvenanceLog,
    compute_spec_hash,
    create_provenance_entry,
)


class TestProvenanceEntry:
    """Tests for ProvenanceEntry dataclass."""

    def test_to_json_line(self) -> None:
        """Test serialization to JSON line."""
        entry = ProvenanceEntry(
            timestamp="2026-04-06T10:30:00",
            spec_name="validate_email",
            spec_hash="abc123",
            model="claude-sonnet-4-20250514",
            action="generate",
            result="success",
            axiom_version="0.1.0",
            duration_ms=2500,
        )
        json_line = entry.to_json_line()

        assert "validate_email" in json_line
        assert "abc123" in json_line
        assert "generate" in json_line
        assert "success" in json_line
        assert "\n" not in json_line

    def test_to_json_line_omits_none_values(self) -> None:
        """Test that None values are omitted from JSON."""
        entry = ProvenanceEntry(
            timestamp="2026-04-06T10:30:00",
            spec_name="test",
            spec_hash="abc",
            model="model",
            action="generate",
            result="success",
            axiom_version="0.1.0",
            # These are None by default
        )
        json_line = entry.to_json_line()

        assert "failure_reason" not in json_line
        assert "duration_ms" not in json_line
        assert "user" not in json_line
        assert "metadata" not in json_line

    def test_from_json_line(self) -> None:
        """Test deserialization from JSON line."""
        original = ProvenanceEntry(
            timestamp="2026-04-06T10:30:00",
            spec_name="validate_email",
            spec_hash="abc123def456",
            model="claude-sonnet-4-20250514",
            action="generate",
            result="success",
            axiom_version="0.1.0",
            duration_ms=1500,
            failure_reason=None,
            user="testuser",
        )
        json_line = original.to_json_line()
        restored = ProvenanceEntry.from_json_line(json_line)

        assert restored.spec_name == original.spec_name
        assert restored.spec_hash == original.spec_hash
        assert restored.model == original.model
        assert restored.action == original.action
        assert restored.result == original.result
        assert restored.duration_ms == original.duration_ms
        assert restored.user == original.user

    def test_from_json_line_minimal(self) -> None:
        """Test deserialization with minimal fields."""
        json_line = '{"timestamp":"2026-04-06","spec_name":"test","spec_hash":"a","model":"m","action":"generate","result":"success","axiom_version":"0.1"}'
        entry = ProvenanceEntry.from_json_line(json_line)

        assert entry.spec_name == "test"
        assert entry.duration_ms is None
        assert entry.failure_reason is None


class TestProvenanceLog:
    """Tests for ProvenanceLog class."""

    def test_log_creates_file(self) -> None:
        """Test that logging creates the file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "provenance.jsonl"
            log = ProvenanceLog(log_path)

            entry = ProvenanceEntry(
                timestamp=datetime.now().isoformat(),
                spec_name="test_spec",
                spec_hash="abc123",
                model="test-model",
                action="generate",
                result="success",
                axiom_version="0.1.0",
            )
            log.log(entry)

            assert log_path.exists()
            content = log_path.read_text()
            assert "test_spec" in content

    def test_log_appends(self) -> None:
        """Test that logging appends to existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "provenance.jsonl"
            log = ProvenanceLog(log_path)

            # Log two entries
            for i in range(2):
                entry = ProvenanceEntry(
                    timestamp=datetime.now().isoformat(),
                    spec_name=f"spec_{i}",
                    spec_hash=f"hash_{i}",
                    model="model",
                    action="generate",
                    result="success",
                    axiom_version="0.1.0",
                )
                log.log(entry)

            # Both should be in the file
            lines = log_path.read_text().strip().split("\n")
            assert len(lines) == 2
            assert "spec_0" in lines[0]
            assert "spec_1" in lines[1]

    def test_query_no_filters(self) -> None:
        """Test querying without filters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "provenance.jsonl"
            log = ProvenanceLog(log_path)

            # Log some entries
            for i in range(3):
                entry = ProvenanceEntry(
                    timestamp=datetime.now().isoformat(),
                    spec_name=f"spec_{i}",
                    spec_hash=f"hash_{i}",
                    model="model",
                    action="generate",
                    result="success",
                    axiom_version="0.1.0",
                )
                log.log(entry)

            entries = log.query()
            assert len(entries) == 3

    def test_query_by_spec_name(self) -> None:
        """Test querying by spec name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "provenance.jsonl"
            log = ProvenanceLog(log_path)

            # Log entries for different specs
            for spec_name in ["spec_a", "spec_b", "spec_a"]:
                entry = ProvenanceEntry(
                    timestamp=datetime.now().isoformat(),
                    spec_name=spec_name,
                    spec_hash="hash",
                    model="model",
                    action="generate",
                    result="success",
                    axiom_version="0.1.0",
                )
                log.log(entry)

            entries = log.query(spec_name="spec_a")
            assert len(entries) == 2
            assert all(e.spec_name == "spec_a" for e in entries)

    def test_query_by_action(self) -> None:
        """Test querying by action type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "provenance.jsonl"
            log = ProvenanceLog(log_path)

            # Log different action types
            for action in ["generate", "cache_hit", "generate", "verify"]:
                entry = ProvenanceEntry(
                    timestamp=datetime.now().isoformat(),
                    spec_name="spec",
                    spec_hash="hash",
                    model="model",
                    action=action,
                    result="success",
                    axiom_version="0.1.0",
                )
                log.log(entry)

            entries = log.query(action="generate")
            assert len(entries) == 2

    def test_query_with_limit(self) -> None:
        """Test querying with a limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "provenance.jsonl"
            log = ProvenanceLog(log_path)

            # Log many entries
            for i in range(10):
                entry = ProvenanceEntry(
                    timestamp=datetime.now().isoformat(),
                    spec_name=f"spec_{i}",
                    spec_hash="hash",
                    model="model",
                    action="generate",
                    result="success",
                    axiom_version="0.1.0",
                )
                log.log(entry)

            entries = log.query(limit=5)
            assert len(entries) == 5

    def test_query_empty_log(self) -> None:
        """Test querying an empty/nonexistent log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "provenance.jsonl"
            log = ProvenanceLog(log_path)

            entries = log.query()
            assert entries == []

    def test_query_returns_most_recent_first(self) -> None:
        """Test that query returns entries in reverse chronological order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "provenance.jsonl"
            log = ProvenanceLog(log_path)

            # Log entries with different timestamps
            base_time = datetime(2026, 4, 6, 10, 0, 0)
            for i in range(3):
                entry = ProvenanceEntry(
                    timestamp=(base_time + timedelta(hours=i)).isoformat(),
                    spec_name=f"spec_{i}",
                    spec_hash="hash",
                    model="model",
                    action="generate",
                    result="success",
                    axiom_version="0.1.0",
                )
                log.log(entry)

            entries = log.query()
            # Most recent (spec_2) should be first
            assert entries[0].spec_name == "spec_2"
            assert entries[2].spec_name == "spec_0"

    def test_get_generation_history(self) -> None:
        """Test getting generation history for a spec."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "provenance.jsonl"
            log = ProvenanceLog(log_path)

            # Log various entries
            for action in ["generate", "cache_hit", "generate", "verify"]:
                entry = ProvenanceEntry(
                    timestamp=datetime.now().isoformat(),
                    spec_name="my_spec",
                    spec_hash="hash",
                    model="model",
                    action=action,
                    result="success",
                    axiom_version="0.1.0",
                )
                log.log(entry)

            history = log.get_generation_history("my_spec")
            assert len(history) == 2
            assert all(e.action == "generate" for e in history)

    def test_get_stats(self) -> None:
        """Test getting statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "provenance.jsonl"
            log = ProvenanceLog(log_path)

            # Log various entries
            entries_data = [
                ("generate", "success"),
                ("generate", "failure"),
                ("cache_hit", "success"),
                ("cache_miss", "success"),
                ("verify", "success"),
            ]
            for action, result in entries_data:
                entry = ProvenanceEntry(
                    timestamp=datetime.now().isoformat(),
                    spec_name="spec",
                    spec_hash="hash",
                    model="model",
                    action=action,
                    result=result,
                    axiom_version="0.1.0",
                )
                log.log(entry)

            stats = log.get_stats()
            assert stats["total_entries"] == 5
            assert stats["generations"] == 2
            assert stats["cache_hits"] == 1
            assert stats["cache_misses"] == 1
            assert stats["verifications"] == 1
            assert stats["successes"] == 4
            assert stats["failures"] == 1

    def test_get_stats_empty_log(self) -> None:
        """Test getting statistics from empty log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "provenance.jsonl"
            log = ProvenanceLog(log_path)

            stats = log.get_stats()
            assert stats["total_entries"] == 0

    def test_clear(self) -> None:
        """Test clearing the log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "provenance.jsonl"
            log = ProvenanceLog(log_path)

            # Log some entries
            for i in range(3):
                entry = ProvenanceEntry(
                    timestamp=datetime.now().isoformat(),
                    spec_name=f"spec_{i}",
                    spec_hash="hash",
                    model="model",
                    action="generate",
                    result="success",
                    axiom_version="0.1.0",
                )
                log.log(entry)

            count = log.clear()
            assert count == 3
            assert not log_path.exists()

    def test_clear_empty_log(self) -> None:
        """Test clearing an empty log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "provenance.jsonl"
            log = ProvenanceLog(log_path)

            count = log.clear()
            assert count == 0


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_compute_spec_hash(self) -> None:
        """Test spec hash computation."""
        content = "some spec content"
        hash1 = compute_spec_hash(content)

        # Hash should be consistent
        assert compute_spec_hash(content) == hash1

        # Different content should have different hash
        assert compute_spec_hash("different content") != hash1

        # Hash should be 64 chars (SHA-256 hex)
        assert len(hash1) == 64

    def test_create_provenance_entry(self) -> None:
        """Test creating a provenance entry."""
        entry = create_provenance_entry(
            spec_name="test_spec",
            spec_content="spec content here",
            model="claude-sonnet-4-20250514",
            action="generate",
            result="success",
            axiom_version="0.1.0",
            duration_ms=1500,
        )

        assert entry.spec_name == "test_spec"
        assert entry.spec_hash == compute_spec_hash("spec content here")
        assert entry.model == "claude-sonnet-4-20250514"
        assert entry.action == "generate"
        assert entry.result == "success"
        assert entry.duration_ms == 1500
        assert entry.timestamp  # Should be set automatically
