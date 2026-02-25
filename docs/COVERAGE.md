# Test Coverage

## Current Status

- **Current Coverage**: 57.47%
- **Minimum Required**: 50%
- **Target**: 100%

## Coverage Goals

### Phase 1: Foundation (v1.0) - 40% → 54% ✅ COMPLETE

- ✅ Unit tests for authentication (68% coverage)
- ✅ Unit tests for healthcheck (100% coverage)
- ✅ Unit tests for validation (91% coverage)
- ✅ Contract tests for API endpoints
- ✅ Integration tests for full stack
- ✅ Coverage reporting infrastructure
- ✅ Mypy type checking enabled

**Result**: 57.47% coverage (exceeded 40% target)

### Phase 2: API Resources (v1.0) - 70% 🔄 IN PROGRESS

**Current**: 57.47% (185 lines missing)
**Target**: 70% (~127 lines missing)
**Estimated**: ~58 lines of new coverage needed

Priority modules:

1. **naas/library/auth.py** (67.95% → 90%) - Rate limiting, failure tracking
2. **naas/resources/send_command.py** (52.38% → 90%) - Job enqueueing
3. **naas/resources/send_config.py** (52.38% → 90%) - Job enqueueing
4. **naas/resources/get_results.py** (28.12% → 75%) - Job status retrieval
5. **naas/library/decorators.py** (31.03% → 70%) - Authentication decorator

### Phase 3: Core Logic (v1.1) - 85%

- [ ] Complete netmiko_lib.py coverage (currently 13%)
- [ ] Complete validation.py edge cases (currently 91%)
- [ ] Add selfsigned.py tests (currently 0%)
- [ ] Worker function tests

### Phase 4: Complete (v2.0) - 100%

- [ ] All code paths covered
- [ ] All error conditions tested
- [ ] All edge cases handled
- [ ] Main entry point tests

## Coverage Breakdown (Current: 57.47%)

| Module | Coverage | Lines Missing | Priority |
|--------|----------|---------------|----------|
| `naas/__init__.py` | 100% | 0 | ✅ Complete |
| `naas/app.py` | 100% | 0 | ✅ Complete |
| `naas/config.py` | 93.10% | 2 | 🟢 Low |
| `naas/library/errorhandlers.py` | 100% | 0 | ✅ Complete |
| `naas/library/validation.py` | 90.59% | 8 | 🟢 Low |
| `naas/resources/healthcheck.py` | 100% | 0 | ✅ Complete |
| `naas/library/auth.py` | 67.95% | 25 | 🔴 High |
| `naas/resources/send_command.py` | 52.38% | 10 | 🔴 High |
| `naas/resources/send_config.py` | 52.38% | 10 | 🔴 High |
| `naas/library/decorators.py` | 31.03% | 20 | 🔴 High |
| `naas/resources/get_results.py` | 28.12% | 23 | 🔴 High |
| `naas/library/netmiko_lib.py` | 13.11% | 53 | 🟡 Medium (integration tested) |
| `naas/library/selfsigned.py` | 0% | 25 | 🟢 Low (not critical) |
| `naas/__main__.py` | 0% | 9 | 🟢 Low (CLI entry) |

## Running Coverage Locally

```bash
# Run all tests with coverage
uv run pytest --cov=naas --cov-report=html --cov-report=term-missing

# View HTML report
open htmlcov/index.html

# Check if coverage meets minimum
uv run pytest tests/unit --cov=naas --cov-report=term --cov-fail-under=15
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
