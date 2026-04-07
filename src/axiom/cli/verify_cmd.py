"""The 'axiom verify' command."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click
import structlog

from axiom.config import load_settings
from axiom.errors import AxiomError
from axiom.escape.verifier import HandWrittenVerificationResult, verify_hand_written_interface
from axiom.sandbox.config import SandboxConfig
from axiom.sandbox.docker import DockerSandbox, create_sandbox
from axiom.spec import parse_spec_file
from axiom.spec.models import Spec
from axiom.spec.resolver import CycleError, get_build_order
from axiom.verify.harness import verify_spec
from axiom.verify.interactive import (
    analyze_failure,
    format_failure_summary,
    format_interactive_failure,
)
from axiom.verify.reporter import format_result, format_summary

if TYPE_CHECKING:
    from axiom.config.settings import Settings

logger = structlog.get_logger()


@click.command()
@click.argument("spec_path", type=click.Path(exists=True))
@click.option(
    "--code",
    "-c",
    type=click.Path(exists=True),
    help="Path to code file (default: generated/<name>.py)",
)
@click.option("--examples/--no-examples", default=True, help="Run example tests")
@click.option("--invariants/--no-invariants", default=True, help="Run invariant tests")
@click.option("--max-examples", "-n", type=int, help="Max Hypothesis examples per invariant")
@click.option(
    "--include-escape-hatches/--no-escape-hatches",
    default=False,
    help="Also verify hand-written module interfaces",
)
@click.option(
    "--sandboxed/--no-sandboxed",
    default=False,
    help="Run verification in an isolated sandbox (Docker if available)",
)
@click.option(
    "--interactive/--no-interactive",
    default=True,
    help="Show interactive failure analysis with suggestions",
)
@click.pass_context
def verify(
    ctx: click.Context,
    spec_path: str,
    code: str | None,
    examples: bool,
    invariants: bool,
    max_examples: int | None,
    include_escape_hatches: bool,
    sandboxed: bool,
    interactive: bool,
) -> None:
    """Verify generated code against a spec file or directory.

    When given a directory, verifies all specs in dependency order.

    Runs example-based tests and property-based invariant checks
    to ensure the generated code satisfies the specification.

    With --include-escape-hatches, also verifies that hand-written modules
    export the interfaces declared in spec dependencies.

    With --sandboxed, runs verification in an isolated environment (Docker
    if available, otherwise subprocess with resource limits).

    With --interactive (default), shows detailed failure analysis with
    actionable suggestions for fixing issues.

    \b
    Examples:
      axiom verify specs/validate_email.axiom
      axiom verify specs/user_crud/              # Verify all specs in directory
      axiom verify specs/my_spec.axiom --code src/my_module.py
      axiom verify specs/my_spec.axiom --no-invariants
      axiom verify specs/my_spec.axiom --max-examples 50
      axiom verify specs/my_spec.axiom --include-escape-hatches
      axiom verify specs/my_spec.axiom --sandboxed
      axiom verify specs/my_spec.axiom --no-interactive  # Simple output
    """
    path = Path(spec_path)
    verbose = ctx.obj.get("verbose", False)

    if sandboxed:
        click.echo("Running verification in sandbox mode...")
        _verify_sandboxed(path, code, verbose)
        return

    try:
        # Load settings
        settings = load_settings()

        # Override settings based on flags
        settings.verification.run_examples = examples
        settings.verification.run_invariants = invariants
        if max_examples is not None:
            settings.verification.hypothesis_max_examples = max_examples

        if path.is_dir():
            # Verify all specs in directory
            _verify_directory(ctx, path, settings, verbose, include_escape_hatches, interactive)
        else:
            # Verify single spec
            _verify_single_spec(
                ctx, path, code, settings, verbose, include_escape_hatches, interactive
            )

    except CycleError as e:
        raise click.ClickException(str(e)) from None
    except AxiomError as e:
        raise click.ClickException(str(e)) from None
    except click.ClickException:
        raise
    except Exception as e:
        logger.exception("Unexpected error during verification")
        raise click.ClickException(f"Verification failed: {e}") from None


def _verify_directory(
    ctx: click.Context,
    directory: Path,
    settings: Settings,
    verbose: bool,
    include_escape_hatches: bool,
    interactive: bool,
) -> None:
    """Verify all specs in a directory in dependency order.

    Args:
        ctx: Click context.
        directory: Path to the directory.
        settings: Axiom settings.
        verbose: Whether to show verbose output.
        include_escape_hatches: Whether to verify hand-written interfaces.
        interactive: Whether to show interactive failure analysis.
    """
    click.echo(f"Verifying specs in: {directory}")
    if include_escape_hatches:
        click.echo("(including escape hatch verification)")
    click.echo("")

    results = []
    escape_hatch_results: list[HandWrittenVerificationResult] = []
    total = 0
    success = 0

    for name, spec, _spec_path in get_build_order(directory):
        total += 1

        # Find corresponding code
        code_path = settings.get_generated_dir() / f"{spec.metadata.name}.py"
        if not code_path.exists():
            click.echo(f"    ⊘ {name} (code not found: {code_path})")
            continue

        try:
            code_content = code_path.read_text(encoding="utf-8")
            result = verify_spec(spec, code_content, settings)
            results.append(result)

            # Brief output
            status = "✓" if result.success else "✗"
            click.echo(
                f"    {status} {name} — "
                f"{result.examples_passed}/{result.examples_total} examples, "
                f"{result.invariants_passed}/{result.invariants_total} invariants"
            )

            if result.success:
                success += 1

            # Verify escape hatches if requested
            if include_escape_hatches:
                escape_results = _verify_escape_hatches(spec, directory.parent, verbose)
                escape_hatch_results.extend(escape_results)

        except Exception as e:
            click.echo(f"    ✗ {name}: {e}")
            logger.debug("Verification failed", spec=name, error=str(e))

    # Summary
    click.echo("")
    click.echo(f"Verify complete: {success}/{total} specs passed")

    if results:
        click.echo(format_summary(results))

    # Show escape hatch results
    if escape_hatch_results:
        click.echo("")
        click.echo("Escape Hatch Verification:")
        for eh_result in escape_hatch_results:
            status = "✓" if eh_result.interface_matches else "✗"
            click.echo(f"    {status} {eh_result.module_name}")
            if not eh_result.interface_matches:
                if eh_result.missing_exports:
                    click.echo(f"        Missing: {', '.join(eh_result.missing_exports)}")
                if eh_result.type_mismatches:
                    for mismatch in eh_result.type_mismatches:
                        click.echo(f"        Mismatch: {mismatch}")
                if eh_result.error_message:
                    click.echo(f"        Error: {eh_result.error_message}")

    failed = sum(1 for r in results if not r.success)
    escape_failed = len([r for r in escape_hatch_results if not r.interface_matches])

    if failed > 0 or escape_failed > 0:
        msg_parts = []
        if failed > 0:
            msg_parts.append(f"{failed} spec(s)")
        if escape_failed > 0:
            msg_parts.append(f"{escape_failed} escape hatch(es)")
        raise click.ClickException(f"{' and '.join(msg_parts)} failed verification")


def _verify_single_spec(
    ctx: click.Context,
    spec_file: Path,
    code: str | None,
    settings: Settings,
    verbose: bool,
    include_escape_hatches: bool,
    interactive: bool,
) -> None:
    """Verify a single spec file.

    Args:
        ctx: Click context.
        spec_file: Path to the spec file.
        code: Optional path to code file.
        settings: Axiom settings.
        verbose: Whether to show verbose output.
        include_escape_hatches: Whether to verify hand-written interfaces.
        interactive: Whether to show interactive failure analysis.
    """
    # Parse spec
    click.echo(f"Loading spec: {spec_file.name}")
    spec = parse_spec_file(spec_file)

    # Determine code path
    if code:
        code_path = Path(code)
    else:
        generated_dir = settings.get_generated_dir()
        code_path = generated_dir / f"{spec.metadata.name}.py"

    # Check code exists
    if not code_path.exists():
        raise click.ClickException(
            f"Code file not found: {code_path}\n"
            f"Run 'axiom build {spec_file}' first to generate the code."
        )

    # Read code
    code_content = code_path.read_text(encoding="utf-8")

    # Run verification
    click.echo(f"Verifying: {spec.spec_name}")
    click.echo(f"Code: {code_path}")
    click.echo("")

    result = verify_spec(spec, code_content, settings)

    # Display results
    output = format_result(result, verbose=verbose)
    click.echo(output)

    # Show interactive failure analysis if verification failed
    if not result.success and interactive:
        click.echo("")
        failures = analyze_failure(result, spec, code_content)
        for failure in failures:
            click.echo(format_interactive_failure(failure, verbose=verbose))
            click.echo("")
        click.echo(format_failure_summary(failures, spec.spec_name))

    # Verify escape hatches if requested
    escape_failed = False
    if include_escape_hatches:
        project_root = spec_file.parent.parent  # Assume specs/ is one level down
        escape_results: list[HandWrittenVerificationResult] = _verify_escape_hatches(
            spec, project_root, verbose
        )

        if escape_results:
            click.echo("")
            click.echo("Escape Hatch Verification:")
            for eh_result in escape_results:
                status = "✓" if eh_result.interface_matches else "✗"
                click.echo(f"    {status} {eh_result.module_name}")
                if not eh_result.interface_matches:
                    escape_failed = True
                    if eh_result.missing_exports:
                        click.echo(f"        Missing: {', '.join(eh_result.missing_exports)}")
                    if eh_result.type_mismatches:
                        for mismatch in eh_result.type_mismatches:
                            click.echo(f"        Mismatch: {mismatch}")
                    if eh_result.error_message:
                        click.echo(f"        Error: {eh_result.error_message}")

    if not result.success or escape_failed:
        raise click.ClickException("Verification failed")


def _verify_escape_hatches(
    spec: Spec,
    project_root: Path,
    verbose: bool,
) -> list[HandWrittenVerificationResult]:
    """Verify hand-written module interfaces for a spec.

    Args:
        spec: The parsed spec.
        project_root: Project root for resolving paths.
        verbose: Whether to show verbose output.

    Returns:
        List of HandWrittenVerificationResult objects.
    """
    results: list[HandWrittenVerificationResult] = []

    # Get hand-written dependencies with structured interfaces
    for dep in spec.get_hand_written_dependencies():
        interface = dep.get_hand_written_interface()
        if interface is None:
            # Dictionary interface - can't verify structurally
            if verbose:
                logger.debug(
                    "Skipping unstructured interface",
                    dependency=dep.name,
                )
            continue

        # Verify the interface
        module_path = Path(interface.module_path)
        result = verify_hand_written_interface(
            module_path=module_path,
            interface=interface,
            project_root=project_root,
        )
        results.append(result)

        if verbose:
            logger.debug(
                "Verified escape hatch",
                module=interface.module_path,
                passed=result.interface_matches,
            )

    return results


def _verify_sandboxed(
    path: Path,
    code: str | None,
    verbose: bool,
) -> None:
    """Run verification in a sandboxed environment.

    Uses Docker if available, otherwise falls back to subprocess with resource limits.

    Args:
        path: Path to spec file or directory.
        code: Optional path to code file.
        verbose: Whether to show verbose output.
    """
    # Load settings
    settings = load_settings()

    # Handle directory or single file
    if path.is_dir():
        spec_files = list(path.glob("*.axiom"))
        if not spec_files:
            raise click.ClickException(f"No .axiom files found in {path}")
    else:
        spec_files = [path]

    # Create sandbox
    config = SandboxConfig.default()
    sandbox = create_sandbox(config)

    sandbox_type = "Docker" if isinstance(sandbox, DockerSandbox) else "subprocess"
    click.echo(f"Using {sandbox_type} sandbox")
    click.echo("")

    # Track results
    total = 0
    passed = 0
    failed_specs: list[str] = []

    for spec_file in spec_files:
        total += 1

        # Parse spec
        spec = parse_spec_file(spec_file)
        spec_name = spec.metadata.name

        # Find code path
        code_path = Path(code) if code else settings.get_generated_dir() / f"{spec_name}.py"

        if not code_path.exists():
            click.echo(f"    ⊘ {spec_name} (code not found: {code_path})")
            continue

        # Read generated code
        code_content = code_path.read_text(encoding="utf-8")

        # Get examples from spec
        examples = []
        for ex in spec.examples:
            examples.append(
                {
                    "name": ex.name,
                    "input": ex.input or {},
                    "expected_output": ex.expected_output,
                }
            )

        # Run verification in sandbox
        click.echo(f"Verifying: {spec_name}")
        result = sandbox.execute_verification(
            generated_code=code_content,
            spec_name=spec.interface.function_name,
            examples=examples,
        )

        if result.success:
            click.echo(f"    ✓ {spec_name} — {len(examples)} examples passed")
            passed += 1
        else:
            click.echo(f"    ✗ {spec_name}")
            failed_specs.append(spec_name)

            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    click.echo(f"        {line}")
            if result.stderr:
                for line in result.stderr.strip().split("\n"):
                    click.echo(f"        {line}")
            if result.timed_out:
                click.echo(f"        Timed out after {config.timeout_seconds}s")
            if result.error:
                click.echo(f"        Error: {result.error}")

        if verbose:
            click.echo(f"        Duration: {result.duration_ms}ms")
            if result.memory_used_mb:
                click.echo(f"        Memory: {result.memory_used_mb:.1f}MB")

    # Summary
    click.echo("")
    click.echo(f"Sandboxed verification complete: {passed}/{total} specs passed")

    if failed_specs:
        raise click.ClickException(
            f"{len(failed_specs)} spec(s) failed verification: {', '.join(failed_specs)}"
        )


@click.command(name="verify-all")
@click.argument("spec_dir", type=click.Path(exists=True), default="specs")
@click.option("--examples/--no-examples", default=True, help="Run example tests")
@click.option("--invariants/--no-invariants", default=True, help="Run invariant tests")
@click.pass_context
def verify_all(
    ctx: click.Context,
    spec_dir: str,
    examples: bool,
    invariants: bool,
) -> None:
    """Verify all specs in a directory.

    Recursively finds all .axiom files and runs verification on each.

    \b
    Examples:
      axiom verify-all specs/
      axiom verify-all specs/examples --no-invariants
    """
    spec_dir_path = Path(spec_dir)
    ctx.obj.get("verbose", False)

    try:
        # Load settings
        settings = load_settings()
        settings.verification.run_examples = examples
        settings.verification.run_invariants = invariants

        # Find all .axiom files
        spec_files = list(spec_dir_path.rglob("*.axiom"))

        if not spec_files:
            click.echo(f"No .axiom files found in {spec_dir}")
            return

        click.echo(f"Found {len(spec_files)} spec files")
        click.echo("")

        results = []
        for spec_file in sorted(spec_files):
            try:
                spec = parse_spec_file(spec_file)

                # Find corresponding code
                code_path = settings.get_generated_dir() / f"{spec.metadata.name}.py"
                if not code_path.exists():
                    click.echo(f"⊘ {spec.spec_name} — code not found")
                    continue

                code_content = code_path.read_text(encoding="utf-8")
                result = verify_spec(spec, code_content, settings)
                results.append(result)

                # Brief output
                status = "✓" if result.success else "✗"
                click.echo(
                    f"{status} {spec.spec_name} — "
                    f"{result.examples_passed}/{result.examples_total} examples, "
                    f"{result.invariants_passed}/{result.invariants_total} invariants"
                )

            except Exception as e:
                click.echo(f"✗ {spec_file.name} — error: {e}")

        # Summary
        if results:
            click.echo("")
            click.echo(format_summary(results))

            failed = sum(1 for r in results if not r.success)
            if failed > 0:
                raise click.ClickException(f"{failed} spec(s) failed verification")

    except click.ClickException:
        raise
    except Exception as e:
        logger.exception("Unexpected error")
        raise click.ClickException(f"Verification failed: {e}") from None
