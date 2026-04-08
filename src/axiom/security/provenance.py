"""Provenance logging for Axiom.

Provides an append-only log of all generation and verification events
for audit trail purposes.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import structlog

# Import spec-driven utilities (dogfooding)
from axiom._generated import compute_spec_hash

logger = structlog.get_logger()


@dataclass
class ProvenanceEntry:
    """A single provenance log entry.

    Attributes:
        timestamp: When the event occurred (ISO format).
        spec_name: Name of the spec being processed.
        spec_hash: SHA-256 hash of the spec content.
        model: The LLM model used (if applicable).
        action: Type of action performed.
        result: Outcome of the action.
        axiom_version: Version of Axiom that processed this.
        duration_ms: Duration of the action in milliseconds.
        failure_reason: Reason for failure (if result is "failure").
        user: Username from git config or environment (if available).
        metadata: Additional metadata about the event.
        input_tokens: Number of input tokens used (for cost tracking).
        output_tokens: Number of output tokens generated (for cost tracking).
        cost_usd: Estimated cost in USD (for cost tracking).
    """

    timestamp: str
    spec_name: str
    spec_hash: str
    model: str
    action: Literal["generate", "verify", "cache_hit", "cache_miss", "cache_stale"]
    result: Literal["success", "failure"]
    axiom_version: str
    duration_ms: int | None = None
    failure_reason: str | None = None
    user: str | None = None
    metadata: dict[str, str] | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None

    def to_json_line(self) -> str:
        """Serialize to a JSON line (no newlines in output).

        Returns:
            JSON string representing this entry.
        """
        data = asdict(self)
        # Remove None values to keep log compact
        data = {k: v for k, v in data.items() if v is not None}
        return json.dumps(data, separators=(",", ":"))

    @classmethod
    def from_json_line(cls, line: str) -> ProvenanceEntry:
        """Deserialize from a JSON line.

        Args:
            line: JSON string to parse.

        Returns:
            ProvenanceEntry instance.

        Raises:
            ValueError: If the JSON is invalid.
        """
        data = json.loads(line)
        return cls(
            timestamp=data["timestamp"],
            spec_name=data["spec_name"],
            spec_hash=data["spec_hash"],
            model=data["model"],
            action=data["action"],
            result=data["result"],
            axiom_version=data["axiom_version"],
            duration_ms=data.get("duration_ms"),
            failure_reason=data.get("failure_reason"),
            user=data.get("user"),
            metadata=data.get("metadata"),
            input_tokens=data.get("input_tokens"),
            output_tokens=data.get("output_tokens"),
            cost_usd=data.get("cost_usd"),
        )


def get_current_user() -> str | None:
    """Get the current user for provenance logging.

    Tries git config first, then falls back to environment variables.

    Returns:
        Username or None if not available.
    """
    import os
    import subprocess

    # Try git config
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass

    # Fall back to environment
    return os.environ.get("USER") or os.environ.get("USERNAME")


class ProvenanceLog:
    """Append-only provenance log.

    Stores entries in a JSON Lines file for easy parsing and streaming.

    Attributes:
        log_path: Path to the log file.
    """

    def __init__(self, log_path: Path) -> None:
        """Initialize the provenance log.

        Args:
            log_path: Path to the log file.
        """
        self.log_path = log_path

    def log(self, entry: ProvenanceEntry) -> None:
        """Append an entry to the log.

        Args:
            entry: The entry to log.
        """
        # Ensure parent directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Append to file
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(entry.to_json_line() + "\n")

        logger.debug(
            "Logged provenance entry",
            spec_name=entry.spec_name,
            action=entry.action,
            result=entry.result,
        )

    def query(
        self,
        spec_name: str | None = None,
        since: datetime | None = None,
        action: str | None = None,
        limit: int | None = None,
    ) -> list[ProvenanceEntry]:
        """Query the provenance log.

        Args:
            spec_name: Filter by spec name.
            since: Filter to entries after this timestamp.
            action: Filter by action type.
            limit: Maximum number of entries to return.

        Returns:
            List of matching entries, most recent first.
        """
        if not self.log_path.exists():
            return []

        entries: list[ProvenanceEntry] = []

        with open(self.log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = ProvenanceEntry.from_json_line(line)
                except (json.JSONDecodeError, KeyError):
                    # Skip malformed entries
                    continue

                # Apply filters
                if spec_name and entry.spec_name != spec_name:
                    continue

                if action and entry.action != action:
                    continue

                if since:
                    entry_time = datetime.fromisoformat(entry.timestamp)
                    if entry_time < since:
                        continue

                entries.append(entry)

        # Sort by timestamp descending (most recent first)
        entries.sort(key=lambda e: e.timestamp, reverse=True)

        if limit:
            entries = entries[:limit]

        return entries

    def get_generation_history(self, spec_name: str) -> list[ProvenanceEntry]:
        """Get full generation history for a spec.

        Args:
            spec_name: Name of the spec.

        Returns:
            List of generation entries for this spec, most recent first.
        """
        return self.query(spec_name=spec_name, action="generate")

    def get_stats(self) -> dict[str, int]:
        """Get statistics from the provenance log.

        Returns:
            Dictionary with counts by action and result.
        """
        if not self.log_path.exists():
            return {
                "total_entries": 0,
                "generations": 0,
                "cache_hits": 0,
                "cache_misses": 0,
                "verifications": 0,
                "successes": 0,
                "failures": 0,
            }

        stats = {
            "total_entries": 0,
            "generations": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "verifications": 0,
            "successes": 0,
            "failures": 0,
        }

        with open(self.log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = ProvenanceEntry.from_json_line(line)
                except (json.JSONDecodeError, KeyError):
                    continue

                stats["total_entries"] += 1

                if entry.action == "generate":
                    stats["generations"] += 1
                elif entry.action == "cache_hit":
                    stats["cache_hits"] += 1
                elif entry.action == "cache_miss":
                    stats["cache_misses"] += 1
                elif entry.action == "verify":
                    stats["verifications"] += 1

                if entry.result == "success":
                    stats["successes"] += 1
                else:
                    stats["failures"] += 1

        return stats

    def clear(self) -> int:
        """Clear the provenance log.

        Returns:
            Number of entries that were cleared.
        """
        if not self.log_path.exists():
            return 0

        # Count entries before clearing
        count = 0
        with open(self.log_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1

        # Clear the file
        self.log_path.unlink()

        logger.info("Cleared provenance log", entries=count)
        return count

    def get_cost_stats(self, since: datetime | None = None) -> dict[str, object]:
        """Get cost statistics from the provenance log.

        Args:
            since: Only include entries after this timestamp.

        Returns:
            Dictionary with cost statistics.
        """
        if not self.log_path.exists():
            return {
                "total_cost_usd": 0.0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "generation_count": 0,
                "avg_cost_per_generation": 0.0,
            }

        total_cost = 0.0
        total_input = 0
        total_output = 0
        gen_count = 0
        cost_by_spec: dict[str, float] = {}

        with open(self.log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = ProvenanceEntry.from_json_line(line)
                except (json.JSONDecodeError, KeyError):
                    continue

                # Filter by time
                if since:
                    entry_time = datetime.fromisoformat(entry.timestamp)
                    if entry_time < since:
                        continue

                # Only count generations with cost data
                if entry.action == "generate":
                    gen_count += 1
                    if entry.cost_usd:
                        total_cost += entry.cost_usd
                        cost_by_spec[entry.spec_name] = (
                            cost_by_spec.get(entry.spec_name, 0.0) + entry.cost_usd
                        )
                    if entry.input_tokens:
                        total_input += entry.input_tokens
                    if entry.output_tokens:
                        total_output += entry.output_tokens

        return {
            "total_cost_usd": round(total_cost, 4),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "generation_count": gen_count,
            "avg_cost_per_generation": (round(total_cost / gen_count, 4) if gen_count > 0 else 0.0),
            "cost_by_spec": cost_by_spec,
        }


def create_provenance_entry(
    spec_name: str,
    spec_content: str,
    model: str,
    action: Literal["generate", "verify", "cache_hit", "cache_miss", "cache_stale"],
    result: Literal["success", "failure"],
    axiom_version: str,
    duration_ms: int | None = None,
    failure_reason: str | None = None,
    metadata: dict[str, str] | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
) -> ProvenanceEntry:
    """Create a provenance entry with automatic timestamp and user.

    Args:
        spec_name: Name of the spec.
        spec_content: Raw spec file content (for hashing).
        model: The LLM model used.
        action: Type of action.
        result: Outcome of the action.
        axiom_version: Axiom version.
        duration_ms: Duration in milliseconds.
        failure_reason: Reason for failure.
        metadata: Additional metadata.
        input_tokens: Number of input tokens used.
        output_tokens: Number of output tokens generated.
        cost_usd: Estimated cost in USD.

    Returns:
        ProvenanceEntry ready to be logged.
    """
    return ProvenanceEntry(
        timestamp=datetime.now().isoformat(),
        spec_name=spec_name,
        spec_hash=compute_spec_hash(spec_content),
        model=model,
        action=action,
        result=result,
        axiom_version=axiom_version,
        duration_ms=duration_ms,
        failure_reason=failure_reason,
        user=get_current_user(),
        metadata=metadata,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
    )


# Model pricing (per 1M tokens) - Updated April 2026
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost for an API call.

    Args:
        model: Model name.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.

    Returns:
        Estimated cost in USD.
    """
    pricing = MODEL_PRICING.get(model, {"input": 3.00, "output": 15.00})
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost, 6)
