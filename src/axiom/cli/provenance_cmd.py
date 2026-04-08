"""The 'axiom provenance' commands.

View and query the provenance log for generation and verification events.
"""

from __future__ import annotations

from datetime import datetime

import click
import structlog

from axiom.config import load_settings
from axiom.security.provenance import ProvenanceLog

logger = structlog.get_logger()


@click.group()
def provenance() -> None:
    """View and query provenance logs.

    \\b
    Commands:
      show     - Show recent provenance entries
      history  - Show full history for a spec
      stats    - Show provenance statistics
      clear    - Clear the provenance log
    """
    pass


@provenance.command(name="show")
@click.argument("spec_name", required=False)
@click.option(
    "--since",
    help="Show entries since date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
)
@click.option(
    "--action",
    type=click.Choice(["generate", "verify", "cache_hit", "cache_miss", "cache_stale"]),
    help="Filter by action type",
)
@click.option(
    "--limit",
    "-n",
    default=20,
    help="Maximum entries to show (default: 20)",
)
def show(
    spec_name: str | None,
    since: str | None,
    action: str | None,
    limit: int,
) -> None:
    """Show recent provenance entries.

    \\b
    Examples:
      axiom provenance show
      axiom provenance show validate_email
      axiom provenance show --since 2026-04-01
      axiom provenance show --action generate --limit 10
    """
    settings = load_settings()
    log_path = settings.get_provenance_log_path()
    prov_log = ProvenanceLog(log_path)

    # Parse since date if provided
    since_dt: datetime | None = None
    if since:
        try:
            # Try ISO format first
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            try:
                # Try date-only format
                since_dt = datetime.strptime(since, "%Y-%m-%d")
            except ValueError:
                raise click.ClickException(
                    f"Invalid date format: {since}. Use YYYY-MM-DD or ISO format."
                ) from None

    entries = prov_log.query(
        spec_name=spec_name,
        since=since_dt,
        action=action,
        limit=limit,
    )

    if not entries:
        click.echo("No provenance entries found.")
        click.echo(f"Log file: {log_path}")
        return

    click.echo(f"Provenance entries ({len(entries)}):")
    click.echo("")

    for entry in entries:
        # Format timestamp
        try:
            ts = datetime.fromisoformat(entry.timestamp)
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            ts_str = entry.timestamp

        # Format result with color hint
        result_str = "✓" if entry.result == "success" else "✗"

        click.echo(f"  {ts_str}  {result_str} {entry.action}")
        click.echo(f"    Spec: {entry.spec_name}")
        click.echo(f"    Model: {entry.model}")
        if entry.duration_ms:
            click.echo(f"    Duration: {entry.duration_ms}ms")
        if entry.failure_reason:
            click.echo(f"    Failure: {entry.failure_reason}")
        click.echo("")


@provenance.command()
@click.argument("spec_name")
def history(spec_name: str) -> None:
    """Show full generation history for a spec.

    \\b
    Examples:
      axiom provenance history validate_email
    """
    settings = load_settings()
    log_path = settings.get_provenance_log_path()
    prov_log = ProvenanceLog(log_path)

    entries = prov_log.get_generation_history(spec_name)

    if not entries:
        click.echo(f"No generation history found for: {spec_name}")
        return

    click.echo(f"Generation history for: {spec_name}")
    click.echo(f"Total generations: {len(entries)}")
    click.echo("")

    for i, entry in enumerate(entries, 1):
        try:
            ts = datetime.fromisoformat(entry.timestamp)
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            ts_str = entry.timestamp

        result_str = "✓ success" if entry.result == "success" else "✗ failure"

        click.echo(f"  [{i}] {ts_str}")
        click.echo(f"      Result: {result_str}")
        click.echo(f"      Model: {entry.model}")
        click.echo(f"      Axiom version: {entry.axiom_version}")
        if entry.duration_ms:
            click.echo(f"      Duration: {entry.duration_ms}ms")
        if entry.failure_reason:
            click.echo(f"      Failure: {entry.failure_reason}")
        if entry.user:
            click.echo(f"      User: {entry.user}")
        click.echo("")


