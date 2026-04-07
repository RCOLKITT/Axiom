"""Tests for configuration loading."""

from pathlib import Path

import pytest

from axiom.config.settings import Settings, load_settings
from axiom.errors import ConfigError


class TestSettings:
    """Tests for Settings model."""

    def test_default_settings(self) -> None:
        """Test default settings values."""
        settings = Settings()

        assert settings.project.name == "axiom"
        assert settings.generation.default_model == "claude-sonnet-4-20250514"
        assert settings.generation.temperature == 0.0
        assert settings.generation.max_retries == 3
        assert settings.verification.run_examples is True
        assert settings.verification.run_invariants is True
        assert settings.verification.hypothesis_max_examples == 100
        assert settings.cache.enabled is True

    def test_get_model_for_target(self) -> None:
        """Test getting model for a specific target."""
        settings = Settings()
        settings.generation.models = {"python:fastapi": "claude-opus-4-20250514"}

        # Should use specific model for fastapi
        assert settings.get_model_for_target("python:fastapi") == "claude-opus-4-20250514"

        # Should use default for unknown target
        assert settings.get_model_for_target("python:function") == settings.generation.default_model

    def test_get_directories(self, tmp_path: Path) -> None:
        """Test getting directory paths."""
        settings = Settings()
        settings.project.spec_dir = "my_specs"
        settings.project.generated_dir = "output"

        spec_dir = settings.get_spec_dir(tmp_path)
        gen_dir = settings.get_generated_dir(tmp_path)

        assert spec_dir == tmp_path / "my_specs"
        assert gen_dir == tmp_path / "output"


class TestLoadSettings:
    """Tests for load_settings function."""

    def test_load_defaults_when_no_file(self, tmp_path: Path) -> None:
        """Test loading defaults when no config file exists."""
        # Create empty directory
        settings = load_settings(config_path=tmp_path / "nonexistent.toml")

        assert settings.project.name == "axiom"
        assert settings.config_path is None

    def test_load_from_file(self, tmp_path: Path) -> None:
        """Test loading settings from a file."""
        config_content = """
[project]
name = "my_project"
version = "2.0.0"

[generation]
default_model = "claude-opus-4-20250514"
temperature = 0.5
max_retries = 5

[verification]
hypothesis_max_examples = 50
"""
        config_file = tmp_path / "axiom.toml"
        config_file.write_text(config_content)

        settings = load_settings(config_path=config_file)

        assert settings.project.name == "my_project"
        assert settings.project.version == "2.0.0"
        assert settings.generation.default_model == "claude-opus-4-20250514"
        assert settings.generation.temperature == 0.5
        assert settings.generation.max_retries == 5
        assert settings.verification.hypothesis_max_examples == 50
        assert settings.config_path == config_file

    def test_load_invalid_toml(self, tmp_path: Path) -> None:
        """Test loading invalid TOML raises ConfigError."""
        config_file = tmp_path / "axiom.toml"
        config_file.write_text("invalid [ toml = syntax")

        with pytest.raises(ConfigError) as exc_info:
            load_settings(config_path=config_file)

        assert "Invalid TOML syntax" in str(exc_info.value)

    def test_load_partial_config(self, tmp_path: Path) -> None:
        """Test loading partial config merges with defaults."""
        config_content = """
[generation]
max_retries = 10
"""
        config_file = tmp_path / "axiom.toml"
        config_file.write_text(config_content)

        settings = load_settings(config_path=config_file)

        # Custom value
        assert settings.generation.max_retries == 10
        # Default values preserved
        assert settings.generation.default_model == "claude-sonnet-4-20250514"
        assert settings.verification.run_examples is True
