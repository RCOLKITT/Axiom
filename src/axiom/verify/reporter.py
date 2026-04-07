"""Format and display verification results."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from axiom.verify.models import CheckStatus, VerificationResult

if TYPE_CHECKING:
    from axiom.escape.verifier import HandWrittenVerificationResult

logger = structlog.get_logger()


def format_result(result: VerificationResult, verbose: bool = False) -> str:
    """Format a verification result for display.

    Args:
        result: The verification result.
        verbose: Whether to include detailed output.

    Returns:
        Formatted string for console output.
    """
    lines = []

    # Header
    status_icon = "✓" if result.success else "✗"
    status_word = "PASSED" if result.success else "FAILED"
    lines.append(f"{status_icon} {result.spec_name} — {status_word}")

    # Summary line
    summary_parts = []
    if result.example_results:
        summary_parts.append(f"{result.examples_passed}/{result.examples_total} examples")
    if result.invariant_results:
        passed = result.invariants_passed
        skipped = sum(1 for r in result.invariant_results if r.status == CheckStatus.SKIPPED)
        total = result.invariants_total
        if skipped > 0:
            summary_parts.append(f"{passed}/{total} invariants ({skipped} skipped)")
        else:
            summary_parts.append(f"{passed}/{total} invariants")
    if result.performance_results:
        summary_parts.append(f"{result.performance_passed}/{result.performance_total} performance")

    if summary_parts:
        lines.append(f"  {' | '.join(summary_parts)}")

    # Performance details
    for perf in result.performance_results:
        if perf.avg_ms is not None:
            perf_line = f"  Performance: avg={perf.avg_ms}ms"
            if perf.p95_ms is not None:
                perf_line += f", p95={perf.p95_ms}ms"
            if perf.constraint_ms is not None:
                perf_line += f" (limit: {perf.constraint_ms}ms)"
            lines.append(perf_line)

    # Duration
    if result.duration_ms:
        lines.append(f"  Duration: {result.duration_ms}ms")

    # Global error
    if result.error:
        lines.append(f"  Error: {result.error}")

    # Verbose output: show all failures
    if verbose or not result.success:
        failure_details = _format_failures(result)
        if failure_details:
            lines.append("")
            lines.append("  Failures:")
            for detail in failure_details:
                lines.append(f"    {detail}")

    return "\n".join(lines)


def _format_failures(result: VerificationResult) -> list[str]:
    """Format failure details.

    Args:
        result: The verification result.

    Returns:
        List of formatted failure strings.
    """
    failures = []

    # Example failures
    for ex in result.example_results:
        if ex.status == CheckStatus.FAILED:
            if ex.error_message:
                failures.append(f"[Example] {ex.name}: {ex.error_message}")
            else:
                failures.append(f"[Example] {ex.name}: expected {ex.expected}, got {ex.actual}")
        elif ex.status == CheckStatus.ERROR:
            failures.append(f"[Example] {ex.name}: ERROR - {ex.error_message}")

    # Invariant failures
    for inv in result.invariant_results:
        if inv.status == CheckStatus.FAILED:
            desc = inv.description[:50] + "..." if len(inv.description) > 50 else inv.description
            if inv.counterexample:
                failures.append(f"[Invariant] {desc}")
                failures.append(f"            Counterexample: {inv.counterexample}")
            elif inv.error_message:
                failures.append(f"[Invariant] {desc}: {inv.error_message}")
        elif inv.status == CheckStatus.ERROR:
            desc = inv.description[:50] + "..." if len(inv.description) > 50 else inv.description
            failures.append(f"[Invariant] {desc}: ERROR - {inv.error_message}")

    # Performance failures
    for perf in result.performance_results:
        if perf.status == CheckStatus.FAILED:
            if perf.error_message:
                failures.append(f"[Performance] {perf.name}: {perf.error_message}")
        elif perf.status == CheckStatus.ERROR:
            failures.append(f"[Performance] {perf.name}: ERROR - {perf.error_message}")

    return failures


def print_result(result: VerificationResult, verbose: bool = False) -> None:
    """Print a verification result to stdout via structlog.

    Args:
        result: The verification result.
        verbose: Whether to include detailed output.
    """
    formatted = format_result(result, verbose=verbose)
    # Use print for user-facing output
    print(formatted)


def format_summary(results: list[VerificationResult]) -> str:
    """Format a summary of multiple verification results.

    Args:
        results: List of verification results.

    Returns:
        Formatted summary string.
    """
    total = len(results)
    passed = sum(1 for r in results if r.success)
    failed = total - passed

    lines = []
    lines.append("=" * 60)
    lines.append(f"Verification Summary: {passed}/{total} specs passed")

    if failed > 0:
        lines.append("")
        lines.append("Failed specs:")
        for r in results:
            if not r.success:
                lines.append(f"  - {r.spec_name}")

    lines.append("=" * 60)

    return "\n".join(lines)


def format_escape_hatch_result(
    result: HandWrittenVerificationResult,
    verbose: bool = False,
) -> str:
    """Format an escape hatch verification result for display.

    Args:
        result: The escape hatch verification result.
        verbose: Whether to include detailed output.

    Returns:
        Formatted string for console output.
    """
    lines = []

    # Header
    status_icon = "✓" if result.interface_matches else "✗"
    status_word = "PASSED" if result.interface_matches else "FAILED"
    lines.append(f"{status_icon} {result.module_name} — {status_word}")

    # Module path
    lines.append(f"  Path: {result.module_path}")

    # Check results summary
    if result.check_results:
        passed = sum(1 for c in result.check_results if c.passed)
        total = len(result.check_results)
        lines.append(f"  Checks: {passed}/{total} passed")

    # Error message
    if result.error_message:
        lines.append(f"  Error: {result.error_message}")

    # Detailed failures
    if not result.interface_matches or verbose:
        if result.missing_exports:
            lines.append("")
            lines.append("  Missing exports:")
            for name in result.missing_exports:
                lines.append(f"    - {name}")

        if result.type_mismatches:
            lines.append("")
            lines.append("  Type mismatches:")
            for mismatch in result.type_mismatches:
                lines.append(f"    - {mismatch}")

        if verbose and result.check_results:
            lines.append("")
            lines.append("  Check details:")
            for check in result.check_results:
                status = "✓" if check.passed else "✗"
                lines.append(f"    {status} {check.name}")
                if verbose and not check.passed:
                    lines.append(f"        Expected: {check.expected}")
                    lines.append(f"        Actual: {check.actual}")
                    if check.error_message:
                        lines.append(f"        Error: {check.error_message}")

    return "\n".join(lines)


def format_escape_hatch_summary(
    results: list[HandWrittenVerificationResult],
) -> str:
    """Format a summary of escape hatch verification results.

    Args:
        results: List of escape hatch verification results.

    Returns:
        Formatted summary string.
    """
    if not results:
        return ""

    total = len(results)
    passed = sum(1 for r in results if r.interface_matches)
    failed = total - passed

    lines = []
    lines.append("-" * 60)
    lines.append(f"Escape Hatch Summary: {passed}/{total} interfaces matched")

    if failed > 0:
        lines.append("")
        lines.append("Failed interfaces:")
        for r in results:
            if not r.interface_matches:
                lines.append(f"  - {r.module_name}: {r.module_path}")
                if r.missing_exports:
                    lines.append(f"      Missing: {', '.join(r.missing_exports)}")

    lines.append("-" * 60)

    return "\n".join(lines)
