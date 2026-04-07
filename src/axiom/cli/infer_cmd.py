"""The 'axiom infer' command for spec inference from existing code."""

from __future__ import annotations

from pathlib import Path

import click
import structlog

from axiom.infer.analyzer import analyze_python_file
from axiom.infer.generator import generate_spec_from_function, write_spec_file

logger = structlog.get_logger()


@click.command()
@click.argument("source_file", type=click.Path(exists=True))
@click.option(
    "--function",
    "-f",
    help="Specific function to infer (default: all public functions)",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default="specs",
    help="Output directory for generated specs (default: specs/)",
)
@click.option(
    "--include-source/--no-source",
    default=False,
    help="Include source code in intent section",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing spec files",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be generated without writing files",
)
@click.pass_context
def infer(
    ctx: click.Context,
    source_file: str,
    function: str | None,
    output_dir: str,
    include_source: bool,
    force: bool,
    dry_run: bool,
) -> None:
    """Infer .axiom specs from existing Python code.

    Analyzes Python source files and generates spec files that describe
    the existing functions. This enables gradual adoption of Axiom for
    existing codebases.

    The inference extracts:
    - Function signatures and type hints
    - Docstrings and descriptions
    - Examples from doctests
    - Exception types that may be raised

    \b
    Examples:
      axiom infer src/utils.py                    # Infer all public functions
      axiom infer src/utils.py -f validate_email  # Infer specific function
      axiom infer src/utils.py --include-source   # Include source in intent
      axiom infer src/utils.py --dry-run          # Preview without writing
      axiom infer src/api.py -o specs/api/        # Custom output directory
    """
    source_path = Path(source_file)
    output_path = Path(output_dir)

    if not source_path.suffix == ".py":
        raise click.ClickException(f"Source file must be a Python file: {source_path}")

    click.echo(f"Analyzing: {source_path}")
    click.echo("")

    # Analyze the file
    try:
        functions = analyze_python_file(source_path, function_name=function)
    except SyntaxError as e:
        raise click.ClickException(f"Python syntax error: {e}") from e
    except Exception as e:
        raise click.ClickException(f"Failed to analyze file: {e}") from e

    if not functions:
        if function:
            raise click.ClickException(f"Function '{function}' not found in {source_path}")
        click.echo("No public functions found to infer.")
        click.echo("(Private functions starting with _ are skipped by default)")
        return

    click.echo(f"Found {len(functions)} function(s) to infer:")
    for func in functions:
        params_str = ", ".join(p.name for p in func.parameters)
        click.echo(f"  • {func.name}({params_str})")

    click.echo("")

    # Generate specs
    specs_written = 0
    specs_skipped = 0

    for func_info in functions:
        click.echo(f"Inferring: {func_info.name}")

        # Generate spec
        inferred = generate_spec_from_function(
            func_info,
            include_source=include_source,
        )

        # Show warnings
        if inferred.warnings:
            click.echo("  Warnings:")
            for warning in inferred.warnings:
                click.echo(f"    ⚠ {warning}")

        # Show confidence
        confidence_str = f"{inferred.confidence * 100:.0f}%"
        click.echo(f"  Confidence: {confidence_str}")

        if dry_run:
            # Just show what would be generated
            click.echo("")
            click.echo(f"  Would write to: {output_path / f'{func_info.name}.axiom'}")
            click.echo("")
            click.echo("  Generated spec:")
            click.echo("  " + "─" * 40)
            for line in inferred.content.split("\n"):
                click.echo(f"  {line}")
            click.echo("  " + "─" * 40)
            click.echo("")
        else:
            # Write the spec
            try:
                spec_path = write_spec_file(
                    inferred,
                    output_path,
                    overwrite=force,
                )
                click.echo(f"  Written: {spec_path}")
                specs_written += 1
            except FileExistsError as e:
                click.echo(f"  Skipped: {e} (use --force to overwrite)")
                specs_skipped += 1
            except Exception as e:
                click.echo(f"  Error: {e}")

        click.echo("")

    # Summary
    if not dry_run:
        click.echo("─" * 50)
        click.echo(f"Inference complete: {specs_written} spec(s) written")
        if specs_skipped > 0:
            click.echo(f"  {specs_skipped} spec(s) skipped (already exist)")
        click.echo("")
        click.echo("Next steps:")
        click.echo(f"  1. Review and edit the generated specs in {output_path}/")
        click.echo("  2. axiom lint specs/                # Check for issues")
        click.echo("  3. axiom build specs/               # Generate new code")
        click.echo("  4. Compare generated code with original implementation")
    else:
        click.echo("─" * 50)
        click.echo(f"Dry run complete: would write {len(functions)} spec(s)")
        click.echo("Run without --dry-run to generate spec files.")


@click.command(name="infer-all")
@click.argument("source_dir", type=click.Path(exists=True))
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default="specs",
    help="Output directory for generated specs",
)
@click.option(
    "--include-source/--no-source",
    default=False,
    help="Include source code in intent section",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing spec files",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be generated without writing files",
)
@click.pass_context
def infer_all(
    ctx: click.Context,
    source_dir: str,
    output_dir: str,
    include_source: bool,
    force: bool,
    dry_run: bool,
) -> None:
    """Infer .axiom specs from all Python files in a directory.

    Recursively finds all Python files and generates specs for public functions.

    \b
    Examples:
      axiom infer-all src/
      axiom infer-all src/ -o specs/inferred/
      axiom infer-all src/ --dry-run
    """
    source_path = Path(source_dir)
    output_path = Path(output_dir)

    # Find all Python files
    py_files = list(source_path.rglob("*.py"))

    # Filter out common non-source files
    py_files = [
        f
        for f in py_files
        if not f.name.startswith("_")
        and "test" not in f.name.lower()
        and "__pycache__" not in str(f)
    ]

    if not py_files:
        click.echo(f"No Python files found in {source_path}")
        return

    click.echo(f"Found {len(py_files)} Python file(s)")
    click.echo("")

    total_specs = 0
    total_functions = 0

    for py_file in sorted(py_files):
        try:
            functions = analyze_python_file(py_file)
        except Exception as e:
            click.echo(f"  ⚠ Skipping {py_file}: {e}")
            continue

        if not functions:
            continue

        total_functions += len(functions)

        # Determine output subdirectory based on relative path
        rel_path = py_file.relative_to(source_path)
        sub_output = output_path / rel_path.parent

        click.echo(f"Processing: {py_file} ({len(functions)} function(s))")

        for func_info in functions:
            inferred = generate_spec_from_function(
                func_info,
                include_source=include_source,
            )

            if dry_run:
                click.echo(f"    Would create: {sub_output / f'{func_info.name}.axiom'}")
                total_specs += 1
            else:
                try:
                    spec_path = write_spec_file(
                        inferred,
                        sub_output,
                        overwrite=force,
                    )
                    click.echo(f"    Created: {spec_path}")
                    total_specs += 1
                except FileExistsError:
                    click.echo(f"    Skipped: {func_info.name}.axiom (exists)")
                except Exception as e:
                    click.echo(f"    Error: {func_info.name} - {e}")

    click.echo("")
    click.echo("─" * 50)
    if dry_run:
        click.echo(
            f"Dry run: would create {total_specs} spec(s) from {total_functions} function(s)"
        )
    else:
        click.echo(f"Created {total_specs} spec(s) from {total_functions} function(s)")
