"""Post-processing for generated code.

Cleans up, formats, and validates generated Python code.
"""

from __future__ import annotations

import ast
import subprocess
import tempfile
from pathlib import Path

import structlog

from axiom.errors import GenerationError

logger = structlog.get_logger()


def post_process(code: str, spec_name: str) -> str:
    """Post-process generated code.

    Steps:
    1. Validate syntax
    2. Ensure imports are present
    3. Format with ruff (if available)

    Args:
        code: The raw generated code.
        spec_name: Name of the spec (for error messages).

    Returns:
        Post-processed code.

    Raises:
        GenerationError: If the code has syntax errors.
    """
    # Step 1: Validate syntax
    try:
        ast.parse(code)
    except SyntaxError as e:
        raise GenerationError(
            f"Generated code has syntax error at line {e.lineno}: {e.msg}. "
            "The LLM produced invalid Python code.",
            spec_name=spec_name,
        ) from e

    # Step 2: Ensure necessary imports
    code = _ensure_imports(code)

    # Step 3: Format with ruff
    code = _format_with_ruff(code)

    return code


def _ensure_imports(code: str) -> str:
    """Ensure the code has necessary imports.

    Analyzes the code to detect used builtins/modules and adds imports if missing.

    Args:
        code: The Python code.

    Returns:
        Code with imports added if needed.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # If we can't parse, just return as-is
        return code

    # Collect existing imports
    existing_imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                existing_imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            existing_imports.add(node.module.split(".")[0])

    # Collect used names
    used_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            # Get the root of attribute access (e.g., 're.match' -> 're')
            if isinstance(node.value, ast.Name):
                used_names.add(node.value.id)

    # Common module mappings
    module_mappings = {
        "re": "re",
        "json": "json",
        "typing": "typing",
        "dataclasses": "dataclasses",
        "datetime": "datetime",
        "collections": "collections",
        "itertools": "itertools",
        "functools": "functools",
        "pathlib": "pathlib",
        "os": "os",
        "sys": "sys",
        "uuid": "uuid",
    }

    # Check what needs to be imported
    needed_imports: list[str] = []
    for name in used_names:
        if name in module_mappings and name not in existing_imports:
            needed_imports.append(f"import {name}")

    # Check for typing imports
    typing_names = {"List", "Dict", "Set", "Tuple", "Optional", "Union", "Any", "Callable"}
    used_typing = used_names & typing_names
    if used_typing and "typing" not in existing_imports:
        # Check if they're using modern type hints (no import needed for 3.12+)
        # For compatibility, we'll add the import anyway
        pass  # Let ruff handle this

    if not needed_imports:
        return code

    # Add imports at the top
    import_block = "\n".join(sorted(needed_imports))

    # Find where to insert (after any existing imports or docstring)
    lines = code.split("\n")
    insert_idx = 0

    # Skip docstring if present
    if lines and (lines[0].startswith('"""') or lines[0].startswith("'''")):
        quote = lines[0][:3]
        if lines[0].count(quote) >= 2:
            # Single-line docstring
            insert_idx = 1
        else:
            # Multi-line docstring
            for i, line in enumerate(lines[1:], 1):
                if quote in line:
                    insert_idx = i + 1
                    break

    # Skip existing imports
    for i, line in enumerate(lines[insert_idx:], insert_idx):
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            insert_idx = i + 1
        elif stripped and not stripped.startswith("#"):
            break

    # Insert new imports
    lines.insert(insert_idx, import_block)
    if insert_idx > 0 and lines[insert_idx - 1].strip():
        lines.insert(insert_idx, "")  # Add blank line before

    return "\n".join(lines)


def _format_with_ruff(code: str) -> str:
    """Format code using ruff if available.

    Args:
        code: The Python code.

    Returns:
        Formatted code, or original if ruff is unavailable.
    """
    try:
        # Write code to temp file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(code)
            temp_path = Path(f.name)

        try:
            # Run ruff format
            result = subprocess.run(
                ["ruff", "format", str(temp_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                # Read formatted code
                formatted = temp_path.read_text(encoding="utf-8")
                logger.debug("Code formatted with ruff")
                return formatted

            logger.debug("Ruff format returned non-zero", stderr=result.stderr)

        finally:
            # Clean up temp file
            temp_path.unlink(missing_ok=True)

    except FileNotFoundError:
        logger.debug("Ruff not found, skipping formatting")
    except subprocess.TimeoutExpired:
        logger.warning("Ruff formatting timed out")
    except Exception as e:
        logger.debug("Ruff formatting failed", error=str(e))

    return code


def validate_function_exists(code: str, function_name: str, spec_name: str) -> None:
    """Validate that the expected function exists in the code.

    Args:
        code: The Python code.
        function_name: Expected function name.
        spec_name: Spec name for error messages.

    Raises:
        GenerationError: If the function is not found.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise GenerationError(
            f"Generated code has syntax error: {e}",
            spec_name=spec_name,
        ) from e

    # Find function definitions (both sync and async)
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)

    if function_name not in functions:
        found = ", ".join(functions) if functions else "none"
        raise GenerationError(
            f"Expected function '{function_name}' not found in generated code. "
            f"Found functions: {found}. "
            "The LLM may have misnamed the function.",
            spec_name=spec_name,
        )


def validate_fastapi_router(code: str, function_name: str, spec_name: str) -> None:
    """Validate that the code defines a FastAPI router with the expected handler.

    Args:
        code: The Python code.
        function_name: Expected route handler function name.
        spec_name: Spec name for error messages.

    Raises:
        GenerationError: If the router or handler is not found.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise GenerationError(
            f"Generated code has syntax error: {e}",
            spec_name=spec_name,
        ) from e

    # Check for router assignment
    has_router = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "router":
                    has_router = True
                    break

    if not has_router:
        raise GenerationError(
            "Generated code must define 'router = APIRouter()'. "
            "The LLM did not create a router variable.",
            spec_name=spec_name,
        )

    # Check for the handler function (can be sync or async)
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)

    if function_name not in functions:
        found = ", ".join(functions) if functions else "none"
        raise GenerationError(
            f"Expected route handler '{function_name}' not found. "
            f"Found functions: {found}. "
            "The LLM may have misnamed the handler.",
            spec_name=spec_name,
        )


def add_generated_header(
    code: str,
    spec_name: str,
    spec_version: str,
    target: str = "python:function",
) -> str:
    """Add the standard Axiom generated header to code.

    Args:
        code: The Python code.
        spec_name: Name of the spec.
        spec_version: Version of the spec.
        target: The target type.

    Returns:
        Code with header prepended.
    """
    header = f"""# AXIOM GENERATED - DO NOT EDIT
# This file was generated by Axiom from: {spec_name}.axiom
# Spec: {spec_name} v{spec_version}
# To modify this code, edit the spec file and run 'axiom build'

"""
    return header + code


def extract_function(code: str, function_name: str) -> str:
    """Extract a specific function from code.

    Useful for extracting just the function without module-level code.

    Args:
        code: The Python code.
        function_name: Function to extract.

    Returns:
        The function definition as a string.

    Raises:
        ValueError: If the function is not found.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        raise ValueError(f"Cannot parse code to extract {function_name}") from None

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            # Get the source lines
            lines = code.split("\n")
            # ast line numbers are 1-indexed
            start = node.lineno - 1
            end = node.end_lineno if node.end_lineno else len(lines)
            return "\n".join(lines[start:end])

    raise ValueError(f"Function '{function_name}' not found in code")
