"""Secret scanning for spec files.

Detects potential secrets (API keys, passwords, tokens) in spec content
before sending to LLM APIs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Patterns to detect common secrets
# Each tuple is (pattern_name, compiled_regex)
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # AWS
    ("AWS Access Key ID", re.compile(r"AKIA[0-9A-Z]{16}")),
    (
        "AWS Secret Access Key",
        re.compile(r"(?<![A-Za-z0-9/+=])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])"),
    ),
    # GitHub
    ("GitHub Personal Access Token", re.compile(r"ghp_[A-Za-z0-9]{36}")),
    ("GitHub OAuth Access Token", re.compile(r"gho_[A-Za-z0-9]{36}")),
    ("GitHub App Token", re.compile(r"ghu_[A-Za-z0-9]{36}")),
    ("GitHub Server Token", re.compile(r"ghs_[A-Za-z0-9]{36}")),
    ("GitHub Refresh Token", re.compile(r"ghr_[A-Za-z0-9]{36}")),
    # OpenAI / Anthropic
    ("OpenAI API Key", re.compile(r"sk-[A-Za-z0-9]{48}")),
    ("Anthropic API Key", re.compile(r"sk-ant-[A-Za-z0-9\-]{95}")),
    # Generic patterns
    (
        "Generic API Key Assignment",
        re.compile(r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]"),
    ),
    (
        "Generic Secret Assignment",
        re.compile(r"(?i)(secret|password|passwd|pwd|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
    ),
    ("Private Key Header", re.compile(r"-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("Basic Auth Header", re.compile(r"(?i)basic\s+[A-Za-z0-9+/=]{20,}")),
    ("Bearer Token", re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.]{20,}")),
    # Database connection strings
    ("Database Connection String", re.compile(r"(?i)(postgres|mysql|mongodb|redis)://[^'\"\s]+")),
    # Slack
    ("Slack Bot Token", re.compile(r"xoxb-[0-9]{11}-[0-9]{11}-[A-Za-z0-9]{24}")),
    ("Slack User Token", re.compile(r"xoxp-[0-9]{11}-[0-9]{11}-[A-Za-z0-9]{24}")),
    # Stripe
    ("Stripe Secret Key", re.compile(r"sk_live_[A-Za-z0-9]{24,}")),
    ("Stripe Publishable Key", re.compile(r"pk_live_[A-Za-z0-9]{24,}")),
]


@dataclass
class SecretMatch:
    """A detected potential secret.

    Attributes:
        pattern_name: Name of the pattern that matched.
        line_number: 1-indexed line number where the match was found.
        column: 0-indexed column where the match starts.
        matched_text: The matched text (redacted for safety).
        context: The full line containing the match.
    """

    pattern_name: str
    line_number: int
    column: int
    matched_text: str
    context: str

    def __str__(self) -> str:
        """Format as human-readable string."""
        return f"Line {self.line_number}: {self.pattern_name} - {self.matched_text}"


def _redact(text: str, visible_chars: int = 4) -> str:
    """Redact a secret, keeping only a few visible characters.

    Args:
        text: The secret text to redact.
        visible_chars: Number of characters to keep visible at start.

    Returns:
        Redacted string like "sk-a***".
    """
    if len(text) <= visible_chars:
        return "*" * len(text)
    return text[:visible_chars] + "*" * (len(text) - visible_chars)


def scan_for_secrets(content: str) -> list[SecretMatch]:
    """Scan content for potential secrets.

    Args:
        content: The text content to scan.

    Returns:
        List of SecretMatch objects for each detected secret.
    """
    matches: list[SecretMatch] = []
    lines = content.split("\n")

    for line_idx, line in enumerate(lines):
        line_number = line_idx + 1  # 1-indexed

        for pattern_name, pattern in SECRET_PATTERNS:
            for match in pattern.finditer(line):
                matched_text = match.group(0)
                matches.append(
                    SecretMatch(
                        pattern_name=pattern_name,
                        line_number=line_number,
                        column=match.start(),
                        matched_text=_redact(matched_text),
                        context=line.strip(),
                    )
                )

    return matches


def scan_spec_file(spec_path: Path) -> list[SecretMatch]:
    """Scan a spec file for potential secrets.

    Args:
        spec_path: Path to the spec file.

    Returns:
        List of SecretMatch objects for each detected secret.

    Raises:
        FileNotFoundError: If the spec file doesn't exist.
    """
    content = spec_path.read_text(encoding="utf-8")
    return scan_for_secrets(content)


def format_secret_matches(matches: list[SecretMatch], file_path: str | None = None) -> str:
    """Format secret matches for display.

    Args:
        matches: List of secret matches to format.
        file_path: Optional file path to include in output.

    Returns:
        Formatted string describing the matches.
    """
    if not matches:
        return "No secrets detected."

    lines = []
    if file_path:
        lines.append(f"Potential secrets detected in {file_path}:")
    else:
        lines.append("Potential secrets detected:")
    lines.append("")

    for match in matches:
        lines.append(f"  Line {match.line_number}, col {match.column}: {match.pattern_name}")
        lines.append(f"    Found: {match.matched_text}")
        # Truncate context if too long
        context = match.context
        if len(context) > 80:
            context = context[:77] + "..."
        lines.append(f"    Context: {context}")
        lines.append("")

    lines.append("Remove secrets from your spec file before building.")
    lines.append("Use environment variables with ${VAR_NAME} syntax instead.")

    return "\n".join(lines)
