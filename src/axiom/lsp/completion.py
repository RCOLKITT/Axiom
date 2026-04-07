"""Code completion provider for Axiom specs.

Provides context-aware completions for:
- Top-level fields (axiom, metadata, interface, etc.)
- Nested fields within sections
- Type values
- Common patterns
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from lsprotocol import types as lsp

# Field type alias for clarity
FieldDef = tuple[str, str, str | None]

# Top-level field completions
TOP_LEVEL_FIELDS: list[FieldDef] = [
    ("axiom", "Axiom spec version", '"0.1"'),
    ("metadata", "Spec metadata (name, version, target)", None),
    ("intent", "Natural language description of behavior", "|"),
    ("interface", "Function/API interface definition", None),
    ("examples", "Input/output example test cases", None),
    ("invariants", "Property-based test invariants", None),
    ("dependencies", "Spec and external dependencies", None),
]

# Metadata field completions
METADATA_FIELDS: list[FieldDef] = [
    ("name", "Unique spec name (used for imports)", None),
    ("version", "Semantic version string", '"1.0.0"'),
    ("description", "Short description of the spec", '""'),
    ("target", "Generation target (language:type)", '"python:function"'),
    ("tags", "Categorization tags", None),
    ("model", "LLM model override", '"claude-3-5-sonnet-20241022"'),
]

# Interface field completions (function type)
INTERFACE_FUNCTION_FIELDS: list[FieldDef] = [
    ("function_name", "Name of the generated function", None),
    ("parameters", "Function parameters list", None),
    ("returns", "Return type specification", None),
    ("raises", "Exceptions that may be raised", None),
]

# Interface field completions (FastAPI type)
INTERFACE_HTTP_FIELDS: list[FieldDef] = [
    ("http", "HTTP interface specification", None),
]

HTTP_FIELDS: list[FieldDef] = [
    ("method", "HTTP method (GET, POST, PUT, DELETE)", '"POST"'),
    ("path", "URL path with parameters", '"/api/resource"'),
    ("request_body", "Request body schema", None),
    ("response", "Response schema", None),
    ("errors", "Error response specifications", None),
]

# Parameter field completions
PARAMETER_FIELDS: list[FieldDef] = [
    ("name", "Parameter name", None),
    ("type", "Parameter type", '"str"'),
    ("description", "Parameter description", '""'),
    ("constraints", "Value constraints", '""'),
    ("default", "Default value (makes param optional)", None),
]

# Returns field completions
RETURNS_FIELDS: list[FieldDef] = [
    ("type", "Return type", '"str"'),
    ("description", "Description of return value", '""'),
]

# Example field completions
EXAMPLE_FIELDS: list[FieldDef] = [
    ("name", "Descriptive example name", None),
    ("input", "Input values mapping", None),
    ("expected_output", "Expected output value or raises", None),
]

# Invariant field completions
INVARIANT_FIELDS: list[FieldDef] = [
    ("description", "Human-readable invariant description", '""'),
    ("check", "Python expression to evaluate", '""'),
    ("property", "Hypothesis property function", '""'),
]

# Dependency field completions
DEPENDENCY_FIELDS: list[FieldDef] = [
    ("name", "Dependency name", None),
    ("type", "Dependency type (spec, hand-written, external-package)", '"spec"'),
    ("interface", "Interface specification for hand-written", None),
    ("version", "Version constraint for external packages", None),
]

# Type values
PYTHON_TYPES = [
    ("str", "String type"),
    ("int", "Integer type"),
    ("float", "Floating point type"),
    ("bool", "Boolean type"),
    ("list", "List type (use list[T] for typed)"),
    ("dict", "Dictionary type (use dict[K, V] for typed)"),
    ("None", "None/null type"),
    ("Any", "Any type (avoid if possible)"),
]

# Target values
TARGET_VALUES = [
    ("python:function", "Pure Python function"),
    ("python:fastapi", "FastAPI endpoint"),
    ("python:class", "Python class"),
    ("typescript:function", "TypeScript function"),
]


def get_completions(
    source: str,
    position: lsp.Position,
) -> list[lsp.CompletionItem]:
    """Get completion items for the current position.

    Args:
        source: Document source text.
        position: Cursor position.

    Returns:
        List of completion items.
    """
    lines = source.split("\n")
    if position.line >= len(lines):
        return []

    line = lines[position.line]
    line_prefix = line[: position.character]

    # Determine context
    context = _determine_context(lines, position.line)

    # Get completions based on context
    if context == "top_level":
        return _make_field_completions(TOP_LEVEL_FIELDS, line_prefix)

    elif context == "metadata":
        return _make_field_completions(METADATA_FIELDS, line_prefix)

    elif context == "interface":
        # Detect if we're in function or http mode
        for i in range(position.line, -1, -1):
            if "http:" in lines[i]:
                return _make_field_completions(HTTP_FIELDS, line_prefix)
        return _make_field_completions(
            INTERFACE_FUNCTION_FIELDS + INTERFACE_HTTP_FIELDS, line_prefix
        )

    elif context == "http":
        return _make_field_completions(HTTP_FIELDS, line_prefix)

    elif context == "parameters":
        return _make_field_completions(PARAMETER_FIELDS, line_prefix)

    elif context == "returns":
        return _make_field_completions(RETURNS_FIELDS, line_prefix)

    elif context == "examples":
        return _make_field_completions(EXAMPLE_FIELDS, line_prefix)

    elif context == "invariants":
        return _make_field_completions(INVARIANT_FIELDS, line_prefix)

    elif context == "dependencies":
        return _make_field_completions(DEPENDENCY_FIELDS, line_prefix)

    elif context == "type_value":
        return _make_type_completions(line_prefix)

    elif context == "target_value":
        return _make_target_completions(line_prefix)

    return []


def _determine_context(lines: list[str], current_line: int) -> str:
    """Determine the context for completions.

    Args:
        lines: All lines in the document.
        current_line: Current line number.

    Returns:
        Context string indicating the section.
    """
    line = lines[current_line]
    indent = len(line) - len(line.lstrip())

    # Check for type value context
    if re.search(r"type:\s*$", line) or re.search(r"type:\s+['\"]?$", line):
        return "type_value"

    # Check for target value context
    if re.search(r"target:\s*$", line) or re.search(r"target:\s+['\"]?$", line):
        return "target_value"

    # Top level (no indent or just starting a field)
    if indent == 0:
        return "top_level"

    # Find the parent section
    for i in range(current_line - 1, -1, -1):
        parent_line = lines[i]
        parent_indent = len(parent_line) - len(parent_line.lstrip())

        if parent_indent < indent:
            # Found a parent
            if parent_line.strip().startswith("metadata:"):
                return "metadata"
            elif parent_line.strip().startswith("interface:"):
                return "interface"
            elif parent_line.strip().startswith("http:"):
                return "http"
            elif parent_line.strip().startswith("parameters:"):
                return "parameters"
            elif parent_line.strip().startswith("returns:"):
                return "returns"
            elif parent_line.strip().startswith("examples:"):
                return "examples"
            elif parent_line.strip().startswith("invariants:"):
                return "invariants"
            elif parent_line.strip().startswith("dependencies:"):
                return "dependencies"

        # If we hit a top-level field, check its name
        if parent_indent == 0 and ":" in parent_line:
            field_name = parent_line.split(":")[0].strip()
            if field_name in ["metadata", "interface", "examples", "invariants", "dependencies"]:
                return field_name
            break

    return "top_level"


def _make_field_completions(
    fields: Sequence[FieldDef],
    line_prefix: str,
) -> list[lsp.CompletionItem]:
    """Create completion items for fields.

    Args:
        fields: List of (name, description, snippet) tuples.
        line_prefix: Text before cursor on current line.

    Returns:
        List of completion items.
    """
    items = []

    # Determine indent level
    if line_prefix.strip() == "" or line_prefix.strip() == "-":
        " " * (len(line_prefix) - len(line_prefix.lstrip()))

    for name, description, snippet in fields:
        insert_text = f"{name}: {snippet}" if snippet else f"{name}:"

        items.append(
            lsp.CompletionItem(
                label=name,
                kind=lsp.CompletionItemKind.Field,
                detail=description,
                insert_text=insert_text,
                insert_text_format=lsp.InsertTextFormat.PlainText,
            )
        )

    return items


def _make_type_completions(line_prefix: str) -> list[lsp.CompletionItem]:
    """Create completion items for type values.

    Args:
        line_prefix: Text before cursor on current line.

    Returns:
        List of completion items.
    """
    items = []

    for type_name, description in PYTHON_TYPES:
        items.append(
            lsp.CompletionItem(
                label=type_name,
                kind=lsp.CompletionItemKind.TypeParameter,
                detail=description,
                insert_text=f'"{type_name}"',
                insert_text_format=lsp.InsertTextFormat.PlainText,
            )
        )

    # Add generic types
    generic_types = [
        ("list[str]", "List of strings"),
        ("list[int]", "List of integers"),
        ("dict[str, Any]", "Dictionary with string keys"),
        ("tuple[str, int]", "Tuple with specific types"),
        ("Optional[str]", "Optional string (can be None)"),
    ]

    for type_name, description in generic_types:
        items.append(
            lsp.CompletionItem(
                label=type_name,
                kind=lsp.CompletionItemKind.TypeParameter,
                detail=description,
                insert_text=f'"{type_name}"',
                insert_text_format=lsp.InsertTextFormat.PlainText,
            )
        )

    return items


def _make_target_completions(line_prefix: str) -> list[lsp.CompletionItem]:
    """Create completion items for target values.

    Args:
        line_prefix: Text before cursor on current line.

    Returns:
        List of completion items.
    """
    items = []

    for target, description in TARGET_VALUES:
        items.append(
            lsp.CompletionItem(
                label=target,
                kind=lsp.CompletionItemKind.EnumMember,
                detail=description,
                insert_text=f'"{target}"',
                insert_text_format=lsp.InsertTextFormat.PlainText,
            )
        )

    return items
