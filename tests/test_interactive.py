"""Tests for interactive verification failure handling."""

from __future__ import annotations

from axiom.verify.interactive import (
    FailureSuggestion,
    InteractiveFailure,
    _format_value,
    _generate_diff,
    _is_close_value,
    _is_type_mismatch,
    analyze_failure,
    format_failure_summary,
    format_interactive_failure,
)
from axiom.verify.models import (
    CheckStatus,
    ExampleResult,
    VerificationResult,
)


class TestFormatValue:
    """Tests for value formatting."""

    def test_format_none(self) -> None:
        assert _format_value(None) == "None"

    def test_format_short_string(self) -> None:
        assert _format_value("hello") == '"hello"'

    def test_format_long_string(self) -> None:
        long_str = "a" * 100
        result = _format_value(long_str)
        assert result.endswith('..."')
        assert len(result) < 60

    def test_format_small_dict(self) -> None:
        result = _format_value({"a": 1})
        assert result == "{'a': 1}"

    def test_format_large_dict(self) -> None:
        large_dict = {f"key{i}": i for i in range(20)}
        result = _format_value(large_dict)
        assert "{20 keys}" in result

    def test_format_small_list(self) -> None:
        result = _format_value([1, 2, 3])
        assert result == "[1, 2, 3]"

    def test_format_large_list(self) -> None:
        result = _format_value(list(range(10)))
        assert "[10 items]" in result

    def test_format_number(self) -> None:
        assert _format_value(42) == "42"
        assert _format_value(3.14) == "3.14"


class TestGenerateDiff:
    """Tests for diff generation."""

    def test_diff_identical_strings(self) -> None:
        result = _generate_diff("hello", "hello")
        assert result is None

    def test_diff_different_strings(self) -> None:
        result = _generate_diff("hello", "world")
        assert result is not None
        assert "-hello" in result or "hello" in result

    def test_diff_non_strings(self) -> None:
        result = _generate_diff(42, 43)
        assert result is None


class TestTypeMismatch:
    """Tests for type mismatch detection."""

    def test_same_types(self) -> None:
        assert _is_type_mismatch("hello", "world") is False
        assert _is_type_mismatch(42, 100) is False

    def test_different_types(self) -> None:
        assert _is_type_mismatch("42", 42) is True
        assert _is_type_mismatch([1], (1,)) is True

    def test_none_values(self) -> None:
        assert _is_type_mismatch(None, "hello") is False
        assert _is_type_mismatch("hello", None) is False


class TestCloseValue:
    """Tests for close value detection."""

    def test_exact_match(self) -> None:
        assert _is_close_value(42, 42) is True

    def test_close_numbers(self) -> None:
        assert _is_close_value(100, 105) is True
        assert _is_close_value(100, 150) is False

    def test_zero_handling(self) -> None:
        assert _is_close_value(0, 0.05) is True
        assert _is_close_value(0, 1) is False

    def test_similar_strings(self) -> None:
        # "hello" vs "helo" has ratio > 0.8 (missing one 'l')
        assert _is_close_value("hello", "helo") is True
        assert _is_close_value("hello", "goodbye") is False


class TestFailureSuggestion:
    """Tests for FailureSuggestion dataclass."""

    def test_create_suggestion(self) -> None:
        suggestion = FailureSuggestion(
            title="Regenerate",
            description="Try regenerating the code",
            action="regenerate",
            priority=1,
        )
        assert suggestion.title == "Regenerate"
        assert suggestion.priority == 1

    def test_default_priority(self) -> None:
        suggestion = FailureSuggestion(
            title="Test",
            description="Test",
            action="test",
        )
        assert suggestion.priority == 2


class TestInteractiveFailure:
    """Tests for InteractiveFailure dataclass."""

    def test_create_failure(self) -> None:
        failure = InteractiveFailure(
            check_type="example",
            check_name="test_example",
            error_summary="Expected 1, got 2",
        )
        assert failure.check_type == "example"
        assert failure.check_name == "test_example"

    def test_default_values(self) -> None:
        failure = InteractiveFailure(
            check_type="example",
            check_name="test",
            error_summary="Error",
        )
        assert failure.suggestions == []
        assert failure.diff is None


