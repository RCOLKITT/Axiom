"""Tests for the cache module."""

import tempfile
from datetime import datetime
from pathlib import Path

from axiom.cache import AXIOM_VERSION, CacheEntry, CacheStore, compute_cache_key
from axiom.spec.models import (
    Constraints,
    Example,
    ExpectedOutput,
    FunctionInterface,
    Metadata,
    Parameter,
    PerformanceConstraints,
    Returns,
    Spec,
)


def make_test_spec(
    name: str = "test_func",
    version: str = "1.0.0",
    target: str = "python:function",
) -> Spec:
    """Create a test spec."""
    return Spec(
        axiom="0.1",
        metadata=Metadata(
            name=name,
            version=version,
            description="A test spec",
            target=target,
        ),
        intent="Returns x + 1",
        interface=FunctionInterface(
            function_name=name,
            parameters=[Parameter(name="x", type="int", description="Input value")],
            returns=Returns(type="int", description="Output value"),
        ),
        examples=[
            Example(
                name="basic",
                input={"x": 1},
                expected_output=ExpectedOutput(value=2),
            ),
        ],
        invariants=[],
        constraints=Constraints(
            performance=PerformanceConstraints(),
        ),
    )


class TestCacheKey:
    """Tests for cache key computation."""

    def test_compute_cache_key(self) -> None:
        """Test basic cache key computation."""
        spec = make_test_spec()
        key = compute_cache_key(spec, "claude-sonnet-4-20250514")

        # Key should be a 64-character hex string (SHA-256)
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_same_inputs_same_key(self) -> None:
        """Test that identical inputs produce the same key."""
        spec1 = make_test_spec()
        spec2 = make_test_spec()

        key1 = compute_cache_key(spec1, "claude-sonnet-4-20250514")
        key2 = compute_cache_key(spec2, "claude-sonnet-4-20250514")

        assert key1 == key2

    def test_different_spec_different_key(self) -> None:
        """Test that different specs produce different keys."""
        spec1 = make_test_spec(name="func1")
        spec2 = make_test_spec(name="func2")

        key1 = compute_cache_key(spec1, "claude-sonnet-4-20250514")
        key2 = compute_cache_key(spec2, "claude-sonnet-4-20250514")

        assert key1 != key2

    def test_different_model_different_key(self) -> None:
        """Test that different models produce different keys."""
        spec = make_test_spec()

        key1 = compute_cache_key(spec, "claude-sonnet-4-20250514")
        key2 = compute_cache_key(spec, "claude-opus-4-20250514")

        assert key1 != key2


