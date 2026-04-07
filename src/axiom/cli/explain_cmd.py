"""The 'axiom explain' command for human-readable spec summaries."""

from __future__ import annotations

from pathlib import Path

import click
import structlog

from axiom.spec.parser import parse_spec_file

logger = structlog.get_logger()


def _format_type(type_str: str | None) -> str:
    """Format a type string for display.

    Args:
        type_str: The type string.

    Returns:
        Formatted type string.
    """
    if not type_str:
        return "Any"
    return type_str


def _truncate(text: str, max_length: int = 60) -> str:
    """Truncate text with ellipsis.

    Args:
        text: The text to truncate.
        max_length: Maximum length before truncation.

    Returns:
        Truncated text.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


@click.command()
@click.argument("spec_file", type=click.Path(exists=True))
@click.option(
    "--full",
    is_flag=True,
    help="Show full details including all examples and invariants",
)
@click.pass_context
def explain(_ctx: click.Context, spec_file: str, full: bool) -> None:
    """Show a human-readable summary of a spec.

    Displays a clear overview of what a spec defines, including
    its purpose, interface, examples, and invariants.

    \b
    Examples:
      axiom explain specs/validate_email.axiom
      axiom explain specs/create_user.axiom --full
    """
    spec_path = Path(spec_file)

    try:
        spec = parse_spec_file(spec_path)
    except Exception as e:
        raise click.ClickException(f"Failed to parse spec: {e}") from e

    # Header
    click.echo("")
    click.echo("=" * 60)
    click.echo(f"  {spec.metadata.name}")
    click.echo(f"  {spec.metadata.description}")
    click.echo("=" * 60)
    click.echo("")

    # Metadata
    click.echo("Metadata:")
    click.echo(f"  Version: {spec.metadata.version}")
    click.echo(f"  Target:  {spec.metadata.target}")
    if spec.metadata.tags:
        click.echo(f"  Tags:    {', '.join(spec.metadata.tags)}")
    click.echo("")

    # Intent
    click.echo("Intent:")
    intent_lines = spec.intent.strip().split("\n")
    if full:
        for line in intent_lines:
            click.echo(f"  {line}")
    else:
        # Show first 3 lines
        for line in intent_lines[:3]:
            click.echo(f"  {_truncate(line, 70)}")
        if len(intent_lines) > 3:
            click.echo(f"  ... ({len(intent_lines) - 3} more lines)")
    click.echo("")

    # Interface
    click.echo("Interface:")
    interface = spec.interface

    # Function name
    if hasattr(interface, "function_name"):
        click.echo(f"  Function: {interface.function_name}")

        # Parameters
        if hasattr(interface, "parameters") and interface.parameters:
            click.echo("  Parameters:")
            for param in interface.parameters:
                type_str = _format_type(param.type)
                click.echo(f"    - {param.name}: {type_str}")
                if full and param.description:
                    click.echo(f"        {param.description}")

        # Returns
        if hasattr(interface, "returns") and interface.returns:
            ret = interface.returns
            click.echo(f"  Returns: {_format_type(ret.type)}")
            if full and ret.description:
                click.echo(f"    {ret.description}")

    # FastAPI-specific
    if hasattr(interface, "method") and hasattr(interface, "path"):
        click.echo(f"  Endpoint: {interface.method} {interface.path}")
        if hasattr(interface, "request_body") and interface.request_body:
            click.echo("  Request Body:")
            for field in interface.request_body.fields:
                click.echo(f"    - {field.name}: {_format_type(field.type)}")
        if hasattr(interface, "response") and interface.response:
            resp = interface.response
            if hasattr(resp, "success") and resp.success:
                click.echo(f"  Success: {resp.success.status}")
            if hasattr(resp, "errors") and resp.errors:
                click.echo(f"  Error codes: {', '.join(str(e.status) for e in resp.errors)}")

    click.echo("")

    # Examples
    click.echo(f"Examples: {len(spec.examples)}")
    if spec.examples:
        if full:
            for ex in spec.examples:
                click.echo(f"  [{ex.name}]")
                click.echo(f"    Input:    {ex.input}")
                if hasattr(ex.expected_output, "value"):
                    click.echo(f"    Expected: {ex.expected_output.value}")
                elif hasattr(ex.expected_output, "raises"):
                    click.echo(f"    Raises:   {ex.expected_output.raises}")
                click.echo("")
        else:
            # Show first 3 example names
            names = [ex.name for ex in spec.examples[:3]]
            click.echo(f"  {', '.join(names)}")
            if len(spec.examples) > 3:
                click.echo(f"  ... and {len(spec.examples) - 3} more")
    click.echo("")

    # Invariants
    invariants = spec.invariants or []
    click.echo(f"Invariants: {len(invariants)}")
    if invariants:
        if full:
            for inv in invariants:
                click.echo(f"  • {inv.description}")
                if inv.check:
                    click.echo(f"    Check: {inv.check}")
        else:
            for inv in invariants[:3]:
                click.echo(f"  • {_truncate(inv.description, 55)}")
            if len(invariants) > 3:
                click.echo(f"  ... and {len(invariants) - 3} more")
    click.echo("")

    # Dependencies
    deps = spec.dependencies or []
    if deps:
        click.echo(f"Dependencies: {len(deps)}")
        for dep in deps:
            dep_type = getattr(dep, "type", "spec")
            click.echo(f"  • {dep.name} ({dep_type})")
        click.echo("")

    # Constraints
    constraints = spec.constraints
    if constraints:
        has_constraints = False
        if hasattr(constraints, "performance") and constraints.performance:
            perf = constraints.performance
            if perf.max_response_time_ms:
                click.echo(f"Performance: max {perf.max_response_time_ms}ms response time")
                has_constraints = True
        if hasattr(constraints, "security") and constraints.security:
            click.echo(f"Security: {len(constraints.security)} requirement(s)")
            has_constraints = True
        if has_constraints:
            click.echo("")

    # Summary line
    click.echo("-" * 60)
    parts = []
    if hasattr(interface, "parameters") and interface.parameters:
        parts.append(f"{len(interface.parameters)} params")
    parts.append(f"{len(spec.examples)} examples")
    parts.append(f"{len(invariants)} invariants")
    click.echo(f"Summary: {', '.join(parts)}")
    click.echo("")

    if not full:
        click.echo("Use --full for complete details")
