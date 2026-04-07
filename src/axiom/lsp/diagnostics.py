"""Diagnostics provider for Axiom spec validation.

Validates .axiom files and produces LSP diagnostics for:
- YAML syntax errors
- Missing required fields
- Invalid field values
- Semantic issues (e.g., invalid types, malformed examples)
"""

from __future__ import annotations

import re

import yaml
from lsprotocol import types as lsp
from pydantic import ValidationError

from axiom.security.scanner import scan_for_secrets
from axiom.spec.models import Spec


def validate_document(source: str, uri: str) -> list[lsp.Diagnostic]:
    """Validate an Axiom spec document and return diagnostics.

    Args:
        source: The document source text.
        uri: The document URI (for error messages).

    Returns:
        List of LSP diagnostics for the document.
    """
    diagnostics: list[lsp.Diagnostic] = []

    # Check for empty document
    if not source.strip():
        diagnostics.append(
            lsp.Diagnostic(
                range=lsp.Range(
                    start=lsp.Position(line=0, character=0),
                    end=lsp.Position(line=0, character=0),
                ),
                message="Empty spec file",
                severity=lsp.DiagnosticSeverity.Warning,
                source="axiom",
            )
        )
        return diagnostics

    # Phase 1: YAML syntax validation
    try:
        data = yaml.safe_load(source)
    except yaml.YAMLError as e:
        line = 0
        char = 0
        if hasattr(e, "problem_mark") and e.problem_mark is not None:
            line = e.problem_mark.line
            char = e.problem_mark.column

        diagnostics.append(
            lsp.Diagnostic(
                range=lsp.Range(
                    start=lsp.Position(line=line, character=char),
                    end=lsp.Position(line=line, character=char + 10),
                ),
                message=f"YAML syntax error: {e}",
                severity=lsp.DiagnosticSeverity.Error,
                source="axiom",
            )
        )
        return diagnostics

    if data is None:
        diagnostics.append(
            lsp.Diagnostic(
                range=lsp.Range(
                    start=lsp.Position(line=0, character=0),
                    end=lsp.Position(line=0, character=0),
                ),
                message="Empty YAML document",
                severity=lsp.DiagnosticSeverity.Warning,
                source="axiom",
            )
        )
        return diagnostics

    # Phase 2: Check for required top-level fields
    required_fields = ["axiom", "metadata", "interface"]
    for field in required_fields:
        if field not in data:
            line = _find_best_insertion_line(source, field)
            diagnostics.append(
                lsp.Diagnostic(
                    range=lsp.Range(
                        start=lsp.Position(line=line, character=0),
                        end=lsp.Position(line=line, character=0),
                    ),
                    message=f"Missing required field: '{field}'",
                    severity=lsp.DiagnosticSeverity.Error,
                    source="axiom",
                )
            )

    # Phase 3: Validate metadata section
    if "metadata" in data:
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            line = _find_field_line(source, "metadata")
            diagnostics.append(
                lsp.Diagnostic(
                    range=lsp.Range(
                        start=lsp.Position(line=line, character=0),
                        end=lsp.Position(line=line, character=20),
                    ),
                    message="'metadata' must be a mapping",
                    severity=lsp.DiagnosticSeverity.Error,
                    source="axiom",
                )
            )
        else:
            if "name" not in metadata:
                line = _find_field_line(source, "metadata")
                diagnostics.append(
                    lsp.Diagnostic(
                        range=lsp.Range(
                            start=lsp.Position(line=line, character=0),
                            end=lsp.Position(line=line + 1, character=0),
                        ),
                        message="Missing required field: 'metadata.name'",
                        severity=lsp.DiagnosticSeverity.Error,
                        source="axiom",
                    )
                )

            if "target" not in metadata:
                line = _find_field_line(source, "metadata")
                diagnostics.append(
                    lsp.Diagnostic(
                        range=lsp.Range(
                            start=lsp.Position(line=line, character=0),
                            end=lsp.Position(line=line + 1, character=0),
                        ),
                        message="Missing required field: 'metadata.target'",
                        severity=lsp.DiagnosticSeverity.Warning,
                        source="axiom",
                    )
                )

            # Validate target format
            target = metadata.get("target", "")
            if target and not _is_valid_target(target):
                line = _find_field_line(source, "target")
                diagnostics.append(
                    lsp.Diagnostic(
                        range=lsp.Range(
                            start=lsp.Position(line=line, character=0),
                            end=lsp.Position(line=line, character=50),
                        ),
                        message=f"Invalid target format: '{target}'. Expected format: 'language:type' (e.g., 'python:function', 'python:fastapi')",
                        severity=lsp.DiagnosticSeverity.Error,
                        source="axiom",
                    )
                )

    # Phase 4: Validate interface section
    if "interface" in data:
        interface = data.get("interface", {})
        if not isinstance(interface, dict):
            line = _find_field_line(source, "interface")
            diagnostics.append(
                lsp.Diagnostic(
                    range=lsp.Range(
                        start=lsp.Position(line=line, character=0),
                        end=lsp.Position(line=line, character=20),
                    ),
                    message="'interface' must be a mapping",
                    severity=lsp.DiagnosticSeverity.Error,
                    source="axiom",
                )
            )
        else:
            # Check for function_name or http fields
            if "function_name" not in interface and "http" not in interface:
                line = _find_field_line(source, "interface")
                diagnostics.append(
                    lsp.Diagnostic(
                        range=lsp.Range(
                            start=lsp.Position(line=line, character=0),
                            end=lsp.Position(line=line + 1, character=0),
                        ),
                        message="Interface must have either 'function_name' or 'http' field",
                        severity=lsp.DiagnosticSeverity.Error,
                        source="axiom",
                    )
                )

    # Phase 5: Validate examples
    if "examples" in data:
        examples = data.get("examples", [])
        if not isinstance(examples, list):
            line = _find_field_line(source, "examples")
            diagnostics.append(
                lsp.Diagnostic(
                    range=lsp.Range(
                        start=lsp.Position(line=line, character=0),
                        end=lsp.Position(line=line, character=20),
                    ),
                    message="'examples' must be a list",
                    severity=lsp.DiagnosticSeverity.Error,
                    source="axiom",
                )
            )
        else:
            for i, example in enumerate(examples):
                if not isinstance(example, dict):
                    continue
                if "input" not in example and "expected_output" not in example:
                    line = _find_example_line(source, i)
                    diagnostics.append(
                        lsp.Diagnostic(
                            range=lsp.Range(
                                start=lsp.Position(line=line, character=0),
                                end=lsp.Position(line=line + 1, character=0),
                            ),
                            message=f"Example {i + 1} should have 'input' and/or 'expected_output'",
                            severity=lsp.DiagnosticSeverity.Warning,
                            source="axiom",
                        )
                    )

    # Phase 6: Full Pydantic validation (if basic structure is ok)
    if not any(d.severity == lsp.DiagnosticSeverity.Error for d in diagnostics):
        try:
            Spec.model_validate(data)
        except ValidationError as e:
            for error in e.errors():
                loc = ".".join(str(x) for x in error["loc"])
                line = _find_field_line(source, str(error["loc"][-1]) if error["loc"] else "")
                diagnostics.append(
                    lsp.Diagnostic(
                        range=lsp.Range(
                            start=lsp.Position(line=line, character=0),
                            end=lsp.Position(line=line, character=50),
                        ),
                        message=f"Validation error at '{loc}': {error['msg']}",
                        severity=lsp.DiagnosticSeverity.Error,
                        source="axiom",
                    )
                )

    # Phase 7: Security scan for secrets
    secret_matches = scan_for_secrets(source)
    for match in secret_matches:
        diagnostics.append(
            lsp.Diagnostic(
                range=lsp.Range(
                    start=lsp.Position(line=match.line_number - 1, character=0),
                    end=lsp.Position(line=match.line_number - 1, character=100),
                ),
                message=f"Potential secret detected: {match.pattern_name}",
                severity=lsp.DiagnosticSeverity.Error,
                source="axiom-security",
            )
        )

    return diagnostics


