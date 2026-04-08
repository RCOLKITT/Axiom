"""The 'axiom create' command for natural language spec generation.

This command represents a paradigm shift: users describe what they want
in natural language, and Axiom generates both the spec AND the code.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import anthropic
import click
import structlog

from axiom.config import load_settings
from axiom.spec import parse_spec

logger = structlog.get_logger()

SPEC_GENERATION_PROMPT = """You are generating an Axiom specification from a natural language description.

Axiom specs follow this EXACT structure:

```yaml
axiom: "0.1"

metadata:
  name: function_name_here
  version: 1.0.0
  description: "Short description"
  target: "python:function"

intent: |
  Detailed explanation of what the function does.
  Include edge cases and error conditions.

interface:
  function_name: function_name_here
  parameters:
    - name: param_name
      type: str  # Use Python type hints: str, int, float, bool, list[str], etc.
      description: "Parameter description"
  returns:
    type: str
    description: "Return value description"

examples:
  - name: example_name
    input:
      param_name: "value"
    expected_output: "result"

  - name: error_case
    input:
      param_name: "bad_value"
    expected_output:
      raises: ValueError

invariants:
  - description: "Property that must hold"
    check: "output == output.lower()"
```

Given this description:
{description}

Generate a complete .axiom spec file following the EXACT structure above. Requirements:
1. The metadata block is REQUIRED with name, version (use 1.0.0), description, and target fields
2. Use lowercase_with_underscores for names
3. Include 3-5 concrete examples
4. Include 1-2 invariants with Python check expressions
5. Use `input` (not `inputs`) and `expected_output` (not `expected`) in examples

Output ONLY the YAML spec, no markdown fences, no explanation."""


@click.command()
@click.argument("description")
@click.option(
    "--name",
    "-n",
    help="Name for the spec (auto-generated if not provided)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output path for spec file (default: specs/<name>.axiom)",
)
@click.option(
    "--build",
    is_flag=True,
    help="Also generate code from the spec",
)
@click.option(
    "--verify",
    is_flag=True,
    help="Verify the generated code (implies --build)",
)
def create(
    description: str,
    name: str | None,
    output: str | None,
    build: bool,
    verify: bool,
) -> None:
    """Generate a spec from natural language description.

    This is the future of software development: describe what you want,
    get verified code that matches your intent.

    \\b
    Examples:
      axiom create "A function that validates email addresses"
      axiom create "Parse CSV row into dict with type coercion" --build
      axiom create "Calculate Fibonacci numbers" --verify
    """
    settings = load_settings()

    click.echo("Generating spec from description...")
    click.echo(f"  \"{description}\"")
    click.echo("")

    # Generate spec using Claude
    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": SPEC_GENERATION_PROMPT.format(description=description),
                }
            ],
        )

        # Extract text content from response
        spec_content = ""
        for block in response.content:
            if hasattr(block, "text"):
                spec_content = block.text
                break

        if not spec_content:
            raise click.ClickException("No text content in API response")

        # Strip markdown code fences if present
        if spec_content.startswith("```"):
            lines = spec_content.split("\n")
            # Find start and end of code block
            start_idx = 0
            end_idx = len(lines)
            for i, line in enumerate(lines):
                if line.startswith("```") and i == 0:
                    start_idx = 1
                elif line.startswith("```") and i > 0:
                    end_idx = i
                    break
            spec_content = "\n".join(lines[start_idx:end_idx])

        # Validate the generated spec
        try:
            spec = parse_spec(spec_content)
            spec_name = spec.metadata.name
        except Exception as e:
            raise click.ClickException(
                f"Generated spec is invalid: {e}\n\nGenerated content:\n{spec_content}"
            ) from None

        # Use provided name or generated name
        final_name = name or spec_name

        # Determine output path
        if output:
            output_path = Path(output)
        else:
            spec_dir = settings.get_spec_dir()
            spec_dir.mkdir(parents=True, exist_ok=True)
            output_path = spec_dir / f"{final_name}.axiom"

        # Write spec file
        output_path.write_text(spec_content, encoding="utf-8")
        click.echo(f"✓ Created spec: {output_path}")
        click.echo("")

        # Show spec summary
        click.echo("Spec summary:")
        click.echo(f"  Name: {spec.metadata.name}")
        click.echo(f"  Description: {spec.metadata.description}")
        click.echo(f"  Examples: {len(spec.examples)}")
        click.echo(f"  Invariants: {len(spec.invariants) if spec.invariants else 0}")

        # Build if requested
        if build or verify:
            click.echo("")
            click.echo("Building code from spec...")

            # Use subprocess to call axiom build
            cmd = [sys.executable, "-m", "axiom.cli.main", "build", str(output_path)]
            if verify:
                cmd.append("--verify")

            result = subprocess.run(cmd, capture_output=False)
            if result.returncode != 0:
                raise click.ClickException("Build failed")

    except anthropic.APIError as e:
        raise click.ClickException(f"API error: {e}") from None
