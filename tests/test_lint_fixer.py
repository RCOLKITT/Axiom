"""Tests for spec lint auto-fixing."""

from __future__ import annotations

import tempfile
from pathlib import Path

from axiom.lint.fixer import (
    FixResult,
    _generate_default_value,
    _generate_error_value,
    _type_to_isinstance,
    fix_spec_file,
    format_fix_result,
)
from axiom.spec.parser import parse_spec_file


class TestGenerateDefaultValue:
    """Tests for default value generation."""

    def test_string_type(self) -> None:
        assert _generate_default_value("str") == "example"
        assert _generate_default_value("string") == "example"

    def test_int_type(self) -> None:
        assert _generate_default_value("int") == 42
        assert _generate_default_value("integer") == 42

    def test_float_type(self) -> None:
        assert _generate_default_value("float") == 3.14

    def test_bool_type(self) -> None:
        assert _generate_default_value("bool") is True
        assert _generate_default_value("boolean") is True

    def test_list_type(self) -> None:
        result = _generate_default_value("list")
        assert isinstance(result, list)

    def test_dict_type(self) -> None:
        result = _generate_default_value("dict")
        assert isinstance(result, dict)

    def test_none_type(self) -> None:
        result = _generate_default_value(None)
        assert result == "example"

    def test_unknown_type(self) -> None:
        result = _generate_default_value("SomeCustomType")
        assert result == "example"


class TestGenerateErrorValue:
    """Tests for error value generation."""

    def test_string_error(self) -> None:
        assert _generate_error_value("str") == ""

    def test_int_error(self) -> None:
        assert _generate_error_value("int") == -1

    def test_list_error(self) -> None:
        assert _generate_error_value("list") == []

    def test_dict_error(self) -> None:
        assert _generate_error_value("dict") == {}


class TestTypeToIsinstance:
    """Tests for type to isinstance conversion."""

    def test_basic_types(self) -> None:
        assert _type_to_isinstance("str") == "str"
        assert _type_to_isinstance("int") == "int"
        assert _type_to_isinstance("float") == "float"
        assert _type_to_isinstance("bool") == "bool"

    def test_collection_types(self) -> None:
        assert _type_to_isinstance("list") == "list"
        assert _type_to_isinstance("dict") == "dict"

    def test_unknown_type(self) -> None:
        assert _type_to_isinstance("CustomType") is None


class TestFixResult:
    """Tests for FixResult dataclass."""

    def test_create_successful_result(self) -> None:
        result = FixResult(
            file_path=Path("/test.axiom"),
            changes=["Added description"],
            success=True,
        )
        assert result.success is True
        assert len(result.changes) == 1

    def test_create_failed_result(self) -> None:
        result = FixResult(
            file_path=Path("/test.axiom"),
            success=False,
            error="Parse error",
        )
        assert result.success is False
        assert result.error == "Parse error"


class TestFormatFixResult:
    """Tests for fix result formatting."""

    def test_format_no_changes(self) -> None:
        result = FixResult(
            file_path=Path("test.axiom"),
            changes=[],
            success=True,
        )
        output = format_fix_result(result)
        assert "No changes needed" in output

    def test_format_with_changes(self) -> None:
        result = FixResult(
            file_path=Path("test.axiom"),
            changes=["Added description", "Added example"],
            success=True,
        )
        output = format_fix_result(result)
        assert "2 change(s)" in output
        assert "Added description" in output

    def test_format_error(self) -> None:
        result = FixResult(
            file_path=Path("test.axiom"),
            success=False,
            error="Parse error",
        )
        output = format_fix_result(result)
        assert "Error" in output
        assert "Parse error" in output


