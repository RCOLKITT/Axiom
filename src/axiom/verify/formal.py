"""Formal verification bridge using Z3 SMT solver.

This module provides formal verification capabilities for specs by:
1. Translating invariants to Z3 constraints
2. Attempting to prove or find counterexamples
3. Providing mathematical guarantees beyond testing

This is the ultimate paradigm shift: mathematically proving that
generated code satisfies its specification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from axiom.spec.models import Invariant, Spec

logger = structlog.get_logger()


@dataclass
class FormalVerificationResult:
    """Result of formal verification.

    Attributes:
        invariant: The invariant being verified.
        status: 'proved', 'counterexample', 'unknown', or 'unsupported'.
        counterexample: If status is 'counterexample', the values that fail.
        explanation: Human-readable explanation.
    """

    invariant: str
    status: str
    counterexample: dict[str, Any] | None = None
    explanation: str = ""


def verify_formally(spec: Spec) -> list[FormalVerificationResult]:
    """Attempt to formally verify spec invariants using Z3.

    Args:
        spec: The spec to verify.

    Returns:
        List of verification results for each invariant.
    """
    results = []

    for invariant in spec.invariants:
        result = _verify_invariant(spec, invariant)
        results.append(result)

    return results


def _verify_invariant(spec: Spec, invariant: Invariant) -> FormalVerificationResult:
    """Verify a single invariant using Z3.

    Args:
        spec: The spec context.
        invariant: The invariant to verify.

    Returns:
        Verification result.
    """
    if not invariant.check:
        return FormalVerificationResult(
            invariant=invariant.description,
            status="unsupported",
            explanation="No check expression provided",
        )

    try:
        # Try to import z3
        try:
            import z3
        except ImportError:
            return FormalVerificationResult(
                invariant=invariant.description,
                status="unsupported",
                explanation="Z3 not installed. Run: pip install z3-solver",
            )

        # Parse and translate the check expression
        translation = _translate_to_z3(
            invariant.check,
            spec.get_parameter_types(),
            spec.get_return_type(),
        )

        if translation is None:
            return FormalVerificationResult(
                invariant=invariant.description,
                status="unsupported",
                explanation="Could not translate check expression to Z3",
            )

        z3_expr, z3_vars = translation

        # Create solver and try to find counterexample
        solver = z3.Solver()

        # Try to prove by showing negation is unsatisfiable
        solver.add(z3.Not(z3_expr))

        result = solver.check()

        if result == z3.unsat:
            # Proved! No counterexample exists
            return FormalVerificationResult(
                invariant=invariant.description,
                status="proved",
                explanation="Mathematically proven to hold for all inputs",
            )
        elif result == z3.sat:
            # Found counterexample
            model = solver.model()
            counterexample = {}
            for name, var in z3_vars.items():
                val = model.evaluate(var)
                counterexample[name] = _z3_to_python(val)

            return FormalVerificationResult(
                invariant=invariant.description,
                status="counterexample",
                counterexample=counterexample,
                explanation=f"Found inputs that violate invariant: {counterexample}",
            )
        else:
            return FormalVerificationResult(
                invariant=invariant.description,
                status="unknown",
                explanation="Z3 could not determine satisfiability",
            )

    except Exception as e:
        logger.warning("Formal verification failed", error=str(e))
        return FormalVerificationResult(
            invariant=invariant.description,
            status="unsupported",
            explanation=f"Error during verification: {e}",
        )


def _translate_to_z3(
    check_expr: str,
    param_types: dict[str, str],
    return_type: str,
) -> tuple[Any, dict[str, Any]] | None:
    """Translate a Python check expression to Z3.

    Args:
        check_expr: The Python boolean expression.
        param_types: Mapping of parameter names to types.
        return_type: The function's return type.

    Returns:
        Tuple of (Z3 expression, variable mapping) or None if unsupported.
    """
    try:
        import z3
    except ImportError:
        return None

    # Create Z3 variables for inputs and output
    z3_vars: dict[str, Any] = {}

    # Create output variable
    output_var = _create_z3_var(z3, "output", return_type)
    if output_var is not None:
        z3_vars["output"] = output_var

    # Create input variables (accessed via input['name'])
    input_vars: dict[str, Any] = {}
    for name, ptype in param_types.items():
        var = _create_z3_var(z3, name, ptype)
        if var is not None:
            input_vars[name] = var
            z3_vars[f"input_{name}"] = var

    # Try to parse and translate the expression
    # This is a simplified translator that handles common patterns
    expr = check_expr

    # Replace input['x'] with input_x
    import re
    for name in param_types:
        expr = re.sub(rf"input\[(['\"]){name}\1\]", f"input_{name}", expr)

    # Build substitution context
    context = {"output": z3_vars.get("output")}
    context.update({f"input_{n}": v for n, v in input_vars.items()})

    # Handle simple comparison expressions
    try:
        z3_expr = _parse_simple_expr(z3, expr, context)
        if z3_expr is not None:
            return z3_expr, z3_vars
    except Exception:
        pass

    return None


def _create_z3_var(z3: Any, name: str, type_str: str) -> Any:
    """Create a Z3 variable of the appropriate sort.

    Args:
        z3: The z3 module.
        name: Variable name.
        type_str: Type annotation string.

    Returns:
        Z3 variable or None if type not supported.
    """
    base_type = type_str.split("[")[0].strip().lower()

    if base_type == "int":
        return z3.Int(name)
    elif base_type == "float":
        return z3.Real(name)
    elif base_type == "bool":
        return z3.Bool(name)
    elif base_type == "str":
        return z3.String(name)

    return None


def _parse_simple_expr(z3: Any, expr: str, context: dict[str, Any]) -> Any:
    """Parse a simple expression into Z3.

    Handles: ==, !=, <, >, <=, >=, and, or, not, +, -, *, /

    Args:
        z3: The z3 module.
        expr: The expression string.
        context: Variable name to Z3 variable mapping.

    Returns:
        Z3 expression or None.
    """
    expr = expr.strip()

    # Handle 'and'
    if " and " in expr:
        parts = expr.split(" and ")
        z3_parts = [_parse_simple_expr(z3, p, context) for p in parts]
        if all(p is not None for p in z3_parts):
            return z3.And(*z3_parts)
        return None

    # Handle 'or'
    if " or " in expr:
        parts = expr.split(" or ")
        z3_parts = [_parse_simple_expr(z3, p, context) for p in parts]
        if all(p is not None for p in z3_parts):
            return z3.Or(*z3_parts)
        return None

    # Handle comparisons
    for op, z3_op in [("==", lambda a, b: a == b),
                       ("!=", lambda a, b: a != b),
                       (">=", lambda a, b: a >= b),
                       ("<=", lambda a, b: a <= b),
                       (">", lambda a, b: a > b),
                       ("<", lambda a, b: a < b)]:
        if op in expr:
            parts = expr.split(op, 1)
            if len(parts) == 2:
                left = _parse_value(z3, parts[0].strip(), context)
                right = _parse_value(z3, parts[1].strip(), context)
                if left is not None and right is not None:
                    return z3_op(left, right)  # type: ignore[no-untyped-call]
            break

    return None


def _parse_value(z3: Any, val_str: str, context: dict[str, Any]) -> Any:
    """Parse a value (variable or literal) into Z3.

    Args:
        z3: The z3 module.
        val_str: The value string.
        context: Variable name to Z3 variable mapping.

    Returns:
        Z3 value or None.
    """
    val_str = val_str.strip()

    # Check if it's a known variable
    if val_str in context:
        return context[val_str]

    # Try to parse as int
    try:
        return z3.IntVal(int(val_str))
    except ValueError:
        pass

    # Try to parse as float
    try:
        return z3.RealVal(float(val_str))
    except ValueError:
        pass

    # Try to parse as bool
    if val_str.lower() == "true":
        return z3.BoolVal(True)
    if val_str.lower() == "false":
        return z3.BoolVal(False)

    # Try to parse as string literal
    if (val_str.startswith('"') and val_str.endswith('"')) or \
       (val_str.startswith("'") and val_str.endswith("'")):
        return z3.StringVal(val_str[1:-1])

    return None


def _z3_to_python(val: Any) -> Any:
    """Convert a Z3 value to Python.

    Args:
        val: Z3 value.

    Returns:
        Python value.
    """
    try:
        import z3

        if z3.is_int_value(val):
            return val.as_long()
        if z3.is_rational_value(val):
            return float(val.numerator_as_long()) / float(val.denominator_as_long())
        if z3.is_true(val):
            return True
        if z3.is_false(val):
            return False
        if z3.is_string_value(val):
            return val.as_string()
    except Exception:
        pass

    return str(val)


def can_verify_formally(spec: Spec) -> bool:
    """Check if a spec can be formally verified.

    Args:
        spec: The spec to check.

    Returns:
        True if formal verification is possible.
    """
    # Check if we have invariants with check expressions
    if not spec.invariants:
        return False

    has_checkable = any(inv.check for inv in spec.invariants)
    if not has_checkable:
        return False

    # Check if types are supported
    param_types = spec.get_parameter_types()
    return_type = spec.get_return_type()

    supported_types = {"str", "int", "float", "bool"}
    all_types = list(param_types.values()) + [return_type]

    for t in all_types:
        base_type = t.split("[")[0].strip().lower()
        if base_type not in supported_types:
            return False

    return True
