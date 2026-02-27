# Test Coverage

## Current Status

- **Current Coverage**: 100%
- **Minimum Required**: 100%

[![codecov](https://codecov.io/gh/lykinsbd/naas/branch/develop/graph/badge.svg)](https://codecov.io/gh/lykinsbd/naas)

## Coverage Breakdown

| Module | Coverage |
|--------|----------|
| `naas/__init__.py` | 100% |
| `naas/app.py` | 100% |
| `naas/config.py` | 100% |
| `naas/library/auth.py` | 100% |
| `naas/library/circuit_breaker.py` | 100% |
| `naas/library/decorators.py` | 100% |
| `naas/library/errorhandlers.py` | 100% |
| `naas/library/netmiko_lib.py` | 100% |
| `naas/library/selfsigned.py` | 100% |
| `naas/library/validation.py` | 100% |
| `naas/models.py` | 100% |
| `naas/resources/get_results.py` | 100% |
| `naas/resources/healthcheck.py` | 100% |
| `naas/resources/list_jobs.py` | 100% |
| `naas/resources/send_command.py` | 100% |
| `naas/resources/send_config.py` | 100% |
| `naas/spec.py` | 100% |

## Running Coverage Locally

```bash
uv run invoke test
```

## CI Coverage

Coverage is measured on every test run and uploaded to Codecov. Results are available at
[app.codecov.io/github/lykinsbd/naas](https://app.codecov.io/github/lykinsbd/naas).

## Excluded from Coverage

Lines marked `# pragma: no cover` are excluded. Each exclusion has an inline justification
comment explaining why the branch is unreachable in normal test execution.