class TestCacheStore:
    """Tests for the cache store."""

    def test_store_and_retrieve(self) -> None:
        """Test storing and retrieving a cache entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CacheStore(Path(tmpdir))
            spec = make_test_spec()
            model = "claude-sonnet-4-20250514"
            code = "def test_func(x: int) -> int:\n    return x + 1"

            # Store
            entry = store.put(spec, model, code, AXIOM_VERSION)
            assert entry.spec_name == "test_func"
            assert entry.model == model
            assert entry.code == code

            # Retrieve
            retrieved = store.get(entry.key)
            assert retrieved is not None
            assert retrieved.code == code
            assert retrieved.model == model

    def test_lookup_cache_hit(self) -> None:
        """Test cache lookup with a hit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CacheStore(Path(tmpdir))
            spec = make_test_spec()
            model = "claude-sonnet-4-20250514"
            code = "def test_func(x: int) -> int:\n    return x + 1"

            # Store
            store.put(spec, model, code, AXIOM_VERSION)

            # Lookup
            status = store.lookup(spec, model, AXIOM_VERSION)
            assert status.hit is True
            assert status.entry is not None
            assert status.entry.code == code

    def test_lookup_cache_miss(self) -> None:
        """Test cache lookup with a miss."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CacheStore(Path(tmpdir))
            spec = make_test_spec()

            # Lookup without storing
            status = store.lookup(spec, "claude-sonnet-4-20250514", AXIOM_VERSION)
            assert status.hit is False
            assert status.entry is None
            assert "no cache entry" in status.reason

    def test_lookup_cache_stale(self) -> None:
        """Test cache lookup when axiom version changed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CacheStore(Path(tmpdir))
            spec = make_test_spec()
            model = "claude-sonnet-4-20250514"
            code = "def test_func(x: int) -> int:\n    return x + 1"

            # Store with old version
            store.put(spec, model, code, "0.0.1")

            # Lookup with new version
            status = store.lookup(spec, model, "0.2.0")
            assert status.hit is False
            assert status.entry is not None  # Entry exists but is stale
            assert "axiom version changed" in status.reason

    def test_delete_entry(self) -> None:
        """Test deleting a cache entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CacheStore(Path(tmpdir))
            spec = make_test_spec()
            model = "claude-sonnet-4-20250514"
            code = "def test_func(x: int) -> int:\n    return x + 1"

            # Store
            entry = store.put(spec, model, code, AXIOM_VERSION)

            # Delete
            assert store.delete(entry.key) is True
            assert store.get(entry.key) is None

            # Delete again (should return False)
            assert store.delete(entry.key) is False

    def test_clear_all(self) -> None:
        """Test clearing all cache entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CacheStore(Path(tmpdir))

            # Store multiple entries
            for i in range(3):
                spec = make_test_spec(name=f"func{i}")
                store.put(spec, "claude-sonnet-4-20250514", f"code{i}", AXIOM_VERSION)

            assert len(store.list_entries()) == 3

            # Clear
            count = store.clear()
            assert count == 3
            assert len(store.list_entries()) == 0

    def test_list_entries(self) -> None:
        """Test listing all cache entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CacheStore(Path(tmpdir))

            # Store multiple entries
            specs = ["func1", "func2", "func3"]
            for name in specs:
                spec = make_test_spec(name=name)
                store.put(spec, "claude-sonnet-4-20250514", f"code_{name}", AXIOM_VERSION)

            entries = store.list_entries()
            assert len(entries) == 3
            names = {e.spec_name for e in entries}
            assert names == set(specs)

    def test_get_entry_for_spec(self) -> None:
        """Test getting an entry by spec name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CacheStore(Path(tmpdir))
            spec = make_test_spec(name="my_func")
            store.put(spec, "claude-sonnet-4-20250514", "my_code", AXIOM_VERSION)

            entry = store.get_entry_for_spec("my_func")
            assert entry is not None
            assert entry.spec_name == "my_func"

            # Non-existent spec
            assert store.get_entry_for_spec("unknown") is None

    def test_stats(self) -> None:
        """Test getting cache statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CacheStore(Path(tmpdir))

            # Store some entries
            for i in range(3):
                spec = make_test_spec(name=f"func{i}")
                store.put(spec, "claude-sonnet-4-20250514", f"code_{i}", AXIOM_VERSION)

            stats = store.stats()
            assert stats["total_entries"] == 3
            assert stats["unique_specs"] == 3
            assert stats["total_size_bytes"] > 0


class TestCacheEntry:
    """Tests for CacheEntry serialization."""

    def test_to_dict_and_from_dict(self) -> None:
        """Test serialization round-trip."""
        entry = CacheEntry(
            key="abc123",
            spec_name="test_func",
            model="claude-sonnet-4-20250514",
            target="python:function",
            code="def test(): pass",
            created_at=datetime.now(),
            axiom_version="0.1.0",
            metadata={"foo": "bar"},
        )

        data = entry.to_dict()
        restored = CacheEntry.from_dict(data)

        assert restored.key == entry.key
        assert restored.spec_name == entry.spec_name
        assert restored.model == entry.model
        assert restored.code == entry.code
        assert restored.axiom_version == entry.axiom_version
        assert restored.metadata == entry.metadata
