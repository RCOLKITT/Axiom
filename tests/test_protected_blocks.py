"""Tests for the protected blocks module."""

from axiom.escape.protected_blocks import (
    ProtectedBlock,
    extract_protected_blocks,
    inject_protected_blocks,
    validate_protected_blocks,
)


class TestExtractProtectedBlocks:
    """Tests for extract_protected_blocks function."""

    def test_no_blocks(self) -> None:
        """Test extraction from code with no protected blocks."""
        code = '''
def validate_email(email: str) -> bool:
    """Validate email format."""
    return "@" in email and "." in email
'''
        blocks = extract_protected_blocks(code)
        assert len(blocks) == 0

    def test_simple_block(self) -> None:
        """Test extraction of a simple unnamed block."""
        code = """
def validate_email(email: str) -> bool:
    # AXIOM:PROTECTED:BEGIN
    # Custom validation logic
    custom_check = True
    # AXIOM:PROTECTED:END
    return "@" in email
"""
        blocks = extract_protected_blocks(code)

        assert len(blocks) == 1
        assert blocks[0].name is None
        assert "Custom validation logic" in blocks[0].content
        assert "custom_check = True" in blocks[0].content
        assert blocks[0].context == "validate_email"

    def test_named_block(self) -> None:
        """Test extraction of a named protected block."""
        code = """
def process_data(data: dict) -> dict:
    # AXIOM:PROTECTED:BEGIN:custom_transform
    data["custom_field"] = "value"
    # AXIOM:PROTECTED:END:custom_transform
    return data
"""
        blocks = extract_protected_blocks(code)

        assert len(blocks) == 1
        assert blocks[0].name == "custom_transform"
        assert blocks[0].context == "process_data"

    def test_multiple_blocks(self) -> None:
        """Test extraction of multiple protected blocks."""
        code = """
def func1():
    # AXIOM:PROTECTED:BEGIN:block1
    pass
    # AXIOM:PROTECTED:END:block1

def func2():
    # AXIOM:PROTECTED:BEGIN:block2
    pass
    # AXIOM:PROTECTED:END:block2
"""
        blocks = extract_protected_blocks(code)

        assert len(blocks) == 2
        assert blocks[0].name == "block1"
        assert blocks[0].context == "func1"
        assert blocks[1].name == "block2"
        assert blocks[1].context == "func2"

    def test_module_level_block(self) -> None:
        """Test extraction of module-level protected block."""
        code = """
# AXIOM:PROTECTED:BEGIN
CUSTOM_CONSTANT = 42
# AXIOM:PROTECTED:END

def regular_function():
    pass
"""
        blocks = extract_protected_blocks(code)

        assert len(blocks) == 1
        assert blocks[0].name is None
        assert blocks[0].context is None
        assert "CUSTOM_CONSTANT = 42" in blocks[0].content

    def test_indented_block(self) -> None:
        """Test extraction preserves indentation info."""
        code = """
def outer():
    if True:
        # AXIOM:PROTECTED:BEGIN
        nested_code = True
        # AXIOM:PROTECTED:END
"""
        blocks = extract_protected_blocks(code)

        assert len(blocks) == 1
        # The block should have indentation
        assert "        " in blocks[0].indentation or blocks[0].indentation != ""

    def test_unclosed_block_warning(self) -> None:
        """Test that unclosed blocks are handled gracefully."""
        code = """
def func():
    # AXIOM:PROTECTED:BEGIN
    # This block is never closed
    pass
"""
        # Should not raise, just log a warning
        blocks = extract_protected_blocks(code)

        # Unclosed block should not be returned
        assert len(blocks) == 0

    def test_mismatched_names(self) -> None:
        """Test that mismatched block names are handled."""
        code = """
def func():
    # AXIOM:PROTECTED:BEGIN:name1
    pass
    # AXIOM:PROTECTED:END:name2
"""
        # Mismatched names mean the block isn't closed properly
        blocks = extract_protected_blocks(code)

        # Should not match since names are different
        assert len(blocks) == 0


