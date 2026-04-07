"""Tests for the security scanner module."""

import tempfile
from pathlib import Path

import pytest

from axiom.security.scanner import (
    SecretMatch,
    format_secret_matches,
    scan_for_secrets,
    scan_spec_file,
)


class TestScanForSecrets:
    """Tests for scan_for_secrets function."""

    def test_no_secrets(self) -> None:
        """Test scanning content with no secrets."""
        content = """
axiom: "0.1"
metadata:
  name: validate_email
  version: "1.0.0"
intent: Validate email format
"""
        matches = scan_for_secrets(content)
        assert len(matches) == 0

    def test_aws_access_key(self) -> None:
        """Test detection of AWS access key."""
        content = "api_key: AKIAIOSFODNN7EXAMPLE"
        matches = scan_for_secrets(content)

        assert len(matches) == 1
        assert matches[0].pattern_name == "AWS Access Key ID"
        assert matches[0].line_number == 1
        assert "AKIA" in matches[0].matched_text
        assert "*" in matches[0].matched_text  # Redacted

    def test_github_token(self) -> None:
        """Test detection of GitHub personal access token."""
        # ghp_ followed by exactly 36 alphanumeric characters
        content = "token: ghp_abcdefghijklmnopqrstuvwxyz0123456789"
        matches = scan_for_secrets(content)

        assert len(matches) == 1
        assert matches[0].pattern_name == "GitHub Personal Access Token"

    def test_openai_key(self) -> None:
        """Test detection of OpenAI API key."""
        # sk- followed by exactly 48 alphanumeric characters
        # abcdefghijklmnopqrstuvwxyz (26) + 0123456789012345678901 (22) = 48
        content = "openai_key: sk-abcdefghijklmnopqrstuvwxyz0123456789012345678901"
        matches = scan_for_secrets(content)

        assert len(matches) == 1
        assert matches[0].pattern_name == "OpenAI API Key"

    def test_generic_api_key(self) -> None:
        """Test detection of generic API key assignment."""
        content = 'api_key: "my-secret-api-key-12345678"'
        matches = scan_for_secrets(content)

        assert len(matches) >= 1
        pattern_names = [m.pattern_name for m in matches]
        assert "Generic API Key Assignment" in pattern_names

    def test_generic_password(self) -> None:
        """Test detection of password assignment."""
        content = 'password: "mysupersecretpassword123"'
        matches = scan_for_secrets(content)

        assert len(matches) >= 1
        pattern_names = [m.pattern_name for m in matches]
        assert "Generic Secret Assignment" in pattern_names

    def test_private_key_header(self) -> None:
        """Test detection of private key header."""
        content = """
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA...
-----END RSA PRIVATE KEY-----
"""
        matches = scan_for_secrets(content)

        assert len(matches) >= 1
        pattern_names = [m.pattern_name for m in matches]
        assert "Private Key Header" in pattern_names

    def test_database_connection_string(self) -> None:
        """Test detection of database connection string."""
        content = "db_url: postgres://user:password@localhost:5432/mydb"
        matches = scan_for_secrets(content)

        assert len(matches) >= 1
        pattern_names = [m.pattern_name for m in matches]
        assert "Database Connection String" in pattern_names

    def test_stripe_key(self) -> None:
        """Test detection of Stripe secret key."""
        content = "stripe_key: sk_live_abcdefghijklmnopqrstuvwx"
        matches = scan_for_secrets(content)

        assert len(matches) >= 1
        pattern_names = [m.pattern_name for m in matches]
        assert "Stripe Secret Key" in pattern_names

    def test_slack_token(self) -> None:
        """Test detection of Slack bot token."""
        content = "slack_token: xoxb-12345678901-12345678901-abcdefghijklmnopqrstuvwx"
        matches = scan_for_secrets(content)

        assert len(matches) >= 1
        pattern_names = [m.pattern_name for m in matches]
        assert "Slack Bot Token" in pattern_names

    def test_multiple_secrets(self) -> None:
        """Test detection of multiple secrets in content."""
        # Use valid-length tokens
        content = """
aws_key: AKIAIOSFODNN7EXAMPLE
github_token: ghp_abcdefghijklmnopqrstuvwxyz0123456789
password: "mypassword123"
"""
        matches = scan_for_secrets(content)

        assert len(matches) >= 3

    def test_line_numbers_correct(self) -> None:
        """Test that line numbers are correct."""
        content = """line 1
line 2
AKIAIOSFODNN7EXAMPLE
line 4
"""
        matches = scan_for_secrets(content)

        assert len(matches) == 1
        assert matches[0].line_number == 3

    def test_safe_environment_variable_syntax(self) -> None:
        """Test that ${VAR_NAME} syntax is not flagged."""
        content = """
api_key: ${API_KEY}
password: ${DB_PASSWORD}
token: ${GITHUB_TOKEN}
"""
        matches = scan_for_secrets(content)

        # Environment variable references should not be flagged
        assert len(matches) == 0

    def test_false_positive_avoidance_short_strings(self) -> None:
        """Test that short strings don't trigger false positives."""
        content = """
name: test
version: "1.0"
type: string
"""
        matches = scan_for_secrets(content)
        assert len(matches) == 0


