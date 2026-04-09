"""Run I/O examples against generated code."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import structlog

from axiom.spec.models import Example, Spec
from axiom.verify.models import CheckStatus, ExampleResult

logger = structlog.get_logger()


def run_examples(
    spec: Spec,
    code: str,
    generated_dir: Path | None = None,
) -> list[ExampleResult]:
    """Run all examples from a spec against generated code.

    Args:
        spec: The parsed spec with examples.
        code: The generated Python code.
        generated_dir: Optional path to generated code directory for dependency imports.

    Returns:
        List of ExampleResult for each example.
    """
    if not spec.examples:
        logger.debug("No examples to run", spec=spec.spec_name)
        return []

    # Load the function from code
    try:
        func = _load_function(code, spec.function_name, generated_dir)
    except Exception as e:
        # Return error results for all examples
        return [
            ExampleResult(
                name=ex.name,
                status=CheckStatus.ERROR,
                error_message=f"Failed to load function: {e}",
            )
            for ex in spec.examples
        ]

    # Run each example
    results = []
    for example in spec.examples:
        result = _run_single_example(func, example)
        results.append(result)
        logger.debug(
            "Example result",
            name=example.name,
            status=result.status.value,
        )

    return results


def _load_function(
    code: str,
    function_name: str,
    generated_dir: Path | None = None,
) -> Callable[..., Any]:
    """Load a function from code string.

    Args:
        code: Python code containing the function.
        function_name: Name of the function to load.
        generated_dir: Optional path to generated code directory for dependency imports.

    Returns:
        The loaded function.

    Raises:
        ValueError: If the function cannot be loaded.
    """
    # Write code to a temporary file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(code)
        temp_path = Path(f.name)

    # Add generated directory to path if provided (for dependency imports)
    added_to_path = False
    if generated_dir and generated_dir.exists():
        gen_dir_str = str(generated_dir.absolute())
        if gen_dir_str not in sys.path:
            sys.path.insert(0, gen_dir_str)
            added_to_path = True

    try:
        # Create a unique module name
        module_name = f"_axiom_generated_{temp_path.stem}"

        # Load the module
        spec = importlib.util.spec_from_file_location(module_name, temp_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Could not load module from {temp_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Get the function
        if not hasattr(module, function_name):
            available = [n for n in dir(module) if not n.startswith("_")]
            raise ValueError(
                f"Function '{function_name}' not found in module. Available: {available}"
            )

        func: Callable[..., Any] = getattr(module, function_name)
        return func

    finally:
        # Clean up
        temp_path.unlink(missing_ok=True)
        if module_name in sys.modules:
            del sys.modules[module_name]
        # Remove generated dir from path if we added it
        if added_to_path and generated_dir:
            gen_dir_str = str(generated_dir.absolute())
            if gen_dir_str in sys.path:
                sys.path.remove(gen_dir_str)


def _run_single_example(
    func: Callable[..., Any],
    example: Example,
) -> ExampleResult:
    """Run a single example.

    Args:
        func: The function to test.
        example: The example to run.

    Returns:
        ExampleResult with pass/fail status.
    """
    start_time = time.time()

    try:
        if example.expected_output.is_exception():
            # Expecting an exception
            return _run_exception_example(func, example, start_time)
        else:
            # Expecting a return value
            return _run_value_example(func, example, start_time)

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return ExampleResult(
            name=example.name,
            status=CheckStatus.ERROR,
            error_message=f"Unexpected error: {e}\n{traceback.format_exc()}",
            duration_ms=duration_ms,
        )


def _run_value_example(
    func: Callable[..., Any],
    example: Example,
    start_time: float,
) -> ExampleResult:
    """Run an example expecting a return value."""
    try:
        actual = func(**example.input)
        duration_ms = int((time.time() - start_time) * 1000)

        expected = example.expected_output.value

        if _values_equal(actual, expected):
            return ExampleResult(
                name=example.name,
                status=CheckStatus.PASSED,
                expected=expected,
                actual=actual,
                duration_ms=duration_ms,
            )
        else:
            return ExampleResult(
                name=example.name,
                status=CheckStatus.FAILED,
                expected=expected,
                actual=actual,
                error_message=f"Expected {_format_value(expected)}, got {_format_value(actual)}",
                duration_ms=duration_ms,
            )

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return ExampleResult(
            name=example.name,
            status=CheckStatus.FAILED,
            expected=example.expected_output.value,
            error_message=f"Unexpected exception: {type(e).__name__}: {e}",
            duration_ms=duration_ms,
        )


def _run_exception_example(
    func: Callable[..., Any],
    example: Example,
    start_time: float,
) -> ExampleResult:
    """Run an example expecting an exception."""
    expected_exc = example.expected_output.raises
    message_contains = example.expected_output.message_contains

    try:
        actual = func(**example.input)
        duration_ms = int((time.time() - start_time) * 1000)

        # Expected exception but got a value
        return ExampleResult(
            name=example.name,
            status=CheckStatus.FAILED,
            expected=f"raises {expected_exc}",
            actual=actual,
            error_message=f"Expected {expected_exc} to be raised, but got return value: {actual}",
            duration_ms=duration_ms,
        )

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)

        # Check exception type
        actual_exc_name = type(e).__name__
        if actual_exc_name != expected_exc:
            return ExampleResult(
                name=example.name,
                status=CheckStatus.FAILED,
                expected=f"raises {expected_exc}",
                actual=f"raises {actual_exc_name}",
                error_message=f"Expected {expected_exc}, got {actual_exc_name}: {e}",
                duration_ms=duration_ms,
            )

        # Check message if required
        if message_contains and message_contains.lower() not in str(e).lower():
            return ExampleResult(
                name=example.name,
                status=CheckStatus.FAILED,
                expected=f'raises {expected_exc} with message containing "{message_contains}"',
                actual=f'raises {actual_exc_name}: "{e}"',
                error_message=f"Exception message doesn't contain '{message_contains}'",
                duration_ms=duration_ms,
            )

        # Exception matches
        return ExampleResult(
            name=example.name,
            status=CheckStatus.PASSED,
            expected=f"raises {expected_exc}",
            actual=f"raises {actual_exc_name}",
            duration_ms=duration_ms,
        )


def _values_equal(actual: Any, expected: Any) -> bool:
    """Check if two values are equal.

    Handles common edge cases like float comparison.
    For dicts, uses partial matching (expected keys must exist and match in actual,
    but actual may have additional keys).

    Args:
        actual: The actual value.
        expected: The expected value.

    Returns:
        True if values are considered equal.
    """
    # Direct equality
    if actual == expected:
        return True

    # Handle float comparison (consistent with TypeScript runner)
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        # Use both relative (1e-9) and absolute (1e-9) tolerance
        return abs(expected - actual) <= max(1e-9 * max(abs(expected), abs(actual)), 1e-9)

    # Handle list/tuple comparison
    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        if len(actual) != len(expected):
            return False
        return all(_values_equal(a, e) for a, e in zip(actual, expected))

    # Handle dict comparison - partial matching
    # Expected keys must exist and match in actual, but actual may have extra keys
    if isinstance(actual, dict) and isinstance(expected, dict):
        for key in expected:
            if key not in actual:
                return False
            if not _values_equal(actual[key], expected[key]):
                return False
        return True

    return False


def _format_value(value: Any) -> str:
    """Format a value for display."""
    if isinstance(value, str):
        return repr(value)
    return str(value)
