"""YAML parser for .axiom spec files.

Parses YAML into Pydantic spec models with strict validation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
import yaml
from pydantic import ValidationError

from axiom.errors import SpecParseError, SpecValidationError
from axiom.spec.models import (
    Constraints,
    Dependency,
    ErrorResponse,
    Example,
    FastAPIInterface,
    FunctionInterface,
    Invariant,
    Metadata,
    Parameter,
    PerformanceConstraints,
    RequestBody,
    RequestField,
    ResponseSchema,
    Returns,
    Spec,
    SuccessResponse,
)

logger = structlog.get_logger()


def parse_spec_file(file_path: Path | str) -> Spec:
    """Parse a .axiom spec file.

    Args:
        file_path: Path to the .axiom file.

    Returns:
        Parsed Spec object.

    Raises:
        SpecParseError: If the file cannot be read or parsed as YAML.
        SpecValidationError: If the spec is syntactically valid but semantically invalid.
    """
    path = Path(file_path)

    if not path.exists():
        raise SpecParseError(
            "File not found. Check that the path is correct.",
            file_path=str(path),
        )

    if not path.suffix == ".axiom":
        raise SpecParseError(
            f"Expected .axiom extension, got '{path.suffix}'. Rename the file or check the path.",
            file_path=str(path),
        )

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as e:
        raise SpecParseError(
            f"Cannot read file: {e}",
            file_path=str(path),
        ) from e

    logger.debug("Parsing spec file", path=str(path))
    return parse_spec(content, file_path=str(path))


def parse_spec(content: str, file_path: str = "<string>") -> Spec:
    """Parse spec content from a string.

    Args:
        content: YAML content of the spec.
        file_path: Path for error messages (default: "<string>").

    Returns:
        Parsed Spec object.

    Raises:
        SpecParseError: If the content cannot be parsed as YAML.
        SpecValidationError: If the spec is syntactically valid but semantically invalid.
    """
    # Parse YAML
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        # Extract line number if available
        line = None
        if hasattr(e, "problem_mark") and e.problem_mark is not None:
            line = e.problem_mark.line + 1  # YAML uses 0-indexed lines

        raise SpecParseError(
            f"Invalid YAML syntax: {e}",
            file_path=file_path,
            line=line,
        ) from e

    if data is None:
        raise SpecParseError(
            "Empty spec file. Add required fields: axiom, metadata, intent, interface.",
            file_path=file_path,
        )

    if not isinstance(data, dict):
        raise SpecParseError(
            f"Spec must be a YAML mapping, got {type(data).__name__}",
            file_path=file_path,
        )

    # Validate required top-level keys
    required_keys = {"axiom", "metadata", "intent", "interface"}
    missing_keys = required_keys - set(data.keys())
    if missing_keys:
        raise SpecParseError(
            f"Missing required keys: {', '.join(sorted(missing_keys))}. "
            "Add these to your spec file.",
            file_path=file_path,
        )

    # Check for unknown keys
    known_keys = {
        "axiom",
        "metadata",
        "intent",
        "interface",
        "examples",
        "invariants",
        "constraints",
        "dependencies",
    }
    unknown_keys = set(data.keys()) - known_keys
    if unknown_keys:
        raise SpecValidationError(
            f"Unknown keys: {', '.join(sorted(unknown_keys))}. "
            f"Valid keys are: {', '.join(sorted(known_keys))}",
            file_path=file_path,
        )

    return _build_spec(data, file_path)


def _build_spec(data: dict[str, Any], file_path: str) -> Spec:
    """Build a Spec from parsed YAML data.

    Args:
        data: Parsed YAML dictionary.
        file_path: Path for error messages.

    Returns:
        Validated Spec object.

    Raises:
        SpecValidationError: If the spec data is invalid.
    """
    try:
        # Build metadata
        metadata = _build_metadata(data["metadata"], file_path)

        # Build interface based on target
        interface: FunctionInterface | FastAPIInterface
        if metadata.target == "python:fastapi":
            interface = _build_fastapi_interface(data["interface"], file_path)
        else:
            interface = _build_function_interface(data["interface"], file_path)

        # Build examples
        examples = _build_examples(data.get("examples", []), file_path)

        # Build invariants
        invariants = _build_invariants(data.get("invariants", []), file_path)

        # Build constraints
        constraints = _build_constraints(data.get("constraints", {}), file_path)

        # Build dependencies
        dependencies = _build_dependencies(data.get("dependencies", []), file_path)

        # Construct and validate the complete spec
        return Spec(
            axiom=data["axiom"],
            metadata=metadata,
            intent=data["intent"],
            interface=interface,
            examples=examples,
            invariants=invariants,
            constraints=constraints,
            dependencies=dependencies,
        )

    except ValidationError as e:
        # Convert Pydantic validation errors to our error type
        errors = "; ".join(
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in e.errors()
        )
        raise SpecValidationError(
            f"Validation failed: {errors}",
            file_path=file_path,
        ) from e


def _build_metadata(data: dict[str, Any], file_path: str) -> Metadata:
    """Build Metadata from raw data.

    Args:
        data: Raw metadata dictionary.
        file_path: Path for error messages.

    Returns:
        Validated Metadata object.
    """
    try:
        return Metadata(**data)
    except ValidationError as e:
        errors = "; ".join(
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in e.errors()
        )
        raise SpecValidationError(
            f"Invalid metadata: {errors}",
            file_path=file_path,
            field="metadata",
        ) from e


def _build_function_interface(data: dict[str, Any], file_path: str) -> FunctionInterface:
    """Build FunctionInterface from raw data.

    Args:
        data: Raw interface dictionary.
        file_path: Path for error messages.

    Returns:
        Validated FunctionInterface object.
    """
    try:
        # Build parameters
        params = []
        for p in data.get("parameters", []):
            params.append(Parameter(**p))

        # Build returns
        returns_data = data.get("returns", {})
        returns = Returns(**returns_data)

        return FunctionInterface(
            function_name=data.get("function_name", ""),
            parameters=params,
            returns=returns,
        )
    except ValidationError as e:
        errors = "; ".join(
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in e.errors()
        )
        raise SpecValidationError(
            f"Invalid interface: {errors}",
            file_path=file_path,
            field="interface",
        ) from e
    except (KeyError, TypeError) as e:
        raise SpecValidationError(
            f"Invalid interface structure: {e}",
            file_path=file_path,
            field="interface",
        ) from e


def _build_fastapi_interface(data: dict[str, Any], file_path: str) -> FastAPIInterface:
    """Build FastAPIInterface from raw data.

    Args:
        data: Raw interface dictionary.
        file_path: Path for error messages.

    Returns:
        Validated FastAPIInterface object.
    """
    try:
        # Build path parameters
        path_params = []
        for p in data.get("path_parameters", []):
            path_params.append(Parameter(**p))

        # Build query parameters
        query_params = []
        for p in data.get("query_parameters", []):
            query_params.append(Parameter(**p))

        # Build request body
        request_body = None
        if "request_body" in data and data["request_body"]:
            fields = []
            for f in data["request_body"].get("fields", []):
                fields.append(RequestField(**f))
            request_body = RequestBody(fields=fields)

        # Build response schema
        response_data = data.get("response", {})
        success_data = response_data.get("success", {})
        success = SuccessResponse(
            status=success_data.get("status", 200),
            body=success_data.get("body"),
        )

        errors = []
        for err in response_data.get("errors", []):
            errors.append(ErrorResponse(**err))

        response = ResponseSchema(success=success, errors=errors)

        return FastAPIInterface(
            method=data.get("method", "GET"),
            path=data.get("path", "/"),
            function_name=data.get("function_name", ""),
            path_parameters=path_params,
            query_parameters=query_params,
            request_body=request_body,
            response=response,
        )
    except ValidationError as e:
        errors_str = "; ".join(
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in e.errors()
        )
        raise SpecValidationError(
            f"Invalid FastAPI interface: {errors_str}",
            file_path=file_path,
            field="interface",
        ) from e
    except (KeyError, TypeError) as e:
        raise SpecValidationError(
            f"Invalid FastAPI interface structure: {e}",
            file_path=file_path,
            field="interface",
        ) from e


def _build_constraints(data: dict[str, Any], file_path: str) -> Constraints:
    """Build Constraints from raw data.

    Args:
        data: Raw constraints dictionary.
        file_path: Path for error messages.

    Returns:
        Validated Constraints object.
    """
    try:
        perf_data = data.get("performance", {})
        performance = PerformanceConstraints(
            max_response_time_ms=perf_data.get("max_response_time_ms"),
        )
        return Constraints(performance=performance)
    except ValidationError as e:
        errors = "; ".join(
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in e.errors()
        )
        raise SpecValidationError(
            f"Invalid constraints: {errors}",
            file_path=file_path,
            field="constraints",
        ) from e


def _build_examples(data: list[Any], file_path: str) -> list[Example]:
    """Build list of Examples from raw data.

    Args:
        data: List of raw example dictionaries.
        file_path: Path for error messages.

    Returns:
        List of validated Example objects.
    """
    examples = []
    for i, ex in enumerate(data):
        if not isinstance(ex, dict):
            raise SpecValidationError(
                f"Example {i} must be a mapping, got {type(ex).__name__}",
                file_path=file_path,
                field=f"examples[{i}]",
            )

        if "name" not in ex:
            raise SpecValidationError(
                f"Example {i} is missing required 'name' field",
                file_path=file_path,
                field=f"examples[{i}]",
            )

        if "expected_output" not in ex:
            raise SpecValidationError(
                f"Example '{ex.get('name', i)}' is missing required 'expected_output' field",
                file_path=file_path,
                field=f"examples[{i}]",
            )

        try:
            examples.append(Example.from_raw(ex))
        except Exception as e:
            raise SpecValidationError(
                f"Invalid example '{ex.get('name', i)}': {e}",
                file_path=file_path,
                field=f"examples[{i}]",
            ) from e

    return examples


def _build_invariants(data: list[Any], file_path: str) -> list[Invariant]:
    """Build list of Invariants from raw data.

    Args:
        data: List of raw invariant dictionaries.
        file_path: Path for error messages.

    Returns:
        List of validated Invariant objects.
    """
    invariants = []
    for i, inv in enumerate(data):
        if not isinstance(inv, dict):
            raise SpecValidationError(
                f"Invariant {i} must be a mapping, got {type(inv).__name__}",
                file_path=file_path,
                field=f"invariants[{i}]",
            )

        if "description" not in inv:
            raise SpecValidationError(
                f"Invariant {i} is missing required 'description' field",
                file_path=file_path,
                field=f"invariants[{i}]",
            )

        try:
            invariants.append(Invariant(**inv))
        except ValidationError as e:
            errors = "; ".join(
                f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in e.errors()
            )
            raise SpecValidationError(
                f"Invalid invariant {i}: {errors}",
                file_path=file_path,
                field=f"invariants[{i}]",
            ) from e

    return invariants


def _build_dependencies(data: list[Any], file_path: str) -> list[Dependency]:
    """Build list of Dependencies from raw data.

    Args:
        data: List of raw dependency dictionaries.
        file_path: Path for error messages.

    Returns:
        List of validated Dependency objects.
    """
    dependencies = []
    for i, dep in enumerate(data):
        if not isinstance(dep, dict):
            raise SpecValidationError(
                f"Dependency {i} must be a mapping, got {type(dep).__name__}",
                file_path=file_path,
                field=f"dependencies[{i}]",
            )

        if "name" not in dep:
            raise SpecValidationError(
                f"Dependency {i} is missing required 'name' field",
                file_path=file_path,
                field=f"dependencies[{i}]",
            )

        try:
            dependencies.append(Dependency(**dep))
        except ValidationError as e:
            errors = "; ".join(
                f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in e.errors()
            )
            raise SpecValidationError(
                f"Invalid dependency {i}: {errors}",
                file_path=file_path,
                field=f"dependencies[{i}]",
            ) from e

    return dependencies
