"""Document symbols provider for Axiom specs.

Provides outline/symbol navigation for .axiom spec files.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog
import yaml
from lsprotocol import types as lsp

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()


def get_document_symbols(source: str) -> list[lsp.DocumentSymbol]:
    """Return document outline symbols for a spec file.

    Provides hierarchical document symbols for IDE outline view.

    Args:
        source: The spec file source text.

    Returns:
        List of DocumentSymbol objects representing the spec structure.
    """
    symbols: list[lsp.DocumentSymbol] = []
    lines = source.split("\n")

    # Try to parse as YAML to get structure
    try:
        spec_data = yaml.safe_load(source)
    except yaml.YAMLError:
        spec_data = None

    # Define the top-level sections and their symbol kinds
    sections = [
        ("axiom", lsp.SymbolKind.Constant),
        ("metadata", lsp.SymbolKind.Namespace),
        ("intent", lsp.SymbolKind.String),
        ("interface", lsp.SymbolKind.Interface),
        ("examples", lsp.SymbolKind.Array),
        ("invariants", lsp.SymbolKind.Array),
        ("constraints", lsp.SymbolKind.Object),
        ("dependencies", lsp.SymbolKind.Array),
    ]

    for section_name, kind in sections:
        line_num = _find_section_line(lines, section_name)
        if line_num is None:
            continue

        section_range = _get_section_range(lines, section_name, line_num)
        selection_range = lsp.Range(
            start=lsp.Position(line=line_num, character=0),
            end=lsp.Position(line=line_num, character=len(section_name)),
        )

        children = _get_section_children(
            lines, section_name, line_num, spec_data.get(section_name) if spec_data else None
        )

        symbol = lsp.DocumentSymbol(
            name=section_name,
            kind=kind,
            range=section_range,
            selection_range=selection_range,
            children=children if children else None,
        )
        symbols.append(symbol)

    return symbols


def _find_section_line(lines: list[str], section_name: str) -> int | None:
    """Find the line number where a section starts.

    Args:
        lines: List of source lines.
        section_name: The section name to find.

    Returns:
        Line number (0-indexed) or None if not found.
    """
    pattern = rf"^{re.escape(section_name)}:"
    for i, line in enumerate(lines):
        if re.match(pattern, line):
            return i
    return None


def _get_section_range(lines: list[str], section_name: str, start_line: int) -> lsp.Range:
    """Get the range of a section including all its content.

    Args:
        lines: List of source lines.
        section_name: The section name.
        start_line: The starting line number.

    Returns:
        Range covering the entire section.
    """
    end_line = start_line

    # Find the end of this section (next top-level key or end of file)
    for i in range(start_line + 1, len(lines)):
        line = lines[i]
        # Check if this is a new top-level section (no leading whitespace)
        if line and not line[0].isspace() and ":" in line:
            end_line = i - 1
            break
        end_line = i

    return lsp.Range(
        start=lsp.Position(line=start_line, character=0),
        end=lsp.Position(line=end_line, character=len(lines[end_line]) if end_line < len(lines) else 0),
    )


def _get_section_children(
    lines: list[str],
    section_name: str,
    start_line: int,
    section_data: object,
) -> list[lsp.DocumentSymbol]:
    """Get child symbols for a section.

    Args:
        lines: List of source lines.
        section_name: The section name.
        start_line: The starting line number.
        section_data: The parsed section data.

    Returns:
        List of child DocumentSymbol objects.
    """
    children: list[lsp.DocumentSymbol] = []

    if section_name == "metadata" and isinstance(section_data, dict):
        # Add metadata fields as children
        for key in section_data:
            line_num = _find_nested_key(lines, start_line, key)
            if line_num is not None:
                children.append(
                    lsp.DocumentSymbol(
                        name=key,
                        kind=lsp.SymbolKind.Property,
                        range=lsp.Range(
                            start=lsp.Position(line=line_num, character=0),
                            end=lsp.Position(line=line_num, character=len(lines[line_num])),
                        ),
                        selection_range=lsp.Range(
                            start=lsp.Position(line=line_num, character=0),
                            end=lsp.Position(line=line_num, character=len(key)),
                        ),
                    )
                )

    elif section_name == "interface" and isinstance(section_data, dict):
        # Add interface components
        for key in ["function_name", "parameters", "returns"]:
            if key in section_data:
                line_num = _find_nested_key(lines, start_line, key)
                if line_num is not None:
                    kind = (
                        lsp.SymbolKind.Function
                        if key == "function_name"
                        else lsp.SymbolKind.Array
                        if key == "parameters"
                        else lsp.SymbolKind.TypeParameter
                    )
                    children.append(
                        lsp.DocumentSymbol(
                            name=key,
                            kind=kind,
                            range=lsp.Range(
                                start=lsp.Position(line=line_num, character=0),
                                end=lsp.Position(line=line_num, character=len(lines[line_num])),
                            ),
                            selection_range=lsp.Range(
                                start=lsp.Position(line=line_num, character=0),
                                end=lsp.Position(line=line_num, character=len(key)),
                            ),
                        )
                    )

    elif section_name == "examples" and isinstance(section_data, list):
        # Add each example as a child
        for i, example in enumerate(section_data):
            name = example.get("name", f"example_{i}") if isinstance(example, dict) else f"example_{i}"
            line_num = _find_list_item_name(lines, start_line, name)
            if line_num is not None:
                children.append(
                    lsp.DocumentSymbol(
                        name=name,
                        kind=lsp.SymbolKind.Method,
                        range=lsp.Range(
                            start=lsp.Position(line=line_num, character=0),
                            end=lsp.Position(line=line_num, character=len(lines[line_num])),
                        ),
                        selection_range=lsp.Range(
                            start=lsp.Position(line=line_num, character=0),
                            end=lsp.Position(line=line_num, character=len(name)),
                        ),
                    )
                )

    elif section_name == "invariants" and isinstance(section_data, list):
        # Add each invariant as a child
        for i, invariant in enumerate(section_data):
            desc = (
                invariant.get("description", f"invariant_{i}")[:30]
                if isinstance(invariant, dict)
                else f"invariant_{i}"
            )
            line_num = _find_list_item_description(lines, start_line, desc)
            if line_num is not None:
                children.append(
                    lsp.DocumentSymbol(
                        name=desc,
                        kind=lsp.SymbolKind.Event,
                        range=lsp.Range(
                            start=lsp.Position(line=line_num, character=0),
                            end=lsp.Position(line=line_num, character=len(lines[line_num])),
                        ),
                        selection_range=lsp.Range(
                            start=lsp.Position(line=line_num, character=0),
                            end=lsp.Position(line=line_num, character=min(30, len(lines[line_num]))),
                        ),
                    )
                )

    elif section_name == "dependencies" and isinstance(section_data, list):
        # Add each dependency as a child
        for i, dep in enumerate(section_data):
            name = dep.get("name", f"dependency_{i}") if isinstance(dep, dict) else f"dependency_{i}"
            line_num = _find_list_item_name(lines, start_line, name)
            if line_num is not None:
                children.append(
                    lsp.DocumentSymbol(
                        name=name,
                        kind=lsp.SymbolKind.Module,
                        range=lsp.Range(
                            start=lsp.Position(line=line_num, character=0),
                            end=lsp.Position(line=line_num, character=len(lines[line_num])),
                        ),
                        selection_range=lsp.Range(
                            start=lsp.Position(line=line_num, character=0),
                            end=lsp.Position(line=line_num, character=len(name)),
                        ),
                    )
                )

    return children


def _find_nested_key(lines: list[str], section_start: int, key: str) -> int | None:
    """Find a nested key within a section.

    Args:
        lines: List of source lines.
        section_start: Starting line of the section.
        key: The key to find.

    Returns:
        Line number or None if not found.
    """
    pattern = rf"^\s+{re.escape(key)}:"
    for i in range(section_start + 1, len(lines)):
        line = lines[i]
        # Stop if we hit another top-level section
        if line and not line[0].isspace() and ":" in line:
            break
        if re.match(pattern, line):
            return i
    return None


def _find_list_item_name(lines: list[str], section_start: int, name: str) -> int | None:
    """Find a list item by its name field.

    Args:
        lines: List of source lines.
        section_start: Starting line of the section.
        name: The name to find.

    Returns:
        Line number or None if not found.
    """
    pattern = rf"^\s+-\s*name:\s*['\"]?{re.escape(name)}['\"]?"
    for i in range(section_start + 1, len(lines)):
        line = lines[i]
        # Stop if we hit another top-level section
        if line and not line[0].isspace() and ":" in line:
            break
        if re.match(pattern, line):
            return i
    return None


def _find_list_item_description(lines: list[str], section_start: int, desc: str) -> int | None:
    """Find a list item by its description field.

    Args:
        lines: List of source lines.
        section_start: Starting line of the section.
        desc: The description prefix to find.

    Returns:
        Line number or None if not found.
    """
    desc_escaped = re.escape(desc)
    pattern = rf"^\s+-\s*description:\s*['\"]?{desc_escaped}"
    for i in range(section_start + 1, len(lines)):
        line = lines[i]
        # Stop if we hit another top-level section
        if line and not line[0].isspace() and ":" in line:
            break
        if re.match(pattern, line):
            return i
    return None
