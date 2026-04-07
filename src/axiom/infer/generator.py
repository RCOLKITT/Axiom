"""Spec generator from analyzed Python code.

Generates .axiom spec files from FunctionInfo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog
import yaml

from axiom.infer.analyzer import FunctionInfo

logger = structlog.get_logger()


@dataclass
class InferredSpec:
    """An inferred spec ready to be written.

    Attributes:
        name: Spec name.
        content: The YAML content.
        source_function: The function it was inferred from.
        confidence: Confidence level (0-1).
        warnings: Any warnings about the inference.
    """

    name: str
    content: str
    source_function: FunctionInfo
    confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)


def generate_spec_from_function(
    func_info: FunctionInfo,
    include_source: bool = False,
) -> InferredSpec:
    """Generate a .axiom spec from function info.

    Args:
        func_info: The analyzed function.
        include_source: Whether to include source code in intent.

    Returns:
        InferredSpec with the generated content.
    """
    warnings: list[str] = []
    confidence = 1.0

    # Build spec data structure
    spec_data: dict[str, Any] = {
        "axiom": "0.1",
        "metadata": _build_metadata(func_info),
        "intent": _build_intent(func_info, include_source),
        "interface": _build_interface(func_info),
        "examples": _build_examples(func_info, warnings),
        "invariants": _build_invariants(func_info),
    }

    # Check confidence
    if not func_info.docstring:
        warnings.append("No docstring found - intent may be unclear")
        confidence -= 0.2

    if not func_info.examples:
        warnings.append("No examples found in docstring - added placeholders")
        confidence -= 0.2

    if not func_info.returns or not func_info.returns.type:
        warnings.append("No return type annotation - invariants may be incomplete")
        confidence -= 0.1

    for param in func_info.parameters:
        if not param.type:
            warnings.append(f"Parameter '{param.name}' has no type annotation")
            confidence -= 0.05

    confidence = max(0.1, confidence)  # Floor at 10%

    # Convert to YAML
    content = _dump_yaml(spec_data)

    return InferredSpec(
        name=func_info.name,
        content=content,
        source_function=func_info,
        confidence=confidence,
        warnings=warnings,
    )


def _build_metadata(func_info: FunctionInfo) -> dict[str, Any]:
    """Build metadata section.

    Args:
        func_info: The function info.

    Returns:
        Metadata dictionary.
    """
    return {
        "name": func_info.name,
        "version": "1.0.0",
        "description": func_info.description or f"TODO: Describe {func_info.name}",
        "target": "python:function",
    }


def _build_intent(func_info: FunctionInfo, include_source: bool) -> str:
    """Build intent section.

    Args:
        func_info: The function info.
        include_source: Whether to include source code.

    Returns:
        Intent string.
    """
    parts = []

    if func_info.description:
        parts.append(func_info.description)

    if func_info.docstring and len(func_info.docstring) > len(func_info.description or ""):
        # Include full docstring minus Args/Returns/Raises sections
        cleaned = _clean_docstring(func_info.docstring)
        if cleaned != func_info.description:
            parts.append("")
            parts.append(cleaned)

    if func_info.raises:
        parts.append("")
        parts.append("Error handling:")
        for exc in func_info.raises:
            parts.append(f"  - Raises {exc} on error conditions")

    if include_source and func_info.source_code:
        parts.append("")
        parts.append("Reference implementation:")
        parts.append("```python")
        parts.append(func_info.source_code)
        parts.append("```")

    if not parts:
        parts.append(f"TODO: Describe what {func_info.name} should do.")

    return "\n".join(parts)


def _build_interface(func_info: FunctionInfo) -> dict[str, Any]:
    """Build interface section.

    Args:
        func_info: The function info.

    Returns:
        Interface dictionary.
    """
    interface: dict[str, Any] = {
        "function_name": func_info.name,
    }

    # Add parameters
    if func_info.parameters:
        params = []
        for param in func_info.parameters:
            param_dict: dict[str, Any] = {
                "name": param.name,
                "type": param.type or "Any",
            }
            if param.description:
                param_dict["description"] = param.description
            else:
                param_dict["description"] = f"TODO: Describe {param.name}"
            if param.default is not None:
                param_dict["default"] = param.default
            params.append(param_dict)
        interface["parameters"] = params

    # Add returns
    if func_info.returns:
        returns_dict: dict[str, Any] = {
            "type": func_info.returns.type or "Any",
        }
        if func_info.returns.description:
            returns_dict["description"] = func_info.returns.description
        else:
            returns_dict["description"] = "TODO: Describe the return value"
        interface["returns"] = returns_dict

    return interface


def _build_examples(
    func_info: FunctionInfo,
    _warnings: list[str],
) -> list[dict[str, Any]]:
    """Build examples section.

    Args:
        func_info: The function info.
        _warnings: List to append warnings to (reserved for future use).

    Returns:
        List of example dictionaries.
    """
    examples: list[dict[str, Any]] = []

    # Add examples from docstring
    for i, ex in enumerate(func_info.examples):
        examples.append(
            {
                "name": f"doctest_example_{i + 1}",
                "input": ex.input,
                "expected_output": ex.expected_output,
            }
        )

    # If we have fewer than 3 examples, add placeholders
    while len(examples) < 3:
        idx = len(examples) + 1
        example = {
            "name": f"example_{idx}",
            "input": _generate_placeholder_input(func_info),
            "expected_output": "TODO: Replace with expected output",
        }
        examples.append(example)

    # Add an error case if we know the function raises exceptions
    if func_info.raises and not any(
        isinstance(ex.get("expected_output"), dict) and "raises" in ex.get("expected_output", {})
        for ex in examples
    ):
        examples.append(
            {
                "name": "error_case",
                "input": _generate_error_input(func_info),
                "expected_output": {"raises": func_info.raises[0]},
            }
        )

    return examples


def _build_invariants(func_info: FunctionInfo) -> list[dict[str, Any]]:
    """Build invariants section.

    Args:
        func_info: The function info.

    Returns:
        List of invariant dictionaries.
    """
    invariants: list[dict[str, Any]] = []

    # Add type invariant if return type is known
    if func_info.returns and func_info.returns.type:
        type_check = _type_to_isinstance(func_info.returns.type)
        if type_check:
            invariants.append(
                {
                    "description": f"Output is always {func_info.returns.type}",
                    "check": f"isinstance(output, {type_check})",
                }
            )

    # Add non-None check if not Optional
    if func_info.returns and func_info.returns.type:
        return_type = func_info.returns.type.lower()
        if "optional" not in return_type and "none" not in return_type:
            invariants.append(
                {
                    "description": "Output is never None",
                    "check": "output is not None",
                }
            )

    # If no invariants generated, add a placeholder
    if not invariants:
        invariants.append(
            {
                "description": "TODO: Add invariant",
                "check": "True",
            }
        )

    return invariants


def _generate_placeholder_input(func_info: FunctionInfo) -> dict[str, Any]:
    """Generate placeholder input values.

    Args:
        func_info: The function info.

    Returns:
        Dictionary of placeholder inputs.
    """
    inputs: dict[str, Any] = {}

    for param in func_info.parameters:
        inputs[param.name] = _type_to_default(param.type)

    return inputs


def _generate_error_input(func_info: FunctionInfo) -> dict[str, Any]:
    """Generate input likely to cause an error.

    Args:
        func_info: The function info.

    Returns:
        Dictionary of error-inducing inputs.
    """
    inputs: dict[str, Any] = {}

    for param in func_info.parameters:
        inputs[param.name] = _type_to_error_value(param.type)

    return inputs


def _type_to_default(type_str: str | None) -> Any:
    """Convert type to a default placeholder value.

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
        return None
    if "path" in type_lower:
        return "/path/to/file"

    return "example"


