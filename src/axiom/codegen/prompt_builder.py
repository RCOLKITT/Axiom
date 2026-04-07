"""Build LLM prompts from spec IR.

Constructs structured prompts for code generation from Pydantic spec models.
No string template interpolation - all prompts are built programmatically.
"""

from __future__ import annotations

from axiom.spec.models import (
    Dependency,
    Example,
    Invariant,
    Spec,
)


def build_system_prompt(target: str = "python:function") -> str:
    """Build the system prompt for code generation.

    Args:
        target: The target type ('python:function' or 'python:fastapi').

    Returns:
        The system prompt string.
    """
    if target == "python:fastapi":
        return _build_fastapi_system_prompt()
    return _build_function_system_prompt()


def _build_function_system_prompt() -> str:
    """Build system prompt for pure function generation."""
    return """You are a code generator for the Axiom system. Your job is to produce
a Python function that satisfies the specification below.

CRITICAL: Output ONLY the Python code. No explanations, no markdown fences (```),
no commentary before or after the code. Just the raw Python code.

The generated code must:
1. Satisfy every example (input → expected output) in the spec.
2. Satisfy every invariant for all valid inputs, not just the examples.
3. Include proper type hints matching the interface definition.
4. Include all necessary imports at the top of the file.
5. Handle all error cases described in the spec.
6. Be clean, idiomatic Python. No unnecessary complexity.
7. Use only standard library modules unless the spec explicitly allows external packages.

If the spec says to raise an exception for certain inputs, raise that exact exception type
with a descriptive message."""


def _build_fastapi_system_prompt() -> str:
    """Build system prompt for FastAPI endpoint generation."""
    return """You are a code generator for the Axiom system. Your job is to produce
a FastAPI router module that satisfies the specification below.

CRITICAL: Output ONLY the Python code. No explanations, no markdown fences (```),
no commentary before or after the code. Just the raw Python code.

The generated code must:
1. Create a FastAPI APIRouter with a single route handler.
2. Use Pydantic models for request/response validation.
3. Satisfy every example (HTTP request → HTTP response) in the spec.
4. Return appropriate HTTP status codes for success and error cases.
5. Include proper type hints and Pydantic models.
6. Include all necessary imports at the top of the file.
7. Handle all error cases with HTTPException using the specified status codes.
8. Be clean, idiomatic FastAPI code. No unnecessary complexity.

Structure the code as:
1. Imports (fastapi, pydantic, etc.)
2. Pydantic models for request body (if needed)
3. Pydantic models for response body
4. APIRouter instance: router = APIRouter()
5. Route handler function with proper decorators

For error cases, use:
    raise HTTPException(status_code=XXX, detail="error message")"""


def build_user_prompt(spec: Spec) -> str:
    """Build the user prompt from a spec.

    Args:
        spec: The parsed spec.

    Returns:
        The user prompt string.
    """
    if spec.is_fastapi:
        return _build_fastapi_user_prompt(spec)
    return _build_function_user_prompt(spec)


def _build_function_user_prompt(spec: Spec) -> str:
    """Build user prompt for pure function specs."""
    sections = [
        _build_header(spec),
        _build_intent_section(spec),
        _build_dependencies_section(spec),
        _build_function_interface_section(spec),
        _build_examples_section(spec),
        _build_invariants_section(spec),
        _build_function_footer(),
    ]

    return "\n\n".join(section for section in sections if section)


def _build_fastapi_user_prompt(spec: Spec) -> str:
    """Build user prompt for FastAPI endpoint specs."""
    sections = [
        _build_header(spec),
        _build_intent_section(spec),
        _build_dependencies_section(spec),
        _build_fastapi_interface_section(spec),
        _build_fastapi_examples_section(spec),
        _build_invariants_section(spec),
        _build_constraints_section(spec),
        _build_fastapi_footer(),
    ]

    return "\n\n".join(section for section in sections if section)


def build_retry_prompt(spec: Spec, failures: list[str]) -> str:
    """Build a retry prompt including failure information.

    Args:
        spec: The parsed spec.
        failures: List of failure descriptions from verification.

    Returns:
        The retry prompt string.
    """
    base_prompt = build_user_prompt(spec)

    failure_section = _format_failures(failures)

    code_type = "router" if spec.is_fastapi else "function"

    return f"""{base_prompt}

## Previous Attempt Failed

The previous code generation failed verification. Here are the specific failures:

{failure_section}

Fix ONLY these specific issues. Do not change working code. Output the complete
corrected {code_type}."""


