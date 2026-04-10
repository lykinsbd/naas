"""Tests for CLI config loading."""

from __future__ import annotations

from typing import TYPE_CHECKING

from naas_client.cli.config import CliConfig

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_ENV_KEYS = ("NAAS_URL", "NAAS_API_KEY", "NAAS_USERNAME", "NAAS_PASSWORD", "NAAS_VERIFY", "NAAS_FORMAT", "NAAS_TIMEOUT")


def _clear_naas_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


class TestCliConfig:
    def test_defaults(self) -> None:
        cfg = CliConfig()
        assert cfg.url == ""
        assert cfg.verify is True
        assert cfg.format == "table"
        assert cfg.timeout == 60.0

    def test_load_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NAAS_URL", "https://test.example.com")
        monkeypatch.setenv("NAAS_API_KEY", "my-key")
        monkeypatch.setenv("NAAS_VERIFY", "false")
        monkeypatch.setenv("NAAS_FORMAT", "json")
        monkeypatch.setenv("NAAS_TIMEOUT", "120")
        monkeypatch.setenv("NAAS_CONFIG", "/nonexistent/path")

        cfg = CliConfig.load()
        assert cfg.url == "https://test.example.com"
        assert cfg.api_key == "my-key"
        assert cfg.verify is False
        assert cfg.format == "json"
        assert cfg.timeout == 120.0

    def test_load_from_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config_file = tmp_path / "config.toml"
        config_file.write_text('url = "https://file.example.com"\nverify = false\nformat = "json"\n')
        monkeypatch.setenv("NAAS_CONFIG", str(config_file))
        _clear_naas_env(monkeypatch)
        monkeypatch.setenv("NAAS_CONFIG", str(config_file))

        cfg = CliConfig.load()
        assert cfg.url == "https://file.example.com"
        assert cfg.verify is False

    def test_env_overrides_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config_file = tmp_path / "config.toml"
        config_file.write_text('url = "https://file.example.com"\n')
        monkeypatch.setenv("NAAS_CONFIG", str(config_file))
        _clear_naas_env(monkeypatch)
        monkeypatch.setenv("NAAS_CONFIG", str(config_file))
        monkeypatch.setenv("NAAS_URL", "https://env.example.com")

        cfg = CliConfig.load()
        assert cfg.url == "https://env.example.com"

    def test_load_no_config_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NAAS_CONFIG", "/nonexistent")
        _clear_naas_env(monkeypatch)
        monkeypatch.setenv("NAAS_CONFIG", "/nonexistent")

        cfg = CliConfig.load()
        assert cfg.url == ""
