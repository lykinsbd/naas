FROM python:3.11-slim

WORKDIR /app

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy workspace files needed for resolution
COPY pyproject.toml uv.lock ./
COPY packages/naas-mcp/ packages/naas-mcp/
COPY packages/naas-client/ packages/naas-client/

# Install the MCP server package
RUN uv sync --package mcp-server-naas --no-dev --frozen

EXPOSE 8081

ENTRYPOINT ["uv", "run", "--package", "mcp-server-naas", "naas-mcp"]
CMD ["--transport", "streamable-http", "--port", "8081"]