def _build_header(spec: Spec) -> str:
    """Build the header section."""
    return f"""## Specification: {spec.metadata.name}
Version: {spec.metadata.version}
Target: {spec.metadata.target}"""


def _build_intent_section(spec: Spec) -> str:
    """Build the intent section."""
    return f"""## Intent

{spec.intent.strip()}"""


def _build_dependencies_section(spec: Spec) -> str:
    """Build the dependencies section.

    Informs the LLM about available dependencies that can be imported and used.

    Args:
        spec: The parsed spec.

    Returns:
        The dependencies section string, or empty string if no dependencies.
    """
    if not spec.dependencies:
        return ""

    lines = ["## Dependencies"]
    lines.append("")
    lines.append("The following dependencies are available for use in your implementation:")
    lines.append("")

    for dep in spec.dependencies:
        lines.append(_format_dependency(dep))
        lines.append("")

    lines.append("Import and use these dependencies as needed. For spec dependencies,")
    lines.append("import with: `from <module_name> import <function_name>`")

    return "\n".join(lines)


def _format_dependency(dep: Dependency) -> str:
    """Format a single dependency for the prompt.

    Args:
        dep: The dependency to format.

    Returns:
        Formatted dependency description.
    """
    lines = [f"### {dep.name} ({dep.type})"]

    if dep.type == "spec":
        # Spec dependency - generated by Axiom
        lines.append(f"Import: `from {dep.name} import {dep.name}`")
    elif dep.type == "hand-written":
        # Hand-written dependency
        lines.append("Type: Hand-written module (already exists in codebase)")
    elif dep.type == "external-package":
        # External package
        if dep.version:
            lines.append(f"Package: {dep.name} (version {dep.version})")
        else:
            lines.append(f"Package: {dep.name}")

    # Add interface description if available
    if dep.interface:
        lines.append("Interface:")
        if isinstance(dep.interface, dict):
            for key, value in dep.interface.items():
                lines.append(f"  - {key}: {value}")
        else:
            # HandWrittenInterface - format structured interface
            lines.append(f"  - module: {dep.interface.module_path}")
            for func in dep.interface.functions:
                lines.append(f"  - {func.name}(...)")

    return "\n".join(lines)


def _build_function_interface_section(spec: Spec) -> str:
    """Build the interface section for function specs."""
    interface = spec.get_function_interface()

    # Format parameters
    params_lines = []
    for p in interface.parameters:
        constraint_info = f" (constraints: {p.constraints})" if p.constraints else ""
        params_lines.append(f"  - {p.name}: {p.type}{constraint_info}")
        params_lines.append(f"    {p.description}")

    params_str = "\n".join(params_lines) if params_lines else "  (no parameters)"

    # Format return type
    returns = interface.returns
    returns_str = f"  Type: {returns.type}\n  {returns.description}"

    return f"""## Interface

Function: {interface.function_name}

Parameters:
{params_str}

Returns:
{returns_str}"""


def _build_fastapi_interface_section(spec: Spec) -> str:
    """Build the interface section for FastAPI specs."""
    interface = spec.get_fastapi_interface()

    lines = ["## HTTP Endpoint"]
    lines.append("")
    lines.append(f"Method: {interface.method}")
    lines.append(f"Path: {interface.path}")
    lines.append(f"Handler Function: {interface.function_name}")

    # Path parameters
    if interface.path_parameters:
        lines.append("")
        lines.append("Path Parameters:")
        for p in interface.path_parameters:
            constraint_info = f" (constraints: {p.constraints})" if p.constraints else ""
            lines.append(f"  - {p.name}: {p.type}{constraint_info}")
            if p.description:
                lines.append(f"    {p.description}")

    # Query parameters
    if interface.query_parameters:
        lines.append("")
        lines.append("Query Parameters:")
        for p in interface.query_parameters:
            constraint_info = f" (constraints: {p.constraints})" if p.constraints else ""
            lines.append(f"  - {p.name}: {p.type}{constraint_info}")
            if p.description:
                lines.append(f"    {p.description}")

    # Request body
    if interface.request_body and interface.request_body.fields:
        lines.append("")
        lines.append("Request Body (JSON):")
        for f in interface.request_body.fields:
            required = " (required)" if f.required else " (optional)"
            constraint_info = f" [{f.constraints}]" if f.constraints else ""
            lines.append(f"  - {f.name}: {f.type}{required}{constraint_info}")
            if f.description:
                lines.append(f"    {f.description}")

    # Response
    lines.append("")
    lines.append("Response:")
    success = interface.response.success
    lines.append(f"  Success ({success.status}):")
    if success.body:
        if isinstance(success.body, dict):
            for k, v in success.body.items():
                lines.append(f"    - {k}: {v}")
        else:
            lines.append(f"    {success.body}")

    if interface.response.errors:
        lines.append("")
        lines.append("  Errors:")
        for err in interface.response.errors:
            lines.append(f"    - {err.status}: {err.when}")

    return "\n".join(lines)


