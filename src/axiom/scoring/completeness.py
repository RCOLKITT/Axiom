"""Spec completeness scoring system.

Analyzes specs and provides a completeness score with suggestions for improvement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from axiom.spec.models import Spec


@dataclass
class CompletenessScore:
    """Completeness score for a spec.

    Attributes:
        overall: Overall completeness score (0.0 - 1.0).
        example_coverage: Score for example coverage.
        invariant_coverage: Score for invariant/property coverage.
        edge_coverage: Score for edge case handling.
        error_coverage: Score for exception case coverage.
        documentation_score: Score for documentation quality.
        missing: List of missing elements.
        suggestions: List of improvement suggestions.
    """

    overall: float
    example_coverage: float = 0.0
    invariant_coverage: float = 0.0
    edge_coverage: float = 0.0
    error_coverage: float = 0.0
    documentation_score: float = 0.0
    missing: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


def score_spec(spec: Spec) -> CompletenessScore:
    """Analyze a spec and return its completeness score.

    Args:
        spec: The parsed spec to score.

    Returns:
        CompletenessScore with detailed breakdown.
    """
    missing: list[str] = []
    suggestions: list[str] = []

    # Score example coverage
    example_score = _score_examples(spec, missing, suggestions)

    # Score invariant coverage
    invariant_score = _score_invariants(spec, missing, suggestions)

    # Score edge case coverage
    edge_score = _score_edge_cases(spec, missing, suggestions)

    # Score error handling coverage
    error_score = _score_error_handling(spec, missing, suggestions)

    # Score documentation quality
    doc_score = _score_documentation(spec, missing, suggestions)

    # Calculate overall score (weighted average)
    weights = {
        "examples": 0.35,
        "invariants": 0.25,
        "edge_cases": 0.15,
        "error_handling": 0.10,
        "documentation": 0.15,
    }

    overall = (
        example_score * weights["examples"]
        + invariant_score * weights["invariants"]
        + edge_score * weights["edge_cases"]
        + error_score * weights["error_handling"]
        + doc_score * weights["documentation"]
    )

    return CompletenessScore(
        overall=overall,
        example_coverage=example_score,
        invariant_coverage=invariant_score,
        edge_coverage=edge_score,
        error_coverage=error_score,
        documentation_score=doc_score,
        missing=missing,
        suggestions=suggestions,
    )


def _score_examples(spec: Spec, missing: list[str], suggestions: list[str]) -> float:
    """Score the example coverage.

    Args:
        spec: The spec to score.
        missing: List to append missing items to.
        suggestions: List to append suggestions to.

    Returns:
        Score from 0.0 to 1.0.
    """
    if not spec.examples:
        missing.append("No examples defined")
        suggestions.append("Add at least 3 examples covering basic, edge, and error cases")
        return 0.0

    num_examples = len(spec.examples)
    num_params = len(spec.interface.parameters) if hasattr(spec.interface, "parameters") else 0

    # Base score based on number of examples
    if num_examples >= 5:
        base_score = 1.0
    elif num_examples >= 3:
        base_score = 0.8
    elif num_examples >= 2:
        base_score = 0.6
    else:
        base_score = 0.4

    # Bonus for covering multiple parameter combinations
    if num_params > 1 and num_examples < num_params * 2:
        suggestions.append(
            f"Consider adding more examples to cover parameter combinations "
            f"({num_examples} examples for {num_params} parameters)"
        )
        base_score *= 0.9

    # Check for variety in examples
    has_negative_case = False
    has_zero_case = False
    has_empty_case = False

    for example in spec.examples:
        for value in example.input.values():
            if isinstance(value, (int, float)):
                if value < 0:
                    has_negative_case = True
                elif value == 0:
                    has_zero_case = True
            elif (isinstance(value, str) and value == "") or (isinstance(value, list) and len(value) == 0):
                has_empty_case = True

    if not has_negative_case and _has_numeric_params(spec):
        suggestions.append("Consider adding examples with negative numbers")

    if not has_zero_case and _has_numeric_params(spec):
        suggestions.append("Consider adding examples with zero values")

    if not has_empty_case and _has_string_or_list_params(spec):
        suggestions.append("Consider adding examples with empty strings/lists")

    return min(1.0, base_score)


def _score_invariants(spec: Spec, missing: list[str], suggestions: list[str]) -> float:
    """Score the invariant coverage.

    Args:
        spec: The spec to score.
        missing: List to append missing items to.
        suggestions: List to append suggestions to.

    Returns:
        Score from 0.0 to 1.0.
    """
    if not spec.invariants:
        missing.append("No invariants defined")
        suggestions.append("Add invariants to specify properties that must always hold")
        return 0.0

    num_invariants = len(spec.invariants)
    has_check = any(inv.check for inv in spec.invariants)

    # Base score based on number of invariants
    if num_invariants >= 3:
        base_score = 1.0
    elif num_invariants >= 2:
        base_score = 0.8
    else:
        base_score = 0.6

    # Bonus for having machine-checkable invariants
    if not has_check:
        suggestions.append("Add 'check' expressions to invariants for automated verification")
        base_score *= 0.7

    # Check ratio of checked to total invariants
    checked_count = sum(1 for inv in spec.invariants if inv.check)
    check_ratio = checked_count / num_invariants if num_invariants > 0 else 0

    if check_ratio < 0.5:
        suggestions.append(
            f"Only {checked_count}/{num_invariants} invariants have check expressions"
        )
        base_score *= 0.8

    return min(1.0, base_score)


def _score_edge_cases(spec: Spec, missing: list[str], suggestions: list[str]) -> float:
    """Score the edge case coverage.

    Args:
        spec: The spec to score.
        missing: List to append missing items to.
        suggestions: List to append suggestions to.

    Returns:
        Score from 0.0 to 1.0.
    """
    if not spec.examples:
        return 0.0

    edge_case_patterns: list[tuple[str, list[object]]] = [
        ("empty", ["", [], {}, 0]),
        ("null", [None]),
        ("boundary", ["boundary", "limit", "max", "min"]),
    ]

    found_patterns: set[str] = set()
    for example in spec.examples:
        name_lower = example.name.lower()
        for pattern_name, keywords in edge_case_patterns:
            if any(str(kw) in name_lower or str(kw) in str(example.input).lower() for kw in keywords):
                found_patterns.add(pattern_name)

        # Check for actual edge values
        for value in example.input.values():
            if value in (None, "", [], {}, 0):
                found_patterns.add("empty")

    coverage = len(found_patterns) / len(edge_case_patterns)

    if "empty" not in found_patterns:
        suggestions.append("Add examples with empty/zero values")

    if "boundary" not in found_patterns:
        suggestions.append("Consider adding boundary condition examples")

    return coverage


def _score_error_handling(spec: Spec, missing: list[str], suggestions: list[str]) -> float:
    """Score the error handling coverage.

    Args:
        spec: The spec to score.
        missing: List to append missing items to.
        suggestions: List to append suggestions to.

    Returns:
        Score from 0.0 to 1.0.
    """
    if not spec.examples:
        return 0.0

    has_error_example = False
    for example in spec.examples:
        if example.expected_output.is_exception():
            has_error_example = True
            break

    if not has_error_example:
        # Check if the function might need error handling
        param_types = spec.get_parameter_types()
        might_need_error_handling = any(
            t in ["int", "float", "str", "list", "dict"]
            for t in param_types.values()
        )
        if might_need_error_handling:
            suggestions.append("Consider adding examples with expected exceptions for error cases")
            return 0.5

    return 1.0 if has_error_example else 0.5


def _score_documentation(spec: Spec, missing: list[str], suggestions: list[str]) -> float:
    """Score the documentation quality.

    Args:
        spec: The spec to score.
        missing: List to append missing items to.
        suggestions: List to append suggestions to.

    Returns:
        Score from 0.0 to 1.0.
    """
    score = 0.0

    # Check metadata description
    if spec.metadata.description:
        score += 0.2
    else:
        missing.append("No description in metadata")

    # Check intent
    if spec.intent:
        intent_words = len(spec.intent.split())
        if intent_words >= 20:
            score += 0.3
        elif intent_words >= 10:
            score += 0.2
            suggestions.append("Consider expanding the intent with more details")
        else:
            score += 0.1
            suggestions.append("Intent is very brief - consider adding more details")
    else:
        missing.append("No intent defined")

    # Check parameter descriptions
    if hasattr(spec.interface, "parameters"):
        params = spec.interface.parameters
        if params:
            described = sum(1 for p in params if p.description)
            if described == len(params):
                score += 0.25
            elif described > 0:
                score += 0.15
                suggestions.append(
                    f"Only {described}/{len(params)} parameters have descriptions"
                )
            else:
                missing.append("No parameter descriptions")
        else:
            score += 0.25  # No params = full credit for param docs

    # Check returns description
    returns = spec.interface.returns if hasattr(spec.interface, "returns") else None
    if returns and returns.description:
        score += 0.25
    else:
        suggestions.append("Add a description to the return value")

    return min(1.0, score)


def _has_numeric_params(spec: Spec) -> bool:
    """Check if spec has numeric parameters."""
    if not hasattr(spec.interface, "parameters"):
        return False
    return any(
        p.type.lower() in ["int", "float", "number"]
        for p in spec.interface.parameters
    )


def _has_string_or_list_params(spec: Spec) -> bool:
    """Check if spec has string or list parameters."""
    if not hasattr(spec.interface, "parameters"):
        return False
    return any(
        p.type.lower() in ["str", "string"] or p.type.lower().startswith("list")
        for p in spec.interface.parameters
    )


def format_score(score: CompletenessScore, spec_name: str, use_color: bool = True) -> str:
    """Format a completeness score for display.

    Args:
        score: The completeness score to format.
        spec_name: Name of the spec.
        use_color: Whether to use ANSI colors.

    Returns:
        Formatted score string.
    """
    def _bar(value: float, width: int = 10) -> str:
        filled = int(value * width)
        empty = width - filled
        return "█" * filled + "░" * empty

    def _color(text: str, color_code: str) -> str:
        if use_color:
            return f"\033[{color_code}m{text}\033[0m"
        return text

    def _score_color(value: float) -> str:
        if value >= 0.8:
            return "32"  # Green
        elif value >= 0.5:
            return "33"  # Yellow
        else:
            return "31"  # Red

    overall_pct = int(score.overall * 100)
    overall_color = _score_color(score.overall)

    lines = [
        f"\nSpec Completeness: {_color(f'{overall_pct}%', overall_color)}",
        "═" * 50,
        "",
        f"  Example Coverage:     {_bar(score.example_coverage)}  {int(score.example_coverage * 100)}%",
        f"  Invariant Coverage:   {_bar(score.invariant_coverage)}  {int(score.invariant_coverage * 100)}%",
        f"  Edge Case Coverage:   {_bar(score.edge_coverage)}  {int(score.edge_coverage * 100)}%",
        f"  Error Handling:       {_bar(score.error_coverage)}  {int(score.error_coverage * 100)}%",
        f"  Documentation:        {_bar(score.documentation_score)}  {int(score.documentation_score * 100)}%",
    ]

    if score.missing:
        lines.append("")
        lines.append(_color("Missing:", "31"))
        for item in score.missing:
            lines.append(f"  • {item}")

    if score.suggestions:
        lines.append("")
        lines.append(_color("Suggestions:", "33"))
        for suggestion in score.suggestions:
            lines.append(f"  • {suggestion}")

    return "\n".join(lines)
