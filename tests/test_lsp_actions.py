"""Tests for LSP code actions."""

from __future__ import annotations

from lsprotocol import types as lsp

from axiom.lsp.actions import get_code_actions


class TestGetCodeActions:
    """Tests for get_code_actions function."""

    def test_no_diagnostics(self) -> None:
        """Test with no diagnostics."""
        actions = get_code_actions("axiom: '0.1'", [], "file:///test.axiom")
        # May have source actions but no quick fixes
        quick_fixes = [a for a in actions if a.kind == lsp.CodeActionKind.QuickFix]
        assert quick_fixes == []

    def test_non_axiom_diagnostic_ignored(self) -> None:
        """Test that diagnostics from other sources are ignored."""
        diagnostic = lsp.Diagnostic(
            range=lsp.Range(
                start=lsp.Position(line=0, character=0),
                end=lsp.Position(line=0, character=10),
            ),
            message="Some error",
            source="other-linter",
        )
        actions = get_code_actions("axiom: '0.1'", [diagnostic], "file:///test.axiom")
        quick_fixes = [a for a in actions if a.kind == lsp.CodeActionKind.QuickFix]
        assert quick_fixes == []

    def test_fix_missing_field(self) -> None:
        """Test suggesting fix for missing required field."""
        source = """axiom: "0.1"
metadata:
  version: "1.0.0"
"""
        diagnostic = lsp.Diagnostic(
            range=lsp.Range(
                start=lsp.Position(line=1, character=0),
                end=lsp.Position(line=2, character=0),
            ),
            message="Required field 'name' is missing",
            source="axiom",
        )
        actions = get_code_actions(source, [diagnostic], "file:///test.axiom")

        quick_fixes = [a for a in actions if a.kind == lsp.CodeActionKind.QuickFix]
        assert len(quick_fixes) > 0
        assert any("name" in a.title for a in quick_fixes)

    def test_fix_invalid_value_suggestions(self) -> None:
        """Test suggesting valid values for invalid value."""
        source = """axiom: "0.1"
metadata:
  target: "invalid_target"
"""
        diagnostic = lsp.Diagnostic(
            range=lsp.Range(
                start=lsp.Position(line=2, character=10),
                end=lsp.Position(line=2, character=26),
            ),
            message="Invalid target. must be one of: ['python:function', 'typescript:function']",
            source="axiom",
        )
        actions = get_code_actions(source, [diagnostic], "file:///test.axiom")

        quick_fixes = [a for a in actions if a.kind == lsp.CodeActionKind.QuickFix]
        assert len(quick_fixes) > 0
        # Should suggest valid targets
        assert any("python:function" in a.title for a in quick_fixes)

    def test_fix_no_examples(self) -> None:
        """Test suggesting fix for no examples."""
        source = """axiom: "0.1"
metadata:
  name: test_func
interface:
  function_name: test_func
"""
        diagnostic = lsp.Diagnostic(
            range=lsp.Range(
                start=lsp.Position(line=0, character=0),
                end=lsp.Position(line=0, character=10),
            ),
            message="No examples defined. Examples required for verification.",
            source="axiom",
        )
        actions = get_code_actions(source, [diagnostic], "file:///test.axiom")

        quick_fixes = [a for a in actions if a.kind == lsp.CodeActionKind.QuickFix]
        assert len(quick_fixes) > 0
        assert any("example" in a.title.lower() for a in quick_fixes)

    def test_code_action_has_edit(self) -> None:
        """Test that code actions have workspace edits."""
        source = """axiom: "0.1"
metadata:
  version: "1.0.0"
"""
        diagnostic = lsp.Diagnostic(
            range=lsp.Range(
                start=lsp.Position(line=1, character=0),
                end=lsp.Position(line=2, character=0),
            ),
            message="Required field 'name' is missing",
            source="axiom",
        )
        actions = get_code_actions(source, [diagnostic], "file:///test.axiom")

        quick_fixes = [a for a in actions if a.kind == lsp.CodeActionKind.QuickFix]
        for fix in quick_fixes:
            assert fix.edit is not None or fix.command is not None

    def test_multiple_diagnostics(self) -> None:
        """Test handling multiple diagnostics."""
        source = """axiom: "0.1"
metadata:
  name: test
"""
        diagnostics = [
            lsp.Diagnostic(
                range=lsp.Range(
                    start=lsp.Position(line=1, character=0),
                    end=lsp.Position(line=1, character=10),
                ),
                message="Required field 'version' is missing",
                source="axiom",
            ),
            lsp.Diagnostic(
                range=lsp.Range(
                    start=lsp.Position(line=0, character=0),
                    end=lsp.Position(line=0, character=10),
                ),
                message="No examples defined. Examples required for verification.",
                source="axiom",
            ),
        ]
        actions = get_code_actions(source, diagnostics, "file:///test.axiom")

        quick_fixes = [a for a in actions if a.kind == lsp.CodeActionKind.QuickFix]
        # Should have fixes for both diagnostics
        assert len(quick_fixes) >= 2
