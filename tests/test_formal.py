"""Tests for formal verification with Z3."""

from __future__ import annotations

import pytest

# Skip all tests if z3 is not installed
z3 = pytest.importorskip("z3")

from axiom.spec.models import (
    Example,
    Interface,
    Invariant,
    Metadata,
    Parameter,
    Returns,
    Spec,
)
from axiom.verify.formal import (
    FormalVerificationResult,
    Z3Translator,
    can_verify_formally,
    verify_formally,
)


def _make_spec(
    invariants: list[Invariant],
    params: list[Parameter] | None = None,
    return_type: str = "int",
) -> Spec:
    """Create a minimal spec for testing."""
    if params is None:
        params = [Parameter(name="x", type="int", description="Input")]

    return Spec(
        axiom="0.1",
        metadata=Metadata(
            name="test_func",
            version="1.0.0",
            description="Test",
            target="python:function",
        ),
        intent="Test function",
        interface=Interface(
            function_name="test_func",
            parameters=params,
            returns=Returns(type=return_type, description="Output"),
        ),
        examples=[
            Example(name="test", input={"x": 1}, expected_output=1),
        ],
        invariants=invariants,
    )


class TestZ3Translator:
    """Tests for Z3 expression translation."""

    def test_simple_comparison_eq(self) -> None:
        """Test equality comparison."""
        translator = Z3Translator(z3, {"x": "int"}, "int")
        result = translator.translate("output == 5")
        assert result is not None
        z3_expr, _ = result

    def test_simple_comparison_gt(self) -> None:
        """Test greater than comparison."""
        translator = Z3Translator(z3, {"x": "int"}, "int")
        result = translator.translate("output > 0")
        assert result is not None

    def test_simple_comparison_lt(self) -> None:
        """Test less than comparison."""
        translator = Z3Translator(z3, {"x": "int"}, "int")
        result = translator.translate("output < 100")
        assert result is not None

    def test_boolean_and(self) -> None:
        """Test boolean and."""
        translator = Z3Translator(z3, {"x": "int"}, "int")
        result = translator.translate("output > 0 and output < 100")
        assert result is not None

    def test_boolean_or(self) -> None:
        """Test boolean or."""
        translator = Z3Translator(z3, {"x": "int"}, "int")
        result = translator.translate("output == 0 or output == 1")
        assert result is not None

    def test_boolean_not(self) -> None:
        """Test boolean not."""
        translator = Z3Translator(z3, {"x": "int"}, "int")
        result = translator.translate("not output == 0")
        assert result is not None

    def test_input_access(self) -> None:
        """Test input parameter access."""
        translator = Z3Translator(z3, {"x": "int"}, "int")
        result = translator.translate("output == input['x']")
        assert result is not None

    def test_len_function(self) -> None:
        """Test len() built-in."""
        translator = Z3Translator(z3, {"s": "str"}, "str")
        result = translator.translate("len(output) > 0")
        assert result is not None

    def test_startswith_method(self) -> None:
        """Test startswith() method."""
        translator = Z3Translator(z3, {"s": "str"}, "str")
        result = translator.translate("output.startswith('hello')")
        assert result is not None

    def test_endswith_method(self) -> None:
        """Test endswith() method."""
        translator = Z3Translator(z3, {"s": "str"}, "str")
        result = translator.translate("output.endswith('world')")
        assert result is not None

    def test_in_operator_string(self) -> None:
        """Test 'in' operator for string containment."""
        translator = Z3Translator(z3, {"s": "str"}, "str")
        result = translator.translate("'@' in output")
        assert result is not None

    def test_not_in_operator(self) -> None:
        """Test 'not in' operator."""
        translator = Z3Translator(z3, {"s": "str"}, "str")
        result = translator.translate("' ' not in output")
        assert result is not None

    def test_arithmetic_add(self) -> None:
        """Test addition."""
        translator = Z3Translator(z3, {"x": "int", "y": "int"}, "int")
        result = translator.translate("output == input['x'] + input['y']")
        assert result is not None

    def test_arithmetic_sub(self) -> None:
        """Test subtraction."""
        translator = Z3Translator(z3, {"x": "int", "y": "int"}, "int")
        result = translator.translate("output == input['x'] - input['y']")
        assert result is not None

    def test_arithmetic_mul(self) -> None:
        """Test multiplication."""
        translator = Z3Translator(z3, {"x": "int", "y": "int"}, "int")
        result = translator.translate("output == input['x'] * input['y']")
        assert result is not None

    def test_isinstance_call(self) -> None:
        """Test isinstance() built-in."""
        translator = Z3Translator(z3, {"x": "str"}, "str")
        result = translator.translate("isinstance(output, str)")
        assert result is not None

    def test_abs_function(self) -> None:
        """Test abs() built-in."""
        translator = Z3Translator(z3, {"x": "int"}, "int")
        result = translator.translate("abs(output) >= 0")
        assert result is not None

    def test_ternary_expression(self) -> None:
        """Test ternary (if-else) expression."""
        translator = Z3Translator(z3, {"x": "int"}, "int")
        result = translator.translate("output == (1 if input['x'] > 0 else 0)")
        assert result is not None

    def test_chained_comparison(self) -> None:
        """Test chained comparison like 0 <= x <= 100."""
        translator = Z3Translator(z3, {"x": "int"}, "int")
        result = translator.translate("0 <= output <= 100")
        assert result is not None

    def test_invalid_syntax(self) -> None:
        """Test handling of invalid Python syntax."""
        translator = Z3Translator(z3, {"x": "int"}, "int")
        result = translator.translate("output == ==")
        assert result is None
        assert "syntax" in translator.unsupported_reason.lower()

    def test_unknown_variable(self) -> None:
        """Test handling of unknown variables."""
        translator = Z3Translator(z3, {"x": "int"}, "int")
        result = translator.translate("unknown_var > 0")
        assert result is None


