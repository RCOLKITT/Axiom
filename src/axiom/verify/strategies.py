"""Hypothesis strategies for property-based testing.

This module provides functions to convert spec type annotations to
Hypothesis strategies for generating test data.
"""

from __future__ import annotations

from typing import Any

import structlog

# Try to import hypothesis
try:
    from hypothesis import strategies as st

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False
    st = None  # type: ignore[assignment]

logger = structlog.get_logger()


def create_strategy_for_type(type_str: str, constraints: str | None = None) -> Any:
    """Convert a Python type string to a Hypothesis strategy.

    Args:
        type_str: Python type annotation string.
        constraints: Optional constraints string.

    Returns:
        A Hypothesis strategy, or None if Hypothesis is not available.
    """
    if not HYPOTHESIS_AVAILABLE:
        return None

    # Normalize type string
    type_lower = type_str.lower().strip()

    # Handle basic types
    if type_lower == "str":
        return _str_strategy(constraints)
    elif type_lower == "int":
        return _int_strategy(constraints)
    elif type_lower == "float":
        return st.floats(allow_nan=False, allow_infinity=False)
    elif type_lower == "bool":
        return st.booleans()
    elif type_lower.startswith("list["):
        inner = type_str[5:-1]
        inner_strategy = create_strategy_for_type(inner, None)
        if inner_strategy is not None:
            return st.lists(inner_strategy, max_size=10)
        return st.lists(st.text(max_size=20), max_size=10)
    elif type_lower.startswith("dict["):
        # Simple dict strategy
        return st.dictionaries(st.text(max_size=10), st.text(max_size=10), max_size=5)
    elif type_lower == "any":
        return st.one_of(st.text(), st.integers(), st.booleans())

    # Default to text
    logger.debug("Unknown type, using text strategy", type=type_str)
    return st.text(max_size=100)


def _str_strategy(constraints: str | None) -> Any:
    """Build a string strategy based on constraints.

    Args:
        constraints: Optional constraints string.

    Returns:
        A Hypothesis string strategy.
    """
    if not HYPOTHESIS_AVAILABLE:
        return None

    if constraints:
        constraints_lower = constraints.lower()
        if "non-empty" in constraints_lower:
            return st.text(min_size=1, max_size=100)
        if "email" in constraints_lower:
            return st.emails()

    # Default: allow any string including empty
    return st.text(max_size=100)


def _int_strategy(constraints: str | None) -> Any:
    """Build an integer strategy based on constraints.

    Args:
        constraints: Optional constraints string.

    Returns:
        A Hypothesis integer strategy.
    """
    if not HYPOTHESIS_AVAILABLE:
        return None

    min_val = None
    max_val = None

    if constraints:
        constraints_lower = constraints.lower()
        if "positive" in constraints_lower or "> 0" in constraints:
            min_val = 1
        if ">= 0" in constraints:
            min_val = 0

    return st.integers(min_value=min_val, max_value=max_val)
