"""Run performance tests against generated code."""

from __future__ import annotations

import contextlib
import importlib.util
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import structlog

from axiom.spec.models import Example, Spec
from axiom.verify.models import CheckStatus, PerformanceResult

logger = structlog.get_logger()


def run_performance_tests(
    spec: Spec,
    code: str,
    num_iterations: int = 10,
) -> list[PerformanceResult]:
    """Run performance tests for a spec.

    Args:
        spec: The parsed spec with performance constraints.
        code: The generated Python code.
        num_iterations: Number of iterations to run for timing.

    Returns:
        List of PerformanceResult.
    """
    max_response_time_ms = spec.constraints.performance.max_response_time_ms
    if max_response_time_ms is None:
        logger.debug("No performance constraints defined", spec=spec.spec_name)
        return []

    if not spec.examples:
        logger.debug("No examples to run for performance test", spec=spec.spec_name)
        return []

    if spec.is_fastapi:
        return _run_http_performance(spec, code, max_response_time_ms, num_iterations)
    else:
        return _run_function_performance(spec, code, max_response_time_ms, num_iterations)


def _run_function_performance(
    spec: Spec,
    code: str,
    max_response_time_ms: int,
    num_iterations: int,
) -> list[PerformanceResult]:
    """Run performance tests for a function."""
    try:
        func = _load_function(code, spec.function_name)
    except Exception as e:
        return [
            PerformanceResult(
                name="performance",
                status=CheckStatus.ERROR,
                error_message=f"Failed to load function: {e}",
            )
        ]

    # Run warmup
    for example in spec.examples[:2]:
        with contextlib.suppress(Exception):
            func(**example.input)

    # Run timed iterations
    times_ms: list[float] = []
    for _ in range(num_iterations):
        for example in spec.examples:
            try:
                start = time.perf_counter()
                func(**example.input)
                end = time.perf_counter()
                times_ms.append((end - start) * 1000)
            except Exception:
                pass

    if not times_ms:
        return [
            PerformanceResult(
                name="performance",
                status=CheckStatus.ERROR,
                error_message="No successful runs to measure",
            )
        ]

    return _analyze_times(times_ms, max_response_time_ms)


def _run_http_performance(
    spec: Spec,
    code: str,
    max_response_time_ms: int,
    num_iterations: int,
) -> list[PerformanceResult]:
    """Run performance tests for a FastAPI endpoint."""
    try:
        app, router = _load_router(code)
    except Exception as e:
        return [
            PerformanceResult(
                name="performance",
                status=CheckStatus.ERROR,
                error_message=f"Failed to load router: {e}",
            )
        ]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(app)
    except ImportError:
        return [
            PerformanceResult(
                name="performance",
                status=CheckStatus.ERROR,
                error_message="FastAPI test client not available",
            )
        ]

    interface = spec.get_fastapi_interface()

    # Run warmup
    for example in spec.examples[:2]:
        with contextlib.suppress(Exception):
            _make_request(client, example, interface.method, interface.path)

    # Run timed iterations
    times_ms: list[float] = []
    for _ in range(num_iterations):
        for example in spec.examples:
            try:
                start = time.perf_counter()
                _make_request(client, example, interface.method, interface.path)
                end = time.perf_counter()
                times_ms.append((end - start) * 1000)
            except Exception:
                pass

    if not times_ms:
        return [
            PerformanceResult(
                name="performance",
                status=CheckStatus.ERROR,
                error_message="No successful runs to measure",
            )
        ]

    return _analyze_times(times_ms, max_response_time_ms)


def _make_request(
    client: Any,
    example: Example,
    method: str,
    path: str,
) -> Any:
    """Make an HTTP request for the example."""
    request_kwargs: dict[str, Any] = {}
    actual_path = path

    for key, value in example.input.items():
        placeholder = f"{{{key}}}"
        if placeholder in actual_path:
            actual_path = actual_path.replace(placeholder, str(value))

    body_fields = {}
    query_fields = {}
    for key, value in example.input.items():
        if f"{{{key}}}" not in path:
            if method.upper() in ("POST", "PUT", "PATCH"):
                body_fields[key] = value
            else:
                query_fields[key] = value

    if body_fields:
        request_kwargs["json"] = body_fields
    if query_fields:
        request_kwargs["params"] = query_fields

    return getattr(client, method.lower())(actual_path, **request_kwargs)


def _analyze_times(times_ms: list[float], max_response_time_ms: int) -> list[PerformanceResult]:
    """Analyze timing results and return performance results."""
    avg_ms = statistics.mean(times_ms)
    median_ms = statistics.median(times_ms)
    p95_ms = sorted(times_ms)[int(len(times_ms) * 0.95)] if len(times_ms) >= 20 else max(times_ms)
    max_ms = max(times_ms)
    min_ms = min(times_ms)

    # Check if average meets constraint
    passes = avg_ms <= max_response_time_ms

    result = PerformanceResult(
        name="response_time",
        status=CheckStatus.PASSED if passes else CheckStatus.FAILED,
        constraint_ms=max_response_time_ms,
        avg_ms=round(avg_ms, 2),
        median_ms=round(median_ms, 2),
        p95_ms=round(p95_ms, 2),
        max_ms=round(max_ms, 2),
        min_ms=round(min_ms, 2),
        samples=len(times_ms),
    )

    if not passes:
        result.error_message = (
            f"Average response time {avg_ms:.2f}ms exceeds constraint of {max_response_time_ms}ms"
        )

    return [result]


def _load_function(code: str, function_name: str) -> Any:
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
        module_name = f"_axiom_perf_{temp_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, temp_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Could not load module from {temp_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        if not hasattr(module, function_name):
            raise ValueError(f"Function '{function_name}' not found")

        return getattr(module, function_name)

    finally:
        temp_path.unlink(missing_ok=True)
        if module_name in sys.modules:
            del sys.modules[module_name]


def _load_router(code: str) -> tuple[Any, Any]:
    """Load a FastAPI router from code string."""
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(code)
        temp_path = Path(f.name)

    try:
        module_name = f"_axiom_perf_router_{temp_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, temp_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Could not load module from {temp_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        if not hasattr(module, "router"):
            raise ValueError("'router' not found in module")

        router = module.router

        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        return app, router

    finally:
        temp_path.unlink(missing_ok=True)
        if module_name in sys.modules:
            del sys.modules[module_name]