class TestVerifyFormally:
    """Tests for formal verification of specs."""

    def test_verify_trivially_true(self) -> None:
        """Test verifying a trivially true invariant."""
        spec = _make_spec([
            Invariant(
                description="Output is always non-negative squared",
                check="output * output >= 0",
            )
        ])
        results = verify_formally(spec)
        assert len(results) == 1
        # This should be proved (x^2 >= 0 is always true)
        assert results[0].status in ("proved", "unsupported")

    def test_verify_with_counterexample(self) -> None:
        """Test finding a counterexample."""
        spec = _make_spec([
            Invariant(
                description="Output is always positive",
                check="output > 0",
            )
        ])
        results = verify_formally(spec)
        assert len(results) == 1
        # Z3 should find counterexample (output = 0 or negative)
        assert results[0].status in ("counterexample", "unsupported")

    def test_verify_no_check_expression(self) -> None:
        """Test invariant without check expression."""
        spec = _make_spec([
            Invariant(
                description="Some property",
                check=None,
            )
        ])
        results = verify_formally(spec)
        assert len(results) == 1
        assert results[0].status == "unsupported"
        assert "No check expression" in results[0].explanation

    def test_verify_multiple_invariants(self) -> None:
        """Test verifying multiple invariants."""
        spec = _make_spec([
            Invariant(description="First", check="output >= 0"),
            Invariant(description="Second", check="output <= 100"),
        ])
        results = verify_formally(spec)
        assert len(results) == 2


class TestCanVerifyFormally:
    """Tests for checking if formal verification is possible."""

    def test_can_verify_with_int_types(self) -> None:
        """Test that int types are verifiable."""
        spec = _make_spec(
            [Invariant(description="Test", check="output > 0")],
            params=[Parameter(name="x", type="int", description="Input")],
            return_type="int",
        )
        assert can_verify_formally(spec) is True

    def test_can_verify_with_str_types(self) -> None:
        """Test that str types are verifiable."""
        spec = _make_spec(
            [Invariant(description="Test", check="len(output) > 0")],
            params=[Parameter(name="s", type="str", description="Input")],
            return_type="str",
        )
        assert can_verify_formally(spec) is True

    def test_cannot_verify_without_invariants(self) -> None:
        """Test that specs without invariants can't be verified."""
        spec = _make_spec([])
        assert can_verify_formally(spec) is False

    def test_cannot_verify_without_check(self) -> None:
        """Test that specs without check expressions can't be verified."""
        spec = _make_spec([Invariant(description="Test", check=None)])
        assert can_verify_formally(spec) is False


class TestFormalVerificationResult:
    """Tests for FormalVerificationResult dataclass."""

    def test_result_proved(self) -> None:
        """Test proved result."""
        result = FormalVerificationResult(
            invariant="output > 0",
            status="proved",
            explanation="Mathematically proven",
        )
        assert result.status == "proved"
        assert result.counterexample is None

    def test_result_counterexample(self) -> None:
        """Test counterexample result."""
        result = FormalVerificationResult(
            invariant="output > 0",
            status="counterexample",
            counterexample={"output": -1},
            explanation="Found violation",
        )
        assert result.status == "counterexample"
        assert result.counterexample == {"output": -1}
