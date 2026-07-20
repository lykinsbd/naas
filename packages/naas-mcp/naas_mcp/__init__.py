"""MCP server for NAAS (Netmiko As A Service)."""

__version__ = "0.1.0a1"


def main() -> None:
    """CLI entry point supporting stdio and streamable-http transport.

    Transport selection:
        --transport stdio|streamable-http  (default: stdio)
        --port PORT                        (default: 8081, HTTP only)

    Or via environment variables:
        NAAS_MCP_TRANSPORT=streamable-http
        NAAS_MCP_PORT=8081
    """
    import argparse
    import os

    parser = argparse.ArgumentParser(
        description="NAAS MCP Server — AI-assisted network operations",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default=os.environ.get("NAAS_MCP_TRANSPORT", "stdio"),
        help="Transport type (default: stdio, or NAAS_MCP_TRANSPORT env var)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("NAAS_MCP_PORT", "8081")),
        help="HTTP port (default: 8081, or NAAS_MCP_PORT env var)",
    )
    args = parser.parse_args()

    # Set env var so server.py picks up the transport choice during module init
    os.environ["NAAS_MCP_TRANSPORT"] = args.transport
    os.environ["NAAS_MCP_PORT"] = str(args.port)

    from naas_mcp.server import mcp

    if args.transport == "stdio":
        mcp.run()
    else:
        mcp.run(transport="streamable-http", port=args.port)
