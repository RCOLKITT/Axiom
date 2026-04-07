"""The 'axiom doctor' command for environment health checks."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import click

from axiom import __version__
from axiom.config import load_settings


@click.command()
@click.pass_context
def doctor(ctx: click.Context) -> None:
    """Check Axiom environment and configuration.

    Verifies that all required components are properly configured:
    - Axiom version and Python environment
    - API keys for LLM providers
    - Docker availability for sandboxed execution
    - Project configuration

    \b
    Examples:
      axiom doctor              # Run all checks
    """
    click.echo("Checking Axiom environment...\n")

    all_passed = True
    warnings = []

    # 1. Axiom version
    click.echo(f"  ✓ Axiom version: {__version__}")

    # 2. Python version
    import sys

    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    click.echo(f"  ✓ Python: {python_version}")

    # 3. API keys
    if os.environ.get("ANTHROPIC_API_KEY"):
        click.echo("  ✓ API key: ANTHROPIC_API_KEY found")
    elif os.environ.get("OPENAI_API_KEY"):
        click.echo("  ✓ API key: OPENAI_API_KEY found")
    else:
        click.echo("  ✗ API key: No ANTHROPIC_API_KEY or OPENAI_API_KEY found")
        click.echo("      Set one with: export ANTHROPIC_API_KEY=sk-...")
        all_passed = False

    # 4. Docker availability
    docker_available = shutil.which("docker") is not None
    if docker_available:
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                click.echo("  ✓ Docker: running (sandboxed execution available)")
            else:
                click.echo("  ⚠ Docker: installed but not running")
                warnings.append("Start Docker for sandboxed execution")
        except (subprocess.TimeoutExpired, Exception):
            click.echo("  ⚠ Docker: installed but not responding")
            warnings.append("Check Docker status")
    else:
        click.echo("  ⚠ Docker: not installed (subprocess fallback will be used)")
        warnings.append("Install Docker for full sandboxed execution")

    # 5. Project configuration
    axiom_toml = Path("axiom.toml")
    if axiom_toml.exists():
        try:
            settings = load_settings()
            click.echo(f"  ✓ Project: {settings.project.name}")

            # Check directories
            spec_dir = Path(settings.project.spec_dir)
            generated_dir = settings.get_generated_dir()
            cache_dir = settings.get_cache_dir()

            if spec_dir.exists():
                spec_count = len(list(spec_dir.rglob("*.axiom")))
                click.echo(f"  ✓ Specs directory: {spec_dir}/ ({spec_count} specs)")
            else:
                click.echo(f"  ⚠ Specs directory: {spec_dir}/ (not created yet)")
                warnings.append(f"Create {spec_dir}/ directory")

            # Check if generated dir is writable
            try:
                generated_dir.mkdir(parents=True, exist_ok=True)
                click.echo(f"  ✓ Generated directory: {generated_dir}/ (writable)")
            except PermissionError:
                click.echo(f"  ✗ Generated directory: {generated_dir}/ (not writable)")
                all_passed = False

            # Check cache dir
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
                click.echo(f"  ✓ Cache directory: {cache_dir}/ (writable)")
            except PermissionError:
                click.echo(f"  ✗ Cache directory: {cache_dir}/ (not writable)")
                all_passed = False

        except Exception as e:
            click.echo(f"  ✗ Project: axiom.toml exists but has errors: {e}")
            all_passed = False
    else:
        click.echo("  ⚠ Project: No axiom.toml found (run 'axiom init' to create)")
        warnings.append("Run 'axiom init' to initialize a project")

    # 6. Check for common issues
    gitignore = Path(".gitignore")
    if gitignore.exists():
        content = gitignore.read_text()
        missing_ignores = []
        if "generated/" not in content and "/generated" not in content:
            missing_ignores.append("generated/")
        if ".axiom-cache/" not in content and "/.axiom-cache" not in content:
            missing_ignores.append(".axiom-cache/")

        if missing_ignores:
            click.echo(f"  ⚠ .gitignore: Missing {', '.join(missing_ignores)}")
            warnings.append(f"Add {', '.join(missing_ignores)} to .gitignore")
        else:
            click.echo("  ✓ .gitignore: Properly configured")

    # Summary
    click.echo("")
    if all_passed and not warnings:
        click.echo("All checks passed. Ready to build!")
    elif all_passed:
        click.echo(f"Checks passed with {len(warnings)} warning(s):")
        for w in warnings:
            click.echo(f"  • {w}")
    else:
        click.echo("Some checks failed. Please fix the issues above.")
        raise SystemExit(1)
