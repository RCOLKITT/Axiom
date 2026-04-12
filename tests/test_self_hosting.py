"""Tests verifying Axiom's self-hosting: using spec-driven code for its own implementation.

Self-hosting is Axiom's key credibility signal. These tests ensure that:
1. Generated code exists and can be imported
2. The _GENERATED_AVAILABLE flag is True
3. All functions imported by _generated.py are actually spec-driven
"""

from __future__ import annotations

import pytest


class TestSelfHostingAvailable:
    """Verify that self-hosting is active."""

    def test_generated_available_is_true(self) -> None:
        """_GENERATED_AVAILABLE must be True when generated/ exists."""
        from axiom._generated import _GENERATED_AVAILABLE

        assert _GENERATED_AVAILABLE is True, (
            "_GENERATED_AVAILABLE is False. This means the generated/ directory "
            "is missing or the spec-driven code failed to import. "
            "Run 'axiom build specs/self/' to regenerate."
        )

    def test_all_exported_functions_are_callable(self) -> None:
        """All functions exported by _generated must be callable."""
        from axiom import _generated

        # These are the functions that _generated.py exports
        expected_functions = [
            "camel_to_snake",
            "chunk_list",
            "compute_spec_hash",
            "count_lines",
            "escape_regex",
            "extract_code",
            "flatten_list",
            "format_duration",
            "format_value",
            "generate_default_value",
            "generate_error_value",
            "is_close_value",
            "merge_dicts",
            "normalize_path",
            "pluralize",
            "safe_get",
            "slugify",
            "snake_to_camel",
            "strip_ansi",
            "topological_sort",
            "validate_python_identifier",
        ]

        for func_name in expected_functions:
            func = getattr(_generated, func_name, None)
            assert func is not None, f"Function {func_name} not found in _generated"
            assert callable(func), f"Function {func_name} is not callable"


class TestSelfHostedFunctionsWork:
    """Verify that self-hosted functions produce correct results."""

    def test_extract_code_works(self) -> None:
        """extract_code should extract Python from markdown fences."""
        from axiom._generated import extract_code

        response = '```python\ndef hello():\n    return "world"\n```'
        result = extract_code(response)
        assert "def hello():" in result
        assert "return" in result

    def test_slugify_works(self) -> None:
        """slugify should convert text to URL-safe slug."""
        from axiom._generated import slugify

        assert slugify("Hello World") == "hello-world"
        assert slugify("  Multiple   Spaces  ") == "multiple-spaces"

    def test_snake_to_camel_works(self) -> None:
        """snake_to_camel should convert snake_case to camelCase."""
        from axiom._generated import snake_to_camel

        assert snake_to_camel("hello_world", False) == "helloWorld"
        assert snake_to_camel("hello_world", True) == "HelloWorld"

    def test_chunk_list_works(self) -> None:
        """chunk_list should split list into chunks."""
        from axiom._generated import chunk_list

        result = chunk_list([1, 2, 3, 4, 5], 2)
        assert result == [[1, 2], [3, 4], [5]]

    def test_format_duration_works(self) -> None:
        """format_duration should format milliseconds."""
        from axiom._generated import format_duration

        assert format_duration(500) == "500ms"
        assert format_duration(1500) == "1.5s"
        assert format_duration(65000) == "1m 5s"

    def test_validate_python_identifier_works(self) -> None:
        """validate_python_identifier should validate identifiers."""
        from axiom._generated import validate_python_identifier

        assert validate_python_identifier("valid_name") is True
        assert validate_python_identifier("123invalid") is False
        assert validate_python_identifier("class") is False  # keyword
        assert validate_python_identifier("") is False


class TestSelfHostingInCodegen:
    """Verify that codegen actually uses spec-driven code."""

    def test_generator_imports_extract_code(self) -> None:
        """codegen/generator.py should import extract_code from _generated."""
        import ast
        from pathlib import Path

        generator_path = Path("src/axiom/codegen/generator.py")
        source = generator_path.read_text()
        tree = ast.parse(source)

        # Check for import from axiom._generated
        imports_extract_code = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "axiom._generated":
                    for alias in node.names:
                        if alias.name == "extract_code":
                            imports_extract_code = True

        assert imports_extract_code, (
            "codegen/generator.py does not import extract_code from axiom._generated. "
            "Self-hosting requires using spec-driven code in the implementation."
        )
