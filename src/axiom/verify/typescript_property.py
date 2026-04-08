"""TypeScript invariant verification using Python-generated test data.

This module runs property-based testing for TypeScript code by:
1. Generating test data using Python's Hypothesis
2. Executing TypeScript code with the generated data
3. Evaluating invariant checks in Python against the results
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from axiom.verify.models import CheckStatus, InvariantResult
from axiom.verify.strategies import create_strategy_for_type
from axiom.verify.typescript_runner import (
    TS_EXECUTION_TIMEOUT,
    _detect_async_function,
    check_typescript_environment,
)

if TYPE_CHECKING:
    from axiom.spec.models import Invariant, Spec

logger = structlog.get_logger()

# Number of test cases to generate
DEFAULT_TEST_COUNT = 100


def run_typescript_invariants(
    code: str,
    spec: Spec,
    test_count: int = DEFAULT_TEST_COUNT,
) -> list[InvariantResult]:
    """Run invariant checks on TypeScript code.

    Uses Python's Hypothesis to generate test data, executes the TypeScript
    function with that data, then evaluates invariant checks in Python.

    Args:
        code: The generated TypeScript code.
        spec: The spec with invariants to verify.
        test_count: Number of test cases to generate.

    Returns:
        List of invariant results.
    """
    if not spec.invariants:
        return []

    # Check environment
    env = check_typescript_environment()
    if not env.available:
        return [
            InvariantResult(
                description=inv.description,
                status=CheckStatus.SKIPPED,
                error_message=env.error,
            )
            for inv in spec.invariants
        ]

    results = []
    func_name = spec.function_name
    is_async = _detect_async_function(code, func_name)
    param_types = spec.get_parameter_types()

    # Generate test data using Hypothesis
    test_data = _generate_test_data(param_types, test_count)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Write the TypeScript code
        code_path = tmppath / "function.ts"
        code_path.write_text(code, encoding="utf-8")

        # Execute batch and collect results
        ts_results = _execute_batch(
            tmppath,
            code_path,
            func_name,
            test_data,
            is_async,
        )

        # Check each invariant
        for invariant in spec.invariants:
            result = _check_invariant(invariant, test_data, ts_results)
            results.append(result)

    return results


def _generate_test_data(
    param_types: dict[str, str],
    count: int,
) -> list[dict[str, Any]]:
    """Generate test data using Hypothesis strategies.

    Args:
        param_types: Mapping of parameter names to types.
        count: Number of test cases to generate.

    Returns:
        List of input dictionaries.
    """
    try:
        from hypothesis import given, settings
        from hypothesis import strategies as st
    except ImportError:
        logger.warning("Hypothesis not available, using simple test data")
        return _generate_simple_test_data(param_types, count)

    # Build combined strategy for all parameters
    param_strategies = {}
    for name, type_str in param_types.items():
        strategy = create_strategy_for_type(type_str)
        if strategy is None:
            # Fallback to text for unknown types
            strategy = st.text(max_size=100)
        param_strategies[name] = strategy

    # Generate data
    test_data: list[dict[str, Any]] = []

    @given(st.fixed_dictionaries(param_strategies))
    @settings(max_examples=count, database=None)
    def collect_examples(data: dict[str, Any]) -> None:
        test_data.append(data)

    try:
        collect_examples()
    except Exception as e:
        logger.warning("Hypothesis generation failed, using simple data", error=str(e))
        return _generate_simple_test_data(param_types, count)

    return test_data


def _generate_simple_test_data(
    param_types: dict[str, str],
    count: int,
) -> list[dict[str, Any]]:
    """Generate simple test data without Hypothesis.

    Args:
        param_types: Mapping of parameter names to types.
        count: Number of test cases to generate.

    Returns:
        List of input dictionaries.
    """
    import random
    import string

    test_data = []

    for _ in range(count):
        data: dict[str, Any] = {}
        for name, type_str in param_types.items():
            base_type = type_str.split("[")[0].strip().lower()

            if base_type == "int":
                data[name] = random.randint(-1000, 1000)
            elif base_type == "float":
                data[name] = random.uniform(-1000.0, 1000.0)
            elif base_type == "str":
                length = random.randint(0, 50)
                data[name] = "".join(random.choices(string.ascii_letters, k=length))
            elif base_type == "bool":
                data[name] = random.choice([True, False])
            elif base_type == "list":
                data[name] = [random.randint(0, 100) for _ in range(random.randint(0, 5))]
            elif base_type == "dict":
                data[name] = {"key": "value"}
            else:
                data[name] = ""

        test_data.append(data)

    return test_data


def _execute_batch(
    tmpdir: Path,
    code_path: Path,
    func_name: str,
    test_data: list[dict[str, Any]],
    is_async: bool,
) -> list[tuple[dict[str, Any], Any, bool]]:
    """Execute TypeScript function with batch of inputs.

    Args:
        tmpdir: Temporary directory.
        code_path: Path to TypeScript code.
        func_name: Function name.
        test_data: List of input dictionaries.
        is_async: Whether function is async.

    Returns:
        List of (input, output, success) tuples.
    """
    results: list[tuple[dict[str, Any], Any, bool]] = []

    # Generate batch test harness
    harness_code = _generate_batch_harness(func_name, test_data, is_async)
    harness_path = tmpdir / "batch_test.ts"
    harness_path.write_text(harness_code, encoding="utf-8")

    try:
        result = subprocess.run(
            ["npx", "tsx", str(harness_path)],
            capture_output=True,
            text=True,
            timeout=TS_EXECUTION_TIMEOUT * 2,  # More time for batch
            cwd=tmpdir,
        )

        if result.returncode != 0:
            logger.warning("Batch execution failed", stderr=result.stderr[:500])
            # Return all as failures
            return [(data, None, False) for data in test_data]

        # Parse results (one JSON per line)
        for i, line in enumerate(result.stdout.strip().split("\n")):
            if i >= len(test_data):
                break
            try:
                output = json.loads(line)
                if output.get("success"):
                    results.append((test_data[i], output.get("result"), True))
                else:
                    results.append((test_data[i], output.get("error"), False))
            except json.JSONDecodeError:
                results.append((test_data[i], None, False))

        # Fill in missing results
        while len(results) < len(test_data):
            results.append((test_data[len(results)], None, False))

    except subprocess.TimeoutExpired:
        logger.warning("Batch execution timed out")
        return [(data, None, False) for data in test_data]
    except Exception as e:
        logger.warning("Batch execution error", error=str(e))
        return [(data, None, False) for data in test_data]

    return results


def _generate_batch_harness(
    func_name: str,
    test_data: list[dict[str, Any]],
    is_async: bool,
) -> str:
    """Generate TypeScript batch test harness.

    Args:
        func_name: Function name.
        test_data: List of input dictionaries.
        is_async: Whether function is async.

    Returns:
        TypeScript code for batch testing.
    """
    test_data_json = json.dumps(test_data)

    # Get parameter names from first test case
    if test_data:
        param_names = list(test_data[0].keys())
        call_args = ", ".join(f"inputs['{k}']" for k in param_names)
    else:
        call_args = ""

    if is_async:
        harness = f'''
import {{ {func_name} }} from './function';

const testData: any[] = {test_data_json};

async function runBatch() {{
    for (const inputs of testData) {{
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
}}

runBatch().catch(() => {{}});
'''
    else:
        harness = f'''
import {{ {func_name} }} from './function';

const testData: any[] = {test_data_json};

for (const inputs of testData) {{
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
}}
'''

    return harness


def _check_invariant(
    invariant: Invariant,
    test_data: list[dict[str, Any]],
    results: list[tuple[dict[str, Any], Any, bool]],
) -> InvariantResult:
    """Check an invariant against test results.

    Args:
        invariant: The invariant to check.
        test_data: Original test data.
        results: Execution results (input, output, success).

    Returns:
        InvariantResult.
    """
    if not invariant.check:
        return InvariantResult(
            description=invariant.description,
            status=CheckStatus.SKIPPED,
            error_message="No check expression provided",
        )

    # Count successful executions
    successful_results = [(inp, out) for inp, out, success in results if success]

    if not successful_results:
        return InvariantResult(
            description=invariant.description,
            status=CheckStatus.SKIPPED,
            error_message="No successful executions to check",
        )

    # Check invariant on each result
    for input_data, output in successful_results:
        try:
            check_passed = _eval_check(invariant.check, input_data, output)
            if not check_passed:
                return InvariantResult(
                    description=invariant.description,
                    status=CheckStatus.FAILED,
                    iterations=len(successful_results),
                    counterexample={"input": input_data, "output": output},
                    error_message=f"Invariant violated: {invariant.check}",
                )
        except Exception as e:
            return InvariantResult(
                description=invariant.description,
                status=CheckStatus.ERROR,
                error_message=f"Error evaluating check: {e}",
            )

    return InvariantResult(
        description=invariant.description,
        status=CheckStatus.PASSED,
        iterations=len(successful_results),
        error_message=f"Passed {len(successful_results)} test cases",
    )


def _eval_check(check_expr: str, input_data: dict[str, Any], output: Any) -> bool:
    """Evaluate a check expression.

    Args:
        check_expr: Python expression to evaluate.
        input_data: Input parameters.
        output: Function output.

    Returns:
        True if check passes.
    """
    # Safe evaluation context
    safe_builtins = {
        "len": len,
        "abs": abs,
        "min": min,
        "max": max,
        "sum": sum,
        "all": all,
        "any": any,
        "isinstance": isinstance,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "True": True,
        "False": False,
        "None": None,
    }

    context = {
        "input": input_data,
        "output": output,
        **safe_builtins,
    }

    try:
        result = eval(check_expr, {"__builtins__": {}}, context)  # noqa: S307
        return bool(result)
    except Exception:
        return False
