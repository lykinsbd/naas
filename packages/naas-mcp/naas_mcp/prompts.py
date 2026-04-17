"""MCP prompts for common NAAS workflows."""

from naas_mcp.server import mcp


@mcp.prompt
def show_commands(host: str, platform: str, commands: str) -> str:
    """Template for running show commands on a network device.

    Args:
        host: Device hostname or IP address.
        platform: Netmiko platform type (e.g. cisco_ios, arista_eos).
        commands: Comma-separated list of show commands.
    """
    cmd_list = [c.strip() for c in commands.split(",")]
    formatted = "\n".join(f"  - {c}" for c in cmd_list)
    return (
        f"Run the following show commands on {host} ({platform}):\n"
        f"{formatted}\n\n"
        f"Use the send_command tool with host={host!r}, platform={platform!r}, "
        f"commands={cmd_list!r}. Report the output for each command."
    )


@mcp.prompt
def config_push(host: str, platform: str, commands: str, save: str = "no") -> str:
    """Template for safely pushing configuration to a network device.

    Args:
        host: Device hostname or IP address.
        platform: Netmiko platform type.
        commands: Comma-separated list of configuration commands.
        save: Whether to save config after applying (yes/no).
    """
    cmd_list = [c.strip() for c in commands.split(",")]
    formatted = "\n".join(f"  - {c}" for c in cmd_list)
    save_flag = save.lower() in ("yes", "true", "1")
    return (
        f"Push the following configuration to {host} ({platform}):\n"
        f"{formatted}\n\n"
        f"Before pushing:\n"
        f"1. Run 'show running-config' to capture the current state\n"
        f"2. Apply the config using send_config with host={host!r}, platform={platform!r}, "
        f"commands={cmd_list!r}, save_config={save_flag}\n"
        f"3. Verify the change by running relevant show commands\n"
        f"4. Report what changed and whether it was successful"
    )


@mcp.prompt
def troubleshoot_device(host: str, platform: str) -> str:
    """Guided troubleshooting workflow for a network device.

    Args:
        host: Device hostname or IP address.
        platform: Netmiko platform type.
    """
    return (
        f"Troubleshoot {host} ({platform}) using this workflow:\n\n"
        f"1. Run 'show version' to check uptime, software version, and hardware\n"
        f"2. Run 'show interfaces status' to check for down/err-disabled ports\n"
        f"3. Run 'show logging last 50' to check for recent errors\n"
        f"4. Run 'show processes cpu history' to check for CPU spikes\n\n"
        f"Use send_command with host={host!r}, platform={platform!r} for each step. "
        f"Summarize findings and flag any issues that need attention."
    )
