"""Models for verification results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CheckStatus(Enum):
    """Status of a single check."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class ExampleResult:
    """Result of running a single example.

    Attributes:
        name: Name of the example.
        status: Whether the example passed, failed, etc.
        expected: The expected output.
        actual: The actual output (if available).
        error_message: Error message if failed.
        duration_ms: Execution time in milliseconds.
    """

    name: str
    status: CheckStatus
    expected: Any = None
    actual: Any = None
    error_message: str | None = None
    duration_ms: int = 0


@dataclass
class InvariantResult:
    """Result of running a single invariant.

    Attributes:
        description: Description of the invariant.
        status: Whether the invariant passed.
        check: The check expression (if any).
        counterexample: A failing input if found.
        error_message: Error message if failed.
        iterations: Number of test iterations run.
    """

    description: str
    status: CheckStatus
    check: str | None = None
    counterexample: dict[str, Any] | None = None
    error_message: str | None = None
    iterations: int = 0


@dataclass
class PerformanceResult:
    """Result of a performance test.

    Attributes:
        name: Name of the performance test.
        status: Whether the test passed.
        constraint_ms: Maximum allowed response time.
        avg_ms: Average response time.
        median_ms: Median response time.
        p95_ms: 95th percentile response time.
        max_ms: Maximum response time.
        min_ms: Minimum response time.
        samples: Number of samples collected.
        error_message: Error message if failed.
    """

    name: str
    status: CheckStatus
    constraint_ms: int | None = None
    avg_ms: float | None = None
    median_ms: float | None = None
    p95_ms: float | None = None
    max_ms: float | None = None
    min_ms: float | None = None
    samples: int = 0
    error_message: str | None = None


@dataclass
class VerificationResult:
    """Complete verification result for a spec.

    Attributes:
        spec_name: Name of the spec.
        success: Whether all checks passed.
        example_results: Results from running examples.
        invariant_results: Results from running invariants.
        performance_results: Results from running performance tests.
        duration_ms: Total verification time.
        error: Global error message if verification couldn't complete.
    """

    spec_name: str
    success: bool
    example_results: list[ExampleResult] = field(default_factory=list)
    invariant_results: list[InvariantResult] = field(default_factory=list)
    performance_results: list[PerformanceResult] = field(default_factory=list)
    duration_ms: int = 0
    error: str | None = None

    @property
    def examples_passed(self) -> int:
        """Count of passed examples."""
        return sum(1 for r in self.example_results if r.status == CheckStatus.PASSED)

    @property
    def examples_failed(self) -> int:
        """Count of failed examples."""
        return sum(1 for r in self.example_results if r.status == CheckStatus.FAILED)

    @property
    def examples_total(self) -> int:
        """Total number of examples."""
        return len(self.example_results)

    @property
    def invariants_passed(self) -> int:
        """Count of passed invariants."""
        return sum(1 for r in self.invariant_results if r.status == CheckStatus.PASSED)

    @property
    def invariants_failed(self) -> int:
        """Count of failed invariants."""
        return sum(1 for r in self.invariant_results if r.status == CheckStatus.FAILED)

    @property
    def invariants_total(self) -> int:
        """Total number of invariants."""
        return len(self.invariant_results)

    @property
    def performance_passed(self) -> int:
        """Count of passed performance tests."""
        return sum(1 for r in self.performance_results if r.status == CheckStatus.PASSED)

    @property
    def performance_failed(self) -> int:
        """Count of failed performance tests."""
        return sum(1 for r in self.performance_results if r.status == CheckStatus.FAILED)

    @property
    def performance_total(self) -> int:
        """Total number of performance tests."""
        return len(self.performance_results)

    def get_failure_messages(self) -> list[str]:
        """Get all failure messages for retry prompts.

        Returns:
            List of failure descriptions.
        """
        failures = []

        for ex_result in self.example_results:
            if ex_result.status == CheckStatus.FAILED:
                if ex_result.error_message:
                    failures.append(f"Example '{ex_result.name}': {ex_result.error_message}")
                else:
                    failures.append(
                        f"Example '{ex_result.name}': expected {ex_result.expected}, got {ex_result.actual}"
                    )

        for inv_result in self.invariant_results:
            if inv_result.status == CheckStatus.FAILED:
                if inv_result.counterexample:
                    failures.append(
                        f"Invariant '{inv_result.description}' failed for input: {inv_result.counterexample}"
                    )
                elif inv_result.error_message:
                    failures.append(
                        f"Invariant '{inv_result.description}': {inv_result.error_message}"
                    )

        for perf_result in self.performance_results:
            if perf_result.status == CheckStatus.FAILED and perf_result.error_message:
                failures.append(f"Performance '{perf_result.name}': {perf_result.error_message}")

        if self.error:
            failures.append(f"Verification error: {self.error}")

        return failures
