"""The 'axiom watch' command for continuous build/verify."""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import click
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from axiom.cache import AXIOM_VERSION, CacheStore
from axiom.codegen.generator import generate_code, generate_with_verification
from axiom.codegen.post_processor import post_process
from axiom.config import load_settings
from axiom.errors import AxiomError
from axiom.security.scanner import scan_spec_file
from axiom.spec import parse_spec_file
from axiom.verify.harness import verify_code_string, verify_spec

if TYPE_CHECKING:
    from axiom.config.settings import Settings


class SpecFileHandler(FileSystemEventHandler):
    """Handles spec file changes and triggers builds."""

    def __init__(
        self,
        settings: Settings,
        verify: bool,
        verbose: bool,
    ) -> None:
        """Initialize the handler.

        Args:
            settings: Axiom settings.
            verify: Whether to verify after build.
            verbose: Whether to show verbose output.
        """
        self.settings = settings
        self.verify = verify
        self.verbose = verbose
        self.last_build: dict[str, float] = {}
        self.debounce_seconds = 0.5  # Debounce rapid changes

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        if path.suffix != ".axiom":
            return

        # Debounce: ignore if we just built this file
        now = time.time()
        last = self.last_build.get(str(path), 0)
        if now - last < self.debounce_seconds:
            return

        self.last_build[str(path)] = now
        self._build_spec(path)

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        if path.suffix != ".axiom":
            return

        self._build_spec(path)

    def _build_spec(self, spec_path: Path) -> None:
        """Build a single spec file.

        Args:
            spec_path: Path to the spec file.
        """
        # Clear screen for fresh output
        _clear_screen()

        timestamp = datetime.now().strftime("%H:%M:%S")
        click.echo(f"[{timestamp}] Change detected: {spec_path.name}")
        click.echo("─" * 50)

        try:
            # Scan for secrets
            secret_matches = scan_spec_file(spec_path)
            if secret_matches:
                click.echo("  ✗ Secrets detected:")
                for match in secret_matches:
                    click.echo(f"      Line {match.line_number}: {match.pattern_name}")
                _show_watching()
                return

            # Parse spec
            click.echo("  → Parsing...", nl=False)
            spec = parse_spec_file(spec_path)
            click.echo(" ✓")

            # Determine output path
            generated_dir = self.settings.get_generated_dir()
            generated_dir.mkdir(parents=True, exist_ok=True)
            output_path = generated_dir / f"{spec.metadata.name}.py"

            # Get model
            model = self.settings.get_model_for_target(spec.metadata.target)

            # Check cache
            cache_store = CacheStore(self.settings.get_cache_dir())
            cache_status = cache_store.lookup(spec, model, AXIOM_VERSION)

            if cache_status.hit and cache_status.entry:
                click.echo("  → Cache hit, using cached code")
                code = cache_status.entry.code
            else:
                # Generate code
                click.echo(f"  → Generating ({model})...", nl=False)
                start_time = time.time()

                if self.verify:

                    def verify_fn(code: str) -> tuple[bool, list[str]]:
                        return verify_code_string(spec, code, self.settings)

                    result = generate_with_verification(
                        spec=spec,
                        settings=self.settings,
                        verify_fn=verify_fn,
                    )
                else:
                    result = generate_code(
                        spec=spec,
                        settings=self.settings,
                    )

                duration = int((time.time() - start_time) * 1000)
                click.echo(f" ✓ ({duration}ms)")

                # Post-process
                click.echo("  → Post-processing...", nl=False)
                code = post_process(result.code, spec.spec_name)
                click.echo(" ✓")

                # Cache
                cache_store.put(spec, model, code, AXIOM_VERSION)

            # Write output
            click.echo("  → Writing...", nl=False)
            output_path.write_text(code, encoding="utf-8")
            click.echo(f" ✓ → {output_path}")

            # Verify if requested
            if self.verify:
                click.echo("")
                click.echo("  Verification:")
                verify_result = verify_spec(spec, code, self.settings)

                examples_str = (
                    f"{verify_result.examples_passed}/{verify_result.examples_total} examples"
                )
                invariants_str = (
                    f"{verify_result.invariants_passed}/{verify_result.invariants_total} invariants"
                )

                if verify_result.success:
                    click.echo(f"    ✓ {examples_str}, {invariants_str}")
                else:
                    click.echo(f"    ✗ {examples_str}, {invariants_str}")

                    # Show failures
                    failed_examples = [
                        ex
                        for ex in verify_result.example_results
                        if ex.status.value in ("failed", "error")
                    ]
                    for ex in failed_examples[:3]:
                        click.echo(f"      • {ex.name}: {ex.error_message}")
                    failed_invariants = [
                        inv
                        for inv in verify_result.invariant_results
                        if inv.status.value in ("failed", "error")
                    ]
                    for inv in failed_invariants[:3]:
                        click.echo(f"      • {inv.description}: {inv.error_message}")

            click.echo("")
            click.echo("✓ Build complete")

        except AxiomError as e:
            click.echo(" ✗")
            click.echo(f"  Error: {e}")

        except Exception as e:
            click.echo(" ✗")
            click.echo(f"  Unexpected error: {e}")

        _show_watching()


def _clear_screen() -> None:
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def _show_watching() -> None:
    """Show the watching status."""
    click.echo("")
    click.echo("─" * 50)
    click.echo("Watching for changes... (Ctrl+C to stop)")


@click.command()
@click.argument("spec_path", type=click.Path(exists=True))
@click.option("--verify/--no-verify", default=True, help="Verify after build")
@click.option("--clear/--no-clear", default=True, help="Clear screen on rebuild")
@click.pass_context
def watch(
    ctx: click.Context,
    spec_path: str,
    verify: bool,
    clear: bool,
) -> None:
    """Watch spec files and rebuild on changes.

    Monitors spec files for changes and automatically rebuilds
    and verifies when modifications are detected.

    \b
    Examples:
      axiom watch specs/                    # Watch all specs in directory
      axiom watch specs/validate_email.axiom  # Watch single spec
      axiom watch specs/ --no-verify        # Skip verification
    """
    path = Path(spec_path)
    verbose = ctx.obj.get("verbose", False)

    try:
        settings = load_settings()
    except Exception as e:
        raise click.ClickException(f"Failed to load settings: {e}") from None

    # Determine watch path
    if path.is_file():
        watch_path = path.parent
        spec_filter = path.name
    else:
        watch_path = path
        spec_filter = None

    # Create event handler
    handler = SpecFileHandler(
        settings=settings,
        verify=verify,
        verbose=verbose,
    )

    # Create observer
    observer = Observer()
    observer.schedule(handler, str(watch_path), recursive=True)

    # Start watching
    if clear:
        _clear_screen()

    click.echo("Axiom Watch Mode")
    click.echo("═" * 50)
    click.echo(f"Watching: {watch_path}/")
    if spec_filter:
        click.echo(f"Filter: {spec_filter}")
    click.echo(f"Verify: {'yes' if verify else 'no'}")
    _show_watching()

    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        click.echo("\n\nStopping watch...")
        observer.stop()

    observer.join()
    click.echo("Watch stopped.")
