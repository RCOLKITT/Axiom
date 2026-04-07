"""Pydantic models for the .axiom spec intermediate representation.

These models define the spec format for python:function and python:fastapi targets.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Parameter(BaseModel):
    """A function parameter definition.

    Attributes:
        name: Parameter name (valid Python identifier).
        type: Python type annotation as a string.
        description: Human-readable description.
        constraints: Optional constraints (e.g., "non-empty", "> 0").
    """

    name: str
    type: str
    description: str
    constraints: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate that name is a valid Python identifier."""
        if not v.isidentifier():
            raise ValueError(f"Parameter name '{v}' is not a valid Python identifier")
        return v


class Returns(BaseModel):
    """Return type definition.

    Attributes:
        type: Python type annotation as a string.
        description: Human-readable description of what is returned.
    """

    type: str
    description: str


class FunctionInterface(BaseModel):
    """Interface definition for a Python function.

    Attributes:
        function_name: Name of the function to generate.
        parameters: List of function parameters.
        returns: Return type specification.
    """

    function_name: str
    parameters: list[Parameter] = Field(default_factory=list)
    returns: Returns

    @field_validator("function_name")
    @classmethod
    def validate_function_name(cls, v: str) -> str:
        """Validate that function_name is a valid Python identifier."""
        if not v.isidentifier():
            raise ValueError(f"Function name '{v}' is not a valid Python identifier")
        return v


# ==============================================================================
# FastAPI Interface Models (Phase 2)
# ==============================================================================


class RequestField(BaseModel):
    """A field in a request body.

    Attributes:
        name: Field name.
        type: Python type annotation as a string.
        description: Human-readable description.
        constraints: Optional constraints (e.g., "non-empty", "valid email").
        required: Whether the field is required (default True).
    """

    name: str
    type: str
    description: str = ""
    constraints: str | None = None
    required: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate that name is a valid Python identifier."""
        if not v.isidentifier():
            raise ValueError(f"Field name '{v}' is not a valid Python identifier")
        return v


class RequestBody(BaseModel):
    """Request body schema for FastAPI endpoints.

    Attributes:
        fields: List of fields in the request body.
    """

    fields: list[RequestField] = Field(default_factory=list)


class SuccessResponse(BaseModel):
    """Success response specification.

    Attributes:
        status: HTTP status code (2xx).
        body: Response body schema as a dict or type string.
    """

    status: int = 200
    body: dict[str, Any] | str | None = None

    @field_validator("status")
    @classmethod
    def validate_success_status(cls, v: int) -> int:
        """Validate that status is a success code."""
        if not 200 <= v < 300:
            raise ValueError(f"Success status must be 2xx, got {v}")
        return v


class ErrorResponse(BaseModel):
    """Error response specification.

    Attributes:
        status: HTTP status code (4xx or 5xx).
        when: Condition description for when this error occurs.
        body: Optional error body schema.
    """

    status: int
    when: str
    body: dict[str, Any] | str | None = None

    @field_validator("status")
    @classmethod
    def validate_error_status(cls, v: int) -> int:
        """Validate that status is an error code."""
        if not (400 <= v < 600):
            raise ValueError(f"Error status must be 4xx or 5xx, got {v}")
        return v


class ResponseSchema(BaseModel):
    """Complete response schema with success and error cases.

    Attributes:
        success: Success response specification.
        errors: List of error response specifications.
    """

    success: SuccessResponse = Field(default_factory=SuccessResponse)
    errors: list[ErrorResponse] = Field(default_factory=list)


class FastAPIInterface(BaseModel):
    """Interface definition for a FastAPI endpoint.

    Attributes:
        method: HTTP method (GET, POST, PUT, DELETE, PATCH).
        path: URL path (e.g., "/api/users/{user_id}").
        function_name: Name of the route handler function.
        path_parameters: Parameters extracted from the path.
        query_parameters: Query string parameters.
        request_body: Request body schema (for POST/PUT/PATCH).
        response: Response schema with success and error cases.
    """

    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"]
    path: str
    function_name: str
    path_parameters: list[Parameter] = Field(default_factory=list)
    query_parameters: list[Parameter] = Field(default_factory=list)
    request_body: RequestBody | None = None
    response: ResponseSchema = Field(default_factory=ResponseSchema)

    @field_validator("function_name")
    @classmethod
    def validate_function_name(cls, v: str) -> str:
        """Validate that function_name is a valid Python identifier."""
        if not v.isidentifier():
            raise ValueError(f"Function name '{v}' is not a valid Python identifier")
        return v

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Validate that path starts with /."""
        if not v.startswith("/"):
            raise ValueError(f"Path must start with /, got '{v}'")
        return v

    @model_validator(mode="after")
    def validate_body_for_method(self) -> FastAPIInterface:
        """Validate that request_body is only present for appropriate methods."""
        if self.method == "GET" and self.request_body is not None:
            if self.request_body.fields:
                raise ValueError("GET requests should not have a request body")
        return self


# ==============================================================================
# Constraints Models (Phase 2)
# ==============================================================================


