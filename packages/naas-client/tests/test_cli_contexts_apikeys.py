"""Tests for contexts and api-keys CLI subcommands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from naas_client.cli import app
from naas_client.exceptions import NaasApiError
from naas_client.models import ApiKeyCreateResponse, ApiKeyListItem, ContextsResponse

runner = CliRunner()

CONTEXTS = ContextsResponse.model_validate(
    {
        "contexts": [
            {"name": "default", "workers": 4, "queue_depth": 0},
            {"name": "oob", "workers": 2, "queue_depth": 1},
        ],
    }
)

API_KEY_LIST = [
    ApiKeyListItem.model_validate(
        {
            "key_id": "k-1",
            "role": "admin",
            "contexts": ["*"],
            "created_at": "2026-04-10T00:00:00Z",
            "expires_at": "2026-07-10T00:00:00Z",
            "created_by": "admin",
        }
    ),
]

API_KEY_CREATED = ApiKeyCreateResponse.model_validate(
    {
        "key_id": "k-2",
        "token": "eyJ...",
        "role": "operator",
        "contexts": ["default"],
        "expires_at": "2026-07-10T00:00:00Z",
    }
)


class TestContextsList:
    @patch("naas_client.cli.NaasClient")
    def test_json(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(list_contexts=MagicMock(return_value=CONTEXTS))
        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "contexts", "list"])
        assert result.exit_code == 0
        assert "default" in result.output
        assert "oob" in result.output

    @patch("naas_client.cli.NaasClient")
    def test_table(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(list_contexts=MagicMock(return_value=CONTEXTS))
        result = runner.invoke(app, ["--url", "https://test", "--format", "table", "contexts", "list"])
        assert result.exit_code == 0
        assert "default" in result.output

    @patch("naas_client.cli.NaasClient")
    def test_api_error(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(
            list_contexts=MagicMock(side_effect=NaasApiError(500, "ISE")),
        )
        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "contexts", "list"])
        assert result.exit_code == 2


class TestApiKeysList:
    @patch("naas_client.cli.NaasClient")
    def test_json(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(list_api_keys=MagicMock(return_value=API_KEY_LIST))
        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "api-keys", "list"])
        assert result.exit_code == 0
        assert "k-1" in result.output

    @patch("naas_client.cli.NaasClient")
    def test_table(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(list_api_keys=MagicMock(return_value=API_KEY_LIST))
        result = runner.invoke(app, ["--url", "https://test", "--format", "table", "api-keys", "list"])
        assert result.exit_code == 0
        assert "k-1" in result.output

    @patch("naas_client.cli.NaasClient")
    def test_api_error(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(
            list_api_keys=MagicMock(side_effect=NaasApiError(500, "ISE")),
        )
        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "api-keys", "list"])
        assert result.exit_code == 2


class TestApiKeysCreate:
    @patch("naas_client.cli.NaasClient")
    def test_create_json(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(create_api_key=MagicMock(return_value=API_KEY_CREATED))
        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "api-keys", "create"])
        assert result.exit_code == 0
        assert "eyJ" in result.output

    @patch("naas_client.cli.NaasClient")
    def test_create_with_options(self, mock_cls: MagicMock) -> None:
        mock = MagicMock(create_api_key=MagicMock(return_value=API_KEY_CREATED))
        mock_cls.return_value = mock
        runner.invoke(
            app,
            [
                "--url",
                "https://test",
                "--format",
                "json",
                "api-keys",
                "create",
                "--role",
                "operator",
                "--contexts",
                "default,oob",
                "--ttl",
                "3600",
            ],
        )
        mock.create_api_key.assert_called_once_with(role="operator", contexts=["default", "oob"], ttl=3600)

    @patch("naas_client.cli.NaasClient")
    def test_create_table(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(create_api_key=MagicMock(return_value=API_KEY_CREATED))
        result = runner.invoke(app, ["--url", "https://test", "--format", "table", "api-keys", "create"])
        assert result.exit_code == 0
        assert "Token:" in result.output

    @patch("naas_client.cli.NaasClient")
    def test_create_api_error(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(
            create_api_key=MagicMock(side_effect=NaasApiError(500, "ISE")),
        )
        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "api-keys", "create"])
        assert result.exit_code == 2


class TestApiKeysDelete:
    @patch("naas_client.cli.NaasClient")
    def test_delete(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(delete_api_key=MagicMock())
        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "api-keys", "delete", "k-1"])
        assert result.exit_code == 0
        assert "revoked" in result.output

    @patch("naas_client.cli.NaasClient")
    def test_delete_api_error(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(
            delete_api_key=MagicMock(side_effect=NaasApiError(404, "Not found")),
        )
        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "api-keys", "delete", "k-1"])
        assert result.exit_code == 2


class TestApiKeysRotate:
    @patch("naas_client.cli.NaasClient")
    def test_rotate_json(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(rotate_api_key=MagicMock(return_value=API_KEY_CREATED))
        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "api-keys", "rotate", "k-1"])
        assert result.exit_code == 0
        assert "eyJ" in result.output

    @patch("naas_client.cli.NaasClient")
    def test_rotate_api_error(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock(
            rotate_api_key=MagicMock(side_effect=NaasApiError(404, "Not found")),
        )
        result = runner.invoke(app, ["--url", "https://test", "--format", "json", "api-keys", "rotate", "k-1"])
        assert result.exit_code == 2
