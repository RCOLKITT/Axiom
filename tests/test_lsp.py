"""Tests for the Axiom LSP server."""

from __future__ import annotations

from lsprotocol import types as lsp

from axiom.lsp.completion import get_completions
from axiom.lsp.diagnostics import validate_document
from axiom.lsp.hover import get_hover_info


class TestDiagnostics:
    """Tests for diagnostic validation."""

    def test_empty_document(self) -> None:
        """Empty documents should produce a warning."""
        diagnostics = validate_document("", "file:///test.axiom")
        assert len(diagnostics) == 1
        assert diagnostics[0].severity == lsp.DiagnosticSeverity.Warning
        assert "Empty" in diagnostics[0].message

    def test_yaml_syntax_error(self) -> None:
        """Invalid YAML should produce an error."""
        source = """
axiom: "0.1"
metadata:
  name: test
  invalid yaml here {{{
"""
        diagnostics = validate_document(source, "file:///test.axiom")
        assert len(diagnostics) >= 1
        assert any(d.severity == lsp.DiagnosticSeverity.Error for d in diagnostics)

    def test_missing_required_fields(self) -> None:
        """Missing required fields should produce errors."""
        source = """
axiom: "0.1"
"""
        diagnostics = validate_document(source, "file:///test.axiom")
        # Should have errors for missing metadata and interface
        error_messages = [d.message for d in diagnostics]
        assert any("metadata" in m for m in error_messages)
        assert any("interface" in m for m in error_messages)

    def test_valid_spec(self) -> None:
        """Valid spec should produce no errors."""
        source = """
axiom: "0.1"

metadata:
  name: test_func
  version: "1.0.0"
  description: "Test function"
  target: "python:function"

intent: |
  A test function that doubles the input.

interface:
  function_name: test_func
  parameters:
    - name: x
      type: int
      description: "Input value"
  returns:
    type: int
    description: "Doubled value"

examples:
  - name: basic
    input:
      x: 1
    expected_output:
      value: 2
"""
        diagnostics = validate_document(source, "file:///test.axiom")
        # Filter to errors only (not warnings)
        errors = [d for d in diagnostics if d.severity == lsp.DiagnosticSeverity.Error]
        assert len(errors) == 0

    def test_invalid_target(self) -> None:
        """Invalid target format should produce an error."""
        source = """
axiom: "0.1"

metadata:
  name: test_func
  target: "invalid_target"

interface:
  function_name: test_func
"""
        diagnostics = validate_document(source, "file:///test.axiom")
        assert any("Invalid target" in d.message for d in diagnostics)

    def test_secret_detection(self) -> None:
        """Specs with secrets should produce security errors."""
        # Use a key that matches the OpenAI pattern: sk- followed by 48 alphanumeric chars
        source = """
axiom: "0.1"

metadata:
  name: test_func
  target: "python:function"

intent: |
  Use this API key: sk-1234567890abcdefghijklmnopqrstuvwxyz123456789012

interface:
  function_name: test_func
"""
        diagnostics = validate_document(source, "file:///test.axiom")
        security_errors = [d for d in diagnostics if d.source == "axiom-security"]
        assert len(security_errors) >= 1

    def test_missing_function_name_or_http(self) -> None:
        """Interface must have function_name or http."""
        source = """
axiom: "0.1"

metadata:
  name: test_func
  target: "python:function"

interface:
  parameters:
    - name: x
      type: int
"""
        diagnostics = validate_document(source, "file:///test.axiom")
        assert any("function_name" in d.message or "http" in d.message for d in diagnostics)


class TestCompletion:
    """Tests for code completion."""

    def test_top_level_completion(self) -> None:
        """Should complete top-level fields."""
        source = """
axiom: "0.1"

"""
        position = lsp.Position(line=3, character=0)
        completions = get_completions(source, position)
        labels = [c.label for c in completions]
        assert "metadata" in labels
        assert "interface" in labels
        assert "examples" in labels

    def test_metadata_completion(self) -> None:
        """Should complete metadata fields."""
        source = """axiom: "0.1"

metadata:
  na"""
        position = lsp.Position(line=3, character=4)
        completions = get_completions(source, position)
        labels = [c.label for c in completions]
        assert "name" in labels
        assert "version" in labels
        assert "target" in labels

    def test_interface_completion(self) -> None:
        """Should complete interface fields."""
        source = """axiom: "0.1"

metadata:
  name: test

interface:
  func"""
        position = lsp.Position(line=6, character=6)
        completions = get_completions(source, position)
        labels = [c.label for c in completions]
        assert "function_name" in labels
        assert "parameters" in labels
        assert "returns" in labels

    def test_type_value_completion(self) -> None:
        """Should complete type values."""
        source = """
interface:
  parameters:
    - name: x
      type:
"""
        position = lsp.Position(line=4, character=12)
        completions = get_completions(source, position)
        labels = [c.label for c in completions]
        assert "str" in labels
        assert "int" in labels
        assert "bool" in labels


class TestHover:
    """Tests for hover information."""

    def test_hover_on_axiom(self) -> None:
        """Should show hover info for 'axiom' field."""
        source = 'axiom: "0.1"'
        position = lsp.Position(line=0, character=2)
        hover = get_hover_info(source, position)
        assert hover is not None
        assert "version" in hover.contents.value.lower()

    def test_hover_on_metadata(self) -> None:
        """Should show hover info for 'metadata' field."""
        source = """
axiom: "0.1"

metadata:
  name: test
"""
        position = lsp.Position(line=3, character=2)
        hover = get_hover_info(source, position)
        assert hover is not None
        assert "metadata" in hover.contents.value.lower()

    def test_hover_on_interface(self) -> None:
        """Should show hover info for 'interface' field."""
        source = """interface:
  function_name: test
"""
        position = lsp.Position(line=0, character=2)
        hover = get_hover_info(source, position)
        assert hover is not None
        assert "interface" in hover.contents.value.lower()

    def test_hover_on_type(self) -> None:
        """Should show hover info for type values."""
        source = """
interface:
  parameters:
    - name: x
      type: str
"""
        position = lsp.Position(line=4, character=13)
        hover = get_hover_info(source, position)
        assert hover is not None
        assert "str" in hover.contents.value

    def test_no_hover_on_empty_line(self) -> None:
        """Should return None for empty lines."""
        source = """
axiom: "0.1"

metadata:
"""
        position = lsp.Position(line=2, character=0)
        hover = get_hover_info(source, position)
        assert hover is None


class TestServerCreation:
    """Tests for LSP server creation."""

    def test_create_server(self) -> None:
        """Server should be created without errors."""
        from axiom.lsp.server import create_server

        server = create_server()
        assert server is not None
        assert server.name == "axiom-lsp"
