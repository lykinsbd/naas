"""Unit tests for MCP prompts."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp.client import Client


async def test_show_commands_prompt(mcp_client: Client):
    result = await mcp_client.get_prompt(
        "show_commands",
        {"host": "10.0.0.1", "platform": "cisco_ios", "commands": "show version, show interfaces"},
    )

    text = result.messages[0].content.text  # type: ignore[union-attr]
    assert "10.0.0.1" in text
    assert "cisco_ios" in text
    assert "show version" in text
    assert "show interfaces" in text
    assert "send_command" in text


async def test_config_push_prompt(mcp_client: Client):
    result = await mcp_client.get_prompt(
        "config_push",
        {"host": "10.0.0.1", "platform": "cisco_ios", "commands": "hostname ROUTER-01", "save": "yes"},
    )

    text = result.messages[0].content.text  # type: ignore[union-attr]
    assert "10.0.0.1" in text
    assert "hostname ROUTER-01" in text
    assert "send_config" in text
    assert "save_config=True" in text


async def test_config_push_no_save(mcp_client: Client):
    result = await mcp_client.get_prompt(
        "config_push",
        {"host": "10.0.0.1", "platform": "cisco_ios", "commands": "hostname ROUTER-01"},
    )

    text = result.messages[0].content.text  # type: ignore[union-attr]
    assert "save_config=False" in text


async def test_troubleshoot_device_prompt(mcp_client: Client):
    result = await mcp_client.get_prompt(
        "troubleshoot_device",
        {"host": "switch-core-01", "platform": "arista_eos"},
    )

    text = result.messages[0].content.text  # type: ignore[union-attr]
    assert "switch-core-01" in text
    assert "arista_eos" in text
    assert "show version" in text
    assert "show interfaces" in text
    assert "show logging" in text