class TestFormatInteractiveFailure:
    """Tests for failure formatting."""

    def test_format_basic_failure(self) -> None:
        failure = InteractiveFailure(
            check_type="example",
            check_name="test_basic",
            error_summary="Expected 1, got 2",
        )
        output = format_interactive_failure(failure)
        assert "[EXAMPLE]" in output
        assert "test_basic" in output
        assert "Expected 1, got 2" in output

    def test_format_with_suggestions(self) -> None:
        failure = InteractiveFailure(
            check_type="example",
            check_name="test",
            error_summary="Error",
            suggestions=[
                FailureSuggestion(
                    title="Fix this",
                    description="Do this to fix",
                    action="fix",
                    priority=1,
                )
            ],
        )
        output = format_interactive_failure(failure)
        assert "Suggestions:" in output
        assert "Fix this" in output


class TestFormatFailureSummary:
    """Tests for summary formatting."""

    def test_format_empty_summary(self) -> None:
        output = format_failure_summary([], "test_spec")
        assert "test_spec" in output
        assert "0 failure(s)" in output

    def test_format_summary_with_failures(self) -> None:
        failures = [
            InteractiveFailure(
                check_type="example",
                check_name="test1",
                error_summary="Error 1",
            ),
            InteractiveFailure(
                check_type="invariant",
                check_name="test2",
                error_summary="Error 2",
            ),
        ]
        output = format_failure_summary(failures, "my_spec")
        assert "my_spec" in output
        assert "2 failure(s)" in output
        assert "example" in output
        assert "invariant" in output


class TestAnalyzeFailure:
    """Tests for failure analysis."""

    def test_analyze_passing_result(self) -> None:
        """No failures should return empty list."""
        # Create a minimal mock spec
        from axiom.spec.models import (
            Example,
            ExpectedOutput,
            FunctionInterface,
            Metadata,
            Returns,
            Spec,
        )

        spec = Spec(
            axiom="0.1",
            metadata=Metadata(
                name="test",
                version="1.0.0",
                description="Test spec",
                target="python:function",
            ),
            intent="Test function.",
            interface=FunctionInterface(
                function_name="test",
                returns=Returns(type="bool", description="Result"),
            ),
            examples=[
                Example(
                    name="test_ex",
                    input={},
                    expected_output=ExpectedOutput(value=True),
                )
            ],
        )

        result = VerificationResult(
            spec_name="test",
            success=True,
            example_results=[
                ExampleResult(
                    name="test_ex",
                    status=CheckStatus.PASSED,
                )
            ],
        )

        failures = analyze_failure(result, spec, "code")
        assert failures == []

    def test_analyze_example_failure(self) -> None:
        """Example failures should generate suggestions."""
        from axiom.spec.models import (
            Example,
            ExpectedOutput,
            FunctionInterface,
            Metadata,
            Returns,
            Spec,
        )

        spec = Spec(
            axiom="0.1",
            metadata=Metadata(
                name="test",
                version="1.0.0",
                description="Test spec",
                target="python:function",
            ),
            intent="Test function.",
            interface=FunctionInterface(
                function_name="test",
                returns=Returns(type="int", description="Result"),
            ),
            examples=[
                Example(
                    name="failing_example",
                    input={"x": 1},
                    expected_output=ExpectedOutput(value=2),
                )
            ],
        )

        result = VerificationResult(
            spec_name="test",
            success=False,
            example_results=[
                ExampleResult(
                    name="failing_example",
                    status=CheckStatus.FAILED,
                    expected=2,
                    actual=3,
                    error_message="Expected 2, got 3",
                )
            ],
        )

        failures = analyze_failure(result, spec, "code")
        assert len(failures) == 1
        assert failures[0].check_type == "example"
        assert len(failures[0].suggestions) > 0
