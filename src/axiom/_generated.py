"""Helper module for importing from generated/ directory.

This module handles the path setup needed to import spec-driven utilities
from the generated/ directory, which is at the project root rather than
inside the src/ package.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path if generated/ exists there
_project_root = Path(__file__).parent.parent.parent
_generated_dir = _project_root / "generated"

if _generated_dir.exists() and str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Now we can import from generated/
# These imports will fail if generated/ doesn't exist or specs aren't built
try:
    from generated.chunk_list import chunk_list
    from generated.compute_spec_hash import compute_spec_hash
    from generated.flatten_list import flatten_list
    from generated.format_value import format_value
    from generated.is_close_value import is_close_value
    from generated.merge_dicts import merge_dicts
    from generated.safe_get import safe_get
    from generated.slugify import slugify
    from generated.snake_to_camel import snake_to_camel
    from generated.strip_ansi import strip_ansi
    from generated.topological_sort import topological_sort

    _GENERATED_AVAILABLE = True
except ImportError:
    _GENERATED_AVAILABLE = False

    # Fallback implementations if generated code doesn't exist
    import hashlib
    from difflib import SequenceMatcher
    from typing import Any

    def compute_spec_hash(content: str) -> str:
        """Fallback: compute SHA-256 hash."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def format_value(value: object) -> str:
        """Fallback: format value for display."""
        if value is None:
            return "None"
        if isinstance(value, str):
            if len(value) > 50:
                return f'"{value[:45]}..."'
            return f'"{value}"'
        if isinstance(value, dict) and len(str(value)) > 80:
            return f"{{{len(value)} keys}}"
        if isinstance(value, list) and len(value) > 5:
            return f"[{len(value)} items]"
        return str(value)

    def is_close_value(expected: object, actual: object) -> bool:
        """Fallback: check if values are close."""
        if expected == actual:
            return True
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            if expected == 0:
                return abs(actual) < 0.1
            return abs(actual - expected) / abs(expected) <= 0.1
        if isinstance(expected, str) and isinstance(actual, str):
            return SequenceMatcher(None, expected, actual).ratio() > 0.8
        return False

    def chunk_list(items: list[Any], size: int) -> list[list[Any]]:
        """Fallback: split list into chunks."""
        if size <= 0:
            raise ValueError("Size must be positive")
        return [items[i : i + size] for i in range(0, len(items), size)]

    def flatten_list(nested: list[Any]) -> list[Any]:
        """Fallback: flatten one level of nesting."""
        result: list[Any] = []
        for item in nested:
            if isinstance(item, list):
                result.extend(item)
            else:
                result.append(item)
        return result

    def safe_get(data: dict[str, Any], path: str, default: Any) -> Any:
        """Fallback: safely get nested dict value using dot notation."""
        if not path:
            return default
        keys = path.split(".")
        current: Any = data
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]
        return current

    def merge_dicts(dicts: list[dict[str, Any]]) -> dict[str, Any]:
        """Fallback: merge dictionaries."""
        result: dict[str, Any] = {}
        for d in dicts:
            result.update(d)
        return result

    def slugify(text: str) -> str:
        """Fallback: convert text to slug."""
        import re

        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[-\s]+", "-", text)
        return text.strip("-")

    def strip_ansi(text: str) -> str:
        """Fallback: remove ANSI escape sequences."""
        import re

        return re.sub(r"\x1b\[[0-9;]*m", "", text)

    def snake_to_camel(name: str, pascal: bool) -> str:
        """Fallback: convert snake_case to camelCase."""
        if not name:
            return ""
        parts = name.split("_")
        if pascal:
            return "".join(p.capitalize() for p in parts)
        return parts[0] + "".join(p.capitalize() for p in parts[1:])

    def topological_sort(graph: dict[str, list[str]]) -> list[str]:
        """Fallback: topological sort."""
        in_degree = dict.fromkeys(graph, 0)
        for deps in graph.values():
            for dep in deps:
                if dep in in_degree:
                    in_degree[dep] += 1
        queue = [n for n, d in in_degree.items() if d == 0]
        result = []
        while queue:
            node = queue.pop(0)
            result.append(node)
            for n, deps in graph.items():
                if node in deps:
                    in_degree[n] -= 1
                    if in_degree[n] == 0:
                        queue.append(n)
        return result


__all__ = [
    "compute_spec_hash",
    "format_value",
    "is_close_value",
    "chunk_list",
    "flatten_list",
    "safe_get",
    "merge_dicts",
    "slugify",
    "strip_ansi",
    "snake_to_camel",
    "topological_sort",
    "_GENERATED_AVAILABLE",
]
