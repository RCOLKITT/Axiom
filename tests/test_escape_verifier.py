"""Tests for the escape hatch verifier module."""

import tempfile
from pathlib import Path

from axiom.escape.verifier import (
    HandWrittenVerificationResult,
    verify_hand_written_interface,
)
from axiom.spec.models import (
    FunctionSignature,
    HandWrittenInterface,
    Parameter,
    Returns,
)


def _create_temp_module(code: str) -> Path:
    """Create a temporary Python module file.

    Args:
        code: The Python code to write.

    Returns:
        Path to the temporary file.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        return Path(f.name)


class TestVerifyHandWrittenInterface:
    """Tests for verify_hand_written_interface function."""

    def test_module_not_found(self) -> None:
        """Test verification when module file doesn't exist."""
        interface = HandWrittenInterface(
            module_path="nonexistent.py",
            functions=[],
        )

        result = verify_hand_written_interface(
            Path("nonexistent.py"),
            interface,
        )

        assert not result.interface_matches
        assert "not found" in result.error_message.lower()

    def test_empty_interface_passes(self) -> None:
        """Test verification of module with empty interface."""
        module_path = _create_temp_module("""
def some_function():
    pass
""")
        try:
            interface = HandWrittenInterface(
                module_path=str(module_path),
                functions=[],
            )

            result = verify_hand_written_interface(module_path, interface)

            assert result.interface_matches
            assert len(result.missing_exports) == 0
        finally:
            module_path.unlink()

    def test_function_exists(self) -> None:
        """Test verification when function exists."""
        module_path = _create_temp_module("""
def validate_email(email: str) -> bool:
    return "@" in email
""")
        try:
            interface = HandWrittenInterface(
                module_path=str(module_path),
                functions=[
                    FunctionSignature(
                        name="validate_email",
                        parameters=[
                            Parameter(
                                name="email",
                                type="str",
                                description="Email to validate",
                            )
                        ],
                        returns=Returns(type="bool", description="Is valid"),
                    )
                ],
            )

            result = verify_hand_written_interface(module_path, interface)

            assert result.interface_matches
            assert len(result.missing_exports) == 0
        finally:
            module_path.unlink()

    def test_function_missing(self) -> None:
        """Test verification when function is missing."""
        module_path = _create_temp_module("""
def other_function():
    pass
""")
        try:
            interface = HandWrittenInterface(
                module_path=str(module_path),
                functions=[
                    FunctionSignature(
                        name="expected_function",
                        parameters=[],
                        returns=Returns(type="None", description=""),
                    )
                ],
            )

            result = verify_hand_written_interface(module_path, interface)

            assert not result.interface_matches
            assert "expected_function" in result.missing_exports
        finally:
            module_path.unlink()

    def test_parameter_count_mismatch(self) -> None:
        """Test verification when parameter count doesn't match."""
        module_path = _create_temp_module("""
def process(a, b, c):
    pass
""")
        try:
            interface = HandWrittenInterface(
                module_path=str(module_path),
                functions=[
                    FunctionSignature(
                        name="process",
                        parameters=[
                            Parameter(name="a", type="Any", description=""),
                            Parameter(name="b", type="Any", description=""),
                        ],
                        returns=Returns(type="None", description=""),
                    )
                ],
            )

            result = verify_hand_written_interface(module_path, interface)

            assert not result.interface_matches
            assert any("mismatch" in msg.lower() for msg in result.type_mismatches)
        finally:
            module_path.unlink()

    def test_async_function_matches(self) -> None:
        """Test verification of async functions."""
        module_path = _create_temp_module("""
async def fetch_data(url: str) -> dict:
    return {}
""")
        try:
            interface = HandWrittenInterface(
                module_path=str(module_path),
                functions=[
                    FunctionSignature(
                        name="fetch_data",
                        parameters=[
                            Parameter(name="url", type="str", description=""),
                        ],
                        returns=Returns(type="dict", description=""),
                        is_async=True,
                    )
                ],
            )

            result = verify_hand_written_interface(module_path, interface)

            assert result.interface_matches
        finally:
            module_path.unlink()

    def test_async_mismatch(self) -> None:
        """Test that sync/async mismatch is detected."""
        module_path = _create_temp_module("""
def sync_function():
    pass
""")
        try:
            interface = HandWrittenInterface(
                module_path=str(module_path),
                functions=[
                    FunctionSignature(
                        name="sync_function",
                        parameters=[],
                        returns=Returns(type="None", description=""),
                        is_async=True,  # Expected async but got sync
                    )
                ],
            )

            result = verify_hand_written_interface(module_path, interface)

            assert not result.interface_matches
        finally:
            module_path.unlink()

    def test_multiple_functions(self) -> None:
        """Test verification of multiple functions."""
        module_path = _create_temp_module("""
def func_a(x: int) -> int:
    return x

def func_b(s: str) -> str:
    return s

def func_c():
    pass
""")
        try:
            interface = HandWrittenInterface(
                module_path=str(module_path),
                functions=[
                    FunctionSignature(
                        name="func_a",
                        parameters=[
                            Parameter(name="x", type="int", description=""),
                        ],
                        returns=Returns(type="int", description=""),
                    ),
                    FunctionSignature(
                        name="func_b",
                        parameters=[
                            Parameter(name="s", type="str", description=""),
                        ],
                        returns=Returns(type="str", description=""),
                    ),
                ],
            )

            result = verify_hand_written_interface(module_path, interface)

            assert result.interface_matches
            assert len(result.check_results) == 2
            assert all(r.passed for r in result.check_results)
        finally:
            module_path.unlink()

    def test_module_with_syntax_error(self) -> None:
        """Test verification of module with syntax error."""
        module_path = _create_temp_module("""
def broken(
    # Missing closing paren
""")
        try:
            interface = HandWrittenInterface(
                module_path=str(module_path),
                functions=[],
            )

            result = verify_hand_written_interface(module_path, interface)

            assert not result.interface_matches
            assert "load module" in result.error_message.lower()
        finally:
            module_path.unlink()

    def test_non_callable_attribute(self) -> None:
        """Test verification when expected function is not callable."""
        module_path = _create_temp_module("""
validate_email = "not a function"
""")
        try:
            interface = HandWrittenInterface(
                module_path=str(module_path),
                functions=[
                    FunctionSignature(
                        name="validate_email",
                        parameters=[],
                        returns=Returns(type="bool", description=""),
                    )
                ],
            )

            result = verify_hand_written_interface(module_path, interface)

            assert not result.interface_matches
            assert any("not callable" in (r.error_message or "") for r in result.check_results)
        finally:
            module_path.unlink()


class TestHandWrittenVerificationResult:
    """Tests for HandWrittenVerificationResult dataclass."""

    def test_result_attributes(self) -> None:
        """Test result dataclass attributes."""
        result = HandWrittenVerificationResult(
            module_name="test_module",
            module_path="/path/to/module.py",
            interface_matches=True,
            missing_exports=[],
            type_mismatches=[],
        )

        assert result.module_name == "test_module"
        assert result.module_path == "/path/to/module.py"
        assert result.interface_matches is True
        assert result.error_message is None
