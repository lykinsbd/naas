# Docker Compose Deployment

Docker Compose is the recommended way to deploy NAAS for development and small production environments.

## Quick Start

```bash
# Clone repository
git clone https://github.com/lykinsbd/naas.git
cd naas

# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

## Services

The `docker-compose.yml` includes:

- **naas-api** - Flask API server (port 8443)
- **naas-worker** - RQ worker for job processing
- **redis** - Redis for job queue and results

## Configuration

Edit `docker-compose.yml` or use environment variables:

```yaml
environment:
  - NAAS_USERNAME=admin
  - NAAS_PASSWORD=your-secure-password
  - REDIS_HOST=redis
  - REDIS_PORT=6379
```

## Production Considerations

- Use secrets management for credentials
- Enable TLS with valid certificates
- Configure resource limits
- Set up log aggregation
- Monitor with health checks

See [Security](../security.md) for hardening guidance.
