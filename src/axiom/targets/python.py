"""Python code generation targets.

Provides targets for generating Python code:
- python:function - Pure Python functions
- python:fastapi - FastAPI endpoints
"""

from __future__ import annotations

from pathlib import Path

from axiom.codegen.prompt_builder import (
    _build_fastapi_system_prompt,
    _build_fastapi_user_prompt,
    _build_function_system_prompt,
    _build_function_user_prompt,
)
from axiom.spec.models import Spec
from axiom.targets.base import Target, TargetCapabilities
from axiom.targets.registry import register_target


class PythonFunctionTarget(Target):
    """Target for generating pure Python functions."""

    name = "python:function"
    language = "python"
    capabilities = TargetCapabilities(
        supports_examples=True,
        supports_invariants=True,
        supports_http=False,
        supports_async=True,
        file_extension=".py",
        package_format="pip",
    )

    def build_system_prompt(self, spec: Spec) -> str:
        """Build system prompt for Python function generation."""
        return _build_function_system_prompt()

    def build_user_prompt(self, spec: Spec) -> str:
        """Build user prompt for Python function generation."""
        return _build_function_user_prompt(spec)

    def post_process(self, code: str, spec: Spec) -> str:
        """Post-process generated Python code.

        - Format with ruff if available
        - Ensure proper imports
        - Validate syntax
        """
        from axiom.codegen.post_processor import post_process

        return post_process(code, spec.metadata.name)

    def get_output_path(self, spec: Spec, output_dir: Path) -> Path:
        """Get output path for generated Python function."""
        return output_dir / f"{spec.metadata.name}.py"


class PythonFastAPITarget(Target):
    """Target for generating FastAPI endpoints."""

    name = "python:fastapi"
    language = "python"
    capabilities = TargetCapabilities(
        supports_examples=True,
        supports_invariants=True,
        supports_http=True,
        supports_async=True,
        file_extension=".py",
        package_format="pip",
    )

    def build_system_prompt(self, spec: Spec) -> str:
        """Build system prompt for FastAPI generation."""
        return _build_fastapi_system_prompt()

    def build_user_prompt(self, spec: Spec) -> str:
        """Build user prompt for FastAPI generation."""
        return _build_fastapi_user_prompt(spec)

    def post_process(self, code: str, spec: Spec) -> str:
        """Post-process generated FastAPI code."""
        from axiom.codegen.post_processor import post_process

        return post_process(code, spec.metadata.name)

    def get_output_path(self, spec: Spec, output_dir: Path) -> Path:
        """Get output path for generated FastAPI endpoint."""
        return output_dir / f"{spec.metadata.name}.py"


# Register Python targets
register_target("python:function", PythonFunctionTarget)
register_target("python:fastapi", PythonFastAPITarget)
