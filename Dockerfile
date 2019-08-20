########################################
# Start with a Alpine based Python image
FROM python:3.7-alpine

# Fixes a host of encoding-related bugs
ENV LC_ALL=C.UTF-8

# Set a more helpful shell prompt
ENV PS1='[\u@\h \W]\$ '

# The python sdist filename includes the version, so
# each new build means a new version and a new tarball.
ARG version
ARG tarball

# Set Docker image metadata
LABEL name="NAAS API Image" \
      maintainer="Brett Lykins <lykinsbd@gmail.com>" \
      author="Brett Lykins <lykinsbd@gmail.com>" \
      license="MIT" \
      version="${version}"

# Make our working dir "/app"
RUN mkdir /app
WORKDIR "/app"

# Copy requirements.txt, gunicorn.py and the tarball of NAAS into place
COPY ["${tarball}", "requirements.txt", "gunicorn.py", "worker.py", "/app/"]

# Install all the things, below is a full breakdown of this monster RUN command:

# Update and upgrade all installed packages
# Install packages that are needed by some python libraries to compile successfully
# Install curl, it's needed for self-healthchecks
# Install requirements for our code
# Install our code
# Remove build dependencies (since it's built now)
RUN apk update && apk upgrade --no-cache && \
    apk add --no-cache --virtual .build-deps build-base python3-dev libffi-dev openssl-dev && \
    apk add --no-cache curl && \
    pip install --no-cache-dir --requirement /app/requirements.txt && \
    pip install --no-cache-dir --no-deps /app/$(basename ${tarball}) && \
    apk del .build-deps

# Export the version as an environment variable for possible logging/debugging
ENV API_VER ${version}

# This container performs its own healthchecks by attempting to connect to
# our HTTP server and GET the healthcheck endpoint.
# Example of a successful response:
# {"status":200,"content":null,"message":"naas is running.","request_id":"2bef8456-c25b-4884-9250-9a0eeb4b4654"}
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD [ $APP_ENVIRONMENT = "staging" ] && staging="-staging"; \
    curl -k -f -H "Host: naas${staging}.localhost" https://127.0.0.1:443/healthcheck

# When this container is run, it executes our code.
CMD ["gunicorn", "-c", "gunicorn.py", "naas.app:app"]
