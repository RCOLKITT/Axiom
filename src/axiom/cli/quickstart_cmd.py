"""The 'axiom quickstart' command.

Gets users to their first verified build in under 3 minutes.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import click
import structlog

from axiom.cli.init_cmd import (
    AXIOM_TOML_TEMPLATE,
    EXAMPLE_SPEC_TEMPLATE,
    GITIGNORE_TEMPLATE,
)
from axiom.config import load_settings
from axiom.spec.parser import parse_spec_file

logger = structlog.get_logger()


@click.command()
@click.argument("path", type=click.Path(), default="axiom-demo")
@click.option("--name", "-n", help="Project name (defaults to directory name)")
@click.pass_context
def quickstart(ctx: click.Context, path: str, name: str | None) -> None:
    """Create a project, build a spec, and verify it — all in one command.

    This is the fastest way to see Axiom in action. It will:
    1. Create a new project directory with axiom.toml
    2. Generate a hello_world.axiom spec
    3. Build Python code from the spec using an LLM
    4. Run verification (examples + invariants) on the generated code

    \b
    Examples:
      axiom quickstart              # Creates ./axiom-demo
      axiom quickstart my-project   # Creates ./my-project
    """
    start_time = time.time()
    project_path = Path(path).resolve()

    # Check for API key first
    if not os.environ.get("ANTHROPIC_API_KEY"):
        click.echo("")
        click.echo("⚠️  ANTHROPIC_API_KEY not set")
        click.echo("")
        click.echo("Axiom uses Claude to generate code from specs.")
        click.echo("Set your API key and try again:")
        click.echo("")
        click.echo("  export ANTHROPIC_API_KEY=sk-ant-...")
        click.echo("  axiom quickstart")
        click.echo("")
        click.echo("Get an API key at: https://console.anthropic.com/")
        raise click.Abort()

    # Header
    click.echo("")
    click.echo("╔════════════════════════════════════════════════════════════╗")
    click.echo("║              🚀 Axiom Quickstart                           ║")
    click.echo("║     Verified code generation in under 3 minutes            ║")
    click.echo("╚════════════════════════════════════════════════════════════╝")
    click.echo("")

    # Step 1: Create project
    click.echo("━━━ Step 1/3: Initialize Project ━━━")
    click.echo("")

    if project_path.exists():
        if (project_path / "axiom.toml").exists():
            click.echo(f"  ✓ Project already exists: {project_path}")
        else:
            raise click.ClickException(
                f"Directory exists but is not an Axiom project: {project_path}"
            )
    else:
        project_path.mkdir(parents=True)
        click.echo(f"  ✓ Created directory: {project_path}")

    project_name = name or project_path.name

    # Create directories
    dirs = ["specs/examples", "generated", ".axiom-cache"]
    for dir_name in dirs:
        (project_path / dir_name).mkdir(parents=True, exist_ok=True)

    # Create axiom.toml
    config_path = project_path / "axiom.toml"
    if not config_path.exists():
        config_content = AXIOM_TOML_TEMPLATE.format(name=project_name)
        config_path.write_text(config_content, encoding="utf-8")
        click.echo("  ✓ Created axiom.toml")

    # Create example spec
    spec_path = project_path / "specs/examples/hello_world.axiom"
    if not spec_path.exists():
        spec_path.write_text(EXAMPLE_SPEC_TEMPLATE, encoding="utf-8")
        click.echo("  ✓ Created hello_world.axiom spec")

    # Create .gitignore
    gitignore_path = project_path / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text(GITIGNORE_TEMPLATE, encoding="utf-8")
        click.echo("  ✓ Created .gitignore")

    # Create .gitkeep files
    (project_path / "generated/.gitkeep").touch()
    (project_path / ".axiom-cache/.gitkeep").touch()

    click.echo("")

    # Step 2: Build the spec
    click.echo("━━━ Step 2/3: Generate Code from Spec ━━━")
    click.echo("")
    click.echo("  📄 Spec: hello_world.axiom")
    click.echo("  🤖 Model: Claude (via Anthropic API)")
    click.echo("")

    # Change to project directory for build
    original_cwd = Path.cwd()
    os.chdir(project_path)

    verify_result = None  # Initialize to handle errors before verification
    try:
        settings = load_settings()
        spec = parse_spec_file(spec_path)

        # Import here to avoid circular imports
        from axiom.codegen.generator import generate_code
        from axiom.codegen.post_processor import post_process

        click.echo("  ⏳ Generating code...")

        result = generate_code(spec, settings)
        final_code = post_process(result.code, spec.spec_name)

        # Write output
        output_path = project_path / "generated/hello_world.py"
        output_path.write_text(final_code, encoding="utf-8")

        click.echo(f"  ✓ Generated code in {result.duration_ms}ms")
        click.echo(f"  ✓ Wrote: generated/hello_world.py")
        click.echo("")

        # Show generated code preview
        click.echo("  ┌─────────────────────────────────────────")
        lines = final_code.strip().split("\n")
        for line in lines[:15]:
            click.echo(f"  │ {line}")
        if len(lines) > 15:
            click.echo(f"  │ ... ({len(lines) - 15} more lines)")
        click.echo("  └─────────────────────────────────────────")
        click.echo("")

        # Step 3: Verify
        click.echo("━━━ Step 3/3: Verify Generated Code ━━━")
        click.echo("")

        from axiom.verify.harness import verify_spec

        click.echo("  ⏳ Running verification...")

        verify_result = verify_spec(spec, final_code, settings)

        if verify_result.success:
            click.echo(f"  ✓ {verify_result.examples_passed}/{verify_result.examples_total} examples passed")
            click.echo(f"  ✓ {verify_result.invariants_passed}/{verify_result.invariants_total} invariants passed")
        else:
            click.echo(f"  ✗ Verification failed")
            for ex in verify_result.example_results:
                if ex.status.value == "failed":
                    click.echo(f"    - Example '{ex.name}': {ex.error_message}")

        click.echo("")

    finally:
        os.chdir(original_cwd)

    # Summary
    total_time = time.time() - start_time
    click.echo("╔════════════════════════════════════════════════════════════╗")
    if verify_result is None:
        click.echo("║  ❌ Build failed. Check the error above.                    ║")
    elif verify_result.success:
        click.echo("║  ✅ SUCCESS! Your first spec is built and verified.        ║")
    else:
        click.echo("║  ⚠️  Build complete, but verification failed.              ║")
    click.echo("╚════════════════════════════════════════════════════════════╝")
    click.echo("")
    click.echo(f"  Time: {total_time:.1f}s")
    click.echo(f"  Project: {project_path}")
    click.echo("")
    click.echo("What just happened:")
    click.echo("  1. Created a spec file describing a 'hello_world' function")
    click.echo("  2. Claude generated Python code matching the spec")
    click.echo("  3. Axiom verified the code against examples and invariants")
    click.echo("")
    click.echo("Next steps:")
    click.echo(f"  cd {path}")
    click.echo("  cat specs/examples/hello_world.axiom   # View the spec")
    click.echo("  cat generated/hello_world.py           # View generated code")
    click.echo("  axiom new my_function                  # Create your own spec")
    click.echo("")
