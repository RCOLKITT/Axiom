"""Cache key computation for deterministic caching.

Keys are content-addressed: hash(spec_content + target + model + axiom_version).
Any change to any input invalidates the cache.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import structlog

from axiom.spec.models import Spec

logger = structlog.get_logger()

# Axiom version for cache invalidation
AXIOM_VERSION = "0.1.0"


def compute_cache_key(
    spec: Spec,
    model: str,
    spec_path: Path | None = None,
) -> str:
    """Compute a deterministic cache key for a spec.

    The key is a SHA-256 hash of:
    - Spec content (serialized to JSON for consistency)
    - Generation target
    - Model name
    - Axiom version

    Args:
        spec: The parsed spec.
        model: The model name used for generation.
        spec_path: Optional path to spec file (for logging).

    Returns:
        A 64-character hex digest cache key.
    """
    # Serialize spec to JSON for deterministic hashing
    spec_json = _serialize_spec(spec)

    # Build the key components
    key_components = {
        "spec": spec_json,
        "target": spec.metadata.target,
        "model": model,
        "axiom_version": AXIOM_VERSION,
    }

    # Create deterministic JSON string
    key_string = json.dumps(key_components, sort_keys=True, separators=(",", ":"))

    # Hash it
    key_hash = hashlib.sha256(key_string.encode("utf-8")).hexdigest()

    logger.debug(
        "Computed cache key",
        spec=spec.spec_name,
        model=model,
        target=spec.metadata.target,
        key=key_hash[:12] + "...",
    )

    return key_hash


def _serialize_spec(spec: Spec) -> dict[str, Any]:
    """Serialize a spec to a deterministic dictionary.

    Args:
        spec: The spec to serialize.

    Returns:
        A dictionary representation suitable for hashing.
    """
    # Use Pydantic's model_dump for consistent serialization
    return spec.model_dump(mode="json")


def get_cache_filename(key: str) -> str:
    """Get the filename for a cache entry.

    Args:
        key: The cache key (hash).

    Returns:
        The filename to use for the cache entry.
    """
    return f"{key}.json"


def parse_cache_key_components(spec: Spec, model: str) -> dict[str, str]:
    """Get the components that make up a cache key (for debugging).

    Args:
        spec: The parsed spec.
        model: The model name.

    Returns:
        Dictionary of key components.
    """
    return {
        "spec_name": spec.spec_name,
        "target": spec.metadata.target,
        "model": model,
        "axiom_version": AXIOM_VERSION,
    }
