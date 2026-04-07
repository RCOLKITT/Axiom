"""The 'axiom lint' command for spec validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import click

from axiom.lint.fixer import fix_spec_file, format_fix_result
from axiom.security.scanner import scan_spec_file
from axiom.spec import parse_spec_file
from axiom.spec.models import Spec


@dataclass
class LintResult:
    """Result of linting a spec file."""

    file_path: Path
    valid: bool
    errors: list[str]
    warnings: list[str]


def lint_spec(spec_path: Path) -> LintResult:
    """Lint a single spec file.

    Args:
        spec_path: Path to the spec file.

    Returns:
        LintResult with errors and warnings.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Check if file exists
    if not spec_path.exists():
        return LintResult(
            file_path=spec_path,
            valid=False,
            errors=[f"File not found: {spec_path}"],
            warnings=[],
        )

    # Try to parse the spec
    try:
        spec = parse_spec_file(spec_path)
    except Exception as e:
        return LintResult(
            file_path=spec_path,
            valid=False,
            errors=[str(e)],
            warnings=[],
        )

    # Check for secrets
    secret_matches = scan_spec_file(spec_path)
    if secret_matches:
        for match in secret_matches:
            errors.append(f"Line {match.line_number}: Potential secret ({match.pattern_name})")

    # Check for best practices
    warnings.extend(_check_best_practices(spec))

    return LintResult(
        file_path=spec_path,
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def _check_best_practices(spec: Spec) -> list[str]:
    """Check spec for best practices.

    Args:
        spec: The parsed spec.

    Returns:
        List of warning messages.
    """
    warnings: list[str] = []

    # Check examples
    if not spec.examples:
        warnings.append("No examples defined (recommend at least 3)")
    elif len(spec.examples) < 3:
        warnings.append(f"Only {len(spec.examples)} example(s) (recommend at least 3)")

    # Check for error examples
    has_error_example = any(
        hasattr(ex.expected_output, "raises")
        or (isinstance(ex.expected_output, dict) and "raises" in ex.expected_output)
        for ex in spec.examples
    )
    if not has_error_example:
        warnings.append("No error examples (consider adding cases that should raise exceptions)")

    # Check invariants
    if not spec.invariants:
        warnings.append("No invariants defined (recommend at least 1 property-based check)")

    # Check description
    if not spec.metadata.description:
        warnings.append("No description in metadata")

    # Check parameter descriptions (only for function interfaces)
    if hasattr(spec.interface, "parameters") and spec.interface.parameters:
        for param in spec.interface.parameters:
            if not param.description:
                warnings.append(f"Parameter '{param.name}' has no description")

    # Check return description (only for function interfaces)
    if hasattr(spec.interface, "returns") and spec.interface.returns:
        if not spec.interface.returns.description:
            warnings.append("Return value has no description")

    # Check version
    if spec.metadata.version == "1.0.0":
        pass  # Default version is fine
    elif not spec.metadata.version:
        warnings.append("No version specified in metadata")

    return warnings


@click.command()
@click.argument("spec_path", type=click.Path(exists=True))
@click.option("--strict", is_flag=True, help="Treat warnings as errors")
@click.option("--fix", is_flag=True, help="Auto-fix issues where possible")
@click.option(
    "--dry-run", is_flag=True, help="Show what --fix would change without modifying files"
)
@click.pass_context
def lint(ctx: click.Context, spec_path: str, strict: bool, fix: bool, dry_run: bool) -> None:
    """Validate spec files without building.

    Checks for:
    - Valid YAML syntax
    - Required spec fields
    - Potential secrets
    - Best practices (examples, invariants, descriptions)

    With --fix, automatically adds:
    - Missing descriptions
    - Placeholder examples (if <3)
    - Error case examples
    - Default invariants

    \b
    Examples:
      axiom lint specs/validate_email.axiom
      axiom lint specs/                        # Lint all specs in directory
      axiom lint specs/ --strict               # Treat warnings as errors
      axiom lint specs/ --fix                  # Auto-fix issues
      axiom lint specs/ --fix --dry-run        # Preview fixes
    """
    path = Path(spec_path)

    # Collect spec files
    if path.is_dir():
        spec_files = list(path.rglob("*.axiom"))
        if not spec_files:
            click.echo(f"No .axiom files found in {path}")
            return
    else:
        spec_files = [path]

    # If --fix mode, run fix first then re-lint
    if fix or dry_run:
        _run_fix_mode(spec_files, dry_run)
        if dry_run:
            return  # Don't lint after dry-run
        click.echo("")
        click.echo("Re-linting after fixes...")
        click.echo("")

    click.echo(f"Linting {len(spec_files)} spec(s)...\n")

    total_errors = 0
    total_warnings = 0
    results: list[LintResult] = []

    for spec_file in sorted(spec_files):
        result = lint_spec(spec_file)
        results.append(result)

        # Display result
        if result.valid and not result.warnings:
            click.echo(f"  ✓ {spec_file.name}")
        elif result.valid:
            click.echo(f"  ⚠ {spec_file.name}")
            for warning in result.warnings:
                click.echo(f"      {warning}")
            total_warnings += len(result.warnings)
        else:
            click.echo(f"  ✗ {spec_file.name}")
            for error in result.errors:
                click.echo(f"      {error}")
            for warning in result.warnings:
                click.echo(f"      {warning}")
            total_errors += len(result.errors)
            total_warnings += len(result.warnings)

    # Summary
    click.echo("")
    valid_count = sum(1 for r in results if r.valid)
    invalid_count = len(results) - valid_count
    warning_count = sum(len(r.warnings) for r in results)

    if invalid_count == 0 and warning_count == 0:
        click.echo(f"✓ All {len(results)} spec(s) valid")
    elif invalid_count == 0:
        click.echo(f"✓ All {len(results)} spec(s) valid with {warning_count} warning(s)")
    else:
        click.echo(f"✗ {invalid_count} error(s), {warning_count} warning(s)")

    # Exit with error if there are errors, or warnings in strict mode
    if invalid_count > 0:
        raise SystemExit(1)
    if strict and warning_count > 0:
        click.echo("\n(--strict mode: warnings treated as errors)")
        raise SystemExit(1)


def _run_fix_mode(spec_files: list[Path], dry_run: bool) -> None:
    """Run fix mode on spec files.

    Args:
        spec_files: List of spec files to fix.
        dry_run: If True, show what would change without modifying.
    """
    if dry_run:
        click.echo("Dry run mode - showing what would be fixed:\n")
    else:
        click.echo("Fixing spec files...\n")

    total_changes = 0

    for spec_file in sorted(spec_files):
        try:
            # Parse spec to analyze
            spec = parse_spec_file(spec_file)

            # Run fixer
            result = fix_spec_file(spec_file, spec, dry_run=dry_run)

            # Display result
            output = format_fix_result(result)
            click.echo(output)

            if result.changes:
                total_changes += len(result.changes)

                # Show diff in dry run
                if dry_run and result.content_before != result.content_after:
                    click.echo("")
                    click.echo(f"    Changes for {spec_file.name}:")
                    _show_diff(result.content_before, result.content_after)
                    click.echo("")

        except Exception as e:
            click.echo(f"✗ {spec_file.name} - Error: {e}")

    # Summary
    click.echo("")
    if dry_run:
        click.echo(f"Would make {total_changes} change(s)")
        click.echo("Run without --dry-run to apply changes")
    else:
        click.echo(f"Applied {total_changes} fix(es)")


def _show_diff(before: str, after: str) -> None:
    """Show a diff between before and after content.

    Args:
        before: Original content.
        after: Modified content.
    """
    import difflib

    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)

    diff = difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile="original",
        tofile="fixed",
        lineterm="",
    )

    for line in diff:
        line = line.rstrip("\n")
        if line.startswith("+") and not line.startswith("+++"):
            click.echo(click.style(f"      {line}", fg="green"))
        elif line.startswith("-") and not line.startswith("---"):
            click.echo(click.style(f"      {line}", fg="red"))
        elif line.startswith("@@"):
            click.echo(click.style(f"      {line}", fg="cyan"))
        else:
            click.echo(f"      {line}")
