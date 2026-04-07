"""Tests for spec inference from Python code."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from axiom.infer.analyzer import (
    FunctionInfo,
    ParameterInfo,
    ReturnInfo,
    analyze_python_file,
)
from axiom.infer.generator import (
    InferredSpec,
    generate_spec_from_function,
    write_spec_file,
)


class TestAnalyzePythonFile:
    """Tests for Python file analysis."""

    def test_analyze_simple_function(self) -> None:
        """Analyze a simple function with type hints."""
        code = '''
def add(a: int, b: int) -> int:
    """Add two numbers.

    Args:
        a: First number.
        b: Second number.

    Returns:
        The sum of a and b.
    """
    return a + b
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            path = Path(f.name)

        try:
            functions = analyze_python_file(path)
            assert len(functions) == 1

            func = functions[0]
            assert func.name == "add"
            assert len(func.parameters) == 2
            assert func.parameters[0].name == "a"
            assert func.parameters[0].type == "int"
            assert func.parameters[1].name == "b"
            assert func.parameters[1].type == "int"
            assert func.returns is not None
            assert func.returns.type == "int"
            assert func.description == "Add two numbers."
        finally:
            path.unlink()

    def test_analyze_specific_function(self) -> None:
        """Analyze only a specific function by name."""
        code = """
def foo():
    pass

def bar():
    pass
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            path = Path(f.name)

        try:
            functions = analyze_python_file(path, function_name="bar")
            assert len(functions) == 1
            assert functions[0].name == "bar"
        finally:
            path.unlink()

    def test_skip_private_functions(self) -> None:
        """Private functions should be skipped by default."""
        code = """
def public_func():
    pass

def _private_func():
    pass
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            path = Path(f.name)

        try:
            functions = analyze_python_file(path)
            assert len(functions) == 1
            assert functions[0].name == "public_func"
        finally:
            path.unlink()

    def test_analyze_async_function(self) -> None:
        """Async functions should be detected."""
        code = '''
async def fetch_data(url: str) -> dict:
    """Fetch data from URL."""
    return {}
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            path = Path(f.name)

        try:
            functions = analyze_python_file(path)
            assert len(functions) == 1
            assert functions[0].is_async is True
        finally:
            path.unlink()

    def test_analyze_function_with_defaults(self) -> None:
        """Functions with default parameters."""
        code = """
