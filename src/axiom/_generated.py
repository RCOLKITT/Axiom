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
    from generated.camel_to_snake import camel_to_snake
    from generated.chunk_list import chunk_list
    from generated.compute_spec_hash import compute_spec_hash
    from generated.count_lines import count_lines
    from generated.escape_regex import escape_regex
    from generated.extract_code import extract_code
    from generated.flatten_list import flatten_list
    from generated.format_duration import format_duration
    from generated.format_value import format_value
    from generated.is_close_value import is_close_value
    from generated.merge_dicts import merge_dicts
    from generated.normalize_path import normalize_path
    from generated.pluralize import pluralize
    from generated.safe_get import safe_get
    from generated.slugify import slugify
    from generated.snake_to_camel import snake_to_camel
    from generated.strip_ansi import strip_ansi
    from generated.topological_sort import topological_sort
    from generated.validate_python_identifier import validate_python_identifier
    from generated.generate_default_value import generate_default_value
    from generated.generate_error_value import generate_error_value
    from generated.type_to_isinstance import type_to_isinstance
    from generated.indent_text import indent_text
    from generated.clean_code import clean_code
    from generated.extract_imports import extract_imports
    from generated.format_bytes import format_bytes
    from generated.format_invariant import format_invariant
    from generated.format_type_annotation import format_type_annotation
    from generated.group_by import group_by
    from generated.lerp import lerp
    from generated.parse_function_signature import parse_function_signature
    from generated.parse_json_safely import parse_json_safely
    from generated.parse_version import parse_version
    from generated.truncate_string import truncate_string
    from generated.values_equal import values_equal
    from generated.compare_versions import compare_versions
    from generated.diff_dicts import diff_dicts
    from generated.extract_urls import extract_urls
    from generated.format_failure import format_failure
    from generated.is_valid_email import is_valid_email
    from generated.redact_secrets import redact_secrets
    from generated.sanitize_filename import sanitize_filename
    from generated.clamp import clamp
    from generated.unique_ordered import unique_ordered
    from generated.hash_content import hash_content
    from generated.compare_values import compare_values
    from generated.normalize_type import normalize_type
    from generated.wrap_text import wrap_text
    from generated.detect_cycle import detect_cycle
    from generated.retry_config import retry_config
    from generated.format_example import format_example

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

    def camel_to_snake(name: str) -> str:
        """Fallback: convert camelCase to snake_case."""
        import re

        if not name:
            return ""
        result = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
        result = re.sub(r"([A-Z])([A-Z][a-z])", r"\1_\2", result)
        return result.lower()

    def normalize_path(path: str) -> str:
        """Fallback: normalize a file path."""
        import os

        if not path:
            return ""
        path = path.replace("\\", "/")
        normalized = os.path.normpath(path).replace("\\", "/")
        if normalized != "/" and normalized.endswith("/"):
            normalized = normalized.rstrip("/")
        return normalized

    def pluralize(count: int, singular: str, plural: str | None = None) -> str:
        """Fallback: pluralize a word based on count."""
        if abs(count) == 1:
            word = singular
        else:
            word = plural if plural is not None else singular + "s"
        return f"{count} {word}"

    def escape_regex(pattern: str) -> str:
        """Fallback: escape regex special characters."""
        import re

        return re.escape(pattern)

    def count_lines(code: str) -> int:
        """Fallback: count significant lines of code."""
        if not code.strip():
            return 0
        lines = code.split("\n")
        return sum(1 for line in lines if line.strip() and not line.strip().startswith("#"))

    def format_duration(ms: int) -> str:
        """Fallback: format duration in milliseconds."""
        if ms < 0:
            raise ValueError("Duration cannot be negative")
        if ms < 1000:
            return f"{ms}ms"
        seconds = ms / 1000
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = int(seconds // 60)
        remaining_seconds = int(seconds % 60)
        if minutes < 60:
            return f"{minutes}m {remaining_seconds}s"
        hours = minutes // 60
        remaining_minutes = minutes % 60
        return f"{hours}h {remaining_minutes}m"

    def extract_code(response: str) -> str:
        """Fallback: extract code from LLM response."""
        import re

        if not response:
            return ""
        python_match = re.search(r"```python\s*\n(.*?)\n```", response, re.DOTALL)
        if python_match:
            return python_match.group(1).strip()
        generic_match = re.search(r"```\s*\n(.*?)\n```", response, re.DOTALL)
        if generic_match:
            return generic_match.group(1).strip()
        stripped = response.strip()
        indicators = ["def ", "class ", "import ", "from ", "return ", "if ", "for ", "while ", "    "]
        if any(ind in stripped for ind in indicators):
            return stripped
        return ""

    def validate_python_identifier(name: str) -> bool:
        """Fallback: validate Python identifier."""
        import keyword

        if not name:
            return False
        if not name.isidentifier():
            return False
        if keyword.iskeyword(name):
            return False
        return True

    def generate_default_value(type_str: str | None) -> object:
        """Fallback: generate default value for a type."""
        if type_str is None:
            return "example"
        type_lower = type_str.lower()
        if type_lower in ("str", "string"):
            return "example"
        if type_lower in ("int", "integer"):
            return 42
        if type_lower == "float":
            return 3.14
        if type_lower in ("bool", "boolean"):
            return True
        if type_lower == "list":
            return ["item1", "item2"]
        if type_lower == "dict":
            return {"key": "value"}
        return "example"

    def generate_error_value(type_str: str | None) -> object:
        """Fallback: generate error-inducing value for a type."""
        if type_str in ("str", "string"):
            return ""
        if type_str in ("int", "integer"):
            return -1
        if type_str == "float":
            return None
        if type_str == "list":
            return []
        if type_str == "dict":
            return {}
        if type_str == "path":
            return "/nonexistent/path"
        return None

    def type_to_isinstance(type_str: str) -> str | None:
        """Fallback: convert type string to isinstance check."""
        type_lower = type_str.lower()
        if type_lower in ("str", "string"):
            return "str"
        if type_lower in ("int", "integer"):
            return "int"
        if type_lower == "float":
            return "float"
        if type_lower == "number":
            return "(int, float)"
        if type_lower in ("bool", "boolean"):
            return "bool"
        if type_lower in ("list", "array"):
            return "list"
        if type_lower == "dict":
            return "dict"
        if type_lower == "tuple":
            return "tuple"
        if type_lower == "set":
            return "set"
        if type_str.startswith("Optional["):
            return None
        return None

    def indent_text(text: str, spaces: int, prefix: str | None) -> str:
        """Fallback: indent text with spaces or prefix."""
        if not text:
            return ""
        if prefix is not None:
            indent = prefix
        else:
            indent = " " * spaces
        lines = text.split("\n")
        return "\n".join(indent + line if line else "" for line in lines)

    def clean_code(code: str) -> str:
        """Fallback: remove comments and blank lines from code."""
        lines = code.split("\n")
        result = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                result.append(line)
        return "\n".join(result)

    def extract_imports(code: str) -> list[str]:
        """Fallback: extract import statements from Python code."""
        lines = code.split("\n")
        imports = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                imports.append(stripped)
        return imports

    def format_bytes(size: int, binary: bool = True) -> str:
        """Fallback: format byte size to human readable."""
        if size == 0:
            return "0 B"
        base = 1024 if binary else 1000
        units = ["B", "KiB", "MiB", "GiB", "TiB"] if binary else ["B", "KB", "MB", "GB", "TB"]
        for unit in units:
            if size < base:
                if unit == "B":
                    return f"{size} {unit}"
                return f"{size:.1f} {unit}"
            size /= base
        return f"{size:.1f} {units[-1]}"

    def format_invariant(description: str, check: str | None) -> str:
        """Fallback: format an invariant for display."""
        if check:
            return f"- {description}\n  Check: `{check}`"
        return f"- {description}"

    def format_type_annotation(type_str: str) -> str:
        """Fallback: format a type annotation."""
        return type_str

    def group_by(items: list[Any], key: str) -> dict[Any, list[Any]]:
        """Fallback: group items by a key."""
        result: dict[Any, list[Any]] = {}
        for item in items:
            k = item.get(key) if isinstance(item, dict) else getattr(item, key, None)
            if k not in result:
                result[k] = []
            result[k].append(item)
        return result

    def lerp(a: float, b: float, t: float) -> float:
        """Fallback: linear interpolation."""
        return a + (b - a) * t

    def parse_function_signature(signature: str) -> dict[str, Any]:
        """Fallback: parse a function signature."""
        return {"name": "", "params": [], "return_type": None}

    def parse_json_safely(text: str, default: Any = None) -> Any:
        """Fallback: safely parse JSON."""
        import json
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return default

    def parse_version(version: str) -> tuple[int, int, int]:
        """Fallback: parse semantic version."""
        parts = version.lstrip("v").split(".")
        return (
            int(parts[0]) if len(parts) > 0 else 0,
            int(parts[1]) if len(parts) > 1 else 0,
            int(parts[2].split("-")[0]) if len(parts) > 2 else 0,
        )

    def truncate_string(text: str, max_length: int, ellipsis: str) -> str:
        """Fallback: truncate string with ellipsis."""
        if len(text) <= max_length:
            return text
        return text[: max_length - len(ellipsis)] + ellipsis

    def values_equal(actual: Any, expected: Any) -> bool:
        """Fallback: deep equality comparison with float tolerance and partial dict matching."""
        import math

        if actual is None or expected is None:
            return actual is expected
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            if isinstance(actual, int) and isinstance(expected, int):
                return actual == expected
            return math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9)
        if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
            if len(actual) != len(expected):
                return False
            return all(values_equal(a, e) for a, e in zip(actual, expected))
        if isinstance(actual, dict) and isinstance(expected, dict):
            for key, expected_value in expected.items():
                if key not in actual:
                    return False
                if not values_equal(actual[key], expected_value):
                    return False
            return True
        return actual == expected

    def compare_versions(v1: str, v2: str) -> int:
        """Fallback: compare two semantic versions."""
        def parse(v: str) -> tuple[int, ...]:
            parts = v.lstrip("v").split("-")[0].split(".")
            return tuple(int(p) for p in parts if p.isdigit())
        p1, p2 = parse(v1), parse(v2)
        # Pad to same length
        max_len = max(len(p1), len(p2))
        p1 = p1 + (0,) * (max_len - len(p1))
        p2 = p2 + (0,) * (max_len - len(p2))
        if p1 < p2:
            return -1
        elif p1 > p2:
            return 1
        # Handle prerelease
        if "-" in v1 and "-" not in v2:
            return -1
        if "-" not in v1 and "-" in v2:
            return 1
        return 0

    def diff_dicts(old: dict[str, Any], new: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Fallback: compute difference between two dictionaries."""
        added = {k: v for k, v in new.items() if k not in old}
        removed = {k: v for k, v in old.items() if k not in new}
        changed = {}
        for k in old.keys() & new.keys():
            if old[k] != new[k]:
                changed[k] = {"old": old[k], "new": new[k]}
        return {"added": added, "removed": removed, "changed": changed}

    def extract_urls(text: str) -> list[str]:
        """Fallback: extract all URLs from text."""
        import re
        pattern = r'(https?://|ftp://)[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(pattern, text)
        seen: set[str] = set()
        result: list[str] = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                result.append(url)
        return result

    def format_failure(test_name: str, expected: Any, actual: Any, error_message: str | None) -> str:
        """Fallback: format a test failure message."""
        lines = [f"FAILED: {test_name}"]
        lines.append(f"  Expected: {repr(expected) if isinstance(expected, str) else expected}")
        lines.append(f"  Actual: {repr(actual) if isinstance(actual, str) else actual}")
        if error_message:
            lines.append(f"  Error: {error_message}")
        return "\n".join(lines) + "\n"

    def is_valid_email(email: str) -> bool:
        """Fallback: check if string is a valid email address."""
        import re
        if not email or "@" not in email:
            return False
        if email.count("@") != 1:
            return False
        local, domain = email.split("@")
        if not local or not domain:
            return False
        if " " in email:
            return False
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    def redact_secrets(data: dict[str, Any]) -> dict[str, Any]:
        """Fallback: redact sensitive values in a dictionary."""
        sensitive_keys = {"password", "secret", "token", "key", "credential"}
        result: dict[str, Any] = {}
        for k, v in data.items():
            if any(s in k.lower() for s in sensitive_keys):
                result[k] = "[REDACTED]"
            elif isinstance(v, dict):
                result[k] = redact_secrets(v)
            else:
                result[k] = v
        return result

    def sanitize_filename(name: str, replacement: str = "_") -> str:
        """Fallback: sanitize a string for use as a filename."""
        import re
        if not name:
            return ""
        # Reserved names on Windows
        reserved = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4",
                    "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2",
                    "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
        # Remove invalid characters
        result = re.sub(r'[\\/:*?"<>|]', replacement, name)
        # Handle reserved names
        if result.upper() in reserved:
            result = replacement + result
        return result

    def clamp(value: float, min_val: float, max_val: float) -> float:
        """Fallback: clamp a value within a range."""
        if value < min_val:
            return min_val
        if value > max_val:
            return max_val
        return value

    def unique_ordered(items: list[Any]) -> list[Any]:
        """Fallback: return unique items preserving order."""
        seen: set[Any] = set()
        result: list[Any] = []
        for item in items:
            # Handle unhashable types
            try:
                if item not in seen:
                    seen.add(item)
                    result.append(item)
            except TypeError:
                # For unhashable items, check by identity
                if item not in result:
                    result.append(item)
        return result

    def hash_content(content: str) -> str:
        """Fallback: compute SHA-256 hash of content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def compare_values(expected: Any, actual: Any, tolerance: float = 0.0) -> bool:
        """Fallback: compare two values with optional tolerance for floats."""
        if expected is None and actual is None:
            return True
        if expected is None or actual is None:
            return False
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            if tolerance > 0:
                return abs(expected - actual) <= tolerance
            return expected == actual
        return expected == actual

    def normalize_type(type_str: str) -> str:
        """Fallback: normalize type string to standard form."""
        if not type_str:
            return ""
        type_lower = type_str.lower().strip()
        mappings = {
            "string": "str",
            "integer": "int",
            "boolean": "bool",
            "number": "float",
            "array": "list",
            "object": "dict",
        }
        return mappings.get(type_lower, type_str)

    def wrap_text(text: str, width: int = 80) -> str:
        """Fallback: wrap text to specified width."""
        if not text or width <= 0:
            return text
        import textwrap
        return textwrap.fill(text, width=width)

    def detect_cycle(graph: dict[str, list[str]]) -> bool:
        """Fallback: detect if a directed graph contains a cycle."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {node: WHITE for node in graph}

        def dfs(node: str) -> bool:
            color[node] = GRAY
            for neighbor in graph.get(node, []):
                if neighbor not in color:
                    color[neighbor] = WHITE
                if color[neighbor] == GRAY:
                    return True  # Back edge found
                if color[neighbor] == WHITE and dfs(neighbor):
                    return True
            color[node] = BLACK
            return False

        for node in graph:
            if color[node] == WHITE and dfs(node):
                return True
        return False

    def retry_config(
        attempt: int,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter: bool = False
    ) -> float:
        """Fallback: calculate retry delay with exponential backoff."""
        import random
        if attempt <= 0:
            delay = base_delay / 2
        else:
            delay = base_delay * (2 ** (attempt - 1))
        if max_delay > 0:
            delay = min(delay, max_delay)
        if jitter:
            delay = delay * random.random()
        return max(0.0, delay)

    def format_example(name: str, input_data: dict[str, Any], expected_output: Any) -> str:
        """Fallback: format an example for prompt display."""
        result = f"Example '{name}':\n"
        if not input_data:
            result += "  Input: (no parameters)\n"
        else:
            parts = []
            for key, value in input_data.items():
                if isinstance(value, str):
                    parts.append(f'{key}="{value}"')
                else:
                    parts.append(f"{key}={repr(value)}")
            result += f"  Input: {', '.join(parts)}\n"
        if isinstance(expected_output, str):
            result += f'  Expected Output: "{expected_output}"\n'
        else:
            result += f"  Expected Output: {repr(expected_output)}\n"
        return result


__all__ = [
    "camel_to_snake",
    "chunk_list",
    "clamp",
    "clean_code",
    "compare_values",
    "compare_versions",
    "compute_spec_hash",
    "count_lines",
    "detect_cycle",
    "diff_dicts",
    "escape_regex",
    "extract_code",
    "extract_imports",
    "extract_urls",
    "flatten_list",
    "format_bytes",
    "format_duration",
    "format_example",
    "format_failure",
    "format_invariant",
    "format_type_annotation",
    "format_value",
    "generate_default_value",
    "generate_error_value",
    "group_by",
    "hash_content",
    "indent_text",
    "is_close_value",
    "is_valid_email",
    "lerp",
    "merge_dicts",
    "normalize_path",
    "normalize_type",
    "parse_function_signature",
    "parse_json_safely",
    "parse_version",
    "pluralize",
    "redact_secrets",
    "retry_config",
    "safe_get",
    "sanitize_filename",
    "slugify",
    "snake_to_camel",
    "strip_ansi",
    "topological_sort",
    "truncate_string",
    "type_to_isinstance",
    "unique_ordered",
    "validate_python_identifier",
    "values_equal",
    "wrap_text",
    "_GENERATED_AVAILABLE",
]
