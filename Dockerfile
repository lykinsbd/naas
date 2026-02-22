########################################
# Multi-stage build for optimized image size
FROM python:3.11-slim AS builder

# Fixes encoding-related bugs
ENV LC_ALL=C.UTF-8

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files and source
COPY pyproject.toml requirements.lock README.md ./
COPY naas/ ./naas/

# Install dependencies and naas package to system Python
RUN uv pip install --system -r requirements.lock && \
    uv pip install --system --no-deps -e .

########################################
# Final runtime image
FROM python:3.11-slim

# Fixes encoding-related bugs
ENV LC_ALL=C.UTF-8

# Set a more helpful shell prompt
ENV PS1='[\u@\h \W]\$ '

# Set Docker image metadata
LABEL name="NAAS API Image" \
      maintainer="Brett Lykins <lykinsbd@gmail.com>" \
      author="Brett Lykins <lykinsbd@gmail.com>" \
      license="MIT" \
      version="1.0.0a1"

# Install curl for healthchecks
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Make our working dir "/app"
WORKDIR /app

# Copy application code
COPY naas/ /app/naas/
COPY gunicorn.py worker.py /app/

# Export version as environment variable
ENV API_VER="1.0.0a1"

# Healthcheck
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD curl -k -f https://127.0.0.1:443/healthcheck || exit 1

# Run gunicorn
CMD ["gunicorn", "-c", "gunicorn.py", "naas.app:app"]
