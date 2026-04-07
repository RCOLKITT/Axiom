"""The 'axiom stats' command for project metrics and self-hosting tracking."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import click
import structlog

from axiom.cache.store import CacheStore
from axiom.config import load_settings
from axiom.spec.parser import parse_spec_file

logger = structlog.get_logger()


def _count_lines(path: Path) -> int:
    """Count non-empty, non-comment lines in a file.

    Args:
        path: Path to the file.

    Returns:
        Number of meaningful lines.
    """
    if not path.exists():
        return 0

    count = 0
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                count += 1
    except Exception:
        return 0
    return count


def _format_percentage(part: int, total: int) -> str:
    """Format a percentage with appropriate precision.

    Args:
        part: The numerator.
        total: The denominator.

    Returns:
        Formatted percentage string.
    """
    if total == 0:
        return "N/A"
    pct = (part / total) * 100
    if pct == 0:
        return "0%"
    if pct < 1:
        return f"{pct:.1f}%"
    return f"{pct:.0f}%"


@click.command()
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output as JSON for programmatic use",
)
@click.pass_context
def stats(_ctx: click.Context, output_json: bool) -> None:
    """Show project statistics and self-hosting metrics.

    Displays metrics about specs, generated code, cache usage,
    and the self-hosting percentage (how much of Axiom is spec-driven).

    \b
    Examples:
      axiom stats              # Show all stats
      axiom stats --json       # Output as JSON
    """
    settings = load_settings()
    spec_dir = Path(settings.project.spec_dir)
    generated_dir = settings.get_generated_dir()
    cache_dir = settings.get_cache_dir()

    # Collect statistics
    stats_data: dict[str, Any] = {}

    # 1. Spec Statistics
    all_specs = list(spec_dir.rglob("*.axiom")) if spec_dir.exists() else []
    dogfood_specs = [s for s in all_specs if "self" in s.parts]
    example_specs = [s for s in all_specs if "examples" in s.parts]
    other_specs = [s for s in all_specs if s not in dogfood_specs and s not in example_specs]

    target_counts: Counter[str] = Counter()
    for spec_path in all_specs:
        try:
            spec = parse_spec_file(spec_path)
            target_counts[spec.metadata.target] += 1
        except Exception:
            target_counts["(parse error)"] += 1

    stats_data["specs"] = {
        "total": len(all_specs),
        "dogfood": len(dogfood_specs),
        "examples": len(example_specs),
        "other": len(other_specs),
        "by_target": dict(target_counts),
    }

    # 2. Generated Code Statistics
    generated_files = list(generated_dir.rglob("*.py")) if generated_dir.exists() else []
    generated_lines = sum(_count_lines(f) for f in generated_files)

    stats_data["generated"] = {
        "files": len(generated_files),
        "lines": generated_lines,
    }

    # 3. Self-Hosting Percentage
    # Count lines in src/axiom/ (excluding __pycache__)
    src_dir = Path("src/axiom")
    src_files = []
    if src_dir.exists():
        src_files = [
            f
            for f in src_dir.rglob("*.py")
            if "__pycache__" not in str(f) and not f.name.startswith("_")
        ]
    total_src_lines = sum(_count_lines(f) for f in src_files)

    # Count lines that are spec-driven (from specs/self/)
    # This is an estimate based on the generated code from dogfood specs
    dogfood_generated = [
        f for f in generated_files if any(ds.stem == f.stem for ds in dogfood_specs)
    ]
    dogfood_lines = sum(_count_lines(f) for f in dogfood_generated)

    self_hosting_pct = (dogfood_lines / total_src_lines * 100) if total_src_lines > 0 else 0.0

    stats_data["self_hosting"] = {
        "total_src_lines": total_src_lines,
        "spec_driven_lines": dogfood_lines,
        "percentage": round(self_hosting_pct, 1),
        "target_percentage": 50,  # Phase 8 target
    }

    # 4. Cache Statistics
    if cache_dir.exists():
        cache_store = CacheStore(cache_dir)
        cache_stats = cache_store.stats()
        stats_data["cache"] = cache_stats
    else:
        stats_data["cache"] = {"total_entries": 0, "unique_specs": 0}

    # 5. Provenance Statistics
    provenance_path = settings.get_provenance_log_path()
    if provenance_path.exists():
        try:
            lines = provenance_path.read_text().strip().split("\n")
            entries = [json.loads(line) for line in lines if line]

            # Count by action
            action_counts: Counter[str] = Counter()
            result_counts: Counter[str] = Counter()
            recent_count = 0
            week_ago = datetime.now() - timedelta(days=7)

            for entry in entries:
                action_counts[entry.get("action", "unknown")] += 1
                result_counts[entry.get("result", "unknown")] += 1
                try:
                    ts = datetime.fromisoformat(entry.get("timestamp", ""))
                    if ts > week_ago:
                        recent_count += 1
                except Exception:
                    pass

            stats_data["provenance"] = {
                "total_entries": len(entries),
                "last_7_days": recent_count,
                "by_action": dict(action_counts),
                "by_result": dict(result_counts),
            }
        except Exception:
            stats_data["provenance"] = {"total_entries": 0}
    else:
        stats_data["provenance"] = {"total_entries": 0}

    # Output
    if output_json:
        click.echo(json.dumps(stats_data, indent=2))
        return

    # Pretty print
    click.echo("Axiom Project Statistics")
    click.echo("=" * 50)
    click.echo("")

    # Specs section
    specs_info = stats_data["specs"]
    click.echo("Specs:")
    click.echo(f"  Total:        {specs_info['total']}")
    click.echo(f"  Dogfood:      {specs_info['dogfood']} (specs/self/)")
    click.echo(f"  Examples:     {specs_info['examples']} (specs/examples/)")
    click.echo(f"  Other:        {specs_info['other']}")

    if specs_info["by_target"]:
        click.echo("  By target:")
        for target, count in sorted(specs_info["by_target"].items()):
            click.echo(f"    {target}: {count}")
    click.echo("")

    # Generated code section
    gen_info = stats_data["generated"]
    click.echo("Generated Code:")
    click.echo(f"  Files:        {gen_info['files']}")
    click.echo(f"  Lines:        {gen_info['lines']:,}")
    click.echo("")

    # Self-hosting section (the key metric!)
    sh_info = stats_data["self_hosting"]
    pct = sh_info["percentage"]
    target = sh_info["target_percentage"]

    click.echo("Self-Hosting (Dogfood):")
    click.echo(f"  Source lines: {sh_info['total_src_lines']:,}")
    click.echo(f"  Spec-driven:  {sh_info['spec_driven_lines']:,}")

    # Progress bar
    bar_width = 30
    filled = int((pct / 100) * bar_width)
    bar = "█" * filled + "░" * (bar_width - filled)
    target_pos = int((target / 100) * bar_width)

    click.echo(f"  Progress:     [{bar}] {pct:.1f}%")
    click.echo(f"  Target:       {' ' * target_pos}↑ {target}%")

    if pct < target:
        remaining = target - pct
        click.echo(f"  Status:       {remaining:.1f}% to target")
    else:
        click.echo("  Status:       ✓ Target reached!")
    click.echo("")

    # Cache section
    cache_info = stats_data["cache"]
    click.echo("Cache:")
    click.echo(f"  Entries:      {cache_info.get('total_entries', 0)}")
    click.echo(f"  Unique specs: {cache_info.get('unique_specs', 0)}")
    if "total_size_human" in cache_info:
        click.echo(f"  Size:         {cache_info['total_size_human']}")
    click.echo("")

    # Provenance section
    prov_info = stats_data["provenance"]
    if prov_info.get("total_entries", 0) > 0:
        click.echo("Provenance:")
        click.echo(f"  Total events: {prov_info['total_entries']}")
        click.echo(f"  Last 7 days:  {prov_info.get('last_7_days', 0)}")
        if "by_action" in prov_info and prov_info["by_action"]:
            click.echo("  By action:")
            for action, count in sorted(prov_info["by_action"].items()):
                click.echo(f"    {action}: {count}")
        click.echo("")

    # Summary
    click.echo("-" * 50)
    if pct >= target:
        click.echo("🎯 Phase 8 self-hosting target achieved!")
    else:
        specs_needed = max(1, int((target - pct) / 5))  # Rough estimate
        click.echo(f"📈 Add ~{specs_needed} more dogfood specs to reach {target}% target")
