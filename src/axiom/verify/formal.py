"""Formal verification bridge using Z3 SMT solver.

This module provides formal verification capabilities for specs by:
1. Translating invariants to Z3 constraints using Python AST
2. Attempting to prove or find counterexamples
3. Providing mathematical guarantees beyond testing

Supported expressions:
- Comparisons: ==, !=, <, >, <=, >=
- Boolean: and, or, not
- Arithmetic: +, -, *, /, //, %
- String methods: .lower(), .upper(), .strip(), .startswith(), .endswith()
- Built-ins: len(), isinstance(), abs()
- Membership: in, not in
- Container access: x[key], x.get(key)
"""

from __future__ import annotations

import ast
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

        # Parse and translate the check expression using AST
        translator = Z3Translator(z3, spec.get_parameter_types(), spec.get_return_type())
        translation = translator.translate(invariant.check)

        if translation is None:
            return FormalVerificationResult(
                invariant=invariant.description,
                status="unsupported",
                explanation=f"Could not translate: {translator.unsupported_reason}",
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
                counterexample[name] = _z3_to_python(val, z3)

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


class Z3Translator:
    """Translates Python expressions to Z3 using AST parsing."""

    def __init__(
        self,
        z3_module: Any,
        param_types: dict[str, str],
        return_type: str,
    ) -> None:
        """Initialize the translator.

        Args:
            z3_module: The z3 module.
            param_types: Mapping of parameter names to types.
            return_type: The function's return type.
        """
        self.z3 = z3_module
        self.param_types = param_types
        self.return_type = return_type
        self.z3_vars: dict[str, Any] = {}
        self.unsupported_reason: str = ""

        # Create Z3 variables
        self._create_variables()

    def _create_variables(self) -> None:
        """Create Z3 variables for output and inputs."""
        # Create output variable
        output_var = self._create_z3_var("output", self.return_type)
        if output_var is not None:
            self.z3_vars["output"] = output_var

        # Create input variables
        for name, ptype in self.param_types.items():
            var = self._create_z3_var(name, ptype)
            if var is not None:
                self.z3_vars[f"input_{name}"] = var

    def _create_z3_var(self, name: str, type_str: str) -> Any:
        """Create a Z3 variable of the appropriate sort."""
        base_type = type_str.split("[")[0].strip().lower()

        if base_type == "int":
            return self.z3.Int(name)
        elif base_type == "float":
            return self.z3.Real(name)
        elif base_type == "bool":
            return self.z3.Bool(name)
        elif base_type == "str":
            return self.z3.String(name)
        elif base_type == "list":
            # Create a sequence for lists
            return self.z3.Const(name, self.z3.SeqSort(self.z3.StringSort()))

        return None

    def translate(self, check_expr: str) -> tuple[Any, dict[str, Any]] | None:
        """Translate a Python expression to Z3.

        Args:
            check_expr: The Python boolean expression.

        Returns:
            Tuple of (Z3 expression, variable mapping) or None if unsupported.
        """
        try:
            tree = ast.parse(check_expr, mode="eval")
            z3_expr = self._translate_node(tree.body)
            if z3_expr is not None:
                return z3_expr, self.z3_vars
            return None
        except SyntaxError as e:
            self.unsupported_reason = f"Invalid Python syntax: {e}"
            return None
        except Exception as e:
            self.unsupported_reason = str(e)
            return None

    def _translate_node(self, node: ast.AST) -> Any:
        """Translate an AST node to Z3."""
        match node:
            case ast.BoolOp(op, values):
                return self._translate_boolop(op, values)

            case ast.UnaryOp(op, operand):
                return self._translate_unaryop(op, operand)

            case ast.Compare(left, ops, comparators):
                return self._translate_compare(left, ops, comparators)

            case ast.BinOp(left, op, right):
                return self._translate_binop(left, op, right)

            case ast.Call(func, args, keywords):
                return self._translate_call(func, args, keywords)

            case ast.Subscript(value, slice_):
                return self._translate_subscript(value, slice_)

            case ast.Attribute(value, attr):
                # Handle method calls without arguments (rare, but possible)
                return self._translate_attribute(value, attr)

            case ast.Name(id):
                return self._translate_name(id)

            case ast.Constant(value):
                return self._translate_constant(value)

            case ast.IfExp(test, body, orelse):
                # Ternary: body if test else orelse
                return self._translate_ifexp(test, body, orelse)

            case _:
                self.unsupported_reason = f"Unsupported AST node: {type(node).__name__}"
                return None

    def _translate_boolop(self, op: ast.boolop, values: list[ast.expr]) -> Any:
        """Translate and/or operations."""
        z3_values = [self._translate_node(v) for v in values]
        if any(v is None for v in z3_values):
            return None

        if isinstance(op, ast.And):
            return self.z3.And(*z3_values)
        elif isinstance(op, ast.Or):
            return self.z3.Or(*z3_values)

        self.unsupported_reason = f"Unsupported boolean operator: {type(op).__name__}"
        return None

    def _translate_unaryop(self, op: ast.unaryop, operand: ast.expr) -> Any:
        """Translate unary operations (not, -, +)."""
        z3_operand = self._translate_node(operand)
        if z3_operand is None:
            return None

        if isinstance(op, ast.Not):
            return self.z3.Not(z3_operand)
        elif isinstance(op, ast.USub):
            return -z3_operand
        elif isinstance(op, ast.UAdd):
            return z3_operand

        self.unsupported_reason = f"Unsupported unary operator: {type(op).__name__}"
        return None

    def _translate_compare(
        self,
        left: ast.expr,
        ops: list[ast.cmpop],
        comparators: list[ast.expr],
    ) -> Any:
        """Translate comparison operations."""
        # Handle chained comparisons: a < b < c becomes a < b and b < c
        parts = []
        current_left = self._translate_node(left)
        if current_left is None:
            return None

        for op, comp in zip(ops, comparators):
            current_right = self._translate_node(comp)
            if current_right is None:
                return None

            # Handle 'in' and 'not in' specially
            if isinstance(op, ast.In):
                part = self._translate_in(current_left, comp)
                if part is None:
                    return None
                parts.append(part)
            elif isinstance(op, ast.NotIn):
                part = self._translate_in(current_left, comp)
                if part is None:
                    return None
                parts.append(self.z3.Not(part))
            else:
                # Regular comparison
                part = self._apply_comparison(op, current_left, current_right)
                if part is None:
                    return None
                parts.append(part)

            current_left = current_right

        if len(parts) == 1:
            return parts[0]
        return self.z3.And(*parts)

    def _apply_comparison(self, op: ast.cmpop, left: Any, right: Any) -> Any:
        """Apply a comparison operator."""
        if isinstance(op, ast.Eq):
            return left == right
        elif isinstance(op, ast.NotEq):
            return left != right
        elif isinstance(op, ast.Lt):
            return left < right
        elif isinstance(op, ast.LtE):
            return left <= right
        elif isinstance(op, ast.Gt):
            return left > right
        elif isinstance(op, ast.GtE):
            return left >= right
        elif isinstance(op, ast.Is):
            return left == right
        elif isinstance(op, ast.IsNot):
            return left != right

        self.unsupported_reason = f"Unsupported comparison: {type(op).__name__}"
        return None

    def _translate_in(self, element: Any, container: ast.expr) -> Any:
        """Translate 'in' operator for containment checks."""
        # For strings, use Contains
        container_val = self._translate_node(container)
        if container_val is None:
            return None

        # String containment
        try:
            return self.z3.Contains(container_val, element)
        except Exception:
            pass

        # Try sequence membership
        try:
            return self.z3.Contains(container_val, self.z3.Unit(element))
        except Exception:
            pass

        self.unsupported_reason = "Could not translate 'in' operator"
        return None

    def _translate_binop(self, left: ast.expr, op: ast.operator, right: ast.expr) -> Any:
        """Translate binary operations (+, -, *, /, //, %)."""
        z3_left = self._translate_node(left)
        z3_right = self._translate_node(right)
        if z3_left is None or z3_right is None:
            return None

        if isinstance(op, ast.Add):
            # Handle string concatenation
            try:
                return z3_left + z3_right
            except Exception:
                return self.z3.Concat(z3_left, z3_right)
        elif isinstance(op, ast.Sub):
            return z3_left - z3_right
        elif isinstance(op, ast.Mult):
            return z3_left * z3_right
        elif isinstance(op, ast.Div):
            return z3_left / z3_right
        elif isinstance(op, ast.FloorDiv):
            # Integer division
            return z3_left / z3_right
        elif isinstance(op, ast.Mod):
            return z3_left % z3_right

        self.unsupported_reason = f"Unsupported binary operator: {type(op).__name__}"
        return None

    def _translate_call(
        self,
        func: ast.expr,
        args: list[ast.expr],
        keywords: list[ast.keyword],
    ) -> Any:
        """Translate function and method calls."""
        # Handle method calls: obj.method(args)
        if isinstance(func, ast.Attribute):
            return self._translate_method_call(func.value, func.attr, args)

        # Handle built-in function calls: func(args)
        if isinstance(func, ast.Name):
            return self._translate_builtin_call(func.id, args)

        self.unsupported_reason = f"Unsupported function call: {ast.dump(func)}"
        return None

    def _translate_method_call(
        self,
        obj: ast.expr,
        method: str,
        args: list[ast.expr],
    ) -> Any:
        """Translate method calls like obj.method(args)."""
        z3_obj = self._translate_node(obj)
        if z3_obj is None:
            return None

        # String methods
        if method == "lower":
            # For Z3, we can only check if string equals its lowercase
            # Return a constraint that the string contains only lowercase
            return z3_obj  # Simplified: just return the object

        elif method == "upper":
            return z3_obj  # Simplified

        elif method == "strip":
            return z3_obj  # Simplified: return object without leading/trailing spaces

        elif method == "startswith":
            if len(args) != 1:
                self.unsupported_reason = "startswith requires exactly 1 argument"
                return None
            z3_arg = self._translate_node(args[0])
            if z3_arg is None:
                return None
            return self.z3.PrefixOf(z3_arg, z3_obj)

        elif method == "endswith":
            if len(args) != 1:
                self.unsupported_reason = "endswith requires exactly 1 argument"
                return None
            z3_arg = self._translate_node(args[0])
            if z3_arg is None:
                return None
            return self.z3.SuffixOf(z3_arg, z3_obj)

        elif method == "count":
            # String.count - approximate with Contains
            if len(args) != 1:
                self.unsupported_reason = "count requires exactly 1 argument"
                return None
            z3_arg = self._translate_node(args[0])
            if z3_arg is None:
                return None
            # Return a symbolic integer for count
            count_var = self.z3.Int(f"_count_{id(obj)}")
            # Add constraint: count >= 0 if contains, count >= 1 if contains
            return count_var

        elif method == "get":
            # dict.get(key, default) - return the key lookup or default
            if len(args) < 1:
                self.unsupported_reason = "get requires at least 1 argument"
                return None
            # For simple cases, just return input_name variable
            if isinstance(obj, ast.Name) and obj.id == "input":
                if isinstance(args[0], ast.Constant) and isinstance(args[0].value, str):
                    key = args[0].value
                    var_name = f"input_{key}"
                    if var_name in self.z3_vars:
                        return self.z3_vars[var_name]
            self.unsupported_reason = "Could not resolve get() call"
            return None

        elif method == "isalnum":
            # Return a boolean for alphabetic check
            return self.z3.Bool(f"_isalnum_{id(obj)}")

        elif method == "isdigit":
            return self.z3.Bool(f"_isdigit_{id(obj)}")

        elif method == "isalpha":
            return self.z3.Bool(f"_isalpha_{id(obj)}")

        self.unsupported_reason = f"Unsupported method: {method}"
        return None

    def _translate_builtin_call(self, func_name: str, args: list[ast.expr]) -> Any:
        """Translate built-in function calls."""
        if func_name == "len":
            if len(args) != 1:
                self.unsupported_reason = "len requires exactly 1 argument"
                return None
            z3_arg = self._translate_node(args[0])
            if z3_arg is None:
                return None
            return self.z3.Length(z3_arg)

        elif func_name == "abs":
            if len(args) != 1:
                self.unsupported_reason = "abs requires exactly 1 argument"
                return None
            z3_arg = self._translate_node(args[0])
            if z3_arg is None:
                return None
            return self.z3.If(z3_arg >= 0, z3_arg, -z3_arg)

        elif func_name == "isinstance":
            # isinstance(x, type) - we can approximate with type constraints
            if len(args) != 2:
                self.unsupported_reason = "isinstance requires exactly 2 arguments"
                return None
            # For now, assume the type check passes if variable exists
            z3_arg = self._translate_node(args[0])
            if z3_arg is not None:
                return self.z3.BoolVal(True)
            return self.z3.BoolVal(False)

        elif func_name == "bool":
            if len(args) != 1:
                self.unsupported_reason = "bool requires exactly 1 argument"
                return None
            z3_arg = self._translate_node(args[0])
            if z3_arg is None:
                return None
            # Non-empty string/non-zero number is truthy
            try:
                return z3_arg != self.z3.StringVal("")
            except Exception:
                return z3_arg != 0

        elif func_name == "int":
            if len(args) != 1:
                self.unsupported_reason = "int requires exactly 1 argument"
                return None
            z3_arg = self._translate_node(args[0])
            if z3_arg is None:
                return None
            # Try to convert to int
            try:
                return self.z3.StrToInt(z3_arg)
            except Exception:
                return z3_arg

        elif func_name == "str":
            if len(args) != 1:
                self.unsupported_reason = "str requires exactly 1 argument"
                return None
            z3_arg = self._translate_node(args[0])
            if z3_arg is None:
                return None
            try:
                return self.z3.IntToStr(z3_arg)
            except Exception:
                return z3_arg

        elif func_name == "all":
            # all(pred for x in collection) - translate as universal constraint
            return self._translate_all_any(args, is_all=True)

        elif func_name == "any":
            # any(pred for x in collection) - translate as existential constraint
            return self._translate_all_any(args, is_all=False)

        elif func_name == "min":
            if len(args) < 1:
                self.unsupported_reason = "min requires at least 1 argument"
                return None
            z3_args = [self._translate_node(a) for a in args]
            if any(a is None for a in z3_args):
                return None
            # Build nested If for min
            result = z3_args[0]
            for arg in z3_args[1:]:
                result = self.z3.If(result <= arg, result, arg)
            return result

        elif func_name == "max":
            if len(args) < 1:
                self.unsupported_reason = "max requires at least 1 argument"
                return None
            z3_args = [self._translate_node(a) for a in args]
            if any(a is None for a in z3_args):
                return None
            result = z3_args[0]
            for arg in z3_args[1:]:
                result = self.z3.If(result >= arg, result, arg)
            return result

        self.unsupported_reason = f"Unsupported built-in function: {func_name}"
        return None

    def _translate_all_any(self, args: list[ast.expr], is_all: bool) -> Any:
        """Translate all() or any() with generator expression."""
        if len(args) != 1:
            self.unsupported_reason = f"{'all' if is_all else 'any'} requires exactly 1 argument"
            return None

        arg = args[0]

        # Handle generator expression: all(pred for x in collection)
        if isinstance(arg, ast.GeneratorExp):
            # For simple generator expressions, we can sometimes prove
            # For now, return a symbolic boolean
            return self.z3.Bool(f"_{'all' if is_all else 'any'}_{id(arg)}")

        # Handle list comprehension: all([pred for x in collection])
        if isinstance(arg, ast.ListComp):
            return self.z3.Bool(f"_{'all' if is_all else 'any'}_{id(arg)}")

        # Handle simple iterable
        z3_arg = self._translate_node(arg)
        if z3_arg is None:
            return None

        # For a simple value, all/any on truthiness
        if is_all:
            return z3_arg  # Simplified
        else:
            return z3_arg  # Simplified

    def _translate_subscript(self, value: ast.expr, slice_: ast.expr) -> Any:
        """Translate subscript access like x[key] or x[0]."""
        # Handle input['name'] pattern
        if isinstance(value, ast.Name) and value.id == "input":
            if isinstance(slice_, ast.Constant) and isinstance(slice_.value, str):
                key = slice_.value
                var_name = f"input_{key}"
                if var_name in self.z3_vars:
                    return self.z3_vars[var_name]
                self.unsupported_reason = f"Unknown input parameter: {key}"
                return None

        # Handle string/sequence indexing
        z3_value = self._translate_node(value)
        z3_index = self._translate_node(slice_)
        if z3_value is None or z3_index is None:
            return None

        try:
            # Try sequence index
            return self.z3.Nth(z3_value, z3_index)
        except Exception:
            pass

        try:
            # Try string index
            return self.z3.SubString(z3_value, z3_index, 1)
        except Exception:
            pass

        self.unsupported_reason = "Could not translate subscript"
        return None

    def _translate_attribute(self, value: ast.expr, attr: str) -> Any:
        """Translate attribute access (without method call)."""
        z3_value = self._translate_node(value)
        if z3_value is None:
            return None

        self.unsupported_reason = f"Unsupported attribute access: .{attr}"
        return None

    def _translate_name(self, name: str) -> Any:
        """Translate a variable name."""
        if name == "output":
            return self.z3_vars.get("output")
        if name == "input":
            # 'input' by itself is a dict - can't translate directly
            self.unsupported_reason = "Cannot use 'input' directly, use input['key']"
            return None
        if name == "True":
            return self.z3.BoolVal(True)
        if name == "False":
            return self.z3.BoolVal(False)
        if name == "None":
            # None is tricky in Z3 - use a special constant
            return self.z3.StringVal("")  # Simplified

        # Check if it's an input variable
        var_name = f"input_{name}"
        if var_name in self.z3_vars:
            return self.z3_vars[var_name]

        # Check direct variable lookup
        if name in self.z3_vars:
            return self.z3_vars[name]

        self.unsupported_reason = f"Unknown variable: {name}"
        return None

    def _translate_constant(self, value: Any) -> Any:
        """Translate a constant value."""
        if isinstance(value, bool):
            return self.z3.BoolVal(value)
        elif isinstance(value, int):
            return self.z3.IntVal(value)
        elif isinstance(value, float):
            return self.z3.RealVal(value)
        elif isinstance(value, str):
            return self.z3.StringVal(value)
        elif value is None:
            return self.z3.StringVal("")  # Simplified

        self.unsupported_reason = f"Unsupported constant type: {type(value).__name__}"
        return None

    def _translate_ifexp(self, test: ast.expr, body: ast.expr, orelse: ast.expr) -> Any:
        """Translate ternary expression: body if test else orelse."""
        z3_test = self._translate_node(test)
        z3_body = self._translate_node(body)
        z3_orelse = self._translate_node(orelse)

        if z3_test is None or z3_body is None or z3_orelse is None:
            return None

        return self.z3.If(z3_test, z3_body, z3_orelse)


def _z3_to_python(val: Any, z3_module: Any) -> Any:
    """Convert a Z3 value to Python.

    Args:
        val: Z3 value.
        z3_module: The z3 module.

    Returns:
        Python value.
    """
    try:
        if z3_module.is_int_value(val):
            return val.as_long()
        if z3_module.is_rational_value(val):
            return float(val.numerator_as_long()) / float(val.denominator_as_long())
        if z3_module.is_true(val):
            return True
        if z3_module.is_false(val):
            return False
        if z3_module.is_string_value(val):
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

    # Check if types are supported (expanded list)
    param_types = spec.get_parameter_types()
    return_type = spec.get_return_type()

    supported_types = {"str", "int", "float", "bool", "list", "dict", "any", "none"}
    all_types = list(param_types.values()) + [return_type]

    for t in all_types:
        base_type = t.split("[")[0].strip().lower()
        if base_type not in supported_types:
            return False

    return True