class PerformanceConstraints(BaseModel):
    """Performance constraints for an endpoint.

    Attributes:
        max_response_time_ms: Maximum acceptable response time in milliseconds.
    """

    max_response_time_ms: int | None = None


class Constraints(BaseModel):
    """Non-functional requirements and constraints.

    Attributes:
        performance: Performance-related constraints.
    """

    performance: PerformanceConstraints = Field(default_factory=PerformanceConstraints)


# ==============================================================================
# Dependency Models (Phase 3) and Escape Hatch Models (Phase 5)
# ==============================================================================


class FunctionSignature(BaseModel):
    """A function signature for interface contracts.

    Used to declare the expected interface of a hand-written module function.

    Attributes:
        name: Function name.
        parameters: List of function parameters.
        returns: Return type specification.
        is_async: Whether the function is async.
        description: Optional description of what the function does.
    """

    name: str
    parameters: list[Parameter] = Field(default_factory=list)
    returns: Returns
    is_async: bool = False
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate that name is a valid Python identifier."""
        if not v.isidentifier():
            raise ValueError(f"Function name '{v}' is not a valid Python identifier")
        return v


class HandWrittenInterface(BaseModel):
    """Structured interface for hand-written dependencies.

    Declares the expected exports of a hand-written module that specs can
    depend on. Used for interface enforcement during verification.

    Attributes:
        module_path: Relative path to the module from project root.
        functions: List of function signatures the module must export.
        description: Optional description of the module.
    """

    module_path: str
    functions: list[FunctionSignature] = Field(default_factory=list)
    description: str | None = None

    @field_validator("module_path")
    @classmethod
    def validate_module_path(cls, v: str) -> str:
        """Validate that module_path is not empty."""
        if not v.strip():
            raise ValueError("Module path cannot be empty")
        return v


class Dependency(BaseModel):
    """A dependency on another spec or module.

    Attributes:
        name: Name of the dependency (spec name or module path).
        type: Type of dependency ('spec', 'hand-written', 'external-package').
        interface: Optional expected interface for hand-written deps.
            Can be a structured HandWrittenInterface or a dict for backward compatibility.
        version: Optional version constraint for external packages.
    """

    name: str
    type: Literal["spec", "hand-written", "external-package"] = "spec"
    interface: HandWrittenInterface | dict[str, Any] | None = None
    version: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate that name is not empty."""
        if not v.strip():
            raise ValueError("Dependency name cannot be empty")
        return v

    def get_hand_written_interface(self) -> HandWrittenInterface | None:
        """Get the interface as HandWrittenInterface if available.

        Returns:
            HandWrittenInterface if interface is structured, None otherwise.
        """
        if isinstance(self.interface, HandWrittenInterface):
            return self.interface
        return None

    def has_structured_interface(self) -> bool:
        """Check if this dependency has a structured interface.

        Returns:
            True if interface is a HandWrittenInterface.
        """
        return isinstance(self.interface, HandWrittenInterface)


# ==============================================================================
# Example and Invariant Models
# ==============================================================================


class ExpectedOutput(BaseModel):
    """Expected output for an example.

    Can be either a direct value or an exception specification.

    Attributes:
        value: The expected return value (if not raising).
        raises: Exception type name to expect.
        message_contains: Optional substring the error message must contain.
    """

    value: Any = None
    raises: str | None = None
    message_contains: str | None = None

    @classmethod
    def from_raw(cls, raw: Any) -> ExpectedOutput:
        """Create ExpectedOutput from raw YAML value.

        Args:
            raw: Raw value from YAML parsing.

        Returns:
            ExpectedOutput instance.
        """
        if isinstance(raw, dict):
            if "raises" in raw:
                return cls(
                    raises=raw["raises"],
                    message_contains=raw.get("message_contains"),
                )
            # Dict is the actual expected value
            return cls(value=raw)
        # Scalar or list value
        return cls(value=raw)

    def is_exception(self) -> bool:
        """Check if this expects an exception."""
        return self.raises is not None


class Example(BaseModel):
    """A concrete input/output example for testing.

    Attributes:
        name: Descriptive name for this example.
        input: Input values mapped to parameter names.
        expected_output: What the function should return or raise.
        precondition: Optional setup description.
        postcondition: Optional state assertion after execution.
    """

    name: str
    input: dict[str, Any]
    expected_output: ExpectedOutput
    precondition: str | None = None
    postcondition: str | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Example:
        """Create Example from raw YAML dict.

        Args:
            raw: Raw dictionary from YAML parsing.

        Returns:
            Example instance.
        """
        expected = ExpectedOutput.from_raw(raw.get("expected_output"))
        return cls(
            name=raw["name"],
            input=raw.get("input", {}),
            expected_output=expected,
            precondition=raw.get("precondition"),
            postcondition=raw.get("postcondition"),
        )


class Invariant(BaseModel):
    """A property-based invariant that must hold for all valid inputs.

    Attributes:
        description: Human-readable description of the invariant.
        check: Optional Python boolean expression using 'input' and 'output'.
    """

    description: str
    check: str | None = None