class TestFixSpecFile:
    """Tests for spec file fixing."""

    def test_fix_adds_error_example(self) -> None:
        """Missing error example should be added."""
        spec_content = """axiom: "0.1"

metadata:
  name: test_func
  version: "1.0.0"
  description: "Test function"
  target: "python:function"

intent: |
  Test function.

interface:
  function_name: test_func
  parameters:
    - name: x
      type: str
      description: "Input string"
  returns:
    type: str
    description: "Output string"

examples:
  - name: basic
    input:
      x: "hello"
    expected_output: "hello"
  - name: example2
    input:
      x: "world"
    expected_output: "world"
  - name: example3
    input:
      x: "test"
    expected_output: "test"

invariants:
  - description: Always returns string
    check: isinstance(output, str)
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".axiom", delete=False) as f:
            f.write(spec_content)
            f.flush()
            path = Path(f.name)

        try:
            spec = parse_spec_file(path)
            result = fix_spec_file(path, spec, dry_run=True)

            # Should add an error case example
            assert result.success is True
            # Check that an error case was added
            assert any("error" in change.lower() for change in result.changes)
        finally:
            path.unlink()

    def test_fix_adds_examples_when_missing(self) -> None:
        """Missing examples should trigger placeholder addition."""
        spec_content = """axiom: "0.1"

metadata:
  name: test_func
  version: "1.0.0"
  description: "Test function"
  target: "python:function"

intent: |
  Test function.

interface:
  function_name: test_func
  parameters:
    - name: x
      type: str
      description: Input string
  returns:
    type: str
    description: Output string

invariants:
  - description: Always returns string
    check: isinstance(output, str)
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".axiom", delete=False) as f:
            f.write(spec_content)
            f.flush()
            path = Path(f.name)

        try:
            spec = parse_spec_file(path)
            result = fix_spec_file(path, spec, dry_run=True)

            assert result.success is True
            # Should have changes for adding examples
            assert any("example" in change.lower() for change in result.changes)
        finally:
            path.unlink()

    def test_fix_adds_invariant_when_missing(self) -> None:
        """Missing invariants should trigger addition."""
        spec_content = """axiom: "0.1"

metadata:
  name: test_func
  version: "1.0.0"
  description: "Test function"
  target: "python:function"

intent: |
  Test function.

interface:
  function_name: test_func
  parameters:
    - name: x
      type: str
      description: Input string
  returns:
    type: str
    description: Output string

examples:
  - name: basic
    input:
      x: "hello"
    expected_output: "hello"
  - name: example2
    input:
      x: "world"
    expected_output: "world"
  - name: example3
    input:
      x: "test"
    expected_output: "test"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".axiom", delete=False) as f:
            f.write(spec_content)
            f.flush()
            path = Path(f.name)

        try:
            spec = parse_spec_file(path)
            result = fix_spec_file(path, spec, dry_run=True)

            assert result.success is True
            # Should have changes for adding invariant
            assert any("invariant" in change.lower() for change in result.changes)
        finally:
            path.unlink()

    def test_dry_run_does_not_modify_file(self) -> None:
        """Dry run should not modify the actual file."""
        spec_content = """axiom: "0.1"

metadata:
  name: test_func
  version: "1.0.0"
  description: "Test function"
  target: "python:function"

intent: Test

interface:
  function_name: test_func
  returns:
    type: str
    description: "Result"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".axiom", delete=False) as f:
            f.write(spec_content)
            f.flush()
            path = Path(f.name)

        try:
            original_content = path.read_text()
            spec = parse_spec_file(path)
            fix_spec_file(path, spec, dry_run=True)

            # File should be unchanged
            assert path.read_text() == original_content
        finally:
            path.unlink()

    def test_fix_writes_when_not_dry_run(self) -> None:
        """Non-dry-run should modify the file."""
        spec_content = """axiom: "0.1"

metadata:
  name: test_func
  version: "1.0.0"
  description: "Test function"
  target: "python:function"

intent: Test

interface:
  function_name: test_func
  returns:
    type: str
    description: "Result"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".axiom", delete=False) as f:
            f.write(spec_content)
            f.flush()
            path = Path(f.name)

        try:
            original_content = path.read_text()
            spec = parse_spec_file(path)
            result = fix_spec_file(path, spec, dry_run=False)

            # File should be modified if there were changes
            if result.changes:
                assert path.read_text() != original_content
        finally:
            path.unlink()
