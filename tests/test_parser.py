"""Tests for the spec parser."""

from pathlib import Path

import pytest

from axiom.errors import SpecParseError, SpecValidationError
from axiom.spec import parse_spec, parse_spec_file


class TestParseSpec:
    """Tests for parse_spec function."""

    def test_parse_minimal_valid_spec(self) -> None:
        """Test parsing a minimal valid spec."""
        content = """
axiom: "0.1"

metadata:
  name: test_func
  version: "1.0.0"
  description: "A test function"
  target: "python:function"

intent: |
  This is a test function that does something.

interface:
  function_name: test_func
  parameters:
    - name: x
      type: int
      description: "An integer"
  returns:
    type: int
    description: "The result"
"""
        spec = parse_spec(content)

        assert spec.axiom == "0.1"
        assert spec.metadata.name == "test_func"
        assert spec.metadata.version == "1.0.0"
        assert spec.metadata.target == "python:function"
        assert spec.interface.function_name == "test_func"
        assert len(spec.interface.parameters) == 1
        assert spec.interface.parameters[0].name == "x"
        assert spec.interface.returns.type == "int"

    def test_parse_spec_with_examples(self) -> None:
        """Test parsing a spec with examples."""
        content = """
axiom: "0.1"

metadata:
  name: add_numbers
  version: "1.0.0"
  description: "Adds two numbers"
  target: "python:function"

intent: Adds two numbers together.

interface:
  function_name: add_numbers
  parameters:
    - name: a
      type: int
      description: "First number"
    - name: b
      type: int
      description: "Second number"
  returns:
    type: int
    description: "Sum of a and b"

examples:
  - name: basic_addition
    input:
      a: 1
      b: 2
    expected_output: 3

  - name: negative_numbers
    input:
      a: -5
      b: 3
    expected_output: -2
"""
        spec = parse_spec(content)

        assert len(spec.examples) == 2
        assert spec.examples[0].name == "basic_addition"
        assert spec.examples[0].input == {"a": 1, "b": 2}
        assert spec.examples[0].expected_output.value == 3

    def test_parse_spec_with_exception_example(self) -> None:
        """Test parsing a spec with an exception example."""
        content = """
axiom: "0.1"

metadata:
  name: divide
  version: "1.0.0"
  description: "Divides two numbers"
  target: "python:function"

intent: Divides a by b.

interface:
  function_name: divide
  parameters:
    - name: a
      type: float
      description: "Dividend"
    - name: b
      type: float
      description: "Divisor"
  returns:
    type: float
    description: "Result of a / b"

examples:
  - name: division_by_zero
    input:
      a: 1.0
      b: 0.0
    expected_output:
      raises: ZeroDivisionError
      message_contains: "division"
"""
        spec = parse_spec(content)

        assert len(spec.examples) == 1
        assert spec.examples[0].expected_output.is_exception()
        assert spec.examples[0].expected_output.raises == "ZeroDivisionError"
        assert spec.examples[0].expected_output.message_contains == "division"

    def test_parse_spec_with_invariants(self) -> None:
        """Test parsing a spec with invariants."""
        content = """
axiom: "0.1"

metadata:
  name: uppercase
  version: "1.0.0"
  description: "Converts to uppercase"
  target: "python:function"

intent: Converts a string to uppercase.

interface:
  function_name: uppercase
  parameters:
    - name: s
      type: str
      description: "Input string"
  returns:
    type: str
    description: "Uppercase string"

invariants:
  - description: "Output is always uppercase"
    check: "output == output.upper()"
  - description: "Output length equals input length"
    check: "len(output) == len(input['s'])"
"""
        spec = parse_spec(content)

        assert len(spec.invariants) == 2
        assert spec.invariants[0].description == "Output is always uppercase"
        assert spec.invariants[0].check == "output == output.upper()"

    def test_parse_missing_required_key(self) -> None:
        """Test that missing required keys raise SpecParseError."""
        content = """
axiom: "0.1"

metadata:
  name: test
  version: "1.0.0"
  description: "Test"
  target: "python:function"

# Missing intent and interface
"""
        with pytest.raises(SpecParseError) as exc_info:
            parse_spec(content)

        assert "Missing required keys" in str(exc_info.value)
        assert "intent" in str(exc_info.value)
        assert "interface" in str(exc_info.value)

    def test_parse_unknown_key(self) -> None:
        """Test that unknown keys raise SpecValidationError."""
        content = """
axiom: "0.1"

metadata:
  name: test
  version: "1.0.0"
  description: "Test"
  target: "python:function"

intent: Test function.

interface:
  function_name: test
  parameters: []
  returns:
    type: str
    description: "Result"

unknown_key: "should fail"
"""
        with pytest.raises(SpecValidationError) as exc_info:
            parse_spec(content)

        assert "Unknown keys" in str(exc_info.value)
        assert "unknown_key" in str(exc_info.value)

    def test_parse_invalid_yaml(self) -> None:
        """Test that invalid YAML raises SpecParseError."""
        content = """
axiom: "0.1"
metadata:
  - invalid: yaml
    structure: here
  name: [broken
"""
        with pytest.raises(SpecParseError) as exc_info:
            parse_spec(content)

        assert "Invalid YAML syntax" in str(exc_info.value)

    def test_parse_invalid_function_name(self) -> None:
        """Test that invalid function names are rejected."""
        content = """
axiom: "0.1"

metadata:
  name: test
  version: "1.0.0"
  description: "Test"
  target: "python:function"

intent: Test function.

interface:
  function_name: "123-invalid"
  parameters: []
  returns:
    type: str
    description: "Result"
"""
        with pytest.raises(SpecValidationError) as exc_info:
            parse_spec(content)

        assert "not a valid Python identifier" in str(exc_info.value)


class TestParseSpecFile:
    """Tests for parse_spec_file function."""

    def test_parse_nonexistent_file(self) -> None:
        """Test that nonexistent files raise SpecParseError."""
        with pytest.raises(SpecParseError) as exc_info:
            parse_spec_file("/nonexistent/file.axiom")

        assert "File not found" in str(exc_info.value)

    def test_parse_wrong_extension(self, tmp_path: Path) -> None:
        """Test that wrong file extensions raise SpecParseError."""
        wrong_file = tmp_path / "test.yaml"
        wrong_file.write_text("axiom: '0.1'")

        with pytest.raises(SpecParseError) as exc_info:
            parse_spec_file(wrong_file)

        assert "Expected .axiom extension" in str(exc_info.value)

    def test_parse_valid_file(self, tmp_path: Path) -> None:
        """Test parsing a valid spec file."""
        spec_content = """
axiom: "0.1"

metadata:
  name: file_test
  version: "1.0.0"
  description: "Test from file"
  target: "python:function"

intent: A test function.

interface:
  function_name: file_test
  parameters: []
  returns:
    type: str
    description: "Result"
"""
        spec_file = tmp_path / "test.axiom"
        spec_file.write_text(spec_content)

        spec = parse_spec_file(spec_file)

        assert spec.metadata.name == "file_test"
        assert spec.interface.function_name == "file_test"
