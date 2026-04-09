"""TypeScript example verification via Node.js.

This module executes TypeScript code using Node.js with tsx (TypeScript Execute)
to verify examples match expected outputs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from axiom.verify.models import CheckStatus, ExampleResult

if TYPE_CHECKING:
    from axiom.spec.models import Example, Spec

logger = structlog.get_logger()

# Timeout for TypeScript execution (seconds)
TS_EXECUTION_TIMEOUT = 30


@dataclass
class TypeScriptEnvironment:
    """Information about the TypeScript execution environment."""

    available: bool
    tsx_path: str | None
    node_path: str | None
    version: str | None
    error: str | None


def check_typescript_environment() -> TypeScriptEnvironment:
    """Check if TypeScript execution is available.

    Returns:
        TypeScriptEnvironment with availability info.
    """
    # Check for Node.js
    node_path = shutil.which("node")
    if not node_path:
        return TypeScriptEnvironment(
            available=False,
            tsx_path=None,
            node_path=None,
            version=None,
            error="Node.js not found. Install from https://nodejs.org/",
        )

    # Check for npx (comes with Node.js)
    npx_path = shutil.which("npx")
    if not npx_path:
        return TypeScriptEnvironment(
            available=False,
            tsx_path=None,
            node_path=node_path,
            version=None,
            error="npx not found. Reinstall Node.js.",
        )

    # Check for tsx
    try:
        result = subprocess.run(
            ["npx", "tsx", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            return TypeScriptEnvironment(
                available=True,
                tsx_path="npx tsx",
                node_path=node_path,
                version=version,
                error=None,
            )
    except subprocess.TimeoutExpired:
        pass
    except FileNotFoundError:
        pass

    return TypeScriptEnvironment(
        available=False,
        tsx_path=None,
        node_path=node_path,
        version=None,
        error="tsx not found. Install with: npm install -g tsx",
    )


def run_typescript_examples(code: str, spec: Spec) -> list[ExampleResult]:
    """Execute TypeScript examples and verify results.

    Args:
        code: The generated TypeScript code.
        spec: The spec with examples to verify.

    Returns:
        List of example results.
    """
    # Check environment
    env = check_typescript_environment()
    if not env.available:
        return [
            ExampleResult(
                name=ex.name,
                status=CheckStatus.SKIPPED,
                error_message=env.error,
            )
            for ex in spec.examples
        ]

    results = []
    func_name = spec.function_name
    is_async = _detect_async_function(code, func_name)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Write the TypeScript code
        code_path = tmppath / "function.ts"
        code_path.write_text(code, encoding="utf-8")

        for example in spec.examples:
            result = _run_single_example(
                tmppath,
                code_path,
                func_name,
                example,
                is_async,
            )
            results.append(result)

    return results


def _detect_async_function(code: str, func_name: str) -> bool:
    """Detect if the function is async.

    Args:
        code: The TypeScript code.
        func_name: The function name.

    Returns:
        True if the function is async.
    """
    # Simple detection: look for "async function name" or "async name ="
    import re

    patterns = [
        rf"async\s+function\s+{func_name}\s*\(",
        rf"export\s+async\s+function\s+{func_name}\s*\(",
        rf"const\s+{func_name}\s*=\s*async\s*\(",
        rf"let\s+{func_name}\s*=\s*async\s*\(",
    ]
    return any(re.search(pattern, code) for pattern in patterns)


def _run_single_example(
    tmpdir: Path,
    code_path: Path,
    func_name: str,
    example: Example,
    is_async: bool,
) -> ExampleResult:
    """Run a single example against the TypeScript code.

    Args:
        tmpdir: Temporary directory for test files.
        code_path: Path to the TypeScript code.
        func_name: The function name.
        example: The example to run.
        is_async: Whether the function is async.

    Returns:
        ExampleResult with pass/fail status.
    """
    import time

    start_time = time.time()

    # Generate test harness
    harness_code = _generate_test_harness(func_name, example, is_async)
    harness_path = tmpdir / f"test_{example.name}.ts"
    harness_path.write_text(harness_code, encoding="utf-8")

    # Execute the test
    try:
        result = subprocess.run(
            ["npx", "tsx", str(harness_path)],
            capture_output=True,
            text=True,
            timeout=TS_EXECUTION_TIMEOUT,
            cwd=tmpdir,
        )

        duration = time.time() - start_time

        if result.returncode != 0:
            # Check if this is an expected exception
            if example.expected_output and isinstance(example.expected_output, dict):
                raises = example.expected_output.get("raises")
                if raises and raises in result.stderr:
                    return ExampleResult(
                        name=example.name,
                        status=CheckStatus.PASSED,
                        duration_ms=int(duration * 1000),
                    )

            return ExampleResult(
                name=example.name,
                status=CheckStatus.ERROR,
                error_message=result.stderr or result.stdout,
                duration_ms=int(duration * 1000),
            )

        # Parse the output
        try:
            output = json.loads(result.stdout.strip())
        except json.JSONDecodeError as e:
            return ExampleResult(
                name=example.name,
                status=CheckStatus.ERROR,
                error_message=f"Could not parse output: {e}\nOutput: {result.stdout}",
                duration_ms=int(duration * 1000),
            )

        # Check the result
        if output.get("success"):
            actual = output.get("result")
            expected = example.expected_output

            # Handle expected exceptions
            if isinstance(expected, dict) and "raises" in expected:
                return ExampleResult(
                    name=example.name,
                    status=CheckStatus.FAILED,
                    expected=f"Exception: {expected['raises']}",
                    actual=str(actual),
                    duration_ms=int(duration * 1000),
                )

            # Compare values
            if _values_match(expected, actual):
                return ExampleResult(
                    name=example.name,
                    status=CheckStatus.PASSED,
                    duration_ms=int(duration * 1000),
                )
            else:
                return ExampleResult(
                    name=example.name,
                    status=CheckStatus.FAILED,
                    expected=str(expected),
                    actual=str(actual),
                    duration_ms=int(duration * 1000),
                )
        else:
            # Function threw an exception
            error_type = output.get("type", "Error")
            error_msg = output.get("error", "Unknown error")

            # Check if exception was expected
            if isinstance(example.expected_output, dict):
                raises = example.expected_output.get("raises")
                if raises and (raises == error_type or raises in error_type):
                    return ExampleResult(
                        name=example.name,
                        status=CheckStatus.PASSED,
                        duration_ms=int(duration * 1000),
                    )

            return ExampleResult(
                name=example.name,
                status=CheckStatus.FAILED,
                expected=str(example.expected_output),
                actual=f"{error_type}: {error_msg}",
                duration_ms=int(duration * 1000),
            )

    except subprocess.TimeoutExpired:
        return ExampleResult(
            name=example.name,
            status=CheckStatus.ERROR,
            error_message=f"Execution timed out after {TS_EXECUTION_TIMEOUT}s",
            duration_ms=TS_EXECUTION_TIMEOUT * 1000,
        )
    except Exception as e:
        return ExampleResult(
            name=example.name,
            status=CheckStatus.ERROR,
            error_message=str(e),
            duration_ms=int((time.time() - start_time) * 1000),
        )


def _generate_test_harness(
    func_name: str,
    example: Example,
    is_async: bool,
) -> str:
    """Generate TypeScript test harness code.

    Args:
        func_name: The function name to test.
        example: The example with inputs.
        is_async: Whether the function is async.

    Returns:
        TypeScript test harness code.
    """
    # Serialize inputs to JSON
    inputs_json = json.dumps(example.input)

    # Build argument list from input dict
    # We pass inputs as positional arguments in the order they appear
    call_args = ", ".join(f"inputs['{k}']" for k in example.input)

    if is_async:
        harness = f'''
import {{ {func_name} }} from './function';

async function runTest() {{
    const inputs = {inputs_json};
    try {{
        const result = await {func_name}({call_args});
        console.log(JSON.stringify({{ success: true, result }}));
    }} catch (e: any) {{
        console.log(JSON.stringify({{
            success: false,
            type: e.constructor?.name || 'Error',
            error: e.message || String(e)
        }}));
    }}
}}

runTest().catch(e => {{
    console.log(JSON.stringify({{
        success: false,
        type: 'UnhandledError',
        error: e.message || String(e)
    }}));
}});
'''
    else:
        harness = f'''
import {{ {func_name} }} from './function';

const inputs = {inputs_json};
try {{
    const result = {func_name}({call_args});
    console.log(JSON.stringify({{ success: true, result }}));
}} catch (e: any) {{
    console.log(JSON.stringify({{
        success: false,
        type: e.constructor?.name || 'Error',
        error: e.message || String(e)
    }}));
}}
'''

    return harness


def _values_match(expected: Any, actual: Any) -> bool:
    """Check if two values match, with some tolerance.

    Args:
        expected: The expected value.
        actual: The actual value from TypeScript.

    Returns:
        True if values match.
    """
    # Exact match
    if expected == actual:
        return True

    # None/null matching
    if expected is None and actual is None:
        return True

    # Numeric tolerance (matches Python's math.isclose defaults)
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        # Use both relative (1e-9) and absolute (1e-9) tolerance
        return abs(expected - actual) <= max(1e-9 * max(abs(expected), abs(actual)), 1e-9)

    # String comparison
    if isinstance(expected, str) and isinstance(actual, str):
        return expected == actual

    # List comparison
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return False
        return all(_values_match(e, a) for e, a in zip(expected, actual))

    # Dict comparison
    if isinstance(expected, dict) and isinstance(actual, dict):
        if set(expected.keys()) != set(actual.keys()):
            return False
        return all(_values_match(expected[k], actual[k]) for k in expected)

    # Boolean comparison
    if isinstance(expected, bool) and isinstance(actual, bool):
        return expected == actual

    return False
