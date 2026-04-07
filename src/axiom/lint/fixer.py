"""Auto-fix functionality for spec linting.

Automatically improves specs by adding missing examples, descriptions, and invariants.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
import yaml

if TYPE_CHECKING:
    from axiom.spec.models import Spec

logger = structlog.get_logger()


@dataclass
class FixResult:
    """Result of fixing a spec file.

    Attributes:
        file_path: Path to the spec file.
        changes: List of changes made.
        content_before: Original content.
        content_after: Fixed content.
        success: Whether the fix was successful.
        error: Error message if failed.
    """

    file_path: Path
    changes: list[str] = field(default_factory=list)
    content_before: str = ""
    content_after: str = ""
    success: bool = True
    error: str | None = None


def fix_spec_file(
    spec_path: Path,
    spec: Spec,
    dry_run: bool = False,
) -> FixResult:
    """Fix a spec file by applying auto-fixes.

    Args:
        spec_path: Path to the spec file.
        spec: The parsed spec (for analysis).
        dry_run: If True, don't actually modify the file.

    Returns:
        FixResult with changes made.
    """
    result = FixResult(file_path=spec_path)

    try:
        content = spec_path.read_text(encoding="utf-8")
        result.content_before = content

        # Parse YAML for modifications
        data = yaml.safe_load(content)
        modified = False

        # Fix missing metadata description
        if not data.get("metadata", {}).get("description"):
            data.setdefault("metadata", {})
            data["metadata"]["description"] = f"TODO: Describe {spec.metadata.name}"
            result.changes.append("Added placeholder metadata description")
            modified = True

        # Fix missing parameter descriptions (for function interfaces)
        if "interface" in data:
            interface = data["interface"]
            if "parameters" in interface:
                for param in interface["parameters"]:
                    if not param.get("description"):
                        param["description"] = f"TODO: Describe {param.get('name', 'param')}"
                        result.changes.append(
                            f"Added placeholder description for parameter '{param.get('name')}'"
                        )
                        modified = True

            # Fix missing return description
            if "returns" in interface:
                returns = interface["returns"]
                if isinstance(returns, dict) and not returns.get("description"):
                    returns["description"] = "TODO: Describe the return value"
                    result.changes.append("Added placeholder return description")
                    modified = True

        # Add example if none exist
        if not data.get("examples"):
            data["examples"] = [
                {
                    "name": "basic_example",
                    "input": _generate_example_input(spec),
                    "expected_output": "TODO: Replace with expected output",
                }
            ]
            result.changes.append("Added placeholder example")
            modified = True
        elif len(data.get("examples", [])) < 3:
            # Suggest adding more examples by adding placeholders
            existing_count = len(data.get("examples", []))
            needed = 3 - existing_count

            for i in range(needed):
                data["examples"].append(
                    {
                        "name": f"additional_example_{existing_count + i + 1}",
                        "input": _generate_example_input(spec),
                        "expected_output": "TODO: Replace with expected output",
                    }
                )
                result.changes.append(f"Added placeholder example #{existing_count + i + 1}")
            modified = True

        # Add error example if none exist
        has_error_example = any(
            isinstance(ex.get("expected_output"), dict)
            and "raises" in ex.get("expected_output", {})
            for ex in data.get("examples", [])
        )
        if not has_error_example:
            data["examples"].append(
                {
                    "name": "error_case",
                    "input": _generate_error_input(spec),
                    "expected_output": {"raises": "ValueError"},
                }
            )
            result.changes.append("Added error case example")
            modified = True

        # Add invariant if none exist
        if not data.get("invariants"):
            data["invariants"] = [_generate_default_invariant(spec)]
            result.changes.append("Added default invariant")
            modified = True

        if modified:
            # Convert back to YAML with nice formatting
            result.content_after = _dump_yaml(data)

            if not dry_run:
                spec_path.write_text(result.content_after, encoding="utf-8")
        else:
            result.content_after = content
            result.changes = []

        return result

    except Exception as e:
        logger.exception("Failed to fix spec", path=str(spec_path))
        return FixResult(
            file_path=spec_path,
            success=False,
            error=str(e),
        )


def _generate_example_input(spec: Spec) -> dict[str, object]:
    """Generate example input based on spec interface.

    Args:
        spec: The parsed spec.

    Returns:
        Dictionary of example inputs.
    """
    inputs: dict[str, object] = {}

    if hasattr(spec.interface, "parameters") and spec.interface.parameters:
        for param in spec.interface.parameters:
            inputs[param.name] = _generate_default_value(param.type)

    return inputs


def _generate_error_input(spec: Spec) -> dict[str, object]:
    """Generate input that should trigger an error.

    Args:
        spec: The parsed spec.

    Returns:
        Dictionary of inputs likely to cause an error.
    """
    inputs: dict[str, object] = {}

    if hasattr(spec.interface, "parameters") and spec.interface.parameters:
        for param in spec.interface.parameters:
            # Use empty or null values to trigger errors
            inputs[param.name] = _generate_error_value(param.type)

    return inputs


def _generate_default_value(type_str: str | None) -> object:
    """Generate a default value for a type.

    Args:
        type_str: The type string.

    Returns:
        A default value for that type.
    """
    if not type_str:
        return "example"

    type_lower = type_str.lower()

    if "str" in type_lower:
        return "example"
    if "int" in type_lower:
        return 42
    if "float" in type_lower:
        return 3.14
    if "bool" in type_lower:
        return True
    if "list" in type_lower:
        return ["item1", "item2"]
    if "dict" in type_lower:
        return {"key": "value"}
    if "optional" in type_lower:
        # Extract inner type
        match = re.search(r"optional\[(.+)\]", type_lower)
        if match:
            return _generate_default_value(match.group(1))
        return None

    return "example"


def _generate_error_value(type_str: str | None) -> object:
    """Generate a value likely to cause an error.

    Args:
        type_str: The type string.

    Returns:
        A value that should trigger validation errors.
    """
    if not type_str:
        return ""

    type_lower = type_str.lower()

    if "str" in type_lower:
        return ""  # Empty string often invalid
    if "int" in type_lower:
        return -1  # Negative often invalid
    if "float" in type_lower:
        return float("nan")
    if "list" in type_lower:
        return []  # Empty list
    if "dict" in type_lower:
        return {}  # Empty dict

    return None


def _generate_default_invariant(spec: Spec) -> dict[str, object]:
    """Generate a default invariant based on spec.

    Args:
        spec: The parsed spec.

    Returns:
        Dictionary representing an invariant.
    """
    # Try to generate a type-checking invariant
    if hasattr(spec.interface, "returns") and spec.interface.returns:
        return_type = spec.interface.returns.type
        if return_type:
            type_check = _type_to_isinstance(return_type)
            if type_check:
                return {
                    "description": f"Output is always {return_type}",
                    "check": f"isinstance(output, {type_check})",
                }

    # Default to a simple truthiness check
    return {
        "description": "Output is valid",
        "check": "output is not None",
    }


def _type_to_isinstance(type_str: str) -> str | None:
    """Convert a type string to isinstance check.

    Args:
        type_str: The type string.

    Returns:
        The type for isinstance or None.
    """
    type_lower = type_str.lower()

    mappings = {
        "str": "str",
        "string": "str",
        "int": "int",
        "integer": "int",
        "float": "float",
        "number": "(int, float)",
        "bool": "bool",
        "boolean": "bool",
        "list": "list",
        "array": "list",
        "dict": "dict",
        "object": "dict",
    }

    for key, value in mappings.items():
        if key in type_lower:
            return value

    return None


def _dump_yaml(data: dict[str, object]) -> str:
    """Dump data to YAML with nice formatting.

    Args:
        data: The data to dump.

    Returns:
        Formatted YAML string.
    """

    class CustomDumper(yaml.SafeDumper):
        pass

    # Add custom representers for better formatting
    def str_representer(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
        if "\n" in data:
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data)

    CustomDumper.add_representer(str, str_representer)

    return yaml.dump(
        data,
        Dumper=CustomDumper,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )


def format_fix_result(result: FixResult) -> str:
    """Format a fix result for display.

    Args:
        result: The fix result.

    Returns:
        Formatted string.
    """
    lines = []

    if not result.success:
        lines.append(f"✗ {result.file_path.name} - Error: {result.error}")
        return "\n".join(lines)

    if not result.changes:
        lines.append(f"✓ {result.file_path.name} - No changes needed")
        return "\n".join(lines)

    lines.append(f"✓ {result.file_path.name} - {len(result.changes)} change(s)")
    for change in result.changes:
        lines.append(f"    • {change}")

    return "\n".join(lines)
