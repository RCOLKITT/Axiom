"""Run HTTP examples against generated FastAPI routers."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import structlog

from axiom.spec.models import Example, Spec
from axiom.verify.models import CheckStatus, ExampleResult

logger = structlog.get_logger()


def run_http_examples(
    spec: Spec,
    code: str,
) -> list[ExampleResult]:
    """Run all HTTP examples from a FastAPI spec against generated code.

    Args:
        spec: The parsed spec with examples.
        code: The generated Python code containing the router.

    Returns:
        List of ExampleResult for each example.
    """
    if not spec.examples:
        logger.debug("No HTTP examples to run", spec=spec.spec_name)
        return []

    if not spec.is_fastapi:
        raise ValueError("run_http_examples requires a FastAPI spec")

    # Get the interface
    interface = spec.get_fastapi_interface()

    # Load the router from code
    try:
        app, router = _load_router(code)
    except Exception as e:
        # Return error results for all examples
        return [
            ExampleResult(
                name=ex.name,
                status=CheckStatus.ERROR,
                error_message=f"Failed to load router: {e}",
            )
            for ex in spec.examples
        ]

    # Create test client
    try:
        from fastapi.testclient import TestClient

        client = TestClient(app)
    except ImportError:
        return [
            ExampleResult(
                name=ex.name,
                status=CheckStatus.ERROR,
                error_message="FastAPI test client not available. Install: pip install fastapi[all]",
            )
            for ex in spec.examples
        ]

    # Run each example
    results = []
    for example in spec.examples:
        result = _run_single_http_example(
            client=client,
            example=example,
            method=interface.method,
            path=interface.path,
        )
        results.append(result)
        logger.debug(
            "HTTP example result",
            name=example.name,
            status=result.status.value,
        )

    return results


def _load_router(code: str) -> tuple[Any, Any]:
    """Load a FastAPI router from code string.

    Args:
        code: Python code containing the router.

    Returns:
        Tuple of (FastAPI app, router).

    Raises:
        ValueError: If the router cannot be loaded.
    """
    # Write code to a temporary file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(code)
        temp_path = Path(f.name)

    try:
        # Create a unique module name
        module_name = f"_axiom_generated_router_{temp_path.stem}"

        # Load the module
        spec = importlib.util.spec_from_file_location(module_name, temp_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Could not load module from {temp_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Get the router
        if not hasattr(module, "router"):
            available = [n for n in dir(module) if not n.startswith("_")]
            raise ValueError(f"'router' not found in module. Available: {available}")

        router = module.router

        # Create a FastAPI app and include the router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        return app, router

    finally:
        # Clean up
        temp_path.unlink(missing_ok=True)
        if module_name in sys.modules:
            del sys.modules[module_name]


def _run_single_http_example(
    client: Any,
    example: Example,
    method: str,
    path: str,
) -> ExampleResult:
    """Run a single HTTP example.

    Args:
        client: FastAPI TestClient.
        example: The example to run.
        method: HTTP method (GET, POST, etc.).
        path: URL path.

    Returns:
        ExampleResult with pass/fail status.
    """
    start_time = time.time()

    try:
        # Build request
        request_kwargs: dict[str, Any] = {}

        # Handle path parameters by substituting them into the path
        actual_path = path
        for key, value in example.input.items():
            placeholder = f"{{{key}}}"
            if placeholder in actual_path:
                actual_path = actual_path.replace(placeholder, str(value))
            else:
                # Not a path parameter, could be query param or body
                pass

        # Separate body fields from other fields
        body_fields = {}
        query_fields = {}
        for key, value in example.input.items():
            if f"{{{key}}}" not in path:
                # Assume POST/PUT/PATCH use body, GET uses query
                if method.upper() in ("POST", "PUT", "PATCH"):
                    body_fields[key] = value
                else:
                    query_fields[key] = value

        if body_fields:
            request_kwargs["json"] = body_fields
        if query_fields:
            request_kwargs["params"] = query_fields

        # Make request
        response = getattr(client, method.lower())(actual_path, **request_kwargs)

        duration_ms = int((time.time() - start_time) * 1000)

        # Check expected output
        if example.expected_output.is_exception():
            # Expecting an error response
            return _check_error_response(
                example=example,
                response=response,
                duration_ms=duration_ms,
            )
        else:
            # Expecting a success response
            return _check_success_response(
                example=example,
                response=response,
                duration_ms=duration_ms,
            )

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return ExampleResult(
            name=example.name,
            status=CheckStatus.ERROR,
            error_message=f"Request failed: {e}",
            duration_ms=duration_ms,
        )


def _check_success_response(
    example: Example,
    response: Any,
    duration_ms: int,
) -> ExampleResult:
    """Check a success response against expected output."""
    expected = example.expected_output.value

    # Get response body
    try:
        actual = response.json()
    except Exception:
        actual = response.text

    # Check status code (should be 2xx for success)
    if not 200 <= response.status_code < 300:
        return ExampleResult(
            name=example.name,
            status=CheckStatus.FAILED,
            expected=expected,
            actual=actual,
            error_message=f"Expected success (2xx), got {response.status_code}: {actual}",
            duration_ms=duration_ms,
        )

    # Compare response body
    if _responses_equal(actual, expected):
        return ExampleResult(
            name=example.name,
            status=CheckStatus.PASSED,
            expected=expected,
            actual=actual,
            duration_ms=duration_ms,
        )
    else:
        return ExampleResult(
            name=example.name,
            status=CheckStatus.FAILED,
            expected=expected,
            actual=actual,
            error_message=f"Response mismatch: expected {expected}, got {actual}",
            duration_ms=duration_ms,
        )


def _check_error_response(
    example: Example,
    response: Any,
    duration_ms: int,
) -> ExampleResult:
    """Check an error response against expected exception."""
    expected_exc = example.expected_output.raises
    message_contains = example.expected_output.message_contains

    # Get response body
    try:
        actual = response.json()
    except Exception:
        actual = {"detail": response.text}

    # Check status code (should be 4xx or 5xx for errors)
    if 200 <= response.status_code < 300:
        return ExampleResult(
            name=example.name,
            status=CheckStatus.FAILED,
            expected=f"raises {expected_exc}",
            actual=actual,
            error_message=f"Expected error response, got success ({response.status_code})",
            duration_ms=duration_ms,
        )

    # Extract detail message from response
    # FastAPI can return detail as string, dict, or list (for validation errors)
    detail = actual.get("detail", str(actual))
    if isinstance(detail, list):
        # FastAPI validation errors come as a list of error objects
        detail_parts = []
        for err in detail:
            if isinstance(err, dict):
                detail_parts.append(err.get("msg", str(err)))
            else:
                detail_parts.append(str(err))
        detail = " ".join(detail_parts)
    elif isinstance(detail, dict):
        detail = str(detail)

    # Check message if required
    if message_contains and message_contains.lower() not in detail.lower():
        return ExampleResult(
            name=example.name,
            status=CheckStatus.FAILED,
            expected=f'raises {expected_exc} with message containing "{message_contains}"',
            actual=f"status {response.status_code}: {detail}",
            error_message=f"Error message doesn't contain '{message_contains}'",
            duration_ms=duration_ms,
        )

    # Error response matches
    return ExampleResult(
        name=example.name,
        status=CheckStatus.PASSED,
        expected=f"raises {expected_exc}",
        actual=f"status {response.status_code}: {detail}",
        duration_ms=duration_ms,
    )


def _responses_equal(actual: Any, expected: Any) -> bool:
    """Check if two response values are equal.

    Handles flexible matching for common cases like:
    - Ignoring extra fields in actual response
    - String/int comparison for IDs

    Args:
        actual: The actual response value.
        expected: The expected response value.

    Returns:
        True if values are considered equal.
    """
    # Direct equality
    if actual == expected:
        return True

    # Handle None comparison
    if expected is None:
        return actual is None

    # Handle dict comparison (check expected keys exist in actual)
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key, exp_value in expected.items():
            if key not in actual:
                return False
            if not _responses_equal(actual[key], exp_value):
                return False
        return True

    # Handle list comparison
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return False
        return all(_responses_equal(a, e) for a, e in zip(actual, expected))

    # Handle string/number comparison (for IDs that may be stringified)
    if isinstance(expected, (int, float)) and isinstance(actual, str):
        try:
            return float(actual) == expected
        except ValueError:
            return False

    if isinstance(expected, str) and isinstance(actual, (int, float)):
        try:
            return float(expected) == actual
        except ValueError:
            return False

    return False
