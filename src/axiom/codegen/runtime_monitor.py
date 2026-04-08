"""Runtime monitoring code generation.

This module generates runtime assertions and monitors that enforce
spec invariants during actual code execution. This extends the
verification from build-time to runtime.

The generated monitors can:
- Validate inputs match expected types and constraints
- Check outputs satisfy invariants
- Log violations for debugging
- Optionally raise exceptions on violation
"""

from __future__ import annotations

import structlog

from axiom.spec.models import Invariant, Parameter, Spec

logger = structlog.get_logger()


def generate_runtime_monitor(spec: Spec, strict: bool = True) -> str:
    """Generate a runtime monitor wrapper for a function.

    Args:
        spec: The spec to generate monitors for.
        strict: If True, raise exceptions on violations. If False, just log.

    Returns:
        Python code for a decorator that monitors the function.
    """
    function_name = spec.function_name
    params: list[Parameter] = []
    if hasattr(spec.interface, "parameters"):
        params = spec.interface.parameters

    # Generate the monitor decorator code
    code_parts = [
        f'"""Runtime monitor for {function_name} - auto-generated from spec."""',
        "",
        "import functools",
        "import logging",
        "from typing import Any, Callable, TypeVar",
        "",
        "F = TypeVar('F', bound=Callable[..., Any])",
        "",
        f"_monitor_logger = logging.getLogger('axiom.monitor.{function_name}')",
        "",
    ]

    # Generate input validators
    input_checks = _generate_input_checks(params)
    if input_checks:
        code_parts.append("def _validate_inputs(**kwargs: Any) -> list[str]:")
        code_parts.append('    """Validate input parameters against spec constraints."""')
        code_parts.append("    violations: list[str] = []")
        code_parts.extend(["    " + line for line in input_checks])
        code_parts.append("    return violations")
        code_parts.append("")

    # Generate output validators from invariants
    invariant_checks = _generate_invariant_checks(spec.invariants)
    if invariant_checks:
        code_parts.append(
            "def _validate_output(output: Any, input_kwargs: dict[str, Any]) -> list[str]:"
        )
        code_parts.append('    """Validate output against spec invariants."""')
        code_parts.append("    violations: list[str] = []")
        code_parts.append("    # Make input available for invariant checks")
        code_parts.append("    input = input_kwargs  # noqa: F841")
        code_parts.extend(["    " + line for line in invariant_checks])
        code_parts.append("    return violations")
        code_parts.append("")

    # Generate the decorator
    code_parts.extend([
        f"def monitor_{function_name}(strict: bool = {strict}) -> Callable[[F], F]:",
        f'    """Runtime monitor decorator for {function_name}.',
        "",
        "    Validates inputs and outputs against the spec.",
        "    ",
        "    Args:",
        "        strict: If True, raise RuntimeError on violations.",
        "                If False, just log warnings.",
        "    ",
        "    Returns:",
        "        Decorator function.",
        '    """',
        "    def decorator(func: F) -> F:",
        "        @functools.wraps(func)",
        "        def wrapper(*args: Any, **kwargs: Any) -> Any:",
        "            # Build kwargs dict from positional args",
        f"            param_names = {[p.name for p in params]}",
        "            all_kwargs = dict(zip(param_names, args))",
        "            all_kwargs.update(kwargs)",
        "",
    ])

    # Add input validation if we have checks
    if input_checks:
        code_parts.extend([
            "            # Validate inputs",
            "            input_violations = _validate_inputs(**all_kwargs)",
            "            if input_violations:",
            "                msg = f'Input violations: {input_violations}'",
            "                if strict:",
            "                    raise RuntimeError(msg)",
            "                _monitor_logger.warning(msg)",
            "",
        ])

    # Call the function
    code_parts.extend([
        "            # Call the actual function",
        "            result = func(*args, **kwargs)",
        "",
    ])

    # Add output validation if we have invariants
    if invariant_checks:
        code_parts.extend([
            "            # Validate output",
            "            output_violations = _validate_output(result, all_kwargs)",
            "            if output_violations:",
            "                msg = f'Output violations: {output_violations}'",
            "                if strict:",
            "                    raise RuntimeError(msg)",
            "                _monitor_logger.warning(msg)",
            "",
        ])

    code_parts.extend([
        "            return result",
        "        return wrapper  # type: ignore[return-value]",
        "    return decorator",
        "",
    ])

    return "\n".join(code_parts)


