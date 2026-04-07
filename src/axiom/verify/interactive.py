"""Interactive verification failure handling.

Provides rich failure information and actionable suggestions when verification fails.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

# Import spec-driven utilities (dogfooding)
from axiom._generated import format_value as _format_value
from axiom._generated import is_close_value as _is_close_value
from axiom.verify.models import (
    CheckStatus,
    ExampleResult,
    InvariantResult,
    PerformanceResult,
    VerificationResult,
)

if TYPE_CHECKING:
    from axiom.spec.models import Spec

logger = structlog.get_logger()


@dataclass
class FailureSuggestion:
    """A suggestion for fixing a verification failure.

    Attributes:
        title: Short description of the suggestion.
        description: Detailed explanation.
        action: Recommended action (e.g., "update_spec", "regenerate", "manual").
        priority: Priority (1=high, 2=medium, 3=low).
        code_hint: Optional code or spec snippet to help.
    """

    title: str
    description: str
    action: str
    priority: int = 2
    code_hint: str | None = None


@dataclass
class InteractiveFailure:
    """Rich failure information with suggestions.

    Attributes:
        check_type: Type of check that failed (example, invariant, performance).
        check_name: Name of the specific check.
        error_summary: One-line error summary.
        expected_formatted: Formatted expected value.
        actual_formatted: Formatted actual value.
        diff: Diff between expected and actual (if applicable).
        suggestions: List of suggestions for fixing.
        raw_error: Raw error message.
        input_values: The input values that caused the failure.
    """

    check_type: str
    check_name: str
    error_summary: str
    expected_formatted: str | None = None
    actual_formatted: str | None = None
    diff: str | None = None
    suggestions: list[FailureSuggestion] = field(default_factory=list)
    raw_error: str | None = None
    input_values: dict[str, object] | None = None


def analyze_failure(
    result: VerificationResult,
    spec: Spec,
    code: str,
) -> list[InteractiveFailure]:
    """Analyze verification failures and generate suggestions.

    Args:
        result: The verification result.
        spec: The spec being verified.
        code: The generated code.

    Returns:
        List of InteractiveFailure with analysis and suggestions.
    """
    failures: list[InteractiveFailure] = []

    # Analyze example failures
    for ex_result in result.example_results:
        if ex_result.status in (CheckStatus.FAILED, CheckStatus.ERROR):
            failure = _analyze_example_failure(ex_result, spec, code)
            failures.append(failure)

    # Analyze invariant failures
    for inv_result in result.invariant_results:
        if inv_result.status in (CheckStatus.FAILED, CheckStatus.ERROR):
            failure = _analyze_invariant_failure(inv_result, spec, code)
            failures.append(failure)

    # Analyze performance failures
    for perf_result in result.performance_results:
        if perf_result.status in (CheckStatus.FAILED, CheckStatus.ERROR):
            failure = _analyze_performance_failure(perf_result, spec, code)
            failures.append(failure)

    return failures


def _analyze_example_failure(
    ex: ExampleResult,
    spec: Spec,
    _code: str,
) -> InteractiveFailure:
    """Analyze an example failure.

    Args:
        ex: The example result.
        spec: The spec.
        _code: The generated code (reserved for future use).

    Returns:
        InteractiveFailure with analysis.
    """
    suggestions: list[FailureSuggestion] = []
    diff_str = None

    # Format expected and actual
    expected_fmt = _format_value(ex.expected)
    actual_fmt = _format_value(ex.actual)

    # Generate diff for string/complex values
    if ex.expected is not None and ex.actual is not None:
        diff_str = _generate_diff(ex.expected, ex.actual)

    # Find the matching example in spec for input values
    input_values = None
    for spec_ex in spec.examples:
        if spec_ex.name == ex.name:
            input_values = spec_ex.input
            break

    # Generate suggestions based on failure type
    if ex.status == CheckStatus.ERROR:
        # Code threw an unexpected error
        suggestions.append(
            FailureSuggestion(
                title="Code threw an exception",
                description=(
                    f"The generated code raised an unexpected exception: {ex.error_message}. "
                    "This usually indicates a bug in the generated code."
                ),
                action="regenerate",
                priority=1,
                code_hint="Run: axiom build <spec> --force",
            )
        )
        suggestions.append(
            FailureSuggestion(
                title="Check if example input is valid",
                description=(
                    "Verify the example input matches what the function expects. "
                    "Parameter types and names must match the interface."
                ),
                action="check_spec",
                priority=2,
            )
        )
    else:
        # Wrong value returned
        if _is_type_mismatch(ex.expected, ex.actual):
            suggestions.append(
                FailureSuggestion(
                    title="Type mismatch",
                    description=(
                        f"Expected type {type(ex.expected).__name__}, "
                        f"got {type(ex.actual).__name__}. "
                        "The spec's return type may need clarification."
                    ),
                    action="update_spec",
                    priority=1,
                )
            )
        elif _is_close_value(ex.expected, ex.actual):
            suggestions.append(
                FailureSuggestion(
                    title="Value is close but not exact",
                    description=(
                        "The actual value is close to expected. This might be a "
                        "precision issue or an off-by-one error."
                    ),
                    action="check_spec",
                    priority=2,
                )
            )

        # Common case: just regenerate
        suggestions.append(
            FailureSuggestion(
                title="Regenerate code",
                description=(
                    "The LLM may have misunderstood the requirement. Try regenerating with --force."
                ),
                action="regenerate",
                priority=2,
                code_hint="Run: axiom build <spec> --force",
            )
        )

        # Suggest adding more examples
        suggestions.append(
            FailureSuggestion(
                title="Add more examples",
                description=(
                    "Adding more examples helps the LLM understand edge cases. "
                    "Consider adding examples that demonstrate the expected behavior."
                ),
                action="update_spec",
                priority=3,
            )
        )

    return InteractiveFailure(
        check_type="example",
        check_name=ex.name,
        error_summary=ex.error_message or f"Expected {expected_fmt}, got {actual_fmt}",
        expected_formatted=expected_fmt,
        actual_formatted=actual_fmt,
        diff=diff_str,
        suggestions=suggestions,
        raw_error=ex.error_message,
        input_values=input_values,
    )


def _analyze_invariant_failure(
    inv: InvariantResult,
    _spec: Spec,
    _code: str,
) -> InteractiveFailure:
    """Analyze an invariant failure.

    Args:
        inv: The invariant result.
        _spec: The spec (reserved for future use).
        _code: The generated code (reserved for future use).

    Returns:
        InteractiveFailure with analysis.
    """

    suggestions: list[FailureSuggestion] = []

    # Format counterexample if present
    counterexample_fmt = None
    if inv.counterexample:
        counterexample_fmt = _format_value(inv.counterexample)

    if inv.status == CheckStatus.ERROR:
        suggestions.append(
            FailureSuggestion(
                title="Invariant check raised an error",
                description=(
                    f"The invariant check itself failed: {inv.error_message}. "
                    "This may indicate an issue with the check expression."
                ),
                action="update_spec",
                priority=1,
                code_hint=(
                    "Check the invariant's 'check' expression for syntax errors "
                    "or undefined variables."
                ),
            )
        )
    elif inv.counterexample:
        suggestions.append(
            FailureSuggestion(
                title="Counterexample found",
                description=(
                    f"Hypothesis found input that violates the invariant: {counterexample_fmt}. "
                    "Either fix the generated code or update the invariant if it's too strict."
                ),
                action="regenerate",
                priority=1,
                code_hint="Run: axiom build <spec> --force --verify",
            )
        )

        # Suggest adding this as an explicit example
        suggestions.append(
            FailureSuggestion(
                title="Add counterexample as test case",
                description=(
                    "Convert this counterexample into an explicit example to ensure "
                    "future generations handle it correctly."
                ),
                action="update_spec",
                priority=2,
            )
        )

    return InteractiveFailure(
        check_type="invariant",
        check_name=inv.description,
        error_summary=inv.error_message or "Invariant violated",
        expected_formatted="Invariant should hold",
        actual_formatted="Invariant violated",
        diff=None,
        suggestions=suggestions,
        raw_error=inv.error_message,
        input_values=inv.counterexample,
    )


def _analyze_performance_failure(
    perf: PerformanceResult,
    _spec: Spec,
    _code: str,
) -> InteractiveFailure:
    """Analyze a performance failure.

    Args:
        perf: The performance result.
        _spec: The spec (reserved for future use).
        _code: The generated code (reserved for future use).

    Returns:
        InteractiveFailure with analysis.
    """

    suggestions: list[FailureSuggestion] = []

    if perf.avg_ms and perf.constraint_ms:
        ratio = perf.avg_ms / perf.constraint_ms

        if ratio > 2:
            suggestions.append(
                FailureSuggestion(
                    title="Significant performance issue",
                    description=(
                        f"Code is {ratio:.1f}x slower than required. "
                        "Consider adding performance hints to the spec intent."
                    ),
                    action="update_spec",
                    priority=1,
                    code_hint=(
                        "Add to intent: 'Performance is critical. "
                        "Optimize for speed over readability.'"
                    ),
                )
            )
        else:
            suggestions.append(
                FailureSuggestion(
                    title="Minor performance issue",
                    description=(
                        f"Code is {ratio:.1f}x slower than required. "
                        "Regeneration might produce faster code."
                    ),
                    action="regenerate",
                    priority=2,
                )
            )

    suggestions.append(
        FailureSuggestion(
            title="Relax performance constraint",
            description="If the constraint is too strict, consider relaxing it in the spec.",
            action="update_spec",
            priority=3,
        )
    )

    return InteractiveFailure(
        check_type="performance",
        check_name=perf.name,
        error_summary=perf.error_message or f"Exceeded {perf.constraint_ms}ms limit",
        expected_formatted=f"<= {perf.constraint_ms}ms",
        actual_formatted=f"{perf.avg_ms:.0f}ms avg" if perf.avg_ms else None,
        diff=None,
        suggestions=suggestions,
        raw_error=perf.error_message,
    )


def format_interactive_failure(failure: InteractiveFailure, verbose: bool = False) -> str:
    """Format an interactive failure for display.

    Args:
        failure: The failure to format.
        verbose: Whether to show detailed information.

    Returns:
        Formatted string for console output.
    """
    lines = []

    # Header
    icon = "✗"
    lines.append(f"{icon} [{failure.check_type.upper()}] {failure.check_name}")
    lines.append(f"   {failure.error_summary}")

    # Input values
    if failure.input_values and verbose:
        lines.append("")
        lines.append("   Input:")
        for key, value in failure.input_values.items():
            lines.append(f"     {key}: {_format_value(value)}")

    # Expected vs Actual
    if failure.expected_formatted and failure.actual_formatted:
        lines.append("")
        lines.append(f"   Expected: {failure.expected_formatted}")
        lines.append(f"   Actual:   {failure.actual_formatted}")

    # Diff
    if failure.diff and verbose:
        lines.append("")
        lines.append("   Diff:")
        for line in failure.diff.split("\n"):
            lines.append(f"   {line}")

    # Suggestions
    if failure.suggestions:
        lines.append("")
        lines.append("   Suggestions:")
        sorted_suggestions = sorted(failure.suggestions, key=lambda s: s.priority)
        for suggestion in sorted_suggestions[:3]:
            priority_marker = "→" if suggestion.priority == 1 else "·"
            lines.append(f"   {priority_marker} {suggestion.title}")
            if verbose:
                lines.append(f"     {suggestion.description}")
            if suggestion.code_hint:
                lines.append(f"     Hint: {suggestion.code_hint}")

    return "\n".join(lines)


def format_failure_summary(
    failures: list[InteractiveFailure],
    spec_name: str,
) -> str:
    """Format a summary of all failures.

    Args:
        failures: List of failures.
        spec_name: Name of the spec.

    Returns:
        Formatted summary string.
    """
    lines = []
    lines.append("")
    lines.append("─" * 60)
    lines.append(f"Verification Failed: {spec_name}")
    lines.append(f"  {len(failures)} failure(s) found")
    lines.append("")

    # Count by type
    by_type: dict[str, int] = {}
    for f in failures:
        by_type[f.check_type] = by_type.get(f.check_type, 0) + 1

    for check_type, count in by_type.items():
        lines.append(f"  • {count} {check_type} failure(s)")

    # Top action
    all_suggestions = [s for f in failures for s in f.suggestions]
    if all_suggestions:
        top = min(all_suggestions, key=lambda s: s.priority)
        lines.append("")
        lines.append(f"  Recommended action: {top.title}")
        if top.code_hint:
            lines.append(f"    {top.code_hint}")

    lines.append("─" * 60)

    return "\n".join(lines)


def _generate_diff(expected: object, actual: object) -> str | None:
    """Generate a diff between expected and actual values.

    Args:
        expected: Expected value.
        actual: Actual value.

    Returns:
        Diff string or None if not applicable.
    """
    # Only diff strings and dicts
    if isinstance(expected, str) and isinstance(actual, str):
        expected_lines = expected.splitlines(keepends=True)
        actual_lines = actual.splitlines(keepends=True)
        diff = difflib.unified_diff(
            expected_lines,
            actual_lines,
            fromfile="expected",
            tofile="actual",
            lineterm="",
        )
        diff_str = "".join(diff)
        return diff_str if diff_str else None

    if isinstance(expected, dict) and isinstance(actual, dict):
        expected_str = str(expected)
        actual_str = str(actual)
        if expected_str != actual_str:
            diff = difflib.unified_diff(
                [expected_str],
                [actual_str],
                fromfile="expected",
                tofile="actual",
                lineterm="",
            )
            return "".join(diff) or None

    return None


def _is_type_mismatch(expected: object, actual: object) -> bool:
    """Check if the failure is a type mismatch."""
    if expected is None or actual is None:
        return False
    return type(expected) is not type(actual)
