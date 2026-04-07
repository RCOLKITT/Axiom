"""Axiom lint module for spec validation and auto-fixing."""

from axiom.lint.fixer import FixResult, fix_spec_file, format_fix_result

__all__ = [
    "FixResult",
    "fix_spec_file",
    "format_fix_result",
]
