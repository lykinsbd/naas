# Secrets Backend Abstraction

* Status: Accepted
* Date: 2026-04-03

## Context and Problem Statement

NAAS v2.0 introduces several features that require cryptographic secrets: API key signing/validation (#101), credential encryption at rest in Redis (#286), and webhook HMAC signing (#277). These secrets (encryption keys, signing keys) need to be stored securely and retrieved at runtime.

Currently, NAAS reads all configuration from environment variables. This works for simple deployments but is insufficient for production environments where secrets should be managed by dedicated systems like HashiCorp Vault or AWS Secrets Manager.

How should NAAS load application secrets in a way that works for both simple Docker Compose deployments and production environments with dedicated secret stores?

## Decision Drivers

* NAAS must remain easy to deploy with Docker Compose (no mandatory external dependencies)
* Production deployments need Vault/AWS Secrets Manager integration
* Multiple v2.0 features will consume secrets — the abstraction must exist before they're built
* The solution should be simple enough that adding a new backend is trivial

## Considered Options

* **Option 1:** Environment variables only (status quo)
* **Option 2:** Pluggable `SecretsBackend` protocol with env default
* **Option 3:** Adopt an existing library (keyring, cloudsecretmanager, etc.)

## Decision Outcome

Chosen option: **Option 2 — Pluggable `SecretsBackend` protocol**, because it keeps the default deployment simple while enabling production secret stores without refactoring consuming code.

### Consequences

* Good: Zero new dependencies for the default (env) backend
* Good: Consuming code is backend-agnostic — no refactoring when switching backends
* Good: Adding a new backend is ~20 lines implementing a Protocol
* Bad: Vault and AWS backends add optional dependencies (`hvac`, `boto3`)
* Bad: Slightly more code than raw `os.environ` calls (but centralizes secret access)

## Pros and Cons of the Options

### Option 1: Environment variables only

* Good: Zero complexity, already works
* Bad: No path to Vault/AWS SM without refactoring every call site
* Bad: Secrets in env vars are visible in `/proc`, `docker inspect`, CI logs
* Bad: No rotation support — requires container restart

### Option 2: Pluggable SecretsBackend protocol

* Good: Default backend reads env vars — no behavior change for existing deployments
* Good: Single configuration point (`SECRETS_BACKEND=env|vault|aws`) to switch backends
* Good: Protocol is tiny — easy to test, easy to extend
* Good: Optional deps only installed when needed
* Bad: Thin abstraction layer to maintain
* Bad: Backend-specific configuration (Vault address, AWS region) adds config surface

### Option 3: Existing library

* Good: No code to write
* Bad: No existing library provides env + Vault + AWS SM with a unified interface
* Bad: `keyring` is desktop-oriented (macOS Keychain, GNOME Keyring) — wrong model for server apps
* Bad: `cloudsecretmanager` covers Azure + GCP only
* Bad: Adding a dependency for ~50 lines of code is poor trade-off

## Design

### Protocol

```python
class SecretsBackend(Protocol):
    def get_secret(self, name: str) -> str:
        """Retrieve a secret by name. Raises KeyError if not found."""
        ...
```

### Backends

**`EnvSecretsBackend`** (default, zero deps):

* Reads from `os.environ`
* Optionally reads from a mounted file path (`SECRETS_FILE_PATH`)
* Configuration: none required

**`VaultSecretsBackend`** (optional, requires `hvac`):

* Reads from HashiCorp Vault KV v2 engine
* Configuration: `VAULT_ADDR`, `VAULT_TOKEN` (or other Vault auth methods), `VAULT_SECRETS_PATH`

**`AWSSecretsBackend`** (optional, requires `boto3`):

* Reads from AWS Secrets Manager
* Configuration: `AWS_REGION`, `AWS_SECRETS_PREFIX`
* Uses default credential chain (IAM role, env vars, etc.)

### Configuration

```bash
# Default — read secrets from environment variables
SECRETS_BACKEND=env

# HashiCorp Vault
SECRETS_BACKEND=vault
VAULT_ADDR=https://vault.example.com:8200
VAULT_TOKEN=s.xxxxxxxx
VAULT_SECRETS_PATH=secret/data/naas

# AWS Secrets Manager
SECRETS_BACKEND=aws
AWS_REGION=us-east-1
AWS_SECRETS_PREFIX=naas/
```

### Consuming Code

```python
from naas.library.secrets import get_secrets_backend

secrets = get_secrets_backend()
encryption_key = secrets.get_secret("NAAS_ENCRYPTION_KEY")
```

Consumers never know which backend is active. Switching backends is a config change, not a code change.

### Initialization

A `get_secrets_backend()` factory reads `SECRETS_BACKEND` and returns the appropriate implementation. Called once at app startup, stored on `app.config["secrets"]` for Flask request context access.

### Scope for v2.0

* Ship `EnvSecretsBackend` as the default
* Ship `VaultSecretsBackend` as optional (document `pip install naas[vault]`)
* Defer `AWSSecretsBackend` to v2.1 unless there's demand
* All v2.0 features (#101, #286, #277) consume secrets through this interface
