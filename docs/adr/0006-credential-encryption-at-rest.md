# Credential Encryption at Rest

* Status: Proposed
* Date: 2026-04-06

## Context and Problem Statement

RQ serializes job arguments (including the `Credentials` object with username,
password, and enable secret) as pickle and stores them in Redis. Anyone with Redis
access can read plaintext device credentials for all in-flight and recently completed
jobs. NAAS needs to encrypt credentials at rest in Redis without coupling to RQ
internals.

## Decision Drivers

* Must protect credentials in Redis from unauthorized access
* Must not couple to RQ serialization internals
* Must support key rotation without downtime
* Must load encryption key from the secrets backend (ADR 0002)
* Must be disableable for environments where Redis is already encrypted at the
  infrastructure level

## Considered Options

* **Option 1:** Hook into RQ's pickle serializer to encrypt all job data
* **Option 2:** Encrypt the `Credentials` object explicitly before enqueue, decrypt
  in the worker function

## Decision Outcome

Chosen option: **Option 2 — explicit encrypt/decrypt**, because it targets only
sensitive data (credentials), doesn't depend on RQ internals, and makes the
encryption boundary visible in the code.

### Consequences

* Good: Only credentials are encrypted, not the entire job payload
* Good: Encryption/decryption points are explicit and auditable
* Good: No dependency on RQ serialization internals
* Good: MultiFernet enables zero-downtime key rotation
* Bad: Every enqueue and worker function must call encrypt/decrypt helpers

## Design

### Encryption

Fernet symmetric encryption from the `cryptography` package (already a transitive
dependency). `MultiFernet` wraps a list of keys — encrypts with the first, decrypts
with any.

### Key Management

The encryption key is loaded from the secrets backend via `NAAS_ENCRYPTION_KEY`.

```bash
# Generate a key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

For key rotation, set `NAAS_ENCRYPTION_KEY` to a comma-separated list of Fernet
keys (newest first). `MultiFernet` decrypts with any key in the list, encrypts with
the first. Drain is not required.

### Encrypt/Decrypt Helpers

```python
def encrypt_credentials(creds: Credentials) -> bytes:
    """Encrypt a Credentials object for storage in Redis."""

def decrypt_credentials(token: bytes) -> Credentials:
    """Decrypt a Credentials object from Redis."""
```

Called explicitly in the resource layer (before `q.enqueue()`) and in the worker
functions (before passing to Netmiko).

### Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `NAAS_ENCRYPTION_KEY` | (from secrets backend) | Fernet key(s), comma-separated for rotation |
| `CREDENTIAL_ENCRYPTION_ENABLED` | `true` | Set `false` to disable (logs warning) |

Enabled by default in v2.0. Plaintext mode will be deprecated in v3.0.

### What Gets Encrypted

Only the `Credentials` object (username, password, enable). Job metadata (host,
platform, port, commands, tags) remains unencrypted — it's not sensitive and is
needed for job listing, dedup, and debugging.

### Worker Compatibility

Workers must have access to the same encryption key(s) as the API. This is already
the case for `NAAS_JWT_SECRET` — same deployment pattern.

### Failure Modes

| Scenario | Behavior |
| --- | --- |
| Key missing, encryption enabled | Startup error — fail fast |
| Key mismatch (API and worker differ) | `InvalidToken` on decrypt — job fails with clear error |
| Encryption disabled | Plaintext credentials, warning logged at startup |
| Key rotated mid-flight | MultiFernet decrypts with old key, new jobs use new key |
