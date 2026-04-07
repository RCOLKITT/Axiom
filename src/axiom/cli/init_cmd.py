"""The 'axiom init' command."""

from __future__ import annotations

from pathlib import Path

import click
import structlog

logger = structlog.get_logger()


AXIOM_TOML_TEMPLATE = """[project]
name = "{name}"
version = "0.1.0"
spec_dir = "specs"
generated_dir = "generated"
cache_dir = ".axiom-cache"

[generation]
default_model = "claude-sonnet-4-20250514"
fallback_model = "claude-haiku-4-5-20251001"
default_target = "python:function"
temperature = 0.0
max_retries = 3
timeout_seconds = 60

[verification]
run_examples = true
run_invariants = true
hypothesis_max_examples = 100
timeout_seconds = 120

[cache]
enabled = true
strategy = "content-hash"

[logging]
level = "INFO"
format = "console"
"""

EXAMPLE_SPEC_TEMPLATE = """axiom: "0.1"

metadata:
  name: hello_world
  version: "1.0.0"
  description: "Returns a greeting message"
  target: "python:function"

intent: |
  Takes a name and returns a greeting message.
  If the name is empty or only whitespace, raises ValueError.

interface:
  function_name: hello_world
  parameters:
    - name: name
      type: str
      description: "The name to greet"
      constraints: "non-empty string"
  returns:
    type: str
    description: "A greeting message"

examples:
  - name: basic_greeting
    input:
      name: "World"
    expected_output: "Hello, World!"

  - name: different_name
    input:
      name: "Axiom"
    expected_output: "Hello, Axiom!"

  - name: empty_name
    input:
      name: ""
    expected_output:
      raises: ValueError

  - name: whitespace_name
    input:
      name: "   "
    expected_output:
      raises: ValueError

invariants:
  - description: "Output always starts with 'Hello, '"
    check: "output.startswith('Hello, ')"
  - description: "Output always ends with '!'"
    check: "output.endswith('!')"
"""

GITIGNORE_TEMPLATE = """# Axiom generated files
generated/
.axiom-cache/

# Python
__pycache__/
*.py[cod]
.venv/
venv/

# IDE
.idea/
.vscode/

# Environment
.env
.env.local
"""


@click.command()
@click.argument("path", type=click.Path(), default=".")
@click.option("--name", "-n", help="Project name (defaults to directory name)")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing files")
@click.pass_context
def init(ctx: click.Context, path: str, name: str | None, force: bool) -> None:
    """Initialize a new Axiom project.

    Creates the project structure with axiom.toml, directories,
    and an example spec file.

    \b
    Examples:
      axiom init                  # Initialize in current directory
      axiom init my-project       # Initialize in ./my-project
      axiom init --name myapp     # Set project name explicitly
    """
    project_path = Path(path).resolve()

    # Create directory if it doesn't exist
    if not project_path.exists():
        project_path.mkdir(parents=True)
        click.echo(f"Created directory: {project_path}")

    # Determine project name
    project_name = name or project_path.name

    # Check for existing axiom.toml
    config_path = project_path / "axiom.toml"
    if config_path.exists() and not force:
        raise click.ClickException(
            "Project already initialized (axiom.toml exists). Use --force to overwrite."
        )

    # Create directories
    dirs = [
        "specs/examples",
        "specs/self",
        "generated",
        ".axiom-cache",
        "tests",
    ]

    for dir_name in dirs:
        dir_path = project_path / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)

    # Create axiom.toml
    config_content = AXIOM_TOML_TEMPLATE.format(name=project_name)
    config_path.write_text(config_content, encoding="utf-8")
    click.echo("Created: axiom.toml")

    # Create example spec
    example_spec_path = project_path / "specs/examples/hello_world.axiom"
    if not example_spec_path.exists() or force:
        example_spec_path.write_text(EXAMPLE_SPEC_TEMPLATE, encoding="utf-8")
        click.echo("Created: specs/examples/hello_world.axiom")

    # Create .gitignore if it doesn't exist
    gitignore_path = project_path / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text(GITIGNORE_TEMPLATE, encoding="utf-8")
        click.echo("Created: .gitignore")
    elif force:
        # Append to existing gitignore
        existing = gitignore_path.read_text(encoding="utf-8")
        if "generated/" not in existing:
            with open(gitignore_path, "a", encoding="utf-8") as f:
                f.write("\n# Axiom\n")
                f.write("generated/\n")
                f.write(".axiom-cache/\n")
            click.echo("Updated: .gitignore")

    # Create .gitkeep files
    (project_path / "generated/.gitkeep").touch()
    (project_path / ".axiom-cache/.gitkeep").touch()

    click.echo("")
    click.echo(f"✓ Initialized Axiom project: {project_name}")
    click.echo("")
    click.echo("Next steps:")
    click.echo(f"  cd {path if path != '.' else project_path.name}")
    click.echo("  axiom build specs/examples/hello_world.axiom")
    click.echo("  axiom verify specs/examples/hello_world.axiom")
