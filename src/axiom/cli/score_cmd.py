"""Score command for spec completeness analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click
import structlog

from axiom.scoring.completeness import format_score, score_spec
from axiom.spec.parser import parse_spec_file

logger = structlog.get_logger()


@click.command("score")
@click.argument(
    "spec_files",
    nargs=-1,
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output scores as JSON",
)
@click.option(
    "--no-color",
    is_flag=True,
    help="Disable colored output",
)
@click.option(
    "--min-score",
    type=float,
    default=None,
    help="Exit with error if any spec scores below this threshold (0.0-1.0)",
)
def score_command(
    spec_files: tuple[Path, ...],
    output_json: bool,
    no_color: bool,
    min_score: float | None,
) -> None:
    """Score spec files for completeness.

    Analyzes one or more .axiom spec files and provides a completeness score
    with suggestions for improvement.

    Examples:

        axiom score specs/validate_email.axiom

        axiom score specs/*.axiom --min-score 0.7

        axiom score specs/ --json
    """
    import json
    import sys

    scores: list[dict[str, Any]] = []
    failed_threshold = False

    for spec_path in spec_files:
        # Handle directories
        if spec_path.is_dir():
            axiom_files = list(spec_path.glob("**/*.axiom"))
            if not axiom_files:
                click.echo(f"No .axiom files found in {spec_path}", err=True)
                continue
            for f in axiom_files:
                _process_spec(f, scores, output_json, no_color, min_score)
        else:
            _process_spec(spec_path, scores, output_json, no_color, min_score)

    # Check threshold
    if min_score is not None:
        for score_data in scores:
            if score_data["overall"] < min_score:
                failed_threshold = True

    # Output JSON if requested
    if output_json:
        click.echo(json.dumps(scores, indent=2))

    # Summary for multiple specs
    if len(scores) > 1 and not output_json:
        avg_score = sum(s["overall"] for s in scores) / len(scores)
        click.echo("")
        click.echo("=" * 50)
        click.echo(f"Average Completeness: {int(avg_score * 100)}%")
        click.echo(f"Specs analyzed: {len(scores)}")

    # Exit with error if threshold not met
    if failed_threshold:
        click.echo(f"\nError: Some specs scored below {min_score:.0%}", err=True)
        sys.exit(1)


def _process_spec(
    spec_path: Path,
    scores: list[dict[str, Any]],
    output_json: bool,
    no_color: bool,
    min_score: float | None,
) -> None:
    """Process a single spec file.

    Args:
        spec_path: Path to the spec file.
        scores: List to append score data to.
        output_json: Whether to output JSON.
        no_color: Whether to disable colors.
        min_score: Minimum score threshold.
    """
    try:
        spec = parse_spec_file(spec_path)
        score = score_spec(spec)

        score_data = {
            "spec": str(spec_path),
            "name": spec.spec_name,
            "overall": score.overall,
            "example_coverage": score.example_coverage,
            "invariant_coverage": score.invariant_coverage,
            "edge_coverage": score.edge_coverage,
            "error_coverage": score.error_coverage,
            "documentation_score": score.documentation_score,
            "missing": score.missing,
            "suggestions": score.suggestions,
        }
        scores.append(score_data)

        if not output_json:
            click.echo(f"\n{spec_path}")
            click.echo(format_score(score, spec.spec_name, use_color=not no_color))

            # Show threshold warning
            if min_score is not None and score.overall < min_score:
                click.echo(
                    click.style(
                        f"\n⚠ Below threshold ({int(min_score * 100)}%)",
                        fg="red" if not no_color else None,
                    )
                )

    except Exception as e:
        logger.error("Failed to score spec", path=str(spec_path), error=str(e))
        if not output_json:
            click.echo(f"Error scoring {spec_path}: {e}", err=True)
