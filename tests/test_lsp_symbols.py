"""Tests for LSP document symbols."""

from __future__ import annotations

from lsprotocol import types as lsp

from axiom.lsp.symbols import get_document_symbols


class TestGetDocumentSymbols:
    """Tests for get_document_symbols function."""

    def test_empty_document(self) -> None:
        """Test with empty document."""
        symbols = get_document_symbols("")
        assert symbols == []

    def test_basic_sections(self) -> None:
        """Test finding basic sections."""
        source = """axiom: "0.1"
metadata:
  name: test_func
  version: "1.0.0"
intent: Test function
interface:
  function_name: test_func
  parameters:
    - name: x
      type: int
  returns:
    type: int
examples:
  - name: basic
    input:
      x: 1
    expected_output: 2
"""
        symbols = get_document_symbols(source)

        # Check that we have the major sections
        symbol_names = [s.name for s in symbols]
        assert "axiom" in symbol_names
        assert "metadata" in symbol_names
        assert "intent" in symbol_names
        assert "interface" in symbol_names
        assert "examples" in symbol_names

    def test_metadata_children(self) -> None:
        """Test metadata section has children."""
        source = """axiom: "0.1"
metadata:
  name: test_func
  version: "1.0.0"
  description: Test function
"""
        symbols = get_document_symbols(source)

        metadata_symbol = next((s for s in symbols if s.name == "metadata"), None)
        assert metadata_symbol is not None
        assert metadata_symbol.children is not None
        child_names = [c.name for c in metadata_symbol.children]
        assert "name" in child_names
        assert "version" in child_names

    def test_examples_children(self) -> None:
        """Test examples section has children."""
        source = """axiom: "0.1"
metadata:
  name: test_func
examples:
  - name: example_one
    input:
      x: 1
    expected_output: 2
  - name: example_two
    input:
      x: 2
    expected_output: 4
"""
        symbols = get_document_symbols(source)

        examples_symbol = next((s for s in symbols if s.name == "examples"), None)
        assert examples_symbol is not None
        assert examples_symbol.children is not None
        child_names = [c.name for c in examples_symbol.children]
        assert "example_one" in child_names
        assert "example_two" in child_names

    def test_symbol_kinds(self) -> None:
        """Test correct symbol kinds are assigned."""
        source = """axiom: "0.1"
metadata:
  name: test_func
interface:
  function_name: test_func
"""
        symbols = get_document_symbols(source)

        axiom_symbol = next((s for s in symbols if s.name == "axiom"), None)
        assert axiom_symbol is not None
        assert axiom_symbol.kind == lsp.SymbolKind.Constant

        metadata_symbol = next((s for s in symbols if s.name == "metadata"), None)
        assert metadata_symbol is not None
        assert metadata_symbol.kind == lsp.SymbolKind.Namespace

        interface_symbol = next((s for s in symbols if s.name == "interface"), None)
        assert interface_symbol is not None
        assert interface_symbol.kind == lsp.SymbolKind.Interface

    def test_symbol_ranges(self) -> None:
        """Test symbol ranges are correct."""
        source = """axiom: "0.1"
metadata:
  name: test_func
  version: "1.0.0"
interface:
  function_name: test_func
"""
        symbols = get_document_symbols(source)

        metadata_symbol = next((s for s in symbols if s.name == "metadata"), None)
        assert metadata_symbol is not None
        # Metadata starts at line 1 (0-indexed)
        assert metadata_symbol.range.start.line == 1
        # Metadata ends before interface starts
        assert metadata_symbol.range.end.line < 4

    def test_invalid_yaml(self) -> None:
        """Test handling of invalid YAML."""
        source = """axiom: "0.1"
metadata:
  invalid yaml here:::
    - broken
"""
        # Should not raise, may return empty or partial
        symbols = get_document_symbols(source)
        # We still find section headers even if YAML parsing fails
        assert isinstance(symbols, list)

    def test_invariants_section(self) -> None:
        """Test invariants section."""
        source = """axiom: "0.1"
metadata:
  name: test_func
invariants:
  - description: Output is positive
    check: "output > 0"
  - description: Output is less than input
    check: "output < input['x']"
"""
        symbols = get_document_symbols(source)

        invariants_symbol = next((s for s in symbols if s.name == "invariants"), None)
        assert invariants_symbol is not None
        assert invariants_symbol.kind == lsp.SymbolKind.Array

    def test_dependencies_section(self) -> None:
        """Test dependencies section."""
        source = """axiom: "0.1"
metadata:
  name: test_func
dependencies:
  - name: helper_func
    type: spec
  - name: util_func
    type: spec
"""
        symbols = get_document_symbols(source)

        deps_symbol = next((s for s in symbols if s.name == "dependencies"), None)
        assert deps_symbol is not None
        assert deps_symbol.kind == lsp.SymbolKind.Array
        assert deps_symbol.children is not None
        child_names = [c.name for c in deps_symbol.children]
        assert "helper_func" in child_names
        assert "util_func" in child_names
