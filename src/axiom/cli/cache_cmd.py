"""The 'axiom cache' commands."""

from __future__ import annotations

import click
import structlog

from axiom.cache import CacheStore
from axiom.config import load_settings

logger = structlog.get_logger()


@click.group()
def cache() -> None:
    """Manage the Axiom generation cache.

    \b
    Commands:
      list    - List all cached entries
      inspect - Show details of a cached spec
      clear   - Clear all cached entries
      stats   - Show cache statistics
    """
    pass


@cache.command(name="list")
@click.option("--verbose", "-v", is_flag=True, help="Show full cache keys")
def cache_list(verbose: bool) -> None:
    """List all cached entries.

    \b
    Examples:
      axiom cache list
      axiom cache list --verbose
    """
    settings = load_settings()
    cache_store = CacheStore(settings.get_cache_dir())

    entries = cache_store.list_entries()

    if not entries:
        click.echo("No cached entries found.")
        click.echo(f"Cache directory: {settings.get_cache_dir()}")
        return

    click.echo(f"Cached entries ({len(entries)}):")
    click.echo("")

    # Sort by created_at (most recent first)
    entries.sort(key=lambda e: e.created_at, reverse=True)

    for entry in entries:
        key_display = entry.key if verbose else entry.key[:12] + "..."
        click.echo(f"  {entry.spec_name}")
        click.echo(f"    Key: {key_display}")
        click.echo(f"    Model: {entry.model}")
        click.echo(f"    Target: {entry.target}")
        click.echo(f"    Created: {entry.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"    Axiom version: {entry.axiom_version}")
        click.echo("")


@cache.command(name="inspect")
@click.argument("spec_name")
@click.option("--show-code", is_flag=True, help="Show the cached code")
def cache_inspect(spec_name: str, show_code: bool) -> None:
    """Show details of a cached spec.

    \b
    Examples:
      axiom cache inspect validate_email
      axiom cache inspect validate_email --show-code
    """
    settings = load_settings()
    cache_store = CacheStore(settings.get_cache_dir())

    entry = cache_store.get_entry_for_spec(spec_name)

    if entry is None:
        click.echo(f"No cache entry found for spec: {spec_name}")
        return

    click.echo(f"Cache entry for: {entry.spec_name}")
    click.echo("")
    click.echo(f"  Key: {entry.key}")
    click.echo(f"  Model: {entry.model}")
    click.echo(f"  Target: {entry.target}")
    click.echo(f"  Created: {entry.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    click.echo(f"  Axiom version: {entry.axiom_version}")

    if entry.metadata:
        click.echo(f"  Metadata: {entry.metadata}")

    if show_code:
        click.echo("")
        click.echo("Cached code:")
        click.echo("-" * 40)
        click.echo(entry.code)
        click.echo("-" * 40)
    else:
        # Show code size
        code_lines = entry.code.count("\n") + 1
        code_bytes = len(entry.code.encode("utf-8"))
        click.echo(f"  Code: {code_lines} lines, {code_bytes} bytes")
        click.echo("")
        click.echo("Use --show-code to see the cached code.")


@cache.command(name="clear")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--spec", "-s", help="Clear cache for a specific spec only")
def cache_clear(yes: bool, spec: str | None) -> None:
    """Clear cached entries.

    \b
    Examples:
      axiom cache clear           # Clear all (with confirmation)
      axiom cache clear --yes     # Clear all (no confirmation)
      axiom cache clear -s validate_email  # Clear specific spec
    """
    settings = load_settings()
    cache_store = CacheStore(settings.get_cache_dir())

    if spec:
        # Clear specific spec
        entry = cache_store.get_entry_for_spec(spec)
        if entry is None:
            click.echo(f"No cache entry found for spec: {spec}")
            return

        if not yes:
            click.confirm(f"Clear cache entry for '{spec}'?", abort=True)

        cache_store.delete(entry.key)
        click.echo(f"Cleared cache entry for: {spec}")
    else:
        # Clear all
        entries = cache_store.list_entries()
        if not entries:
            click.echo("Cache is already empty.")
            return

        if not yes:
            click.confirm(f"Clear all {len(entries)} cache entries?", abort=True)

        count = cache_store.clear()
        click.echo(f"Cleared {count} cache entries.")


@cache.command(name="stats")
def cache_stats() -> None:
    """Show cache statistics.

    \b
    Examples:
      axiom cache stats
    """
    settings = load_settings()
    cache_store = CacheStore(settings.get_cache_dir())

    stats = cache_store.stats()

    click.echo("Cache statistics:")
    click.echo("")
    click.echo(f"  Location: {settings.get_cache_dir()}")
    click.echo(f"  Total entries: {stats['total_entries']}")
    click.echo(f"  Unique specs: {stats['unique_specs']}")
    click.echo(f"  Total size: {stats['total_size_human']}")

    if stats["entries_by_spec"]:
        click.echo("")
        click.echo("  Entries by spec:")
        for name, count in sorted(stats["entries_by_spec"].items()):
            click.echo(f"    {name}: {count}")
