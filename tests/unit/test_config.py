"""Unit tests for config module."""

import os
from unittest.mock import MagicMock, patch

from flask import Flask

from naas.config import app_configure


class TestAppConfigure:
    """Tests for app_configure function."""

    def test_invalid_environment_defaults_to_dev(self):
        """Invalid APP_ENVIRONMENT should default to 'dev'."""
        app = Flask(__name__)
        with patch.dict(os.environ, {"APP_ENVIRONMENT": "invalid"}):
            with patch("naas.config.Redis") as mock_redis:
                mock_redis.return_value = MagicMock()
                app_configure(app)
                assert app.config["APP_ENVIRONMENT"] == "dev"

    def test_dev_environment_sets_debug_log_level(self):
        """Dev environment should set LOG_LEVEL to DEBUG by default."""
        app = Flask(__name__)
        with patch.dict(os.environ, {"APP_ENVIRONMENT": "dev"}, clear=True):
            with patch("naas.config.Redis") as mock_redis:
                mock_redis.return_value = MagicMock()
                app_configure(app)
                assert app.config["LOG_LEVEL"] == "DEBUG"

    def test_production_environment_sets_info_log_level(self):
        """Production environment should set LOG_LEVEL to INFO by default."""
        app = Flask(__name__)
        with patch.dict(os.environ, {"APP_ENVIRONMENT": "production"}, clear=True):
            with patch("naas.config.Redis") as mock_redis:
                mock_redis.return_value = MagicMock()
                app_configure(app)
                assert app.config["LOG_LEVEL"] == "INFO"
