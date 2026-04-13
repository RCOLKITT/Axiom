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
            "clamp",
            "clean_code",
            "compare_values",
            "compare_versions",
            "compute_spec_hash",
            "count_lines",
            "detect_cycle",
            "diff_dicts",
            "escape_regex",
            "extract_code",
            "extract_imports",
            "extract_urls",
            "flatten_list",
            "format_bytes",
            "format_duration",
            "format_example",
            "format_failure",
            "format_invariant",
            "format_type_annotation",
            "format_value",
            "generate_default_value",
            "generate_error_value",
            "group_by",
            "hash_content",
            "indent_text",
            "is_close_value",
            "is_valid_email",
            "lerp",
            "merge_dicts",
            "normalize_path",
            "normalize_type",
            "parse_function_signature",
            "parse_json_safely",
            "parse_version",
            "pluralize",
            "redact_secrets",
            "retry_config",
            "safe_get",
            "sanitize_filename",
            "slugify",
            "snake_to_camel",
            "strip_ansi",
            "topological_sort",
            "truncate_string",
            "type_to_isinstance",
            "unique_ordered",
            "validate_python_identifier",
            "values_equal",
            "wrap_text",
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

    def test_values_equal_works(self) -> None:
        """values_equal should handle complex equality comparisons."""
        from axiom._generated import values_equal

        # Direct equality
        assert values_equal(42, 42) is True
        assert values_equal("hello", "hello") is True

        # Float tolerance
        assert values_equal(1.0000000001, 1.0) is True
        assert values_equal(1.1, 1.0) is False

        # List comparison
        assert values_equal([1, 2, 3], [1, 2, 3]) is True
        assert values_equal([1, 2], [1, 2, 3]) is False

        # Dict partial matching (actual can have extra keys)
        assert values_equal({"a": 1, "b": 2, "c": 3}, {"a": 1, "b": 2}) is True
        assert values_equal({"a": 1}, {"a": 1, "b": 2}) is False

        # Nested structures
        assert values_equal({"user": {"name": "Alice", "age": 30}}, {"user": {"name": "Alice"}}) is True

    def test_compare_versions_works(self) -> None:
        """compare_versions should compare semantic versions."""
        from axiom._generated import compare_versions

        assert compare_versions("1.0.0", "1.0.0") == 0
        assert compare_versions("2.0.0", "1.0.0") == 1
        assert compare_versions("1.0.0", "2.0.0") == -1
        assert compare_versions("1.2.0", "1.1.0") == 1

    def test_redact_secrets_works(self) -> None:
        """redact_secrets should redact sensitive values."""
        from axiom._generated import redact_secrets

        result = redact_secrets({"username": "admin", "password": "secret123"})
        assert result["username"] == "admin"
        assert result["password"] == "[REDACTED]"

    def test_is_valid_email_works(self) -> None:
        """is_valid_email should validate email addresses."""
        from axiom._generated import is_valid_email

        assert is_valid_email("user@example.com") is True
        assert is_valid_email("invalid") is False
        assert is_valid_email("") is False

    def test_diff_dicts_works(self) -> None:
        """diff_dicts should compute dictionary differences."""
        from axiom._generated import diff_dicts

        result = diff_dicts({"a": 1}, {"a": 1, "b": 2})
        assert result["added"] == {"b": 2}
        assert result["removed"] == {}
        assert result["changed"] == {}


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

    def test_infer_generator_imports_spec_driven(self) -> None:
        """infer/generator.py should import generate_default_value and generate_error_value."""
        import ast
        from pathlib import Path

        generator_path = Path("src/axiom/infer/generator.py")
        source = generator_path.read_text()
        tree = ast.parse(source)

        # Check for imports from axiom._generated
        imports_found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "axiom._generated":
                    for alias in node.names:
                        imports_found.add(alias.name)

        expected = {"generate_default_value", "generate_error_value", "type_to_isinstance"}
        assert expected <= imports_found, (
            f"infer/generator.py should import {expected} from axiom._generated. "
            f"Found: {imports_found}"
        )

    def test_stats_cmd_imports_count_lines(self) -> None:
        """cli/stats_cmd.py should import count_lines from _generated."""
        import ast
        from pathlib import Path

        cmd_path = Path("src/axiom/cli/stats_cmd.py")
        source = cmd_path.read_text()
        tree = ast.parse(source)

        # Check for import from axiom._generated
        imports_count_lines = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "axiom._generated":
                    for alias in node.names:
                        if alias.name == "count_lines":
                            imports_count_lines = True

        assert imports_count_lines, (
            "cli/stats_cmd.py does not import count_lines from axiom._generated. "
            "Self-hosting requires using spec-driven code in the implementation."
        )

    def test_interactive_imports_spec_driven(self) -> None:
        """verify/interactive.py should import format_value and is_close_value."""
        import ast
        from pathlib import Path

        path = Path("src/axiom/verify/interactive.py")
        source = path.read_text()
        tree = ast.parse(source)

        # Check for imports from axiom._generated
        imports_found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "axiom._generated":
                    for alias in node.names:
                        imports_found.add(alias.name)

        expected = {"format_value", "is_close_value"}
        assert expected <= imports_found, (
            f"verify/interactive.py should import {expected} from axiom._generated. "
            f"Found: {imports_found}"
        )

    def test_provenance_imports_compute_spec_hash(self) -> None:
        """security/provenance.py should import compute_spec_hash."""
        import ast
        from pathlib import Path

        path = Path("src/axiom/security/provenance.py")
        source = path.read_text()
        tree = ast.parse(source)

        # Check for import from axiom._generated
        imports_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "axiom._generated":
                    for alias in node.names:
                        if alias.name == "compute_spec_hash":
                            imports_found = True

        assert imports_found, (
            "security/provenance.py does not import compute_spec_hash from axiom._generated."
        )

    def test_lint_fixer_imports_type_to_isinstance(self) -> None:
        """lint/fixer.py should import type_to_isinstance from _generated."""
        import ast
        from pathlib import Path

        path = Path("src/axiom/lint/fixer.py")
        source = path.read_text()
        tree = ast.parse(source)

        # Check for import from axiom._generated
        imports_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "axiom._generated":
                    for alias in node.names:
                        if alias.name == "type_to_isinstance":
                            imports_found = True

        assert imports_found, (
            "lint/fixer.py does not import type_to_isinstance from axiom._generated."
        )

    def test_cache_store_imports_format_bytes(self) -> None:
        """cache/store.py should import format_bytes from _generated."""
        import ast
        from pathlib import Path

        path = Path("src/axiom/cache/store.py")
        source = path.read_text()
        tree = ast.parse(source)

        # Check for import from axiom._generated
        imports_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "axiom._generated":
                    for alias in node.names:
                        if alias.name == "format_bytes":
                            imports_found = True

        assert imports_found, (
            "cache/store.py does not import format_bytes from axiom._generated."
        )

    def test_explain_cmd_imports_truncate_string(self) -> None:
        """cli/explain_cmd.py should import truncate_string from _generated."""
        import ast
        from pathlib import Path

        path = Path("src/axiom/cli/explain_cmd.py")
        source = path.read_text()
        tree = ast.parse(source)

        # Check for import from axiom._generated
        imports_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "axiom._generated":
                    for alias in node.names:
                        if alias.name == "truncate_string":
                            imports_found = True

        assert imports_found, (
            "cli/explain_cmd.py does not import truncate_string from axiom._generated."
        )

    def test_new_cmd_imports_camel_to_snake(self) -> None:
        """cli/new_cmd.py should import camel_to_snake from _generated."""
        import ast
        from pathlib import Path

        path = Path("src/axiom/cli/new_cmd.py")
        source = path.read_text()
        tree = ast.parse(source)

        # Check for import from axiom._generated
        imports_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "axiom._generated":
                    for alias in node.names:
                        if alias.name == "camel_to_snake":
                            imports_found = True

        assert imports_found, (
            "cli/new_cmd.py does not import camel_to_snake from axiom._generated."
        )

    def test_reporter_imports_truncate_string(self) -> None:
        """verify/reporter.py should import truncate_string from _generated."""
        import ast
        from pathlib import Path

        path = Path("src/axiom/verify/reporter.py")
        source = path.read_text()
        tree = ast.parse(source)

        imports_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "axiom._generated":
                    for alias in node.names:
                        if alias.name == "truncate_string":
                            imports_found = True

        assert imports_found, (
            "verify/reporter.py does not import truncate_string from axiom._generated."
        )

    def test_property_runner_imports_truncate_string(self) -> None:
        """verify/property_runner.py should import truncate_string from _generated."""
        import ast
        from pathlib import Path

        path = Path("src/axiom/verify/property_runner.py")
        source = path.read_text()
        tree = ast.parse(source)

        imports_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "axiom._generated":
                    for alias in node.names:
                        if alias.name == "truncate_string":
                            imports_found = True

        assert imports_found, (
            "verify/property_runner.py does not import truncate_string from axiom._generated."
        )

    def test_lsp_symbols_imports_escape_regex(self) -> None:
        """lsp/symbols.py should import escape_regex from _generated."""
        import ast
        from pathlib import Path

        path = Path("src/axiom/lsp/symbols.py")
        source = path.read_text()
        tree = ast.parse(source)

        imports_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "axiom._generated":
                    for alias in node.names:
                        if alias.name == "escape_regex":
                            imports_found = True

        assert imports_found, (
            "lsp/symbols.py does not import escape_regex from axiom._generated."
        )

    def test_lsp_diagnostics_imports_escape_regex(self) -> None:
        """lsp/diagnostics.py should import escape_regex from _generated."""
        import ast
        from pathlib import Path

        path = Path("src/axiom/lsp/diagnostics.py")
        source = path.read_text()
        tree = ast.parse(source)

        imports_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "axiom._generated":
                    for alias in node.names:
                        if alias.name == "escape_regex":
                            imports_found = True

        assert imports_found, (
            "lsp/diagnostics.py does not import escape_regex from axiom._generated."
        )

    def test_lsp_hover_imports_escape_regex(self) -> None:
        """lsp/hover.py should import escape_regex from _generated."""
        import ast
        from pathlib import Path

        path = Path("src/axiom/lsp/hover.py")
        source = path.read_text()
        tree = ast.parse(source)

        imports_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "axiom._generated":
                    for alias in node.names:
                        if alias.name == "escape_regex":
                            imports_found = True

        assert imports_found, (
            "lsp/hover.py does not import escape_regex from axiom._generated."
        )

    def test_verify_cmd_imports_pluralize(self) -> None:
        """cli/verify_cmd.py should import pluralize from _generated."""
        import ast
        from pathlib import Path

        path = Path("src/axiom/cli/verify_cmd.py")
        source = path.read_text()
        tree = ast.parse(source)

        imports_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "axiom._generated":
                    for alias in node.names:
                        if alias.name == "pluralize":
                            imports_found = True

        assert imports_found, (
            "cli/verify_cmd.py does not import pluralize from axiom._generated."
        )

    def test_spec_models_imports_validate_python_identifier(self) -> None:
        """spec/models.py should import validate_python_identifier from _generated."""
        import ast
        from pathlib import Path

        path = Path("src/axiom/spec/models.py")
        source = path.read_text()
        tree = ast.parse(source)

        imports_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "axiom._generated":
                    for alias in node.names:
                        if alias.name == "validate_python_identifier":
                            imports_found = True

        assert imports_found, (
            "spec/models.py does not import validate_python_identifier from axiom._generated."
        )

    def test_provenance_cmd_imports_format_duration(self) -> None:
        """cli/provenance_cmd.py should import format_duration from _generated."""
        import ast
        from pathlib import Path

        path = Path("src/axiom/cli/provenance_cmd.py")
        source = path.read_text()
        tree = ast.parse(source)

        imports_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "axiom._generated":
                    for alias in node.names:
                        if alias.name == "format_duration":
                            imports_found = True

        assert imports_found, (
            "cli/provenance_cmd.py does not import format_duration from axiom._generated."
        )

    def test_example_runner_imports_values_equal(self) -> None:
        """verify/example_runner.py should import values_equal from _generated."""
        import ast
        from pathlib import Path

        path = Path("src/axiom/verify/example_runner.py")
        source = path.read_text()
        tree = ast.parse(source)

        imports_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "axiom._generated":
                    for alias in node.names:
                        if alias.name == "values_equal":
                            imports_found = True

        assert imports_found, (
            "verify/example_runner.py does not import values_equal from axiom._generated."
        )