class Metadata(BaseModel):
    """Spec metadata.

    Attributes:
        name: Unique identifier (snake_case).
        version: Semantic version string.
        description: Human-readable one-liner.
        target: Generation target (e.g., 'python:function', 'typescript:function').
        tags: Optional tags for organization.
    """

    name: str
    version: str
    description: str
    target: Literal[
        "python:function",
        "python:fastapi",
        "python:class",
        "typescript:function",
    ] = "python:function"
    tags: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate that name is snake_case."""
        if not v.replace("_", "").isalnum():
            raise ValueError(f"Spec name '{v}' must be snake_case (letters, numbers, underscores)")
        if v[0].isdigit():
            raise ValueError(f"Spec name '{v}' cannot start with a digit")
        return v


class Spec(BaseModel):
    """Complete .axiom spec representation.

    This is the top-level model that represents a parsed spec file.

    Attributes:
        axiom: Spec format version.
        metadata: Spec metadata.
        intent: Natural language description of behavior.
        interface: Function or FastAPI interface definition.
        examples: List of I/O examples.
        invariants: List of property-based invariants.
        constraints: Non-functional requirements.
        dependencies: List of specs or modules this spec depends on.
    """

    axiom: str = "0.1"
    metadata: Metadata
    intent: str
    interface: FunctionInterface | FastAPIInterface
    examples: list[Example] = Field(default_factory=list)
    invariants: list[Invariant] = Field(default_factory=list)
    constraints: Constraints = Field(default_factory=Constraints)
    dependencies: list[Dependency] = Field(default_factory=list)

    @field_validator("axiom")
    @classmethod
    def validate_axiom_version(cls, v: str) -> str:
        """Validate spec format version."""
        supported = ["0.1"]
        if v not in supported:
            raise ValueError(f"Unsupported axiom version '{v}'. Supported: {supported}")
        return v

    @model_validator(mode="after")
    def validate_interface_matches_target(self) -> Spec:
        """Validate that interface type matches the target."""
        if self.metadata.target == "python:function":
            if not isinstance(self.interface, FunctionInterface):
                raise ValueError("Target 'python:function' requires FunctionInterface")
        elif self.metadata.target == "python:fastapi":
            if not isinstance(self.interface, FastAPIInterface):
                raise ValueError("Target 'python:fastapi' requires FastAPIInterface")
        return self

    @property
    def function_name(self) -> str:
        """Get the function name from the interface."""
        return self.interface.function_name

    @property
    def spec_name(self) -> str:
        """Get the spec name from metadata."""
        return self.metadata.name

    @property
    def is_fastapi(self) -> bool:
        """Check if this is a FastAPI spec."""
        return self.metadata.target == "python:fastapi"

    @property
    def is_function(self) -> bool:
        """Check if this is a pure function spec."""
        return self.metadata.target == "python:function"

    def get_parameter_types(self) -> dict[str, str]:
        """Get a mapping of parameter names to their types.

        Returns:
            Dict mapping parameter name to type string.
        """
        if isinstance(self.interface, FunctionInterface):
            return {p.name: p.type for p in self.interface.parameters}
        # For FastAPI, combine path and query parameters
        params = {}
        for p in self.interface.path_parameters:
            params[p.name] = p.type
        for p in self.interface.query_parameters:
            params[p.name] = p.type
        return params

    def get_return_type(self) -> str:
        """Get the return type.

        Returns:
            The return type string.
        """
        if isinstance(self.interface, FunctionInterface):
            return self.interface.returns.type
        # For FastAPI, return the response body type or dict
        success = self.interface.response.success
        if isinstance(success.body, str):
            return success.body
        return "dict"

    def get_fastapi_interface(self) -> FastAPIInterface:
        """Get the interface as FastAPIInterface.

        Raises:
            ValueError: If this is not a FastAPI spec.

        Returns:
            The FastAPIInterface.
        """
        if not isinstance(self.interface, FastAPIInterface):
            raise ValueError("This is not a FastAPI spec")
        return self.interface

    def get_function_interface(self) -> FunctionInterface:
        """Get the interface as FunctionInterface.

        Raises:
            ValueError: If this is not a function spec.

        Returns:
            The FunctionInterface.
        """
        if not isinstance(self.interface, FunctionInterface):
            raise ValueError("This is not a function spec")
        return self.interface

    def get_spec_dependencies(self) -> list[str]:
        """Get names of all spec dependencies.

        Returns:
            List of spec names this spec depends on.
        """
        return [d.name for d in self.dependencies if d.type == "spec"]

    def get_hand_written_dependencies(self) -> list[Dependency]:
        """Get all hand-written dependencies.

        Returns:
            List of Dependency objects with type 'hand-written'.
        """
        return [d for d in self.dependencies if d.type == "hand-written"]

    def has_hand_written_dependencies(self) -> bool:
        """Check if this spec has any hand-written dependencies.

        Returns:
            True if there are hand-written dependencies.
        """
        return any(d.type == "hand-written" for d in self.dependencies)

    def has_dependencies(self) -> bool:
        """Check if this spec has any dependencies.

        Returns:
            True if there are dependencies.
        """
        return len(self.dependencies) > 0