@provenance.command()
def stats() -> None:
    """Show provenance statistics.

    \\b
    Examples:
      axiom provenance stats
    """
    settings = load_settings()
    log_path = settings.get_provenance_log_path()
    prov_log = ProvenanceLog(log_path)

    stats = prov_log.get_stats()

    click.echo("Provenance statistics:")
    click.echo("")
    click.echo(f"  Log file: {log_path}")
    click.echo(f"  Total entries: {stats['total_entries']}")
    click.echo("")
    click.echo("  By action:")
    click.echo(f"    Generations: {stats['generations']}")
    click.echo(f"    Cache hits: {stats['cache_hits']}")
    click.echo(f"    Cache misses: {stats['cache_misses']}")
    click.echo(f"    Verifications: {stats['verifications']}")
    click.echo("")
    click.echo("  By result:")
    click.echo(f"    Successes: {stats['successes']}")
    click.echo(f"    Failures: {stats['failures']}")

    if stats["total_entries"] > 0:
        success_rate = stats["successes"] / stats["total_entries"] * 100
        click.echo(f"    Success rate: {success_rate:.1f}%")

    if stats["generations"] > 0 and stats["cache_hits"] > 0:
        cache_rate = stats["cache_hits"] / (stats["cache_hits"] + stats["cache_misses"]) * 100
        click.echo(f"    Cache hit rate: {cache_rate:.1f}%")


@provenance.command()
@click.option(
    "--since",
    help="Show costs since date (YYYY-MM-DD)",
)
@click.option("--by-spec", is_flag=True, help="Show breakdown by spec")
def cost(since: str | None, by_spec: bool) -> None:
    """Show API cost statistics.

    \\b
    Examples:
      axiom provenance cost
      axiom provenance cost --since 2026-04-01
      axiom provenance cost --by-spec
    """
    settings = load_settings()
    log_path = settings.get_provenance_log_path()
    prov_log = ProvenanceLog(log_path)

    # Parse since date if provided
    since_dt: datetime | None = None
    if since:
        try:
            since_dt = datetime.strptime(since, "%Y-%m-%d")
        except ValueError:
            raise click.ClickException(
                f"Invalid date format: {since}. Use YYYY-MM-DD."
            ) from None

    cost_stats = prov_log.get_cost_stats(since=since_dt)

    click.echo("API Cost Statistics:")
    click.echo("")
    if since:
        click.echo(f"  Period: Since {since}")
    else:
        click.echo("  Period: All time")
    click.echo("")
    click.echo(f"  Total cost: ${cost_stats['total_cost_usd']:.4f}")
    click.echo(f"  Generations: {cost_stats['generation_count']}")
    click.echo(f"  Avg per generation: ${cost_stats['avg_cost_per_generation']:.4f}")
    click.echo("")
    click.echo("  Tokens:")
    click.echo(f"    Input: {cost_stats['total_input_tokens']:,}")
    click.echo(f"    Output: {cost_stats['total_output_tokens']:,}")

    cost_by_spec = cost_stats.get("cost_by_spec")
    if by_spec and isinstance(cost_by_spec, dict) and cost_by_spec:
        click.echo("")
        click.echo("  By spec:")
        sorted_specs = sorted(
            cost_by_spec.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        for spec_name, spec_cost in sorted_specs[:10]:
            click.echo(f"    {spec_name}: ${spec_cost:.4f}")
        if len(sorted_specs) > 10:
            click.echo(f"    ... and {len(sorted_specs) - 10} more")


@provenance.command()
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def clear(yes: bool) -> None:
    """Clear the provenance log.

    \\b
    Examples:
      axiom provenance clear
      axiom provenance clear --yes
    """
    settings = load_settings()
    log_path = settings.get_provenance_log_path()
    prov_log = ProvenanceLog(log_path)

    # Get current count
    stats = prov_log.get_stats()
    count = stats["total_entries"]

    if count == 0:
        click.echo("Provenance log is already empty.")
        return

    if not yes:
        click.confirm(f"Clear {count} provenance entries?", abort=True)

    cleared = prov_log.clear()
    click.echo(f"Cleared {cleared} provenance entries.")