class TestInjectProtectedBlocks:
    """Tests for inject_protected_blocks function."""

    def test_no_blocks(self) -> None:
        """Test injection with no blocks."""
        code = """
def func():
    pass
"""
        result = inject_protected_blocks(code, [])
        assert result == code

    def test_inject_module_level_block(self) -> None:
        """Test injecting a module-level protected block."""
        code = """
def func():
    pass
"""
        blocks = [
            ProtectedBlock(
                name=None,
                content="# AXIOM:PROTECTED:BEGIN\nCUSTOM = 42\n# AXIOM:PROTECTED:END",
                context=None,
                start_line=1,
                end_line=3,
            )
        ]

        result = inject_protected_blocks(code, blocks)

        assert "CUSTOM = 42" in result
        assert "Protected blocks preserved" in result

    def test_inject_into_function_context(self) -> None:
        """Test injecting a block with function context."""
        code = """
def validate_email(email: str) -> bool:
    return "@" in email
"""
        blocks = [
            ProtectedBlock(
                name="custom_check",
                content="    # AXIOM:PROTECTED:BEGIN:custom_check\n    custom = True\n    # AXIOM:PROTECTED:END:custom_check",
                context="validate_email",
                start_line=2,
                end_line=4,
                indentation="    ",
            )
        ]

        result = inject_protected_blocks(code, blocks)

        # Block should be injected
        assert "custom_check" in result

    def test_orphan_block_with_warning(self) -> None:
        """Test that blocks with missing context get warning."""
        code = """
def different_function():
    pass
"""
        blocks = [
            ProtectedBlock(
                name="old_block",
                content="# AXIOM:PROTECTED:BEGIN:old_block\nold_code\n# AXIOM:PROTECTED:END:old_block",
                context="deleted_function",
                start_line=1,
                end_line=3,
            )
        ]

        result = inject_protected_blocks(code, blocks)

        # Should include the block with a warning
        assert "old_code" in result
        assert "deleted_function" in result
        assert "no longer exists" in result


class TestValidateProtectedBlocks:
    """Tests for validate_protected_blocks function."""

    def test_no_warnings(self) -> None:
        """Test validation with unique block names."""
        blocks = [
            ProtectedBlock(
                name="block1",
                content="",
                context=None,
                start_line=1,
                end_line=3,
            ),
            ProtectedBlock(
                name="block2",
                content="",
                context=None,
                start_line=5,
                end_line=7,
            ),
        ]
        warnings = validate_protected_blocks(blocks)
        assert len(warnings) == 0

    def test_duplicate_names(self) -> None:
        """Test validation detects duplicate block names."""
        blocks = [
            ProtectedBlock(
                name="duplicate",
                content="",
                context=None,
                start_line=1,
                end_line=3,
            ),
            ProtectedBlock(
                name="duplicate",
                content="",
                context=None,
                start_line=5,
                end_line=7,
            ),
        ]
        warnings = validate_protected_blocks(blocks)

        assert len(warnings) == 1
        assert "duplicate" in warnings[0].lower()

    def test_unnamed_blocks_allowed(self) -> None:
        """Test that multiple unnamed blocks don't generate warnings."""
        blocks = [
            ProtectedBlock(
                name=None,
                content="",
                context=None,
                start_line=1,
                end_line=3,
            ),
            ProtectedBlock(
                name=None,
                content="",
                context=None,
                start_line=5,
                end_line=7,
            ),
        ]
        warnings = validate_protected_blocks(blocks)
        assert len(warnings) == 0


class TestRoundTrip:
    """Test extracting and re-injecting blocks."""

    def test_round_trip_preserves_content(self) -> None:
        """Test that extract -> inject preserves block content."""
        original_code = '''
def validate_email(email: str) -> bool:
    """Validate email format."""
    # AXIOM:PROTECTED:BEGIN:custom
    # Custom validation here
    if "spam" in email:
        return False
    # AXIOM:PROTECTED:END:custom
    return "@" in email
'''
        # Extract blocks
        blocks = extract_protected_blocks(original_code)
        assert len(blocks) == 1

        # Simulate regeneration (new code without the block)
        new_code = '''
def validate_email(email: str) -> bool:
    """Validate email format - regenerated."""
    return "@" in email
'''
        # Inject blocks back
        result = inject_protected_blocks(new_code, blocks)

        # Original custom code should be preserved
        assert "spam" in result
        assert "Custom validation" in result
