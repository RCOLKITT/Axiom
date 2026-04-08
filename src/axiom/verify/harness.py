"""Verification harness orchestrating all verification layers."""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from axiom.spec.models import Spec
from axiom.spec.parser import parse_spec_file
from axiom.verify.example_runner import run_examples
from axiom.verify.http_runner import run_http_examples
from axiom.verify.models import CheckStatus, VerificationResult
from axiom.verify.performance_runner import run_performance_tests
from axiom.verify.property_runner import run_invariants
from axiom.verify.typescript_property import run_typescript_invariants
from axiom.verify.typescript_runner import run_typescript_examples

if TYPE_CHECKING:
    from axiom.config.settings import Settings

logger = structlog.get_logger()


def verify_spec(
    spec: Spec,
    code: str,
    settings: Settings,
) -> VerificationResult:
    """Verify generated code against a spec.

    Runs all verification layers:
    1. Example-based tests
    2. Property-based invariant tests

    Supports Python and TypeScript targets.

    Args:
        spec: The parsed spec.
        code: The generated code.
        settings: Axiom settings.

    Returns:
        VerificationResult with all check results.
    """
    start_time = time.time()

    # Detect target language
    target = spec.metadata.target
    language = target.split(":")[0].lower() if target else "python"

    logger.info("Starting verification", spec=spec.spec_name, language=language)

    example_results = []
    invariant_results = []
    performance_results = []

    # Run examples
    if settings.verification.run_examples:
        if language == "typescript":
            logger.debug("Running TypeScript examples")
            example_results = run_typescript_examples(code, spec)
        elif spec.is_fastapi:
            logger.debug("Running HTTP examples")
            example_results = run_http_examples(spec, code)
        else:
            logger.debug("Running Python examples")
            generated_dir = settings.get_generated_dir()
            example_results = run_examples(spec, code, generated_dir)
    else:
        logger.debug("Examples disabled")

    # Run invariants
    if settings.verification.run_invariants and not spec.is_fastapi:
        if language == "typescript":
            logger.debug("Running TypeScript invariants")
            invariant_results = run_typescript_invariants(
                code,
                spec,
                test_count=settings.verification.hypothesis_max_examples,
            )
        else:
            logger.debug("Running Python invariants")
            invariant_results = run_invariants(
                spec,
                code,
                max_examples=settings.verification.hypothesis_max_examples,
            )
    else:
        logger.debug("Invariants disabled or not applicable")

    # Run performance tests if constraints are defined
    if spec.constraints.performance.max_response_time_ms is not None:
        logger.debug("Running performance tests")
        performance_results = run_performance_tests(spec, code)

    duration_ms = int((time.time() - start_time) * 1000)

    # Determine overall success
    all_examples_pass = all(r.status == CheckStatus.PASSED for r in example_results)
    all_invariants_pass = all(
        r.status in (CheckStatus.PASSED, CheckStatus.SKIPPED) for r in invariant_results
    )
    all_performance_pass = all(
        r.status in (CheckStatus.PASSED, CheckStatus.SKIPPED) for r in performance_results
    )
    success = all_examples_pass and all_invariants_pass and all_performance_pass

    result = VerificationResult(
        spec_name=spec.spec_name,
        success=success,
        example_results=example_results,
        invariant_results=invariant_results,
        performance_results=performance_results,
        duration_ms=duration_ms,
    )

    logger.info(
        "Verification complete",
        spec=spec.spec_name,
        success=success,
        examples=f"{result.examples_passed}/{result.examples_total}",
        invariants=f"{result.invariants_passed}/{result.invariants_total}",
        duration_ms=duration_ms,
    )

    return result


def verify_from_file(
    spec_path: Path | str,
    code_path: Path | str,
    settings: Settings,
) -> VerificationResult:
    """Verify code from files.

    Args:
        spec_path: Path to the .axiom spec file.
        code_path: Path to the generated Python file.
        settings: Axiom settings.

    Returns:
        VerificationResult.
    """
    spec_path = Path(spec_path)
    code_path = Path(code_path)

    # Parse spec
    spec = parse_spec_file(spec_path)

    # Read code
    if not code_path.exists():
        return VerificationResult(
            spec_name=spec.spec_name,
            success=False,
            error=f"Code file not found: {code_path}. Run 'axiom build' first.",
        )

    code = code_path.read_text(encoding="utf-8")

    return verify_spec(spec, code, settings)


def verify_code_string(
    spec: Spec,
    code: str,
    settings: Settings,
) -> tuple[bool, list[str]]:
    """Verify code string and return simple pass/fail with failures.

    This is the interface used by the generator for retry loops.

    Args:
        spec: The parsed spec.
        code: The generated code.
        settings: Axiom settings.

    Returns:
        Tuple of (success, list of failure messages).
    """
    result = verify_spec(spec, code, settings)
    return result.success, result.get_failure_messages()
