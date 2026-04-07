"""Tests for the multi-language target system."""

from __future__ import annotations

import pytest

from axiom.targets import (
    PythonFastAPITarget,
    PythonFunctionTarget,
    TypeScriptFunctionTarget,
    get_target,
)
from axiom.targets.registry import TargetNotFoundError, is_target_registered, list_targets


class TestTargetRegistry:
    """Tests for target registry."""

    def test_get_python_function_target(self) -> None:
        """Should retrieve Python function target."""
        target = get_target("python:function")
        assert target is not None
        assert isinstance(target, PythonFunctionTarget)
        assert target.name == "python:function"
        assert target.language == "python"

    def test_get_python_fastapi_target(self) -> None:
        """Should retrieve Python FastAPI target."""
        target = get_target("python:fastapi")
        assert target is not None
        assert isinstance(target, PythonFastAPITarget)
        assert target.name == "python:fastapi"

    def test_get_typescript_function_target(self) -> None:
        """Should retrieve TypeScript function target."""
        target = get_target("typescript:function")
        assert target is not None
        assert isinstance(target, TypeScriptFunctionTarget)
        assert target.name == "typescript:function"
        assert target.language == "typescript"

    def test_unknown_target_raises(self) -> None:
        """Should raise TargetNotFoundError for unknown targets."""
        with pytest.raises(TargetNotFoundError) as exc_info:
            get_target("unknown:target")
        assert "unknown:target" in str(exc_info.value)

    def test_list_targets(self) -> None:
        """Should list all registered targets."""
        targets = list_targets()
        assert "python:function" in targets
        assert "python:fastapi" in targets
        assert "typescript:function" in targets

    def test_is_target_registered(self) -> None:
        """Should check if target is registered."""
        assert is_target_registered("python:function") is True
        assert is_target_registered("unknown:target") is False


class TestPythonFunctionTarget:
    """Tests for Python function target."""

    def test_capabilities(self) -> None:
        """Should have correct capabilities."""
        target = PythonFunctionTarget()
        caps = target.capabilities
        assert caps.supports_examples is True
        assert caps.supports_invariants is True
        assert caps.supports_http is False
        assert caps.file_extension == ".py"
        assert caps.package_format == "pip"

    def test_build_system_prompt(self) -> None:
        """Should build system prompt."""
        from axiom.spec.models import (
            FunctionInterface,
            Metadata,
            Parameter,
            Returns,
            Spec,
        )

        spec = Spec(
            axiom="0.1",
            metadata=Metadata(
                name="test_func",
                version="1.0.0",
                description="Test",
                target="python:function",
            ),
            intent="Test function",
            interface=FunctionInterface(
                function_name="test_func",
                parameters=[Parameter(name="x", type="int", description="Input")],
                returns=Returns(type="int", description="Output"),
            ),
        )

        target = PythonFunctionTarget()
        prompt = target.build_system_prompt(spec)

        assert "code generator" in prompt.lower()
        assert "python" in prompt.lower()


class TestTypeScriptFunctionTarget:
    """Tests for TypeScript function target."""

    def test_capabilities(self) -> None:
        """Should have correct capabilities."""
        target = TypeScriptFunctionTarget()
        caps = target.capabilities
        assert caps.supports_examples is True
        assert caps.supports_invariants is True
        assert caps.supports_http is False
        assert caps.file_extension == ".ts"
        assert caps.package_format == "npm"

    def test_build_system_prompt(self) -> None:
        """Should build TypeScript system prompt."""
        from axiom.spec.models import (
            FunctionInterface,
            Metadata,
            Parameter,
            Returns,
            Spec,
        )

        spec = Spec(
            axiom="0.1",
            metadata=Metadata(
                name="test_func",
                version="1.0.0",
                description="Test",
                target="typescript:function",
            ),
            intent="Test function",
            interface=FunctionInterface(
                function_name="test_func",
                parameters=[Parameter(name="x", type="int", description="Input")],
                returns=Returns(type="int", description="Output"),
            ),
        )

        target = TypeScriptFunctionTarget()
        prompt = target.build_system_prompt(spec)

        assert "typescript" in prompt.lower()
        assert "export" in prompt.lower()

    def test_python_to_ts_type_basic(self) -> None:
        """Should convert basic Python types to TypeScript."""
        target = TypeScriptFunctionTarget()

        assert target._python_to_ts_type("str") == "string"
        assert target._python_to_ts_type("int") == "number"
        assert target._python_to_ts_type("float") == "number"
        assert target._python_to_ts_type("bool") == "boolean"
        assert target._python_to_ts_type("None") == "null"
        assert target._python_to_ts_type("Any") == "any"

    def test_python_to_ts_type_generics(self) -> None:
        """Should convert generic Python types to TypeScript."""
        target = TypeScriptFunctionTarget()

        assert target._python_to_ts_type("list[str]") == "string[]"
        assert target._python_to_ts_type("list[int]") == "number[]"
        assert target._python_to_ts_type("dict[str, int]") == "Record<string, number>"
        assert target._python_to_ts_type("Optional[str]") == "string | null"

    def test_python_to_ts_type_tuple(self) -> None:
        """Should convert tuple types to TypeScript."""
        target = TypeScriptFunctionTarget()

        assert target._python_to_ts_type("tuple[str, int]") == "[string, number]"

    def test_post_process_adds_export(self) -> None:
        """Should add export to function if missing."""
        from axiom.spec.models import FunctionInterface, Metadata, Returns, Spec

        target = TypeScriptFunctionTarget()
        spec = Spec(
            axiom="0.1",
            metadata=Metadata(
                name="test",
                version="1.0.0",
                description="Test",
                target="typescript:function",
            ),
            intent="Test",
            interface=FunctionInterface(
                function_name="test",
                parameters=[],
                returns=Returns(type="string", description="Output"),
            ),
        )

        code = """function greet(name: string): string {
    return `Hello, ${name}!`;
}"""
        processed = target.post_process(code, spec)
        assert "export function" in processed

    def test_post_process_removes_fences(self) -> None:
        """Should remove markdown fences."""
        from axiom.spec.models import FunctionInterface, Metadata, Returns, Spec

        target = TypeScriptFunctionTarget()
        spec = Spec(
            axiom="0.1",
            metadata=Metadata(
                name="test",
                version="1.0.0",
                description="Test",
                target="typescript:function",
            ),
            intent="Test",
            interface=FunctionInterface(
                function_name="test",
                parameters=[],
                returns=Returns(type="string", description="Output"),
            ),
        )

        code = """```typescript
export function greet(name: string): string {
    return `Hello, ${name}!`;
}
```"""
        processed = target.post_process(code, spec)
        assert "```" not in processed
        assert "export function greet" in processed


class TestTargetExtraction:
    """Tests for code extraction."""

    def test_extract_python_from_fenced(self) -> None:
        """Should extract Python code from markdown fences."""
        target = PythonFunctionTarget()
        response = """Here's the implementation:

```python
def hello():
    return "world"
```

This function returns "world"."""

        code = target.extract_code(response)
        assert "def hello():" in code
        assert 'return "world"' in code
        assert "```" not in code

    def test_extract_typescript_from_fenced(self) -> None:
        """Should extract TypeScript code from markdown fences."""
        target = TypeScriptFunctionTarget()
        response = """Here's the implementation:

```typescript
export function hello(): string {
    return "world";
}
```"""

        code = target.extract_code(response)
        assert "export function hello" in code
        assert "```" not in code