def _generate_input_checks(params: list[Parameter]) -> list[str]:
    """Generate input validation checks.

    Args:
        params: List of parameters.

    Returns:
        List of Python code lines for validation.
    """
    checks = []

    for param in params:
        name = param.name
        ptype = param.type

        # Type checks
        python_type = _type_to_python_check(ptype)
        if python_type:
            checks.append(f"if '{name}' in kwargs and not isinstance(kwargs['{name}'], {python_type}):")
            checks.append(f"    violations.append(f'{name} must be {ptype}, got {{type(kwargs[\"{name}\"]).__name__}}')")

        # Constraint checks
        if param.constraints:
            constraint_check = _constraint_to_check(name, param.constraints)
            if constraint_check:
                checks.append(f"if '{name}' in kwargs:")
                checks.append(f"    {constraint_check}")

    return checks


def _generate_invariant_checks(invariants: list[Invariant]) -> list[str]:
    """Generate invariant validation checks.

    Args:
        invariants: List of invariants.

    Returns:
        List of Python code lines for validation.
    """
    checks = []

    for inv in invariants:
        if inv.check:
            # The check expression uses 'output' and 'input' variables
            checks.append("try:")
            checks.append(f"    if not ({inv.check}):")
            checks.append(f"        violations.append('{inv.description}')")
            checks.append("except Exception as e:")
            checks.append(f"    violations.append(f'{inv.description}: {{e}}')")

    return checks


def _type_to_python_check(type_str: str) -> str | None:
    """Convert a type string to a Python isinstance check type.

    Args:
        type_str: The type annotation string.

    Returns:
        Python type for isinstance check, or None if not checkable.
    """
    # Handle basic types
    basic_types = {
        "str": "str",
        "int": "int",
        "float": "(int, float)",
        "bool": "bool",
        "list": "list",
        "dict": "dict",
        "tuple": "tuple",
        "set": "set",
    }

    # Check for basic type
    base_type = type_str.split("[")[0].strip()
    return basic_types.get(base_type)


def _constraint_to_check(param_name: str, constraint: str) -> str | None:
    """Convert a constraint description to a Python check.

    Args:
        param_name: The parameter name.
        constraint: The constraint description.

    Returns:
        Python code for the check, or None if not convertible.
    """
    constraint_lower = constraint.lower()

    if "non-empty" in constraint_lower:
        return f"if not kwargs['{param_name}']: violations.append('{param_name} must be non-empty')"
    if "> 0" in constraint:
        return f"if kwargs['{param_name}'] <= 0: violations.append('{param_name} must be > 0')"
    if ">= 0" in constraint:
        return f"if kwargs['{param_name}'] < 0: violations.append('{param_name} must be >= 0')"
    if "positive" in constraint_lower:
        return f"if kwargs['{param_name}'] <= 0: violations.append('{param_name} must be positive')"

    return None


def inject_monitor(code: str, monitor_code: str, function_name: str) -> str:
    """Inject runtime monitor into generated code.

    Args:
        code: The generated function code.
        monitor_code: The monitor decorator code.
        function_name: The function name to wrap.

    Returns:
        Code with monitor decorator applied.
    """
    # Find the function definition
    func_def = f"def {function_name}("
    if func_def not in code:
        logger.warning(
            "Could not find function definition to inject monitor",
            function=function_name,
        )
        return code

    # Insert monitor code at the beginning
    # Then apply decorator to function
    decorated_def = f"@monitor_{function_name}(strict=True)\ndef {function_name}("

    result = monitor_code + "\n\n" + code.replace(func_def, decorated_def)
    return result