def _find_field_line(source: str, field: str) -> int:
    """Find the line number where a field is defined.

    Args:
        source: Document source text.
        field: Field name to find.

    Returns:
        Line number (0-indexed), or 0 if not found.
    """
    lines = source.split("\n")
    # Pattern to match field at start of line or after whitespace
    pattern = re.compile(rf"^\s*{re.escape(field)}:")
    for i, line in enumerate(lines):
        if pattern.match(line):
            return i
    return 0


def _find_example_line(source: str, example_index: int) -> int:
    """Find the line number for a specific example.

    Args:
        source: Document source text.
        example_index: 0-based index of the example.

    Returns:
        Line number (0-indexed).
    """
    lines = source.split("\n")
    in_examples = False
    example_count = 0

    for i, line in enumerate(lines):
        if re.match(r"^examples:", line):
            in_examples = True
            continue

        if in_examples:
            # Check for new top-level section
            if re.match(r"^\w+:", line):
                break

            # Count example entries (lines starting with '  - ')
            if re.match(r"^\s+-\s", line):
                if example_count == example_index:
                    return i
                example_count += 1

    return 0


def _find_best_insertion_line(source: str, missing_field: str) -> int:
    """Find the best line to report a missing field error.

    Args:
        source: Document source text.
        missing_field: The field that is missing.

    Returns:
        Line number (0-indexed) for the error.
    """
    # Map fields to their expected position order
    field_order = ["axiom", "metadata", "intent", "interface", "examples", "invariants"]

    try:
        missing_index = field_order.index(missing_field)
    except ValueError:
        return 0

    lines = source.split("\n")

    # Find the last field that should come before this one
    for field in reversed(field_order[:missing_index]):
        for i, line in enumerate(lines):
            if re.match(rf"^{field}:", line):
                return i + 1

    return 0


def _is_valid_target(target: str) -> bool:
    """Check if a target string is valid.

    Args:
        target: Target string to validate.

    Returns:
        True if valid, False otherwise.
    """
    valid_languages = ["python", "typescript", "rust"]
    valid_types = ["function", "fastapi", "class", "module"]

    if ":" not in target:
        return False

    parts = target.split(":", 1)
    if len(parts) != 2:
        return False

    language, target_type = parts
    return language in valid_languages and target_type in valid_types
