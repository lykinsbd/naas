# Test Coverage

## Current Status

- **Current Coverage**: 15.74%
- **Minimum Required**: 15%
- **Target**: 100%

## Coverage Goals

### Phase 1: Foundation (v1.0) - 15% ✅

- ✅ Unit tests for authentication (68% coverage)
- ✅ Contract tests for API endpoints
- ✅ Integration tests for full stack
- ✅ Coverage reporting infrastructure

### Phase 2: API Layer (v1.1) - 40%

- [ ] Resource endpoint tests (healthcheck, send_command, send_config, get_results)
- [ ] Validation logic tests
- [ ] Error handler tests
- [ ] Decorator tests

### Phase 3: Core Logic (v1.2) - 70%

- [ ] Worker function tests (send_command, send_config)
- [ ] Netmiko library wrapper tests
- [ ] Configuration module tests
- [ ] App initialization tests

### Phase 4: Complete (v2.0) - 100%

- [ ] All code paths covered
- [ ] All error conditions tested
- [ ] All edge cases handled
- [ ] SSL/TLS certificate generation tests
- [ ] Main entry point tests

## Coverage Breakdown (Current)

| Module | Coverage | Priority |
|--------|----------|----------|
| `naas/library/auth.py` | 67.95% | ✅ Done |
| `naas/config.py` | 41.38% | 🟡 Medium |
| `naas/library/validation.py` | 0% | 🔴 High |
| `naas/resources/*.py` | 0% | 🔴 High |
| `naas/library/decorators.py` | 0% | 🟡 Medium |
| `naas/library/errorhandlers.py` | 0% | 🟡 Medium |
| `naas/workers/*.py` | 0% | 🟢 Low (tested via integration) |

## Running Coverage Locally

```bash
# Run all tests with coverage
pytest --cov=naas --cov-report=html --cov-report=term-missing

# View HTML report
open htmlcov/index.html

# Check if coverage meets minimum
pytest tests/unit --cov=naas --cov-report=term --cov-fail-under=15
```

## CI Coverage

Coverage is automatically:

- Measured on every test run
- Uploaded to Codecov
- Displayed in PR comments
- Enforced via minimum threshold (15%)

## Excluded from Coverage

- Test files (`tests/*`, `test_*.py`)
- Virtual environments (`.venv/*`)
- Cache directories (`__pycache__/*`)

## Coverage Badge

[![codecov](https://codecov.io/gh/lykinsbd/naas/branch/develop/graph/badge.svg)](https://codecov.io/gh/lykinsbd/naas)

The badge shows current coverage percentage and links to detailed reports on Codecov.

## Improving Coverage

To increase coverage, focus on:

1. **Validation tests** - Test IP validation, command validation, UUID validation
2. **Resource tests** - Test API endpoint logic (not just contracts)
3. **Decorator tests** - Test authentication decorators
4. **Error handler tests** - Test error response formatting
