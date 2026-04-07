"""Protected code blocks that survive regeneration.

Protected blocks allow users to add custom code to generated files
that will be preserved when the spec is rebuilt.

Usage in generated code:
    # AXIOM:PROTECTED:BEGIN
    # Custom code here...
    # AXIOM:PROTECTED:END

Or with a named block:
    # AXIOM:PROTECTED:BEGIN:custom_validation
    # Named custom code here...
    # AXIOM:PROTECTED:END:custom_validation
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

import structlog

logger = structlog.get_logger()

# Regex patterns for protected block markers
PROTECTED_BEGIN_PATTERN = re.compile(r"^(\s*)#\s*AXIOM:PROTECTED:BEGIN(?::(\w+))?\s*$")
PROTECTED_END_PATTERN = re.compile(r"^(\s*)#\s*AXIOM:PROTECTED:END(?::(\w+))?\s*$")


@dataclass
class ProtectedBlock:
    """A protected code block that survives regeneration.

    Attributes:
        name: Optional name for the block (from AXIOM:PROTECTED:BEGIN:name).
        content: The code between the markers (including the markers).
        context: The function name this block is inside (if any).
        start_line: 1-indexed line number where the block starts.
        end_line: 1-indexed line number where the block ends.
        indentation: The indentation string for this block.
    """

    name: str | None
    content: str
    context: str | None
    start_line: int
    end_line: int
    indentation: str = ""


def extract_protected_blocks(code: str) -> list[ProtectedBlock]:
    """Extract all protected blocks from code.

    Args:
        code: Python source code to scan.

    Returns:
        List of ProtectedBlock objects found in the code.
    """
    lines = code.split("\n")
    blocks: list[ProtectedBlock] = []

    # First, build a map of line numbers to function names for context
    function_ranges = _get_function_ranges(code)

    i = 0
    while i < len(lines):
        line = lines[i]
        begin_match = PROTECTED_BEGIN_PATTERN.match(line)

        if begin_match:
            indentation = begin_match.group(1)
            block_name = begin_match.group(2)
            start_line = i + 1  # 1-indexed

            # Find the matching end
            block_lines = [line]
            j = i + 1
            found_end = False

            while j < len(lines):
                block_lines.append(lines[j])
                end_match = PROTECTED_END_PATTERN.match(lines[j])

                if end_match:
                    end_name = end_match.group(2)
                    # Check for matching names
                    if block_name == end_name or (block_name is None and end_name is None):
                        found_end = True
                        break
                j += 1

            if found_end:
                end_line = j + 1  # 1-indexed

                # Determine context (which function this block is in)
                context = _find_context(start_line, function_ranges)

                blocks.append(
                    ProtectedBlock(
                        name=block_name,
                        content="\n".join(block_lines),
                        context=context,
                        start_line=start_line,
                        end_line=end_line,
                        indentation=indentation,
                    )
                )
                i = j + 1
                continue
            else:
                logger.warning(
                    "Unclosed protected block",
                    start_line=start_line,
                    block_name=block_name,
                )

        i += 1

    return blocks


def _get_function_ranges(code: str) -> list[tuple[str, int, int]]:
    """Get the line ranges for all function definitions.

    Args:
        code: Python source code.

    Returns:
        List of (function_name, start_line, end_line) tuples.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    ranges: list[tuple[str, int, int]] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Get the end line of the function
            end_line = node.end_lineno or node.lineno
            ranges.append((node.name, node.lineno, end_line))

    return ranges


def _find_context(line_number: int, function_ranges: list[tuple[str, int, int]]) -> str | None:
    """Find which function contains a given line number.

    Args:
        line_number: 1-indexed line number.
        function_ranges: List of (function_name, start, end) tuples.

    Returns:
        Function name if line is inside a function, None otherwise.
    """
    for name, start, end in function_ranges:
        if start <= line_number <= end:
            return name
    return None


def inject_protected_blocks(
    new_code: str,
    blocks: list[ProtectedBlock],
) -> str:
    """Inject protected blocks into newly generated code.

    Strategy:
    1. If a block has a context (function name), inject at the end of that function
    2. If a block is at module level, inject at the end of the module
    3. If a context function doesn't exist in new code, append at end with warning

    Args:
        new_code: The newly generated code to inject blocks into.
        blocks: List of protected blocks to inject.

    Returns:
        New code with protected blocks injected.
    """
    if not blocks:
        return new_code

    # Get function ranges in new code
    function_ranges = _get_function_ranges(new_code)
    function_map = {name: (start, end) for name, start, end in function_ranges}

    # Group blocks by whether they have context and if that context exists
    module_level_blocks: list[ProtectedBlock] = []
    function_blocks: dict[str, list[ProtectedBlock]] = {}
    orphan_blocks: list[ProtectedBlock] = []

    for block in blocks:
        if block.context is None:
            module_level_blocks.append(block)
        elif block.context in function_map:
            if block.context not in function_blocks:
                function_blocks[block.context] = []
            function_blocks[block.context].append(block)
        else:
            # Context function doesn't exist anymore
            orphan_blocks.append(block)
            logger.warning(
                "Protected block context function no longer exists",
                block_name=block.name,
                context=block.context,
            )

    lines = new_code.split("\n")

    # Inject function-context blocks (in reverse order by line number to avoid shifting)
    for func_name, func_blocks in function_blocks.items():
        _, end_line = function_map[func_name]
        # Find the last line of the function body
        insert_idx = end_line - 1  # 0-indexed, before the line after function ends

        # Insert each block at the end of the function
        for block in reversed(func_blocks):
            block_content = _adjust_indentation(block.content, block.indentation)
            lines.insert(insert_idx, block_content)

    # Append module-level blocks at the end
    if module_level_blocks or orphan_blocks:
        lines.append("")
        lines.append("# " + "=" * 70)
        lines.append("# Protected blocks preserved from previous generation")
        lines.append("# " + "=" * 70)

        for block in module_level_blocks:
            lines.append("")
            lines.append(block.content)

        for block in orphan_blocks:
            lines.append("")
            lines.append(f"# WARNING: Original context function '{block.context}' no longer exists")
            lines.append(block.content)

    return "\n".join(lines)


def _adjust_indentation(content: str, original_indent: str) -> str:
    """Adjust indentation of block content.

    Args:
        content: Block content.
        original_indent: Original indentation string.

    Returns:
        Content with consistent indentation.
    """
    # For now, just return the content as-is
    # Could implement more sophisticated indentation adjustment if needed
    return content


def validate_protected_blocks(blocks: list[ProtectedBlock]) -> list[str]:
    """Validate protected blocks and return any warnings.

    Args:
        blocks: List of protected blocks to validate.

    Returns:
        List of warning messages.
    """
    warnings: list[str] = []
    names_seen: set[str] = set()

    for block in blocks:
        if block.name:
            if block.name in names_seen:
                warnings.append(
                    f"Duplicate protected block name: '{block.name}' "
                    f"(lines {block.start_line}-{block.end_line})"
                )
            names_seen.add(block.name)

    return warnings