def _build_examples_section(spec: Spec) -> str:
    """Build the examples section."""
    if not spec.examples:
        return ""

    examples_lines = []
    for ex in spec.examples:
        examples_lines.append(_format_example(ex))

    return f"""## Examples

{chr(10).join(examples_lines)}"""


def _format_example(example: Example) -> str:
    """Format a single example."""
    lines = [f"### {example.name}"]

    # Input
    if example.input:
        input_str = ", ".join(f"{k}={_format_value(v)}" for k, v in example.input.items())
        lines.append(f"Input: {input_str}")
    else:
        lines.append("Input: (no arguments)")

    # Expected output
    if example.expected_output.is_exception():
        exc = example.expected_output.raises
        if example.expected_output.message_contains:
            lines.append(
                f"Expected: raises {exc} with message containing "
                f'"{example.expected_output.message_contains}"'
            )
        else:
            lines.append(f"Expected: raises {exc}")
    else:
        lines.append(f"Expected: {_format_value(example.expected_output.value)}")

    return "\n".join(lines)


def _format_value(value: object) -> str:
    """Format a value for display in prompts."""
    if isinstance(value, str):
        return repr(value)
    return str(value)


def _build_invariants_section(spec: Spec) -> str:
    """Build the invariants section."""
    if not spec.invariants:
        return ""

    inv_lines = []
    for inv in spec.invariants:
        inv_lines.append(_format_invariant(inv))

    return f"""## Invariants (must hold for ALL valid inputs)

{chr(10).join(inv_lines)}"""


def _format_invariant(invariant: Invariant) -> str:
    """Format a single invariant."""
    if invariant.check:
        return f"- {invariant.description}\n  Check: `{invariant.check}`"
    return f"- {invariant.description}"


def _build_function_footer() -> str:
    """Build the footer section for function specs."""
    return """## Instructions

Generate the complete Python function that satisfies all the above requirements.
Include all necessary imports. Output ONLY the code, nothing else."""


def _build_fastapi_footer() -> str:
    """Build the footer section for FastAPI specs."""
    return """## Instructions

Generate the complete FastAPI router module that satisfies all the above requirements.
Include:
1. All necessary imports (fastapi, pydantic, etc.)
2. Pydantic models for request/response bodies
3. An APIRouter instance: router = APIRouter()
4. The route handler with proper decorators and type hints

Output ONLY the code, nothing else."""


def _build_fastapi_examples_section(spec: Spec) -> str:
    """Build the examples section for FastAPI specs."""
    if not spec.examples:
        return ""

    examples_lines = []
    for ex in spec.examples:
        examples_lines.append(_format_http_example(ex))

    return f"""## Examples (HTTP Request → Response)

{chr(10).join(examples_lines)}"""


def _format_http_example(example: Example) -> str:
    """Format a single HTTP example."""
    lines = [f"### {example.name}"]

    # Input (request)
    if example.input:
        lines.append("Request:")
        for k, v in example.input.items():
            lines.append(f"  {k}: {_format_value(v)}")
    else:
        lines.append("Request: (no body)")

    # Expected output (response)
    if example.expected_output.is_exception():
        # For HTTP, exceptions map to error status codes
        exc = example.expected_output.raises
        if example.expected_output.message_contains:
            lines.append(
                f"Expected Response: HTTP error (like {exc}) with detail containing "
                f'"{example.expected_output.message_contains}"'
            )
        else:
            lines.append(f"Expected Response: HTTP error (like {exc})")
    else:
        lines.append(f"Expected Response: {_format_value(example.expected_output.value)}")

    return "\n".join(lines)


def _build_constraints_section(spec: Spec) -> str:
    """Build the constraints section."""
    constraints = spec.constraints
    if not constraints.performance.max_response_time_ms:
        return ""

    return f"""## Performance Constraints

- Maximum response time: {constraints.performance.max_response_time_ms}ms"""


def _format_failures(failures: list[str]) -> str:
    """Format failure descriptions for retry prompt."""
    if not failures:
        return "No specific failures recorded."

    lines = []
    for i, failure in enumerate(failures, 1):
        lines.append(f"{i}. {failure}")

    return "\n".join(lines)
