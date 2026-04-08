"""The 'axiom decompose' command for intelligent requirement decomposition.

This command takes a PRD, feature spec, or complex requirement and
intelligently decomposes it into properly structured, atomic Axiom specs.

This is the enterprise-grade workflow:
1. User provides PRD/requirements (file or description)
2. Axiom analyzes and identifies discrete components
3. Generates multiple atomic specs with proper dependencies
4. Creates a build order for the spec hierarchy
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anthropic
import click
import structlog

from axiom.config import load_settings
from axiom.spec import parse_spec

logger = structlog.get_logger()

DECOMPOSITION_PROMPT = """You are an expert software architect analyzing requirements to create Axiom specifications.

Axiom is a system where specs are source code and Python code is generated from them. Each spec should be:
- ATOMIC: One function, one responsibility
- TESTABLE: Clear inputs, outputs, and examples
- COMPOSABLE: Can depend on other specs

Given this requirement/PRD:

---
{requirement}
---

Analyze this and decompose it into atomic Axiom specs. For each spec you identify:

1. Determine the function name (snake_case)
2. Identify parameters with types
3. Determine return type
4. Create 3-5 concrete examples with actual values
5. Identify any invariants that must hold
6. Note dependencies on other specs in this decomposition

Return a JSON object with this structure:
{{
  "analysis": {{
    "summary": "Brief summary of what the requirement describes",
    "components_identified": ["list of main components/functions identified"],
    "build_order": ["spec names in order they should be built (dependencies first)"]
  }},
  "specs": [
    {{
      "name": "function_name",
      "description": "What this function does",
      "intent": "Detailed explanation including edge cases",
      "parameters": [
        {{"name": "param_name", "type": "str", "description": "What this param is"}}
      ],
      "returns": {{"type": "str", "description": "What is returned"}},
      "examples": [
        {{"name": "example_name", "input": {{"param": "value"}}, "expected_output": "result"}}
      ],
      "invariants": [
        {{"description": "Property that must hold", "check": "output > 0"}}
      ],
      "dependencies": ["other_spec_name"]
    }}
  ]
}}

IMPORTANT:
- Each spec should be for ONE function only
- Examples must have CONCRETE values, not placeholders
- Dependencies should only reference specs you're creating
- Order specs so dependencies come first in the build_order
- If an example should raise an exception, use: {{"expected_output": {{"raises": "ValueError"}}}}

