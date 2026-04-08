"""Tests for spec completeness scoring."""

from __future__ import annotations

from axiom.scoring.completeness import CompletenessScore, format_score, score_spec
from axiom.spec.models import (
    Example,
    ExpectedOutput,
    FunctionInterface,
    Invariant,
    Metadata,
    Parameter,
    Returns,
    Spec,
)


def _make_spec(
    examples: list[Example] | None = None,
    invariants: list[Invariant] | None = None,
    params: list[Parameter] | None = None,
    description: str = "Test function",
    intent: str = "Test intent for the function that does something useful",
) -> Spec:
    """Create a test spec."""
    if params is None:
        params = [Parameter(name="x", type="int", description="Input value")]

    return Spec(
        axiom="0.1",
        metadata=Metadata(
            name="test_func",
            version="1.0.0",
            description=description,
            target="python:function",
        ),
        intent=intent,
        interface=FunctionInterface(
            function_name="test_func",
            parameters=params,
            returns=Returns(type="int", description="Output value"),
        ),
        examples=examples or [],
        invariants=invariants or [],
    )


class TestScoreSpec:
    """Tests for score_spec function."""

    def test_empty_spec_scores_low(self) -> None:
        """Empty spec should score low."""
        spec = _make_spec(examples=[], invariants=[])
        score = score_spec(spec)

        assert score.overall < 0.5
        assert score.example_coverage == 0.0
        assert score.invariant_coverage == 0.0
        assert "No examples defined" in score.missing

    def test_basic_spec_scores_medium(self) -> None:
        """Spec with minimal content scores medium."""
        spec = _make_spec(
            examples=[
                Example(name="basic", input={"x": 1}, expected_output=ExpectedOutput(value=2)),
            ],
            invariants=[
                Invariant(description="Output is positive", check="output > 0"),
            ],
        )
        score = score_spec(spec)

        assert 0.3 < score.overall < 0.8
        assert score.example_coverage > 0
        assert score.invariant_coverage > 0

    def test_complete_spec_scores_high(self) -> None:
        """Comprehensive spec should score high."""
        spec = _make_spec(
            examples=[
                Example(name="positive", input={"x": 5}, expected_output=ExpectedOutput(value=10)),
                Example(name="negative", input={"x": -5}, expected_output=ExpectedOutput(value=-10)),
                Example(name="zero", input={"x": 0}, expected_output=ExpectedOutput(value=0)),
                Example(name="large", input={"x": 1000}, expected_output=ExpectedOutput(value=2000)),
                Example(
                    name="error_case",
                    input={"x": None},
                    expected_output=ExpectedOutput(raises="TypeError"),
                ),
            ],
            invariants=[
                Invariant(
                    description="Output is double the input",
                    check="output == input['x'] * 2",
                ),
                Invariant(
                    description="Sign is preserved",
                    check="(output >= 0) == (input['x'] >= 0)",
                ),
                Invariant(description="Zero gives zero", check="output == 0 if input['x'] == 0 else True"),
            ],
        )
        score = score_spec(spec)

        assert score.overall > 0.7
        assert score.example_coverage > 0.8
        assert score.invariant_coverage > 0.8

    def test_invariants_without_check_score_lower(self) -> None:
        """Invariants without check expressions score lower."""
        spec_with_check = _make_spec(
            examples=[Example(name="test", input={"x": 1}, expected_output=ExpectedOutput(value=2))],
            invariants=[Invariant(description="Test", check="output > 0")],
        )
        spec_without_check = _make_spec(
            examples=[Example(name="test", input={"x": 1}, expected_output=ExpectedOutput(value=2))],
            invariants=[Invariant(description="Test")],
        )

        score_with = score_spec(spec_with_check)
        score_without = score_spec(spec_without_check)

        assert score_with.invariant_coverage > score_without.invariant_coverage

    def test_suggestions_generated(self) -> None:
        """Score includes actionable suggestions."""
        spec = _make_spec(
            examples=[Example(name="basic", input={"x": 1}, expected_output=ExpectedOutput(value=2))],
        )
        score = score_spec(spec)

        assert len(score.suggestions) > 0

    def test_error_case_coverage(self) -> None:
        """Specs with error cases score higher on error coverage."""
        spec_with_error = _make_spec(
            examples=[
                Example(name="basic", input={"x": 1}, expected_output=ExpectedOutput(value=2)),
                Example(
                    name="error",
                    input={"x": None},
                    expected_output=ExpectedOutput(raises="TypeError"),
                ),
            ],
        )
        spec_without_error = _make_spec(
            examples=[
                Example(name="basic", input={"x": 1}, expected_output=ExpectedOutput(value=2)),
                Example(name="another", input={"x": 2}, expected_output=ExpectedOutput(value=4)),
            ],
        )

        score_with = score_spec(spec_with_error)
        score_without = score_spec(spec_without_error)

        assert score_with.error_coverage > score_without.error_coverage


class TestCompletenessScore:
    """Tests for CompletenessScore dataclass."""

    def test_score_creation(self) -> None:
        """Test creating a score object."""
        score = CompletenessScore(
            overall=0.75,
            example_coverage=0.8,
            invariant_coverage=0.7,
            edge_coverage=0.6,
            error_coverage=0.8,
            documentation_score=0.9,
            missing=["No edge cases"],
            suggestions=["Add more examples"],
        )

        assert score.overall == 0.75
        assert len(score.missing) == 1
        assert len(score.suggestions) == 1


class TestFormatScore:
    """Tests for format_score function."""

    def test_format_includes_percentages(self) -> None:
        """Formatted output includes percentages."""
        score = CompletenessScore(
            overall=0.72,
            example_coverage=0.8,
            invariant_coverage=0.6,
        )

        output = format_score(score, "test_spec", use_color=False)

        assert "72%" in output
        assert "80%" in output
        assert "60%" in output

    def test_format_includes_missing(self) -> None:
        """Formatted output includes missing items."""
        score = CompletenessScore(
            overall=0.5,
            missing=["No examples"],
        )

        output = format_score(score, "test_spec", use_color=False)

        assert "Missing" in output
        assert "No examples" in output

    def test_format_includes_suggestions(self) -> None:
        """Formatted output includes suggestions."""
        score = CompletenessScore(
            overall=0.5,
            suggestions=["Add more tests"],
        )

        output = format_score(score, "test_spec", use_color=False)

        assert "Suggestions" in output
        assert "Add more tests" in output

    def test_format_with_color(self) -> None:
        """Formatted output includes ANSI codes when color enabled."""
        score = CompletenessScore(overall=0.9)

        output = format_score(score, "test_spec", use_color=True)

        # Should contain ANSI escape codes
        assert "\033[" in output

    def test_format_without_color(self) -> None:
        """Formatted output has no ANSI codes when color disabled."""
        score = CompletenessScore(overall=0.9)

        output = format_score(score, "test_spec", use_color=False)

        # Should not contain ANSI escape codes
        assert "\033[" not in output
