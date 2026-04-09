"""Run property-based invariant checks using Hypothesis."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import structlog

from axiom.spec.models import Invariant, Spec
from axiom.verify.models import CheckStatus, InvariantResult

logger = structlog.get_logger()

# Try to import hypothesis
try:
    from hypothesis import Verbosity, given, settings
    from hypothesis import strategies as st
    from hypothesis.errors import Unsatisfiable

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False


def run_invariants(
    spec: Spec,
    code: str,
    max_examples: int = 100,
) -> list[InvariantResult]:
    """Run all invariants from a spec against generated code.

    Args:
        spec: The parsed spec with invariants.
        code: The generated Python code.
        max_examples: Maximum number of Hypothesis examples per invariant.

    Returns:
        List of InvariantResult for each invariant.
    """
    if not spec.invariants:
        logger.debug("No invariants to run", spec=spec.spec_name)
        return []

    if not HYPOTHESIS_AVAILABLE:
        logger.warning("Hypothesis not available, skipping property-based tests")
        return [
            InvariantResult(
                description=inv.description,
                status=CheckStatus.SKIPPED,
                check=inv.check,
                error_message="Hypothesis not installed",
            )
            for inv in spec.invariants
        ]

    # Load the function
    try:
        func = _load_function(code, spec.function_name)
    except Exception as e:
        return [
            InvariantResult(
                description=inv.description,
                status=CheckStatus.ERROR,
                check=inv.check,
                error_message=f"Failed to load function: {e}",
            )
            for inv in spec.invariants
        ]

    # Build strategies for the function parameters
    try:
        strategies = _build_strategies(spec)
    except Exception as e:
        logger.warning("Failed to build strategies", error=str(e))
        return [
            InvariantResult(
                description=inv.description,
                status=CheckStatus.ERROR,
                check=inv.check,
                error_message=f"Failed to build test strategies: {e}",
            )
            for inv in spec.invariants
        ]

    # Run each invariant
    results = []
    for invariant in spec.invariants:
        if invariant.check:
            result = _run_check_invariant(func, invariant, strategies, max_examples)
        else:
            # Natural language invariant without check - skip for now
            result = InvariantResult(
                description=invariant.description,
                status=CheckStatus.SKIPPED,
                error_message="No check expression provided (NL-only invariants not yet supported)",
            )
        results.append(result)
        logger.debug(
            "Invariant result",
            description=invariant.description[:50],
            status=result.status.value,
        )

    return results


def _load_function(code: str, function_name: str) -> Callable[..., Any]:
    """Load a function from code string."""
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(code)
        temp_path = Path(f.name)

    try:
        module_name = f"_axiom_invariant_{temp_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, temp_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Could not load module from {temp_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        if not hasattr(module, function_name):
            raise ValueError(f"Function '{function_name}' not found")

        func: Callable[..., Any] = getattr(module, function_name)
        return func
    finally:
        temp_path.unlink(missing_ok=True)
        if module_name in sys.modules:
            del sys.modules[module_name]


def _build_strategies(spec: Spec) -> dict[str, Any]:
    """Build Hypothesis strategies from spec parameter types.

    Args:
        spec: The parsed spec.

    Returns:
        Dict mapping parameter names to Hypothesis strategies.
    """
    if not HYPOTHESIS_AVAILABLE:
        return {}

    strategies = {}
    # Only FunctionInterface has .parameters; FastAPIInterface uses path/query params
    interface = spec.interface
    if hasattr(interface, "parameters"):
        for param in interface.parameters:
            strategy = _type_to_strategy(param.type, param.constraints)
            strategies[param.name] = strategy

    return strategies


def _type_to_strategy(type_str: str, constraints: str | None) -> Any:
    """Convert a Python type string to a Hypothesis strategy.

    Args:
        type_str: Python type annotation string.
        constraints: Optional constraints.

    Returns:
        A Hypothesis strategy.
    """
    if not HYPOTHESIS_AVAILABLE:
        raise RuntimeError("Hypothesis not available")

    # Normalize type string
    type_lower = type_str.lower().strip()

    # Handle basic types
    if type_lower == "str":
        return _str_strategy(constraints)
    elif type_lower == "int":
        return _int_strategy(constraints)
    elif type_lower == "float":
        return st.floats(allow_nan=False, allow_infinity=False)
    elif type_lower == "bool":
        return st.booleans()
    elif type_lower.startswith("list["):
        inner = type_str[5:-1]
        return st.lists(_type_to_strategy(inner, None), max_size=10)
    elif type_lower.startswith("dict["):
        # Simple dict strategy
        return st.dictionaries(st.text(max_size=10), st.text(max_size=10), max_size=5)
    elif type_lower == "any":
        return st.one_of(st.text(), st.integers(), st.booleans())

    # Default to text
    logger.debug("Unknown type, using text strategy", type=type_str)
    return st.text(max_size=100)


def _str_strategy(constraints: str | None) -> Any:
    """Build a string strategy based on constraints."""
    if not HYPOTHESIS_AVAILABLE:
        raise RuntimeError("Hypothesis not available")

    if constraints:
        constraints_lower = constraints.lower()
        if "non-empty" in constraints_lower:
            return st.text(min_size=1, max_size=100)
        if "email" in constraints_lower:
            return st.emails()

    # Default: allow any string including empty
    return st.text(max_size=100)


def _int_strategy(constraints: str | None) -> Any:
    """Build an integer strategy based on constraints."""
    if not HYPOTHESIS_AVAILABLE:
        raise RuntimeError("Hypothesis not available")

    min_val = None
    max_val = None

    if constraints:
        constraints_lower = constraints.lower()
        if "positive" in constraints_lower or "> 0" in constraints:
            min_val = 1
        if ">= 0" in constraints:
            min_val = 0

    return st.integers(min_value=min_val, max_value=max_val)


def _run_check_invariant(
    func: Callable[..., Any],
    invariant: Invariant,
    strategies: dict[str, Any],
    max_examples: int,
) -> InvariantResult:
    """Run an invariant with a check expression.

    Args:
        func: The function to test.
        invariant: The invariant to check.
        strategies: Parameter strategies.
        max_examples: Maximum test iterations.

    Returns:
        InvariantResult with pass/fail status.
    """
    if not HYPOTHESIS_AVAILABLE:
        return InvariantResult(
            description=invariant.description,
            status=CheckStatus.SKIPPED,
            check=invariant.check,
            error_message="Hypothesis not available",
        )

    check_expr = invariant.check
    if not check_expr:
        return InvariantResult(
            description=invariant.description,
            status=CheckStatus.SKIPPED,
            error_message="No check expression",
        )

    # Build a composite strategy for all parameters
    @st.composite
    def input_strategy(draw: Any) -> dict[str, Any]:
        return {name: draw(strat) for name, strat in strategies.items()}

    failing_example: dict[str, Any] | None = None
    error_msg: str | None = None
    iterations = 0

    @given(inputs=input_strategy())
    @settings(max_examples=max_examples, verbosity=Verbosity.quiet, deadline=None)
    def check_invariant(inputs: dict[str, Any]) -> None:
        nonlocal iterations, failing_example, error_msg
        iterations += 1

        try:
            output = func(**inputs)
        except Exception:
            # Invariants only apply to successful executions
            return

        # Evaluate the check expression
        # SECURITY: eval() with restricted builtins. Check expressions come from
        # .axiom spec files (developer-written, version-controlled, reviewed).
        # __builtins__ is restricted to safe functions only.
        try:
            safe_builtins = {
                "all": all,
                "any": any,
                "len": len,
                "abs": abs,
                "min": min,
                "max": max,
                "sum": sum,
                "sorted": sorted,
                "list": list,
                "dict": dict,
                "set": set,
                "tuple": tuple,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "isinstance": isinstance,
                "hasattr": hasattr,
                "getattr": getattr,
                "True": True,
                "False": False,
                "None": None,
            }
            context = {"input": inputs, "output": output, "__builtins__": safe_builtins}
            result = eval(check_expr, context)

            if not result:
                failing_example = inputs.copy()
                error_msg = (
                    f"Check '{check_expr}' returned False for input {inputs}, output {output}"
                )
                raise AssertionError(error_msg)
        except AssertionError:
            raise
        except Exception as e:
            failing_example = inputs.copy()
            error_msg = f"Check expression error: {e}"
            raise AssertionError(error_msg) from e

    try:
        check_invariant()
        return InvariantResult(
            description=invariant.description,
            status=CheckStatus.PASSED,
            check=check_expr,
            iterations=iterations,
        )
    except (AssertionError, Unsatisfiable) as e:
        return InvariantResult(
            description=invariant.description,
            status=CheckStatus.FAILED,
            check=check_expr,
            counterexample=failing_example,
            error_message=error_msg or str(e),
            iterations=iterations,
        )
    except Exception as e:
        return InvariantResult(
            description=invariant.description,
            status=CheckStatus.ERROR,
            check=check_expr,
            error_message=f"Unexpected error: {e}",
            iterations=iterations,
        )
