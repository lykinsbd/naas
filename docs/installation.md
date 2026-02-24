# Installation

## Docker Compose (Recommended)

The easiest way to run NAAS is with Docker Compose:

```bash
# Clone the repository
git clone https://github.com/lykinsbd/naas.git
cd naas

# Start services
docker-compose up -d

# Verify it's running
curl -k https://localhost:8443/healthcheck -u admin:password
```

## Manual Installation

### Prerequisites

- Python 3.11+
- Redis 6.0+
- uv (Python package manager)

### Steps

```bash
# Clone repository
git clone https://github.com/lykinsbd/naas.git
cd naas

# Install dependencies
uv sync

# Set environment variables
export REDIS_HOST=localhost
export REDIS_PORT=6379
export NAAS_USERNAME=admin
export NAAS_PASSWORD=password

# Start Redis
redis-server

# Start API server
uv run gunicorn -c gunicorn.py naas.app:app

# Start worker (in another terminal)
uv run python worker.py
```

## Configuration

See [Security](security.md) for production configuration options.
