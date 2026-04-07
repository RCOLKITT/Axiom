"""Verification for hand-written escape hatch modules.

Verifies that hand-written modules export the interfaces declared
in spec dependencies.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from axiom.spec.models import (
    Dependency,
    FunctionSignature,
    HandWrittenInterface,
)

logger = structlog.get_logger()


@dataclass
class InterfaceCheckResult:
    """Result of checking a single interface element.

    Attributes:
        name: Name of the function/class being checked.
        passed: Whether the check passed.
        expected: What was expected.
        actual: What was found.
        error_message: Description of the failure (if any).
    """

    name: str
    passed: bool
    expected: str
    actual: str
    error_message: str | None = None


@dataclass
class HandWrittenVerificationResult:
    """Result of verifying a hand-written module.

    Attributes:
        module_name: Name of the module being verified.
        module_path: Path to the module file.
        interface_matches: Whether the interface matches overall.
        missing_exports: List of expected exports that weren't found.
        type_mismatches: List of type mismatches found.
        check_results: Detailed results for each check.
        error_message: Overall error message if verification failed.
    """

    module_name: str
    module_path: str
    interface_matches: bool
    missing_exports: list[str] = field(default_factory=list)
    type_mismatches: list[str] = field(default_factory=list)
    check_results: list[InterfaceCheckResult] = field(default_factory=list)
    error_message: str | None = None


def verify_hand_written_interface(
    module_path: Path,
    interface: HandWrittenInterface,
    project_root: Path | None = None,
) -> HandWrittenVerificationResult:
    """Verify a hand-written module exports what the interface declares.

    Checks:
    1. All declared functions exist
    2. Functions have correct number of parameters
    3. Functions have approximately matching signatures (best effort)

    Args:
        module_path: Path to the module file.
        interface: The declared interface to verify against.
        project_root: Project root for resolving relative module paths.

    Returns:
        HandWrittenVerificationResult with verification details.
    """
    # Resolve the actual path
    if project_root and not module_path.is_absolute():
        full_path = project_root / module_path
    else:
        full_path = module_path

    # Check if file exists
    if not full_path.exists():
        return HandWrittenVerificationResult(
            module_name=interface.module_path,
            module_path=str(module_path),
            interface_matches=False,
            error_message=f"Module file not found: {full_path}",
        )

    # Try to load the module
    try:
        module = _load_module_from_path(full_path)
    except Exception as e:
        return HandWrittenVerificationResult(
            module_name=interface.module_path,
            module_path=str(module_path),
            interface_matches=False,
            error_message=f"Failed to load module: {e}",
        )

    # Verify each function in the interface
    missing_exports: list[str] = []
    type_mismatches: list[str] = []
    check_results: list[InterfaceCheckResult] = []

    for func_sig in interface.functions:
        result = _verify_function(module, func_sig)
        check_results.append(result)

        if not result.passed:
            if "not found" in (result.error_message or "").lower():
                missing_exports.append(func_sig.name)
            elif "mismatch" in (result.error_message or "").lower():
                type_mismatches.append(f"{func_sig.name}: {result.error_message}")

    interface_matches = all(r.passed for r in check_results)

    return HandWrittenVerificationResult(
        module_name=interface.module_path,
        module_path=str(module_path),
        interface_matches=interface_matches,
        missing_exports=missing_exports,
        type_mismatches=type_mismatches,
        check_results=check_results,
    )


def _load_module_from_path(module_path: Path) -> Any:
    """Load a Python module from a file path.

    Args:
        module_path: Path to the .py file.

    Returns:
        The loaded module object.

    Raises:
        ImportError: If the module cannot be loaded.
    """
    module_name = module_path.stem

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create module spec for {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        # Clean up partial module
        sys.modules.pop(module_name, None)
        raise ImportError(f"Error executing module: {e}") from e

    return module


def _verify_function(module: Any, func_sig: FunctionSignature) -> InterfaceCheckResult:
    """Verify a single function in a module.

    Args:
        module: The loaded module.
        func_sig: The expected function signature.

    Returns:
        InterfaceCheckResult for this function.
    """
    # Check if function exists
    if not hasattr(module, func_sig.name):
        return InterfaceCheckResult(
            name=func_sig.name,
            passed=False,
            expected=f"function {func_sig.name}",
            actual="not found",
            error_message=f"Function '{func_sig.name}' not found in module",
        )

    func = getattr(module, func_sig.name)

    # Check if it's callable
    if not callable(func):
        return InterfaceCheckResult(
            name=func_sig.name,
            passed=False,
            expected="callable",
            actual=f"{type(func).__name__}",
            error_message=f"'{func_sig.name}' is not callable",
        )

    # Check if async matches
    if func_sig.is_async and not inspect.iscoroutinefunction(func):
        return InterfaceCheckResult(
            name=func_sig.name,
            passed=False,
            expected="async function",
            actual="sync function",
            error_message=f"'{func_sig.name}' should be async but is not",
        )

    if not func_sig.is_async and inspect.iscoroutinefunction(func):
        return InterfaceCheckResult(
            name=func_sig.name,
            passed=False,
            expected="sync function",
            actual="async function",
            error_message=f"'{func_sig.name}' should be sync but is async",
        )

    # Check parameter count
    try:
        sig = inspect.signature(func)
        actual_params = [
            p
            for p in sig.parameters.values()
            if p.kind
            not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            )
        ]
        expected_param_count = len(func_sig.parameters)

        if len(actual_params) != expected_param_count:
            return InterfaceCheckResult(
                name=func_sig.name,
                passed=False,
                expected=f"{expected_param_count} parameters",
                actual=f"{len(actual_params)} parameters",
                error_message=f"Parameter count mismatch for '{func_sig.name}'",
            )

        # Check parameter names (optional, best effort)
        for i, (actual_param, expected_param) in enumerate(zip(actual_params, func_sig.parameters)):
            if actual_param.name != expected_param.name:
                # Parameter name mismatch - warn but don't fail
                logger.debug(
                    "Parameter name mismatch",
                    function=func_sig.name,
                    position=i,
                    expected=expected_param.name,
                    actual=actual_param.name,
                )

    except ValueError:
        # Can't inspect signature (e.g., built-in)
        pass

    # All checks passed
    expected_str = _format_function_signature(func_sig)
    actual_str = _format_actual_signature(func)

    return InterfaceCheckResult(
        name=func_sig.name,
        passed=True,
        expected=expected_str,
        actual=actual_str,
    )


def _format_function_signature(func_sig: FunctionSignature) -> str:
    """Format a FunctionSignature as a string.

    Args:
        func_sig: The function signature.

    Returns:
        String representation like "func(a: int, b: str) -> bool".
    """
    params = ", ".join(f"{p.name}: {p.type}" for p in func_sig.parameters)
    async_prefix = "async " if func_sig.is_async else ""
    return f"{async_prefix}def {func_sig.name}({params}) -> {func_sig.returns.type}"


def _format_actual_signature(func: Any) -> str:
    """Format an actual function's signature as a string.

    Args:
        func: The function object.

    Returns:
        String representation of the signature.
    """
    try:
        sig = inspect.signature(func)
        async_prefix = "async " if inspect.iscoroutinefunction(func) else ""
        return f"{async_prefix}def {func.__name__}{sig}"
    except (ValueError, TypeError):
        return f"def {getattr(func, '__name__', str(func))}(...)"


def verify_dependency_interface(
    dependency: Dependency,
    project_root: Path,
) -> HandWrittenVerificationResult | None:
    """Verify a dependency's interface if it's a hand-written module.

    Args:
        dependency: The dependency to verify.
        project_root: Project root for resolving paths.

    Returns:
        HandWrittenVerificationResult if this is a hand-written dependency
        with a structured interface, None otherwise.
    """
    if dependency.type != "hand-written":
        return None

    interface = dependency.get_hand_written_interface()
    if interface is None:
        # Has dict interface, not structured - can't verify
        return None

    module_path = Path(interface.module_path)
    return verify_hand_written_interface(module_path, interface, project_root)


def verify_all_hand_written_dependencies(
    dependencies: list[Dependency],
    project_root: Path,
) -> list[HandWrittenVerificationResult]:
    """Verify all hand-written dependencies in a list.

    Args:
        dependencies: List of dependencies to check.
        project_root: Project root for resolving paths.

    Returns:
        List of verification results for hand-written dependencies.
    """
    results: list[HandWrittenVerificationResult] = []

    for dep in dependencies:
        result = verify_dependency_interface(dep, project_root)
        if result is not None:
            results.append(result)

    return results
