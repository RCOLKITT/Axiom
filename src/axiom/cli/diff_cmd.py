"""The 'axiom diff' command for detecting drift in generated code.

Compares cached generated code with the current files to detect hand-edits.
"""

from __future__ import annotations

import difflib
from pathlib import Path

import click
import structlog

from axiom.cache import CacheStore
from axiom.config import load_settings
from axiom.spec import parse_spec_file

logger = structlog.get_logger()


@click.command()
@click.argument("spec_path", type=click.Path(exists=True))
@click.option("--quiet", "-q", is_flag=True, help="Only output exit code, no details")
@click.option("--show-diff", is_flag=True, help="Show unified diff of changes")
@click.pass_context
def diff(ctx: click.Context, spec_path: str, quiet: bool, show_diff: bool) -> None:
    """Detect if generated code has been hand-edited.

    Compares the current generated files with what's in the cache.
    Exits with code 1 if drift is detected, 0 otherwise.

    \\b
    Examples:
      axiom diff specs/                    # Check all specs
      axiom diff specs/validate_email.axiom  # Check single spec
      axiom diff specs/ --show-diff        # Show actual changes
      axiom diff specs/ --quiet            # Silent, just exit code
    """
    path = Path(spec_path)

    try:
        settings = load_settings()
    except Exception as e:
        raise click.ClickException(f"Failed to load settings: {e}") from None

    cache_store = CacheStore(settings.get_cache_dir())
    generated_dir = settings.get_generated_dir()

    # Collect spec files
    if path.is_file():
        spec_files = [path]
    else:
        spec_files = sorted(path.rglob("*.axiom"))

    if not spec_files:
        if not quiet:
            click.echo("No spec files found.")
        return

    drift_found = False
    drift_specs: list[str] = []

    for spec_file in spec_files:
        try:
            spec = parse_spec_file(spec_file)
        except Exception as e:
            if not quiet:
                click.echo(f"  ⚠ {spec_file.name}: Parse error - {e}")
            continue

        # Get the generated file
        output_path = generated_dir / f"{spec.metadata.name}.py"
        if not output_path.exists():
            if not quiet:
                click.echo(f"  ○ {spec.metadata.name}: No generated file")
            continue

        # Get cached code
        cache_entry = cache_store.get_entry_for_spec(spec.metadata.name)
        if not cache_entry:
            if not quiet:
                click.echo(f"  ○ {spec.metadata.name}: Not in cache")
            continue

        # Compare
        current_code = output_path.read_text(encoding="utf-8")
        cached_code = cache_entry.code

        if current_code != cached_code:
            drift_found = True
            drift_specs.append(spec.metadata.name)

            if not quiet:
                click.echo(f"  ✗ {spec.metadata.name}: DRIFT DETECTED")

                if show_diff:
                    # Show unified diff
                    cached_lines = cached_code.splitlines(keepends=True)
                    current_lines = current_code.splitlines(keepends=True)
                    diff_lines = difflib.unified_diff(
                        cached_lines,
                        current_lines,
                        fromfile=f"cached/{spec.metadata.name}.py",
                        tofile=f"generated/{spec.metadata.name}.py",
                    )
                    click.echo("")
                    for line in diff_lines:
                        if line.startswith("+") and not line.startswith("+++"):
                            click.echo(f"    {click.style(line.rstrip(), fg='green')}")
                        elif line.startswith("-") and not line.startswith("---"):
                            click.echo(f"    {click.style(line.rstrip(), fg='red')}")
                        else:
                            click.echo(f"    {line.rstrip()}")
                    click.echo("")
        else:
            if not quiet:
                click.echo(f"  ✓ {spec.metadata.name}: OK")

    # Summary
    if not quiet:
        click.echo("")
        if drift_found:
            click.echo(f"Drift detected in {len(drift_specs)} spec(s):")
            for name in drift_specs:
                click.echo(f"  - {name}")
            click.echo("")
            click.echo("Run 'axiom build <spec> --force' to regenerate.")
        else:
            click.echo("No drift detected. Generated code matches cache.")

    if drift_found:
        raise SystemExit(1)
