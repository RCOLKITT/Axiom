"""Code actions provider for Axiom specs.

Provides quick fixes and code actions for .axiom spec files.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

import structlog
from lsprotocol import types as lsp

logger = structlog.get_logger()


@dataclass
class SpecFix:
    """A suggested fix for a spec issue.

    Attributes:
        description: Human-readable description of the fix.
        range: The text range to replace.
        new_text: The replacement text.
    """

    description: str
    range: lsp.Range
    new_text: str


def get_code_actions(
    source: str,
    diagnostics: Sequence[lsp.Diagnostic],
    document_uri: str,
) -> list[lsp.CodeAction]:
    """Get code actions for the given diagnostics.

    Args:
        source: The document source text.
        diagnostics: List of diagnostics to provide actions for.
        document_uri: URI of the document.

    Returns:
        List of code actions.
    """
    actions: list[lsp.CodeAction] = []

    for diagnostic in diagnostics:
        if diagnostic.source != "axiom":
            continue

        fixes = _suggest_fixes(source, diagnostic)
        for fix in fixes:
            action = lsp.CodeAction(
                title=fix.description,
                kind=lsp.CodeActionKind.QuickFix,
                diagnostics=[diagnostic],
                edit=lsp.WorkspaceEdit(
                    changes={
                        document_uri: [
                            lsp.TextEdit(
                                range=fix.range,
                                new_text=fix.new_text,
                            )
                        ]
                    }
                ),
            )
            actions.append(action)

    # Add source actions (not diagnostic-related)
    actions.extend(_get_source_actions(source, document_uri))

    return actions


def _suggest_fixes(source: str, diagnostic: lsp.Diagnostic) -> list[SpecFix]:
    """Suggest fixes for a specific diagnostic.

    Args:
        source: The document source text.
        diagnostic: The diagnostic to fix.

    Returns:
        List of suggested fixes.
    """
    fixes: list[SpecFix] = []
    message = diagnostic.message.lower()
    lines = source.split("\n")

    # Fix missing required field
    if "required field" in message or "missing" in message:
        field_match = re.search(r"'(\w+)'", diagnostic.message)
        if field_match:
            field_name = field_match.group(1)
            fix = _suggest_add_required_field(lines, field_name, diagnostic.range)
            if fix:
                fixes.append(fix)

    # Fix invalid value suggestions
    if "must be one of" in message:
        valid_match = re.search(r"must be one of:\s*\[([^\]]+)\]", diagnostic.message)
        if valid_match:
            valid_values = [v.strip().strip("'\"") for v in valid_match.group(1).split(",")]
            for value in valid_values[:3]:  # Limit to 3 suggestions
                fixes.append(
                    SpecFix(
                        description=f"Change to '{value}'",
                        range=diagnostic.range,
                        new_text=value,
                    )
                )

    # Fix empty examples array
    if "no examples" in message or "examples required" in message:
        fixes.append(_suggest_add_example(lines, diagnostic.range))

    # Fix empty invariants
    if "no invariants" in message:
        fixes.append(_suggest_add_invariant(lines, diagnostic.range))

    # Fix invalid function name
    if "invalid function name" in message:
        # Extract the invalid name and suggest a valid version
        line_content = lines[diagnostic.range.start.line] if diagnostic.range.start.line < len(lines) else ""
        name_match = re.search(r"function_name:\s*['\"]?(\w+)", line_content)
        if name_match:
            invalid_name = name_match.group(1)
            valid_name = _make_valid_python_name(invalid_name)
            if valid_name != invalid_name:
                fixes.append(
                    SpecFix(
                        description=f"Rename to '{valid_name}'",
                        range=diagnostic.range,
                        new_text=line_content.replace(invalid_name, valid_name),
                    )
                )

    return fixes


def _suggest_add_required_field(
    lines: list[str],
    field_name: str,
    diagnostic_range: lsp.Range,
) -> SpecFix | None:
    """Suggest adding a required field.

    Args:
        lines: Source lines.
        field_name: The missing field name.
        diagnostic_range: Range of the diagnostic.

    Returns:
        SpecFix or None if unable to suggest.
    """
    # Determine appropriate template based on field name
    templates = {
        "name": "name: my_function",
        "description": 'description: "Description here"',
        "version": 'version: "1.0.0"',
        "target": 'target: "python:function"',
        "function_name": "function_name: my_function",
        "type": "type: str",
        "parameters": "parameters:\n    - name: param1\n      type: str\n      description: Parameter description",
        "returns": "returns:\n    type: str\n    description: Return value description",
    }

    template = templates.get(field_name, f'{field_name}: "value"')

    # Insert at the appropriate indentation
    if diagnostic_range.start.line < len(lines):
        ref_line = lines[diagnostic_range.start.line]
        indent = len(ref_line) - len(ref_line.lstrip())
    else:
        indent = 2

    new_text = " " * indent + template + "\n"

    return SpecFix(
        description=f"Add '{field_name}' field",
        range=lsp.Range(
            start=lsp.Position(line=diagnostic_range.end.line, character=0),
            end=lsp.Position(line=diagnostic_range.end.line, character=0),
        ),
        new_text=new_text,
    )


def _suggest_add_example(lines: list[str], diagnostic_range: lsp.Range) -> SpecFix:
    """Suggest adding an example.

    Args:
        lines: Source lines.
        diagnostic_range: Range of the diagnostic.

    Returns:
        SpecFix for adding an example.
    """
    example_template = """examples:
  - name: basic_example
    input:
      param1: "value"
    expected_output: "result"