class TestScanSpecFile:
    """Tests for scan_spec_file function."""

    def test_scan_clean_file(self) -> None:
        """Test scanning a clean spec file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".axiom", delete=False) as f:
            f.write("""
axiom: "0.1"
metadata:
  name: validate_email
  version: "1.0.0"
  description: Validate email format
  target: "python:function"
intent: Check if email is valid
""")
            f.flush()
            spec_path = Path(f.name)

        try:
            matches = scan_spec_file(spec_path)
            assert len(matches) == 0
        finally:
            spec_path.unlink()

    def test_scan_file_with_secret(self) -> None:
        """Test scanning a spec file containing a secret."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".axiom", delete=False) as f:
            # Use an AWS key which has a simpler pattern (AKIA + 16 chars)
            f.write("""
axiom: "0.1"
metadata:
  name: api_client
  version: "1.0.0"
intent: |
  Call external API with key: AKIAIOSFODNN7EXAMPLE
""")
            f.flush()
            spec_path = Path(f.name)

        try:
            matches = scan_spec_file(spec_path)
            assert len(matches) >= 1
        finally:
            spec_path.unlink()

    def test_file_not_found(self) -> None:
        """Test that FileNotFoundError is raised for missing file."""
        with pytest.raises(FileNotFoundError):
            scan_spec_file(Path("/nonexistent/path/spec.axiom"))


class TestFormatSecretMatches:
    """Tests for format_secret_matches function."""

    def test_no_matches(self) -> None:
        """Test formatting with no matches."""
        result = format_secret_matches([])
        assert result == "No secrets detected."

    def test_with_matches(self) -> None:
        """Test formatting with matches."""
        matches = [
            SecretMatch(
                pattern_name="AWS Access Key ID",
                line_number=5,
                column=10,
                matched_text="AKIA****",
                context="api_key: AKIAIOSFODNN7EXAMPLE",
            )
        ]
        result = format_secret_matches(matches, file_path="test.axiom")

        assert "test.axiom" in result
        assert "Line 5" in result
        assert "AWS Access Key ID" in result
        assert "AKIA****" in result
        assert "environment variables" in result.lower()

    def test_truncates_long_context(self) -> None:
        """Test that long context lines are truncated."""
        long_line = "a" * 100
        matches = [
            SecretMatch(
                pattern_name="Test Pattern",
                line_number=1,
                column=0,
                matched_text="test",
                context=long_line,
            )
        ]
        result = format_secret_matches(matches)

        assert "..." in result


class TestSecretMatch:
    """Tests for SecretMatch dataclass."""

    def test_str_representation(self) -> None:
        """Test string representation of SecretMatch."""
        match = SecretMatch(
            pattern_name="GitHub Token",
            line_number=10,
            column=5,
            matched_text="ghp_****",
            context="token: ghp_abcdef",
        )
        result = str(match)

        assert "Line 10" in result
        assert "GitHub Token" in result
        assert "ghp_****" in result
