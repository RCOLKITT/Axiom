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
    from generated.compute_spec_hash import compute_spec_hash
    from generated.format_value import format_value
    from generated.is_close_value import is_close_value
except ImportError:
    # Fallback implementations if generated code doesn't exist
    import hashlib
    from difflib import SequenceMatcher

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


__all__ = ["compute_spec_hash", "format_value", "is_close_value"]