def _type_to_error_value(type_str: str | None) -> Any:
    """Convert type to an error-inducing value.

    Args:
        type_str: The type string.

    Returns:
        A value likely to cause errors.
    """
    if not type_str:
        return None

    type_lower = type_str.lower()

    if "str" in type_lower:
        return ""
    if "int" in type_lower:
        return -1
    if "float" in type_lower:
        return float("inf")
    if "list" in type_lower:
        return []
    if "dict" in type_lower:
        return {}
    if "path" in type_lower:
        return "/nonexistent/path"

    return None


def _type_to_isinstance(type_str: str) -> str | None:
    """Convert type string to isinstance check.

    Args:
        type_str: The type string.

    Returns:
        Type for isinstance or None.
    """
    type_lower = type_str.lower()

    # Remove optional wrapper
    if "optional[" in type_lower:
        return None  # Can be None, so no check

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
        "tuple": "tuple",
        "set": "set",
    }

    for key, value in mappings.items():
        if key in type_lower:
            return value

    return None


def _clean_docstring(docstring: str) -> str:
    """Remove Args/Returns/Raises sections from docstring.

    Args:
        docstring: The full docstring.

    Returns:
        Cleaned docstring with only description.
    """
    lines = docstring.split("\n")
    result = []
    skip_until_unindented = False

    for line in lines:
        stripped = line.strip()

        # Check for section headers
        if stripped in ("Args:", "Returns:", "Raises:", "Example:", "Examples:", "Note:", "Notes:"):
            skip_until_unindented = True
            continue

        # Check if we should stop skipping
        if skip_until_unindented:
            if stripped and not line.startswith("    ") and not line.startswith("\t"):
                skip_until_unindented = False
            else:
                continue

        result.append(line)

    return "\n".join(result).strip()


def _dump_yaml(data: dict[str, Any]) -> str:
    """Dump data to YAML with nice formatting.

    Args:
        data: The data to dump.

    Returns:
        Formatted YAML string.
    """

    class CustomDumper(yaml.SafeDumper):
        pass

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


def write_spec_file(
    inferred: InferredSpec,
    output_dir: Path,
    overwrite: bool = False,
) -> Path:
    """Write an inferred spec to a file.

    Args:
        inferred: The inferred spec.
        output_dir: Directory to write to.
        overwrite: Whether to overwrite existing files.

    Returns:
        Path to the written file.

    Raises:
        FileExistsError: If file exists and overwrite=False.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{inferred.name}.axiom"

    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Spec file already exists: {output_path}")

    output_path.write_text(inferred.content, encoding="utf-8")
    return output_path