Return ONLY the JSON, no markdown fences or explanation."""


@click.command()
@click.argument("requirement", required=False)
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    help="Path to a PRD or requirements file",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    help="Output directory for generated specs (default: specs/)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be generated without writing files",
)
@click.option(
    "--build",
    is_flag=True,
    help="Also build the generated specs",
)
@click.pass_context
def decompose(
    ctx: click.Context,
    requirement: str | None,
    file: str | None,
    output_dir: str | None,
    dry_run: bool,
    build: bool,
) -> None:
    """Decompose a PRD or requirement into atomic Axiom specs.

    Takes a complex requirement and intelligently breaks it down into
    properly structured specs with dependencies.

    \\b
    Examples:
      axiom decompose "Build a user authentication system with login, logout, and password reset"
      axiom decompose --file requirements/auth.md
      axiom decompose "E-commerce checkout flow" --build
    """
    settings = load_settings()

    # Get requirement text
    if file:
        requirement_text = Path(file).read_text(encoding="utf-8")
        click.echo(f"Reading requirements from: {file}")
    elif requirement:
        requirement_text = requirement
    else:
        raise click.ClickException(
            "Provide a requirement description or use --file to specify a requirements file"
        )

    click.echo("")
    click.echo("Analyzing requirements...")
    click.echo("═" * 60)

    # Call Claude to decompose
    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[
                {
                    "role": "user",
                    "content": DECOMPOSITION_PROMPT.format(requirement=requirement_text),
                }
            ],
        )

        # Extract response text
        response_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                response_text = block.text
                break

        if not response_text:
            raise click.ClickException("No response from API")

        # Parse JSON response
        try:
            decomposition = json.loads(response_text)
        except json.JSONDecodeError as e:
            # Try to extract JSON from response
            if "{" in response_text and "}" in response_text:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                try:
                    decomposition = json.loads(response_text[start:end])
                except json.JSONDecodeError:
                    raise click.ClickException(
                        f"Could not parse response as JSON: {e}\n\nResponse:\n{response_text[:500]}"
                    ) from e
            else:
                raise click.ClickException(
                    f"Invalid JSON response: {e}\n\nResponse:\n{response_text[:500]}"
                ) from e

        # Display analysis
        analysis = decomposition.get("analysis", {})
        click.echo("")
        click.echo(f"Summary: {analysis.get('summary', 'N/A')}")
        click.echo("")
        click.echo("Components identified:")
        for comp in analysis.get("components_identified", []):
            click.echo(f"  • {comp}")
        click.echo("")
        click.echo(f"Build order: {' → '.join(analysis.get('build_order', []))}")
        click.echo("")
        click.echo("─" * 60)

        # Generate specs
        specs = decomposition.get("specs", [])
        click.echo(f"Generating {len(specs)} specs...")
        click.echo("")

        # Determine output directory
        spec_dir = Path(output_dir) if output_dir else settings.get_spec_dir()
        spec_dir.mkdir(parents=True, exist_ok=True)

        generated_files = []

        for spec_data in specs:
            spec_yaml = _generate_spec_yaml(spec_data)
            spec_name = spec_data.get("name", "unknown")
            output_path = spec_dir / f"{spec_name}.axiom"

            if dry_run:
                click.echo(f"Would create: {output_path}")
                click.echo("─" * 40)
                # Show first 20 lines
                lines = spec_yaml.split("\n")[:20]
                for line in lines:
                    click.echo(f"  {line}")
                if len(spec_yaml.split("\n")) > 20:
                    click.echo("  ...")
                click.echo("")
            else:
                # Validate spec before writing
                try:
                    parse_spec(spec_yaml)
                except Exception as e:
                    click.echo(f"  ✗ {spec_name}: Invalid spec - {e}")
                    continue

                output_path.write_text(spec_yaml, encoding="utf-8")
                generated_files.append(output_path)
                click.echo(f"  ✓ {output_path}")

        click.echo("")
        click.echo("═" * 60)

        if dry_run:
            click.echo(f"Dry run complete. Would generate {len(specs)} specs.")
        else:
            click.echo(f"Generated {len(generated_files)} specs in {spec_dir}/")

            # Build if requested
            if build and generated_files:
                click.echo("")
                click.echo("Building generated specs...")
                import subprocess
                import sys

                for spec_file in generated_files:
                    click.echo(f"  Building {spec_file.name}...")
                    result = subprocess.run(
                        [sys.executable, "-m", "axiom.cli.main", "build", str(spec_file)],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode != 0:
                        click.echo(f"    ✗ Build failed")
                    else:
                        click.echo(f"    ✓ Built")

    except anthropic.APIError as e:
        raise click.ClickException(f"API error: {e}") from None


def _generate_spec_yaml(spec_data: dict[str, Any]) -> str:
    """Generate YAML content for a spec from decomposition data.

    Args:
        spec_data: The spec data from decomposition.

    Returns:
        YAML string for the spec.
    """
    lines = [
        'axiom: "0.1"',
        "",
        "metadata:",
        f"  name: {spec_data.get('name', 'unnamed')}",
        "  version: 1.0.0",
        f"  description: \"{spec_data.get('description', '')}\"",
        '  target: "python:function"',
        "",
        "intent: |",
    ]

    # Add intent with proper indentation
    intent = spec_data.get("intent", spec_data.get("description", ""))
    for line in intent.split("\n"):
        lines.append(f"  {line}")

    lines.append("")
    lines.append("interface:")
    lines.append(f"  function_name: {spec_data.get('name', 'unnamed')}")
    lines.append("  parameters:")

    # Add parameters
    for param in spec_data.get("parameters", []):
        lines.append(f"    - name: {param.get('name', 'param')}")
        lines.append(f"      type: {param.get('type', 'str')}")
        lines.append(f"      description: \"{param.get('description', '')}\"")

    # Add returns
    returns = spec_data.get("returns", {"type": "str", "description": ""})
    lines.append("  returns:")
    lines.append(f"    type: {returns.get('type', 'str')}")
    lines.append(f"    description: \"{returns.get('description', '')}\"")

    # Add examples
    lines.append("")
    lines.append("examples:")
    for ex in spec_data.get("examples", []):
        lines.append(f"  - name: {ex.get('name', 'example')}")
        lines.append("    input:")
        for key, value in ex.get("input", {}).items():
            lines.append(f"      {key}: {_yaml_value(value)}")

        expected = ex.get("expected_output")
        if isinstance(expected, dict) and "raises" in expected:
            lines.append("    expected_output:")
            lines.append(f"      raises: {expected['raises']}")
        else:
            lines.append(f"    expected_output: {_yaml_value(expected)}")

    # Add invariants if present
    invariants = spec_data.get("invariants", [])
    if invariants:
        lines.append("")
        lines.append("invariants:")
        for inv in invariants:
            lines.append(f"  - description: \"{inv.get('description', '')}\"")
            if inv.get("check"):
                lines.append(f"    check: \"{inv.get('check')}\"")

    # Add dependencies if present
    deps = spec_data.get("dependencies", [])
    if deps:
        lines.append("")
        lines.append("dependencies:")
        for dep in deps:
            lines.append(f"  - name: {dep}")
            lines.append("    type: spec")

    return "\n".join(lines)


def _yaml_value(value: object) -> str:
    """Convert a Python value to YAML string representation.

    Args:
        value: The value to convert.

    Returns:
        YAML-compatible string.
    """
    if isinstance(value, str):
        # Quote strings that might be ambiguous
        if value in ("true", "false", "null", "yes", "no", "on", "off"):
            return f'"{value}"'
        if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
            return f'"{value}"'
        if '"' in value or ":" in value or "#" in value:
            return f'"{value}"'
        return f'"{value}"'
    elif isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, list):
        return json.dumps(value)
    elif isinstance(value, dict):
        return json.dumps(value)
    elif value is None:
        return "null"
    else:
        return f'"{value}"'
