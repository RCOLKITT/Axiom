"""Python code analyzer for spec inference.

Parses Python files to extract function signatures, docstrings, and type hints.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class ParameterInfo:
    """Information about a function parameter.

    Attributes:
        name: Parameter name.
        type: Type annotation (as string).
        default: Default value (as string), or None.
        description: Description from docstring.
    """

    name: str
    type: str | None = None
    default: str | None = None
    description: str | None = None


@dataclass
class ReturnInfo:
    """Information about a function's return value.

    Attributes:
        type: Return type annotation (as string).
        description: Description from docstring.
    """

    type: str | None = None
    description: str | None = None


@dataclass
class ExampleInfo:
    """An example extracted from docstring or tests.

    Attributes:
        input: Input values.
        expected_output: Expected output.
        description: Optional description.
    """

    input: dict[str, Any]
    expected_output: Any
    description: str | None = None


@dataclass
class FunctionInfo:
    """Complete information about a function.

    Attributes:
        name: Function name.
        module_path: Path to the module.
        line_number: Line number where function is defined.
        is_async: Whether the function is async.
        parameters: List of parameters.
        returns: Return information.
        docstring: Full docstring.
        description: First line of docstring (summary).
        examples: Examples extracted from docstring.
        raises: Exceptions that may be raised.
        source_code: The function's source code.
    """

    name: str
    module_path: Path
    line_number: int
    is_async: bool = False
    parameters: list[ParameterInfo] = field(default_factory=list)
    returns: ReturnInfo | None = None
    docstring: str | None = None
    description: str | None = None
    examples: list[ExampleInfo] = field(default_factory=list)
    raises: list[str] = field(default_factory=list)
    source_code: str | None = None


def analyze_python_file(
    file_path: Path,
    function_name: str | None = None,
) -> list[FunctionInfo]:
    """Analyze a Python file and extract function information.

    Args:
        file_path: Path to the Python file.
        function_name: Optional specific function to analyze.

    Returns:
        List of FunctionInfo for each function found.
    """
    content = file_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(file_path))

    functions: list[FunctionInfo] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Skip private functions unless specifically requested
            if function_name is None and node.name.startswith("_"):
                continue

            # Skip if function_name specified and doesn't match
            if function_name is not None and node.name != function_name:
                continue

            info = _analyze_function(node, file_path, content)
            functions.append(info)

    return functions


def _analyze_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    file_path: Path,
    source: str,
) -> FunctionInfo:
    """Analyze a single function node.

    Args:
        node: The AST function node.
        file_path: Path to the source file.
        source: Full source code.

    Returns:
        FunctionInfo for the function.
    """
    # Extract basic info
    info = FunctionInfo(
        name=node.name,
        module_path=file_path,
        line_number=node.lineno,
        is_async=isinstance(node, ast.AsyncFunctionDef),
    )

    # Extract parameters
    info.parameters = _extract_parameters(node)

    # Extract return type
    if node.returns:
        info.returns = ReturnInfo(type=_annotation_to_str(node.returns))
    else:
        info.returns = ReturnInfo()

    # Extract docstring
    docstring = ast.get_docstring(node)
    if docstring:
        info.docstring = docstring
        info.description = _extract_description(docstring)
        info.examples = _extract_docstring_examples(docstring, info.parameters)
        info.raises = _extract_raises(docstring)

        # Try to get param descriptions from docstring
        _enrich_params_from_docstring(info.parameters, docstring)

        # Try to get return description from docstring
        if info.returns:
            info.returns.description = _extract_return_description(docstring)

    # Extract source code
    info.source_code = _extract_source(node, source)

    return info


def _extract_parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ParameterInfo]:
    """Extract parameter information from function node.

    Args:
        node: The function node.

    Returns:
        List of ParameterInfo.
    """
    params: list[ParameterInfo] = []

    # Get args
    args = node.args

    # Calculate defaults offset
    defaults = [None] * (len(args.args) - len(args.defaults)) + list(args.defaults)

    for arg, default in zip(args.args, defaults):
        # Skip 'self' and 'cls'
        if arg.arg in ("self", "cls"):
            continue

        param = ParameterInfo(
            name=arg.arg,
            type=_annotation_to_str(arg.annotation) if arg.annotation else None,
            default=_default_to_str(default) if default else None,
        )
        params.append(param)

    # Add keyword-only args
    kw_defaults = args.kw_defaults
    for arg, default in zip(args.kwonlyargs, kw_defaults):
        param = ParameterInfo(
            name=arg.arg,
            type=_annotation_to_str(arg.annotation) if arg.annotation else None,
            default=_default_to_str(default) if default else None,
        )
        params.append(param)

    return params


def _annotation_to_str(annotation: ast.expr | None) -> str | None:
    """Convert an AST annotation to a string.

    Args:
        annotation: The annotation node.

    Returns:
        String representation of the annotation.
    """
    if annotation is None:
        return None

    if isinstance(annotation, ast.Name):
        return annotation.id
    elif isinstance(annotation, ast.Constant):
        return str(annotation.value)
    elif isinstance(annotation, ast.Subscript):
        base = _annotation_to_str(annotation.value)
        slice_str = _annotation_to_str(annotation.slice)
        return f"{base}[{slice_str}]"
    elif isinstance(annotation, ast.Attribute):
        value = _annotation_to_str(annotation.value)
        return f"{value}.{annotation.attr}"
    elif isinstance(annotation, ast.Tuple):
        elts = ", ".join(_annotation_to_str(e) or "" for e in annotation.elts)
        return elts
    elif isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        # Union type using |
        left = _annotation_to_str(annotation.left)
        right = _annotation_to_str(annotation.right)
        return f"{left} | {right}"

    # Fallback: try to get source
    try:
        return ast.unparse(annotation)
    except Exception:
        return str(type(annotation).__name__)


def _default_to_str(default: ast.expr | None) -> str | None:
    """Convert a default value node to string.

    Args:
        default: The default value node.

    Returns:
        String representation of the default.
    """
    if default is None:
        return None

    if isinstance(default, ast.Constant):
        return repr(default.value)
    elif isinstance(default, ast.Name):
        return default.id
    elif isinstance(default, ast.List):
        return "[]"
    elif isinstance(default, ast.Dict):
        return "{}"
    elif isinstance(default, ast.Tuple):
        return "()"

    try:
        return ast.unparse(default)
    except Exception:
        return "..."


def _extract_description(docstring: str) -> str:
    """Extract the first line (summary) from a docstring.

    Args:
        docstring: The full docstring.

    Returns:
        The first line/summary.
    """
    lines = docstring.strip().split("\n")
    if lines:
        return lines[0].strip()
    return ""


def _extract_docstring_examples(
    docstring: str,
    parameters: list[ParameterInfo],
) -> list[ExampleInfo]:
    """Extract examples from docstring.

    Supports Google-style docstrings with Examples section,
    and doctest-style >>> examples.

    Args:
        docstring: The docstring.
        parameters: Function parameters for context.

    Returns:
        List of ExampleInfo.
    """
    examples: list[ExampleInfo] = []

    # Try to extract doctest-style examples
    doctest_pattern = r">>>\s*(\w+)\((.*?)\)\n(.+?)(?=>>>|\n\n|$)"
    matches = re.findall(doctest_pattern, docstring, re.MULTILINE | re.DOTALL)

    for match in matches:
        func_name, args_str, result_str = match
        try:
            # Parse arguments
            inputs = _parse_doctest_args(args_str, parameters)
            # Parse result
            result = _parse_doctest_result(result_str.strip())

            examples.append(
                ExampleInfo(
                    input=inputs,
                    expected_output=result,
                )
            )
        except Exception:
            # Skip malformed examples
            continue

    return examples


def _parse_doctest_args(args_str: str, parameters: list[ParameterInfo]) -> dict[str, Any]:
    """Parse doctest argument string into dict.

    Args:
        args_str: The arguments string.
        parameters: Function parameters for names.

    Returns:
        Dictionary of input values.
    """
    inputs: dict[str, Any] = {}

    # Simple case: just values, map to parameter names
    parts = [p.strip() for p in args_str.split(",") if p.strip()]

    for i, part in enumerate(parts):
        # Check for keyword argument
        if "=" in part:
            key, value = part.split("=", 1)
            key = key.strip()
            value = value.strip()
        else:
            # Positional - use parameter name
            key = parameters[i].name if i < len(parameters) else f"arg{i}"
            value = part

        # Try to evaluate the value
        try:
            inputs[key] = eval(value)  # noqa: S307
        except Exception:
            inputs[key] = value

    return inputs


def _parse_doctest_result(result_str: str) -> Any:
    """Parse doctest result string.

    Args:
        result_str: The result string.

    Returns:
        The parsed result value.
    """
    # Remove any trailing lines
    result_str = result_str.split("\n")[0].strip()

    try:
        return eval(result_str)  # noqa: S307
    except Exception:
        return result_str


def _extract_raises(docstring: str) -> list[str]:
    """Extract exception types from docstring.

    Args:
        docstring: The docstring.

    Returns:
        List of exception type names.
    """
    raises: list[str] = []

    # Google-style: "Raises:\n    ExceptionType: description"
    raises_pattern = r"Raises:\s*\n((?:\s+\w+:.+\n?)+)"
    match = re.search(raises_pattern, docstring)

    if match:
        raises_section = match.group(1)
        exception_pattern = r"^\s*(\w+):"
        for line in raises_section.split("\n"):
            exc_match = re.match(exception_pattern, line)
            if exc_match:
                raises.append(exc_match.group(1))

    return raises


def _enrich_params_from_docstring(
    parameters: list[ParameterInfo],
    docstring: str,
) -> None:
    """Enrich parameter info with descriptions from docstring.

    Args:
        parameters: Parameters to enrich (modified in place).
        docstring: The docstring.
    """
    # Google-style: "Args:\n    param_name: description"
    args_pattern = r"Args:\s*\n((?:\s+\w+:.+\n?)+)"
    match = re.search(args_pattern, docstring)

    if match:
        args_section = match.group(1)
        param_pattern = r"^\s*(\w+):\s*(.+)"

        for line in args_section.split("\n"):
            param_match = re.match(param_pattern, line)
            if param_match:
                param_name = param_match.group(1)
                description = param_match.group(2).strip()

                for param in parameters:
                    if param.name == param_name:
                        param.description = description
                        break


def _extract_return_description(docstring: str) -> str | None:
    """Extract return description from docstring.

    Args:
        docstring: The docstring.

    Returns:
        Return description or None.
    """
    # Google-style: "Returns:\n    description"
    returns_pattern = r"Returns:\s*\n\s+(.+?)(?=\n\n|\n\w+:|$)"
    match = re.search(returns_pattern, docstring, re.DOTALL)

    if match:
        return match.group(1).strip()

    return None


def _extract_source(node: ast.FunctionDef | ast.AsyncFunctionDef, source: str) -> str:
    """Extract the source code of a function.

    Args:
        node: The function node.
        source: Full source code.

    Returns:
        The function's source code.
    """
    lines = source.split("\n")

    # Get start and end lines
    start = node.lineno - 1  # 0-indexed

    # Find end by looking at the last node
    end = start
    for child in ast.walk(node):
        if hasattr(child, "lineno"):
            end = max(end, child.lineno)
        if hasattr(child, "end_lineno") and child.end_lineno:
            end = max(end, child.end_lineno)

    return "\n".join(lines[start:end])