"""
    return SpecFix(
        description="Add example",
        range=lsp.Range(
            start=lsp.Position(line=len(lines), character=0),
            end=lsp.Position(line=len(lines), character=0),
        ),
        new_text="\n" + example_template,
    )


def _suggest_add_invariant(lines: list[str], diagnostic_range: lsp.Range) -> SpecFix:
    """Suggest adding an invariant.

    Args:
        lines: Source lines.
        diagnostic_range: Range of the diagnostic.

    Returns:
        SpecFix for adding an invariant.
    """
    invariant_template = """invariants:
  - description: Output is valid
    check: "output is not None"
"""
    return SpecFix(
        description="Add invariant",
        range=lsp.Range(
            start=lsp.Position(line=len(lines), character=0),
            end=lsp.Position(line=len(lines), character=0),
        ),
        new_text="\n" + invariant_template,
    )


def _make_valid_python_name(name: str) -> str:
    """Convert a string to a valid Python identifier.

    Args:
        name: The original name.

    Returns:
        A valid Python identifier.
    """
    # Replace invalid characters with underscores
    result = re.sub(r"[^a-zA-Z0-9_]", "_", name)

    # Ensure it doesn't start with a digit
    if result and result[0].isdigit():
        result = "_" + result

    # Convert to snake_case
    result = re.sub(r"([a-z])([A-Z])", r"\1_\2", result).lower()

    return result or "my_function"


def _get_source_actions(source: str, document_uri: str) -> list[lsp.CodeAction]:
    """Get source-level code actions (refactoring, organize, etc).

    Args:
        source: The document source text.
        document_uri: URI of the document.

    Returns:
        List of source actions.
    """
    actions: list[lsp.CodeAction] = []
    lines = source.split("\n")

    # Suggest organizing sections in canonical order
    sections_found = []
    canonical_order = ["axiom", "metadata", "intent", "interface", "examples", "invariants", "constraints", "dependencies"]

    for section in canonical_order:
        for i, line in enumerate(lines):
            if re.match(rf"^{section}:", line):
                sections_found.append((section, i))
                break

    # Check if sections are out of order
    section_indices = [s[1] for s in sections_found]
    if section_indices != sorted(section_indices):
        actions.append(
            lsp.CodeAction(
                title="Organize sections",
                kind=lsp.CodeActionKind.SourceOrganizeImports,
                # This would require more complex edit logic
                # For now, just indicate the action is available
            )
        )

    return actions
