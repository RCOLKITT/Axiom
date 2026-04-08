"""The 'axiom build-all' command for multi-language code generation.

This command generates code for multiple targets from a single spec,
demonstrating the paradigm shift where one specification becomes the
single source of truth across all languages.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

import click
import structlog

from axiom.cache import AXIOM_VERSION, CacheStore
from axiom.codegen.generator import generate_code
from axiom.codegen.post_processor import post_process
from axiom.config import load_settings
from axiom.security.scanner import scan_spec_file
from axiom.spec import parse_spec_file
from axiom.spec.models import Metadata, Spec

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()

# Supported targets for multi-language generation
SUPPORTED_TARGETS = [
    "python:function",
    "typescript:function",
    # "go:function",  # Future
    # "rust:function",  # Future
]


@click.command(name="build-all")
@click.argument("spec_path", type=click.Path(exists=True))
@click.option(
    "--targets",
    "-t",
    multiple=True,
    help="Target languages (default: all supported). Can specify multiple times.",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    help="Base output directory (default: generated/)",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Regenerate even if cached",
)
@click.pass_context
def build_all(
    ctx: click.Context,
    spec_path: str,
    targets: tuple[str, ...],
    output_dir: str | None,
    force: bool,
) -> None:
    """Generate code for multiple targets from a single spec.

    This is the future of software development: write once, run everywhere.
    Your spec becomes the single source of truth across Python, TypeScript, and more.

    \\b
    Examples:
      axiom build-all specs/validate_email.axiom
      axiom build-all specs/slugify.axiom --targets python:function --targets typescript:function
      axiom build-all specs/ -o dist/
    """
    settings = load_settings()
    path = Path(spec_path)

    # Determine targets
    target_list = list(targets) if targets else SUPPORTED_TARGETS

    # Validate targets
    for t in target_list:
        if t not in SUPPORTED_TARGETS:
            raise click.ClickException(
                f"Unsupported target: {t}. Supported: {', '.join(SUPPORTED_TARGETS)}"
            )

    # Determine output base directory
    base_output = Path(output_dir) if output_dir else settings.get_generated_dir()
    base_output.mkdir(parents=True, exist_ok=True)

    # Collect spec files
    if path.is_dir():
        spec_files = list(path.glob("**/*.axiom"))
    else:
        spec_files = [path]

    if not spec_files:
        raise click.ClickException(f"No .axiom files found in {path}")

    click.echo(f"Multi-target build: {len(spec_files)} spec(s) → {len(target_list)} target(s)")
    click.echo("═" * 60)
    click.echo("")

    # Track results
    results: dict[str, dict[str, str]] = {}  # spec_name -> {target -> status}

    for spec_file in spec_files:
        spec_name = spec_file.stem
        results[spec_name] = {}

        click.echo(f"Building: {spec_file.name}")
        click.echo("─" * 40)

        # Scan for secrets
        secret_matches = scan_spec_file(spec_file)
        if secret_matches:
            click.echo("  ✗ Secrets detected - skipping")
            for t in target_list:
                results[spec_name][t] = "skipped (secrets)"
            continue

        # Parse spec (without target override)
        try:
            base_spec = parse_spec_file(spec_file)
        except Exception as e:
            click.echo(f"  ✗ Parse error: {e}")
            for t in target_list:
                results[spec_name][t] = "parse error"
            continue

        # Generate for each target
        for target in target_list:
            try:
                # Create spec variant with different target
                variant_spec = _create_target_variant(base_spec, target)

                # Determine output path based on target
                target_dir = base_output / _get_target_subdir(target)
                target_dir.mkdir(parents=True, exist_ok=True)
                output_path = target_dir / _get_output_filename(spec_name, target)

                # Check cache
                cache_store = CacheStore(settings.get_cache_dir())
                model = settings.get_model_for_target(target)
                cache_status = cache_store.lookup(variant_spec, model, AXIOM_VERSION)

                if cache_status.hit and cache_status.entry and not force:
                    code = cache_status.entry.code
                    click.echo(f"  → {target}: cache hit")
                else:
                    # Generate
                    start = time.time()
                    result = generate_code(variant_spec, settings)
                    duration = int((time.time() - start) * 1000)

                    # Post-process
                    code = post_process(result.code, spec_name)

                    # Cache
                    cache_store.put(variant_spec, model, code, AXIOM_VERSION)
                    click.echo(f"  → {target}: generated ({duration}ms)")

                # Write output
                output_path.write_text(code, encoding="utf-8")
                results[spec_name][target] = "success"

            except Exception as e:
                click.echo(f"  ✗ {target}: {e}")
                results[spec_name][target] = f"error: {e}"

        click.echo("")

    # Summary
    click.echo("═" * 60)
    click.echo("Summary")
    click.echo("═" * 60)

    total_success = 0
    total_attempts = 0

    for _spec_name, target_results in results.items():
        for _target, status in target_results.items():
            total_attempts += 1
            if status == "success":
                total_success += 1

    click.echo(f"  Successful: {total_success}/{total_attempts}")
    click.echo(f"  Output: {base_output}/")

    for target in target_list:
        subdir = _get_target_subdir(target)
        click.echo(f"    {target}: {base_output}/{subdir}/")


def _create_target_variant(spec: Spec, target: str) -> Spec:
    """Create a spec variant with a different target.

    Args:
        spec: The base spec.
        target: The target to use.

    Returns:
        New spec with updated target.
    """
    # Create new metadata with updated target
    new_metadata = Metadata(
        name=spec.metadata.name,
        version=spec.metadata.version,
        description=spec.metadata.description,
        target=target,  # type: ignore[arg-type]
        tags=spec.metadata.tags,
    )

    # Return new spec with same content but different target
    return Spec(
        axiom=spec.axiom,
        metadata=new_metadata,
        intent=spec.intent,
        interface=spec.interface,
        examples=spec.examples,
        invariants=spec.invariants,
        constraints=spec.constraints,
        dependencies=spec.dependencies,
    )


def _get_target_subdir(target: str) -> str:
    """Get subdirectory name for a target.

    Args:
        target: The target string (e.g., 'python:function').

    Returns:
        Subdirectory name (e.g., 'python').
    """
    return target.split(":")[0]


def _get_output_filename(spec_name: str, target: str) -> str:
    """Get output filename for a target.

    Args:
        spec_name: The spec name.
        target: The target string.

    Returns:
        Filename with appropriate extension.
    """
    lang = target.split(":")[0]
    extensions = {
        "python": ".py",
        "typescript": ".ts",
        "go": ".go",
        "rust": ".rs",
    }
    ext = extensions.get(lang, ".txt")
    return f"{spec_name}{ext}"
