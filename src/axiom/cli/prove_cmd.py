"""The 'axiom prove' command for formal verification.

This command uses Z3 SMT solver to mathematically prove that spec
invariants hold for all possible inputs - not just test cases.

This is the ultimate paradigm shift: mathematical certainty about code behavior.
"""

from __future__ import annotations

from pathlib import Path

import click
import structlog

from axiom.spec import parse_spec_file
from axiom.verify.formal import can_verify_formally, verify_formally

logger = structlog.get_logger()


@click.command()
@click.argument("spec_path", type=click.Path(exists=True))
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed proof information",
)
@click.pass_context
def prove(
    ctx: click.Context,
    spec_path: str,
    verbose: bool,
) -> None:
    """Formally verify spec invariants using mathematical proof.

    Unlike testing (which checks examples) or property-based testing
    (which checks random samples), formal verification proves that
    invariants hold for ALL possible inputs.

    Requires z3-solver: pip install z3-solver

    \\b
    Examples:
      axiom prove specs/validate_email.axiom
      axiom prove specs/ --verbose
    """
    path = Path(spec_path)

    # Handle directory
    if path.is_dir():
        spec_files = list(path.glob("**/*.axiom"))
    else:
        spec_files = [path]

    if not spec_files:
        raise click.ClickException(f"No .axiom files found in {path}")

    click.echo("Formal Verification")
    click.echo("═" * 60)
    click.echo("")

    total_proved = 0
    total_failed = 0
    total_unsupported = 0

    for spec_file in spec_files:
        # Parse spec
        try:
            spec = parse_spec_file(spec_file)
        except Exception as e:
            click.echo(f"  ✗ Could not parse {spec_file.name}: {e}")
            continue

        click.echo(f"Spec: {spec.metadata.name}")

        # Check if formal verification is possible
        if not spec.invariants:
            click.echo("  ○ No invariants to verify")
            click.echo("")
            continue

        if not can_verify_formally(spec):
            click.echo("  ○ Types not supported for formal verification")
            total_unsupported += len(spec.invariants)
            click.echo("")
            continue

        # Run formal verification
        results = verify_formally(spec)

        for result in results:
            if result.status == "proved":
                click.echo(f"  ✓ PROVED: {result.invariant}")
                total_proved += 1
                if verbose:
                    click.echo(f"      {result.explanation}")
            elif result.status == "counterexample":
                click.echo(f"  ✗ FAILED: {result.invariant}")
                click.echo(f"      Counterexample: {result.counterexample}")
                total_failed += 1
            elif result.status == "unknown":
                click.echo(f"  ? UNKNOWN: {result.invariant}")
                total_unsupported += 1
                if verbose:
                    click.echo(f"      {result.explanation}")
            else:
                click.echo(f"  ○ UNSUPPORTED: {result.invariant}")
                total_unsupported += 1
                if verbose:
                    click.echo(f"      {result.explanation}")

        click.echo("")

    # Summary
    click.echo("═" * 60)
    click.echo("Summary")
    click.echo("═" * 60)
    click.echo(f"  Proved:      {total_proved}")
    click.echo(f"  Failed:      {total_failed}")
    click.echo(f"  Unsupported: {total_unsupported}")
    click.echo("")

    if total_proved > 0:
        click.echo("✓ Mathematical proofs provide stronger guarantees than testing!")

    if total_failed > 0:
        raise click.ClickException(
            f"Formal verification found {total_failed} counterexample(s)"
        )
