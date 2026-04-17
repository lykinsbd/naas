"""MCP server for NAAS (Netmiko As A Service)."""

__version__ = "0.1.0a1"


def main() -> None:
    """CLI entry point for stdio transport."""
    from naas_mcp.server import mcp

    mcp.run()