def greet(name: str, greeting: str = "Hello") -> str:
    return f"{greeting}, {name}!"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            path = Path(f.name)

        try:
            functions = analyze_python_file(path)
            assert len(functions) == 1
            params = functions[0].parameters
            assert len(params) == 2
            assert params[0].default is None
            assert params[1].default == "'Hello'"
        finally:
            path.unlink()

    def test_extract_raises_from_docstring(self) -> None:
        """Extract exception types from docstring."""
        code = '''
def divide(a: int, b: int) -> float:
    """Divide two numbers.

    Raises:
        ValueError: If b is zero.
        TypeError: If inputs are not numbers.
    """
    return a / b
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            path = Path(f.name)

        try:
            functions = analyze_python_file(path)
            assert len(functions) == 1
            assert "ValueError" in functions[0].raises
            assert "TypeError" in functions[0].raises
        finally:
            path.unlink()


class TestParameterInfo:
    """Tests for ParameterInfo dataclass."""

    def test_create_parameter(self) -> None:
        param = ParameterInfo(
            name="x",
            type="int",
            description="A number",
        )
        assert param.name == "x"
        assert param.type == "int"
        assert param.default is None

    def test_parameter_with_default(self) -> None:
        param = ParameterInfo(
            name="count",
            type="int",
            default="10",
        )
        assert param.default == "10"


class TestReturnInfo:
    """Tests for ReturnInfo dataclass."""

    def test_create_return_info(self) -> None:
        ret = ReturnInfo(
            type="str",
            description="The result",
        )
        assert ret.type == "str"
        assert ret.description == "The result"


class TestFunctionInfo:
    """Tests for FunctionInfo dataclass."""

    def test_create_function_info(self) -> None:
        func = FunctionInfo(
            name="test_func",
            module_path=Path("/test.py"),
            line_number=10,
        )
        assert func.name == "test_func"
        assert func.is_async is False
        assert func.parameters == []


class TestGenerateSpecFromFunction:
    """Tests for spec generation from function info."""

    def test_generate_basic_spec(self) -> None:
        func = FunctionInfo(
            name="validate_email",
            module_path=Path("/test.py"),
            line_number=1,
            parameters=[
                ParameterInfo(name="email", type="str", description="Email to validate"),
            ],
            returns=ReturnInfo(type="bool", description="True if valid"),
            description="Validate an email address.",
        )

        spec = generate_spec_from_function(func)

        assert spec.name == "validate_email"
        assert "axiom:" in spec.content
        assert "validate_email" in spec.content
        assert "email" in spec.content
        assert "bool" in spec.content

    def test_spec_confidence_with_good_info(self) -> None:
        """Well-documented functions should have high confidence."""
        func = FunctionInfo(
            name="add",
            module_path=Path("/test.py"),
            line_number=1,
            docstring="Add two numbers together.",
            description="Add two numbers together.",
            parameters=[
                ParameterInfo(name="a", type="int", description="First number"),
                ParameterInfo(name="b", type="int", description="Second number"),
            ],
            returns=ReturnInfo(type="int", description="The sum"),
        )

        spec = generate_spec_from_function(func)
        assert spec.confidence >= 0.8

    def test_spec_confidence_without_docstring(self) -> None:
        """Functions without docstrings should have lower confidence."""
        func = FunctionInfo(
            name="mystery",
            module_path=Path("/test.py"),
            line_number=1,
            parameters=[
                ParameterInfo(name="x", type=None),  # No type
            ],
            returns=None,
        )

        spec = generate_spec_from_function(func)
        assert spec.confidence < 0.8
        assert len(spec.warnings) > 0

    def test_include_source_option(self) -> None:
        """Source code can be included in intent."""
        func = FunctionInfo(
            name="test",
            module_path=Path("/test.py"),
            line_number=1,
            source_code="def test(): pass",
        )

        spec_without = generate_spec_from_function(func, include_source=False)
        spec_with = generate_spec_from_function(func, include_source=True)

        assert "def test():" not in spec_without.content
        assert "def test():" in spec_with.content


class TestInferredSpec:
    """Tests for InferredSpec dataclass."""

    def test_create_inferred_spec(self) -> None:
        func = FunctionInfo(
            name="test",
            module_path=Path("/test.py"),
            line_number=1,
        )
        spec = InferredSpec(
            name="test",
            content="axiom: 0.1",
            source_function=func,
            confidence=0.9,
        )
        assert spec.name == "test"
        assert spec.confidence == 0.9
        assert spec.warnings == []


class TestWriteSpecFile:
    """Tests for writing spec files."""

    def test_write_spec_file(self) -> None:
        func = FunctionInfo(
            name="test_func",
            module_path=Path("/test.py"),
            line_number=1,
        )
        spec = InferredSpec(
            name="test_func",
            content="axiom: 0.1\nmetadata:\n  name: test_func",
            source_function=func,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = write_spec_file(spec, output_dir)

            assert result.exists()
            assert result.name == "test_func.axiom"
            assert result.read_text().startswith("axiom:")

    def test_write_spec_file_no_overwrite(self) -> None:
        """Writing without overwrite should raise on existing file."""
        func = FunctionInfo(
            name="existing",
            module_path=Path("/test.py"),
            line_number=1,
        )
        spec = InferredSpec(
            name="existing",
            content="axiom: 0.1",
            source_function=func,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            # Create existing file
            existing = output_dir / "existing.axiom"
            existing.parent.mkdir(parents=True, exist_ok=True)
            existing.write_text("existing content")

            with pytest.raises(FileExistsError):
                write_spec_file(spec, output_dir, overwrite=False)

    def test_write_spec_file_with_overwrite(self) -> None:
        """Writing with overwrite should replace existing file."""
        func = FunctionInfo(
            name="existing",
            module_path=Path("/test.py"),
            line_number=1,
        )
        spec = InferredSpec(
            name="existing",
            content="axiom: 0.1\nnew content",
            source_function=func,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            existing = output_dir / "existing.axiom"
            existing.parent.mkdir(parents=True, exist_ok=True)
            existing.write_text("old content")

            result = write_spec_file(spec, output_dir, overwrite=True)
            assert "new content" in result.read_text()
