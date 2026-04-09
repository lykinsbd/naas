"""CLI configuration with Pydantic validation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

_DEFAULT_CONFIG_PATH = Path.home() / ".config" / "naas" / "config.toml"


class CliConfig(BaseModel):
    """CLI configuration loaded from file, env vars, and flags."""

    url: str = ""
    username: str | None = None
    password: str | None = None
    api_key: str | None = None
    verify: bool = True
    format: Literal["json", "table"] = "table"
    timeout: float = 60.0

    @classmethod
    def load(cls) -> CliConfig:
        """Load config from file, then overlay env vars."""
        data: dict[str, object] = {}

        config_path = Path(os.environ.get("NAAS_CONFIG", str(_DEFAULT_CONFIG_PATH)))
        if config_path.exists():
            import tomllib

            data = tomllib.loads(config_path.read_text())

        # Env vars override file
        env_map = {
            "NAAS_URL": "url",
            "NAAS_USERNAME": "username",
            "NAAS_PASSWORD": "password",
            "NAAS_API_KEY": "api_key",
            "NAAS_TIMEOUT": "timeout",
        }
        for env_key, field in env_map.items():
            val = os.environ.get(env_key)
            if val is not None:
                data[field] = val

        if os.environ.get("NAAS_VERIFY", "").lower() == "false":
            data["verify"] = False

        if fmt := os.environ.get("NAAS_FORMAT"):
            data["format"] = fmt

        return cls.model_validate(data)
